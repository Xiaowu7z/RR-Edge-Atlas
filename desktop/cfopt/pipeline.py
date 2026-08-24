from __future__ import annotations

import datetime as dt
import math
import socket
import statistics
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Iterable

from .models import (
    ASIA_HUNT,
    BALANCED,
    BASELINE_DOMAIN,
    MODES,
    DomainMetric,
    FamilyRunResult,
    ModeParams,
    OptimizerResult,
    PopDiscovery,
    ProbeResult,
    Snapshot,
)
from .probe import probe_download, probe_trace
from .ranges import family_of, is_cloudflare_ip, normalized_ip, prefix_of
from .ranking import address_floor, compare_to_baseline, median_ttfb, rank, rank_asia, stability_label, success_rate, variation


StageCallback = Callable[[str, int, int, str], None]
LogCallback = Callable[[str], None]
ProbeFunction = Callable[..., ProbeResult]
TraceFunction = Callable[..., tuple[str, str]]

ASIA_POP_ORDER = ("HKG", "NRT", "SIN", "ICN", "TPE")
POP_PRIORITY = {"HKG": 5, "NRT": 4, "SIN": 3, "ICN": 2, "TPE": 1}


class OptimizerCancelled(RuntimeError):
    pass


class NetworkChanged(RuntimeError):
    pass


def pop_priority(pop: str) -> int:
    return POP_PRIORITY.get(pop.upper(), 0)


def default_domains_path() -> Path:
    local = Path(__file__).resolve().parents[1] / "domains.txt"
    if local.is_file():
        return local
    return Path(__file__).resolve().parents[2] / "cf-optimizer" / "domains.txt"


def load_domains(path: Path | None = None, limit: int = 0) -> list[str]:
    source = path or default_domains_path()
    domains: list[str] = []
    seen: set[str] = set()
    for raw in source.read_text(encoding="utf-8-sig").splitlines():
        domain = raw.strip().lower().rstrip(".")
        if not domain or domain.startswith("#") or domain in seen:
            continue
        seen.add(domain)
        domains.append(domain)
    if limit > 0:
        domains = domains[:limit]
    if BASELINE_DOMAIN not in domains:
        domains.append(BASELINE_DOMAIN)
    return domains


def _cancelled(cancel_event: threading.Event) -> None:
    if cancel_event.is_set():
        raise OptimizerCancelled("已取消")


def _resolve_domain(domain: str, family: str) -> list[str]:
    wanted = socket.AF_INET6 if family == "IPv6" else socket.AF_INET
    try:
        rows = socket.getaddrinfo(domain, None, wanted, socket.SOCK_STREAM)
    except OSError:
        return []
    output: list[str] = []
    seen: set[str] = set()
    for row in rows:
        raw = row[4][0]
        try:
            value = normalized_ip(raw)
        except ValueError:
            continue
        if value in seen or family_of(value) != family or not is_cloudflare_ip(value):
            continue
        seen.add(value)
        output.append(value)
    return output


def build_snapshot(
    domains: list[str],
    family: str,
    cancel_event: threading.Event,
    on_stage: StageCallback,
    log: LogCallback,
    resolver: Callable[[str, str], list[str]] = _resolve_domain,
) -> Snapshot:
    names = list(dict.fromkeys(item.strip().lower() for item in domains if item.strip()))
    on_stage(f"DNS 快照 {family}", 0, len(names), "解析候选域名")
    resolved: dict[str, list[str]] = {}
    with ThreadPoolExecutor(max_workers=24, thread_name_prefix="rr-dns") as pool:
        futures: dict[Future[list[str]], tuple[int, str]] = {
            pool.submit(resolver, domain, family): (index, domain)
            for index, domain in enumerate(names)
        }
        completed = 0
        ordered: list[tuple[int, str, list[str]]] = []
        for future in as_completed(futures):
            _cancelled(cancel_event)
            index, domain = futures[future]
            try:
                ips = future.result()
            except Exception:
                ips = []
            ordered.append((index, domain, ips))
            completed += 1
            on_stage(f"DNS 快照 {family}", completed, len(names), domain)
    ordered.sort(key=lambda row: row[0])
    domain_to_ips: dict[str, list[str]] = {}
    ip_to_domains: dict[str, list[str]] = {}
    for _, domain, ips in ordered:
        if not ips:
            continue
        resolved[domain] = ips
        domain_to_ips[domain] = ips
        for ip in ips:
            ip_to_domains.setdefault(ip, []).append(domain)
    snapshot = Snapshot(family, domain_to_ips, ip_to_domains, list(ip_to_domains))
    log(f"候选快照({family})：有效域名 {len(domain_to_ips)}，去重地址 {len(snapshot.unique_ips)}")
    return snapshot


def required_full_attempts(address_count: int, full_rounds: int) -> int:
    return 0 if address_count <= 0 else max(address_count, full_rounds)


def full_schedule(ips: list[str], full_rounds: int) -> list[str]:
    if not ips:
        return []
    return [ips[index % len(ips)] for index in range(required_full_attempts(len(ips), full_rounds))]


def estimate_traffic_mb(
    snapshot: Snapshot,
    params: ModeParams,
    micro_domains: Iterable[str],
    finalists: Iterable[str],
) -> float:
    pre = len(snapshot.unique_ips) * params.pre_bytes
    micro_ips = {
        ip
        for domain in micro_domains
        for ip in snapshot.domain_to_ips.get(domain, [])
    }
    micro = len(micro_ips) * params.micro_bytes
    full = sum(
        required_full_attempts(len(snapshot.domain_to_ips.get(domain, [])), params.full_rounds)
        * params.full_bytes
        for domain in finalists
    )
    return (pre + micro + full) / 1_000_000.0


def estimate_traffic_upper_bound_mb(snapshot: Snapshot, params: ModeParams) -> float:
    counts = sorted((len(ips) for ips in snapshot.domain_to_ips.values()), reverse=True)
    pre = len(snapshot.unique_ips) * params.pre_bytes
    micro = sum(counts[: params.top_domains]) * params.micro_bytes
    full = sum(required_full_attempts(count, params.full_rounds) for count in counts[: params.final_domains]) * params.full_bytes
    return (pre + micro + full) / 1_000_000.0


def network_fingerprint() -> tuple[str, str]:
    def source_for(family: int, address: tuple[object, ...]) -> str:
        probe = socket.socket(family, socket.SOCK_DGRAM)
        try:
            probe.connect(address)
            return normalized_ip(probe.getsockname()[0])
        except OSError:
            return ""
        finally:
            probe.close()

    return (
        source_for(socket.AF_INET, ("1.1.1.1", 53)),
        source_for(socket.AF_INET6, ("2606:4700:4700::1111", 53, 0, 0)),
    )


def _run_parallel_probes(
    ips: list[str],
    bytes_target: int,
    timeout_sec: int,
    concurrency: int,
    stage_name: str,
    cancel_event: threading.Event,
    on_stage: StageCallback,
    probe_fn: ProbeFunction,
    include_trace: bool = False,
) -> dict[str, ProbeResult]:
    results: dict[str, ProbeResult] = {}
    on_stage(stage_name, 0, len(ips), "")
    with ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="rr-probe") as pool:
        futures: dict[Future[ProbeResult], str] = {
            pool.submit(
                probe_fn,
                ip,
                bytes_target,
                timeout_sec,
                include_trace,
                cancel_event,
            ): ip
            for ip in ips
        }
        completed = 0
        for future in as_completed(futures):
            _cancelled(cancel_event)
            ip = futures[future]
            try:
                results[ip] = future.result()
            except Exception as exc:
                results[ip] = ProbeResult(ok=False, error=f"{type(exc).__name__}: {exc}", target_ip=ip)
            completed += 1
            on_stage(stage_name, completed, len(ips), ip)
    return {ip: results.get(ip, ProbeResult(ok=False, target_ip=ip)) for ip in ips}


def _discover_pops(
    snapshot: Snapshot,
    cancel_event: threading.Event,
    on_stage: StageCallback,
    log: LogCallback,
    trace_fn: TraceFunction,
) -> PopDiscovery:
    stage = f"POP 发现 {snapshot.family}"
    on_stage(stage, 0, len(snapshot.unique_ips), "")
    rows: dict[str, tuple[str, str]] = {}
    with ThreadPoolExecutor(max_workers=12, thread_name_prefix="rr-trace") as pool:
        futures = {
            pool.submit(trace_fn, ip, 5, cancel_event): ip
            for ip in snapshot.unique_ips
        }
        completed = 0
        for future in as_completed(futures):
            _cancelled(cancel_event)
            ip = futures[future]
            try:
                colo, loc = future.result()
            except Exception:
                colo, loc = "", ""
            rows[ip] = (colo.upper(), loc.upper())
            completed += 1
            on_stage(stage, completed, len(snapshot.unique_ips), ip)
    ip_to_pop = {ip: rows.get(ip, ("", ""))[0] for ip in snapshot.unique_ips}
    ip_to_loc = {ip: rows.get(ip, ("", ""))[1] for ip in snapshot.unique_ips}
    candidates: list[dict[str, object]] = []
    for ip in snapshot.unique_ips:
        pop = ip_to_pop[ip] or "UNKNOWN"
        candidates.append(
            {
                "ip": ip,
                "pop": pop,
                "loc": ip_to_loc[ip],
                "prefix": prefix_of(ip),
                "domains": sorted(snapshot.ip_to_domains.get(ip, [])),
                "priority": pop_priority(pop),
            }
        )
    candidates.sort(key=lambda row: (-int(row["priority"]), str(row["pop"]), str(row["prefix"]), str(row["ip"])))
    counts = dict(sorted(Counter(str(row["pop"]) for row in candidates).items()))
    summary = " · ".join(f"{pop}={counts.get(pop, 0)}" for pop in ASIA_POP_ORDER)
    far = sum(1 for row in candidates if row["priority"] == 0 and row["pop"] != "UNKNOWN")
    log(f"{snapshot.family} POP 发现：{summary} · 非目标={far} · 未知={counts.get('UNKNOWN', 0)}")
    if not counts.get("HKG"):
        log(f"{snapshot.family} 本轮未发现 HKG 区域入口")
    return PopDiscovery(counts, candidates, ip_to_pop, ip_to_loc)


def _rank_domains_by_pre(
    snapshot: Snapshot,
    pre_cache: dict[str, ProbeResult],
    discovery_pops: dict[str, str],
    asia_hunt: bool,
) -> list[str]:
    rows: list[tuple[str, int, float, float, float, float]] = []
    for domain, ips in snapshot.domain_to_ips.items():
        probes = [pre_cache.get(ip, ProbeResult(False, target_ip=ip)) for ip in ips]
        ok = sum(1 for item in probes if item.ok)
        speeds = [item.complete_mbps if item.ok else 0.0 for item in probes]
        priorities = [pop_priority(discovery_pops.get(ip, "")) for ip in ips]
        rows.append(
            (
                domain,
                min(priorities) if priorities else 0,
                address_floor(speeds, len(probes) - ok),
                success_rate(ok, len(probes)),
                median_ttfb([item.ttfb_ms for item in probes]),
                variation(speeds),
            )
        )
    def key(row: tuple[str, int, float, float, float, float]) -> tuple[float, ...]:
        _, pop_score, floor, rate, ttfb, var = row
        tail = (-floor, -rate, ttfb if ttfb >= 0.0 else math.inf, var)
        return (-pop_score, *tail) if asia_hunt else tail
    rows.sort(key=key)
    return [row[0] for row in rows]


def _domain_metric(
    domain: str,
    family: str,
    addresses: list[str],
    micro_cache: dict[str, ProbeResult],
    full_by_ip: dict[str, list[ProbeResult]],
    discovery_pops: dict[str, str],
) -> DomainMetric:
    full_attempts = [item for ip in addresses for item in full_by_ip.get(ip, [])]
    full_speeds = [item.complete_mbps if item.ok else 0.0 for item in full_attempts]
    full_payloads = [item.payload_mbps if item.ok else 0.0 for item in full_attempts]
    full_ttfbs = [item.ttfb_ms if item.ok else -1.0 for item in full_attempts]
    final_per_ip: dict[str, float] = {}
    for ip in addresses:
        attempts = full_by_ip.get(ip, [])
        final_per_ip[ip] = (
            0.0
            if not attempts or any(not item.ok for item in attempts)
            else statistics.fmean(item.complete_mbps for item in attempts)
        )
    address_successes = sum(1 for value in final_per_ip.values() if value > 0.0)
    final_floor = address_floor(list(final_per_ip.values()), len(addresses) - address_successes)
    micro_probes = [micro_cache.get(ip, ProbeResult(False, target_ip=ip)) for ip in addresses]
    micro_ok = sum(1 for item in micro_probes if item.ok)
    micro_floor = address_floor(
        [item.complete_mbps if item.ok else 0.0 for item in micro_probes],
        len(addresses) - micro_ok,
    )
    ip_pops: list[str] = []
    ip_locs: list[str] = []
    final_pops: dict[str, str] = {}
    for ip in addresses:
        full_ok = next((item for item in reversed(full_by_ip.get(ip, [])) if item.ok), None)
        source = full_ok or micro_cache.get(ip)
        if source and source.colo:
            ip_pops.append(f"{ip}: {source.colo}")
        if source and source.loc:
            ip_locs.append(f"{ip}: {source.loc}")
        final_pops[ip] = (full_ok.colo if full_ok and full_ok.colo else discovery_pops.get(ip, ""))
    pops = [value for value in final_pops.values() if value]
    primary_pop = "" if not pops else pops[0] if len(set(pops)) == 1 else f"混合({'/'.join(dict.fromkeys(pops))})"
    edge_priorities = [pop_priority(final_pops.get(ip, "")) for ip in addresses]
    average = statistics.fmean(full_speeds) if full_speeds else 0.0
    metric = DomainMetric(
        domain=domain,
        family=family,
        min_complete_mbps=min(full_speeds) if full_speeds else 0.0,
        avg_complete_mbps=average,
        max_complete_mbps=max(full_speeds) if full_speeds else 0.0,
        min_payload_mbps=min(full_payloads) if full_payloads else 0.0,
        avg_payload_mbps=statistics.fmean(full_payloads) if full_payloads else 0.0,
        success_rate_pct=success_rate(sum(1 for item in full_attempts if item.ok), len(full_attempts)),
        variation_pct=variation(full_speeds),
        median_ttfb_ms=median_ttfb(full_ttfbs),
        micro_address_floor_mbps=micro_floor,
        address_floor_mbps=final_floor,
        micro_address_success_rate_pct=success_rate(micro_ok, len(addresses)),
        address_success_rate_pct=success_rate(address_successes, len(addresses)),
        addresses_tested=len(addresses),
        sampled=not addresses or any(not full_by_ip.get(ip) for ip in addresses),
        best_ip=max(final_per_ip, key=final_per_ip.get, default=""),
        worst_ip=min(final_per_ip, key=final_per_ip.get, default=""),
        current_ips=addresses,
        ip_pops=ip_pops,
        ip_locs=ip_locs,
        primary_pop=primary_pop,
        edge_score=min(edge_priorities) if edge_priorities else 0,
        pop_drift=any(
            discovery_pops.get(ip, "")
            and final_pops.get(ip, "")
            and discovery_pops[ip].upper() != final_pops[ip].upper()
            for ip in addresses
        ),
    )
    metric.stability = stability_label(metric.variation_pct, metric.success_rate_pct)
    return metric


def run_family(
    snapshot: Snapshot,
    params: ModeParams,
    cancel_event: threading.Event,
    on_stage: StageCallback,
    log: LogCallback,
    network_changed: Callable[[], bool] | None = None,
    probe_fn: ProbeFunction = probe_download,
    trace_fn: TraceFunction = probe_trace,
    delays: bool = True,
) -> FamilyRunResult:
    started = time.perf_counter()
    if not snapshot.domain_to_ips:
        return FamilyRunResult(snapshot.family, [], [], elapsed_seconds=time.perf_counter() - started)
    guard = network_changed or (lambda: False)

    def check() -> None:
        _cancelled(cancel_event)
        if guard():
            raise NetworkChanged("测试期间网络出口发生变化")

    discovery: PopDiscovery | None = None
    discovery_pops: dict[str, str] = {}
    discovery_locs: dict[str, str] = {}
    if params.asia_hunt:
        check()
        discovery = _discover_pops(snapshot, cancel_event, on_stage, log, trace_fn)
        discovery_pops = discovery.ip_to_pop
        discovery_locs = discovery.ip_to_loc

    check()
    pre_cache = _run_parallel_probes(
        snapshot.unique_ips,
        params.pre_bytes,
        8,
        params.pre_concurrency,
        f"初筛 {snapshot.family}",
        cancel_event,
        on_stage,
        probe_fn,
    )
    for ip, result in pre_cache.items():
        result.colo = result.colo or discovery_pops.get(ip, "")
        result.loc = result.loc or discovery_locs.get(ip, "")
    log(f"{snapshot.family} 初筛完成：{sum(1 for item in pre_cache.values() if item.ok)}/{len(snapshot.unique_ips)} IP 可用")

    ranked_domains = _rank_domains_by_pre(snapshot, pre_cache, discovery_pops, params.asia_hunt)
    micro_domains: list[str] = []
    if BASELINE_DOMAIN in snapshot.domain_to_ips:
        micro_domains.append(BASELINE_DOMAIN)
    for domain in ranked_domains:
        if len(micro_domains) >= params.top_domains:
            break
        if domain not in micro_domains:
            micro_domains.append(domain)
    log(f"{snapshot.family} 入围小流量筛选：{len(micro_domains)} 个域名" + ("（含参考域名）" if BASELINE_DOMAIN in micro_domains else ""))

    micro_ips = list(dict.fromkeys(ip for domain in micro_domains for ip in snapshot.domain_to_ips.get(domain, [])))
    check()
    micro_cache = _run_parallel_probes(
        micro_ips,
        params.micro_bytes,
        12,
        params.micro_concurrency,
        f"小流量筛选 {snapshot.family}",
        cancel_event,
        on_stage,
        probe_fn,
    )
    for ip, result in micro_cache.items():
        result.colo = result.colo or discovery_pops.get(ip, "")
        result.loc = result.loc or discovery_locs.get(ip, "")
    log(f"{snapshot.family} 小流量筛选完成：去重 IP {len(micro_cache)} 个（共享 IP 自动复用）")

    micro_rows: list[dict[str, object]] = []
    for domain in micro_domains:
        ips = snapshot.domain_to_ips.get(domain, [])
        probes = [micro_cache.get(ip, ProbeResult(False, target_ip=ip)) for ip in ips]
        ok = sum(1 for item in probes if item.ok)
        pops = [discovery_pops.get(ip, "") for ip in ips if discovery_pops.get(ip, "")]
        primary_pop = pops[0] if pops and len(set(pops)) == 1 else "" if not pops else "MIXED"
        priorities = [pop_priority(discovery_pops.get(ip, "")) for ip in ips]
        micro_rows.append(
            {
                "domain": domain,
                "pop_score": min(priorities) if priorities else 0,
                "primary_pop": primary_pop,
                "floor": address_floor(
                    [item.complete_mbps if item.ok else 0.0 for item in probes],
                    len(probes) - ok,
                ),
                "rate": success_rate(ok, len(probes)),
                "ttfb": median_ttfb([item.ttfb_ms for item in probes]),
            }
        )

    def micro_key(row: dict[str, object]) -> tuple[float, ...]:
        tail = (
            -float(row["floor"]),
            -float(row["rate"]),
            float(row["ttfb"]) if float(row["ttfb"]) >= 0.0 else math.inf,
        )
        return (-float(row["pop_score"]), *tail) if params.asia_hunt else tail

    micro_rows.sort(key=micro_key)
    finalists: list[str] = []

    def add_finalist(domain: str) -> None:
        if domain and domain not in finalists:
            finalists.append(domain)

    if BASELINE_DOMAIN in snapshot.domain_to_ips:
        add_finalist(BASELINE_DOMAIN)
    if params.asia_hunt:
        for pop, quota in (("HKG", 8), ("NRT", 3), ("SIN", 3), ("ICN", 2), ("TPE", 2)):
            matches = [row for row in micro_rows if row["primary_pop"] == pop]
            for row in matches[:quota]:
                add_finalist(str(row["domain"]))
        far = [row for row in micro_rows if int(row["pop_score"]) == 0]
        for row in far[:2]:
            add_finalist(str(row["domain"]))
    for row in micro_rows:
        if len(finalists) >= params.final_domains:
            break
        add_finalist(str(row["domain"]))
    finalists = finalists[: params.final_domains]
    estimated = estimate_traffic_mb(snapshot, params, micro_domains, finalists)
    log(f"{snapshot.family} 最终候选({len(finalists)})：{', '.join(finalists)}" + ("（含参考域名）" if BASELINE_DOMAIN in finalists else ""))
    log(f"{snapshot.family} 当前晋级组合理论流量 ≈ {estimated:.1f} MB")

    schedules = {domain: full_schedule(snapshot.domain_to_ips.get(domain, []), params.full_rounds) for domain in finalists}
    full_total = sum(len(items) for items in schedules.values())
    full_done = 0
    metrics: list[DomainMetric] = []
    for domain in finalists:
        check()
        ips = snapshot.domain_to_ips.get(domain, [])
        full_by_ip: dict[str, list[ProbeResult]] = {ip: [] for ip in ips}
        schedule = schedules[domain]
        for round_index, ip in enumerate(schedule):
            check()
            on_stage(f"最终复核 {snapshot.family}", full_done + 1, full_total, f"{domain} · {ip}")
            result = probe_fn(ip, params.full_bytes, 30, True, cancel_event)
            full_by_ip.setdefault(ip, []).append(result)
            if not result.ok:
                log(f"{domain} 最终复核第 {round_index + 1}/{len(schedule)} 轮失败（{ip}）：{result.error}")
            before = discovery_pops.get(ip, "")
            if params.asia_hunt and before and result.colo and before.upper() != result.colo.upper():
                log(f"⚠ POP 漂移 {ip}：{before} → {result.colo}")
            full_done += 1
            if delays and cancel_event.wait(0.3):
                raise OptimizerCancelled("已取消")
        if delays and cancel_event.wait(0.4):
            raise OptimizerCancelled("已取消")
        metrics.append(_domain_metric(domain, snapshot.family, ips, micro_cache, full_by_ip, discovery_pops))

    on_stage(f"排名 {snapshot.family}", 1, 1, "完成")
    ranked = rank(metrics)
    baseline = next((item for item in ranked if item.domain == BASELINE_DOMAIN), None)
    challenger = next((item for item in ranked if item.domain != BASELINE_DOMAIN), None)
    baseline_comparison: dict[str, object] | None = None
    if baseline is not None:
        if not ranked or ranked[0].domain == BASELINE_DOMAIN or challenger is None:
            baseline_comparison = {
                "decision": "KEEP",
                "challenger": challenger.domain if challenger else "",
                "baseline": BASELINE_DOMAIN,
                "message": f"参考域名 {BASELINE_DOMAIN} 表现稳定，继续保留",
            }
        else:
            comparison = compare_to_baseline(ranked[0], baseline)
            messages = {
                "REPLACE": f"建议改用当前候选 → {ranked[0].domain}",
                "OBSERVE": "挑战者小幅领先，继续观察（暂不替换）",
                "KEEP": f"继续保留参考域名 {BASELINE_DOMAIN}",
            }
            baseline_comparison = {
                "decision": comparison.decision,
                "challenger": ranked[0].domain,
                "baseline": BASELINE_DOMAIN,
                "message": messages[comparison.decision],
                "floor_gain_pct": comparison.floor_gain_pct,
                "minimum_gain_pct": comparison.minimum_gain_pct,
                "average_gain_pct": comparison.average_gain_pct,
                "reliability_not_worse": comparison.reliability_not_worse,
                "stability_not_worse": comparison.stability_not_worse,
            }
    return FamilyRunResult(
        family=snapshot.family,
        ranked=ranked,
        asia_ranked=rank_asia(metrics) if params.asia_hunt else ranked,
        discovery=discovery,
        estimated_traffic_mb=estimated,
        elapsed_seconds=time.perf_counter() - started,
        baseline_comparison=baseline_comparison,
    )


def run_optimizer(
    mode: str = "balanced",
    family: str = "dual",
    operator: str = "自动",
    limit: int = 0,
    domains_path: Path | None = None,
    cancel_event: threading.Event | None = None,
    on_stage: StageCallback | None = None,
    log: LogCallback | None = None,
    resolver: Callable[[str, str], list[str]] = _resolve_domain,
    probe_fn: ProbeFunction = probe_download,
    trace_fn: TraceFunction = probe_trace,
    delays: bool = True,
) -> OptimizerResult:
    if mode not in MODES:
        raise ValueError(f"未知模式：{mode}")
    if family not in {"ipv4", "ipv6", "dual"}:
        raise ValueError(f"未知协议族：{family}")
    cancel = cancel_event or threading.Event()
    stage_callback = on_stage or (lambda _name, _current, _total, _detail: None)
    logger = log or (lambda _message: None)
    params = MODES[mode]
    domains = load_domains(domains_path, limit)
    requested = ["IPv4", "IPv6"] if family == "dual" else ["IPv6" if family == "ipv6" else "IPv4"]
    started = time.perf_counter()
    initial_fingerprint = network_fingerprint()
    family_results: list[FamilyRunResult] = []
    cancelled = False
    try:
        for family_name in requested:
            _cancelled(cancel)
            snapshot = build_snapshot(domains, family_name, cancel, stage_callback, logger, resolver)
            if not snapshot.domain_to_ips:
                logger(f"{family_name} 没有可用候选地址，已跳过")
                continue
            logger(f"{family_name} 安全预计流量上限 ≈ {estimate_traffic_upper_bound_mb(snapshot, params):.1f} MB")

            def changed() -> bool:
                current = network_fingerprint()
                before = initial_fingerprint[1 if family_name == "IPv6" else 0]
                after = current[1 if family_name == "IPv6" else 0]
                return bool(before and after and before != after)

            try:
                family_results.append(run_family(
                    snapshot,
                    params,
                    cancel,
                    stage_callback,
                    logger,
                    changed,
                    probe_fn,
                    trace_fn,
                    delays,
                ))
            except NetworkChanged:
                logger("!! 网络出口已变化，本轮结果作废")
                family_results.append(FamilyRunResult(family_name, [], [], invalid=True))
                break
    except OptimizerCancelled:
        cancelled = True
        logger("优选已停止")
    return OptimizerResult(
        created_at=dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        mode=mode,
        operator=operator,
        requested_family=family,
        domain_count=len(domains),
        families=family_results,
        elapsed_seconds=time.perf_counter() - started,
        cancelled=cancelled,
    )


__all__ = [
    "ASIA_HUNT",
    "BALANCED",
    "build_snapshot",
    "estimate_traffic_mb",
    "estimate_traffic_upper_bound_mb",
    "full_schedule",
    "load_domains",
    "network_fingerprint",
    "required_full_attempts",
    "run_family",
    "run_optimizer",
]
