from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


SPEED_HOST = "speed.cloudflare.com"
BASELINE_DOMAIN = "www.nexusmods.com"


@dataclass(frozen=True)
class ModeParams:
    name: str
    label: str
    top_domains: int
    pre_bytes: int
    micro_bytes: int
    full_bytes: int
    full_rounds: int
    final_domains: int
    pre_concurrency: int
    micro_concurrency: int
    full_concurrency: int = 1
    asia_hunt: bool = False


BALANCED = ModeParams(
    name="balanced",
    label="均衡模式",
    top_domains=12,
    pre_bytes=128_000,
    micro_bytes=2_000_000,
    full_bytes=10_000_000,
    full_rounds=2,
    final_domains=5,
    pre_concurrency=8,
    micro_concurrency=6,
)

ASIA_HUNT = ModeParams(
    name="asia",
    label="区域优选",
    top_domains=36,
    pre_bytes=96_000,
    micro_bytes=1_000_000,
    full_bytes=10_000_000,
    full_rounds=2,
    final_domains=20,
    pre_concurrency=12,
    micro_concurrency=8,
    asia_hunt=True,
)

MODES = {BALANCED.name: BALANCED, ASIA_HUNT.name: ASIA_HUNT}


@dataclass
class ProbeResult:
    ok: bool
    error: str = ""
    family: str = ""
    target_ip: str = ""
    actual_remote_address: str = ""
    target_matches_remote: bool = False
    remote_is_ipv6: bool = False
    sni: str = SPEED_HOST
    cert_verified: bool = False
    http_code: int = 0
    http_version: str = ""
    tcp_ms: float = -1.0
    tls_ms: float = -1.0
    ttfb_ms: float = -1.0
    body_ms: float = -1.0
    total_ms: float = -1.0
    bytes_downloaded: int = 0
    bytes_target: int = 0
    payload_mbps: float = 0.0
    complete_mbps: float = 0.0
    colo: str = ""
    loc: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Snapshot:
    family: str
    domain_to_ips: dict[str, list[str]]
    ip_to_domains: dict[str, list[str]]
    unique_ips: list[str]


@dataclass
class DomainMetric:
    domain: str
    family: str
    min_complete_mbps: float = 0.0
    avg_complete_mbps: float = 0.0
    max_complete_mbps: float = 0.0
    min_payload_mbps: float = 0.0
    avg_payload_mbps: float = 0.0
    success_rate_pct: float = 0.0
    variation_pct: float = 0.0
    median_ttfb_ms: float = -1.0
    micro_address_floor_mbps: float = 0.0
    address_floor_mbps: float = 0.0
    micro_address_success_rate_pct: float = 0.0
    address_success_rate_pct: float = 0.0
    addresses_tested: int = 0
    sampled: bool = False
    best_ip: str = ""
    worst_ip: str = ""
    current_ips: list[str] = field(default_factory=list)
    ip_pops: list[str] = field(default_factory=list)
    ip_locs: list[str] = field(default_factory=list)
    primary_pop: str = ""
    edge_score: int = 0
    pop_drift: bool = False
    stability: str = ""

    @property
    def mb_per_sec(self) -> float:
        return self.avg_complete_mbps / 8.0

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["mb_per_sec"] = self.mb_per_sec
        return row


@dataclass
class PopDiscovery:
    counts: dict[str, int]
    candidates: list[dict[str, Any]]
    ip_to_pop: dict[str, str]
    ip_to_loc: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FamilyRunResult:
    family: str
    ranked: list[DomainMetric]
    asia_ranked: list[DomainMetric]
    invalid: bool = False
    discovery: PopDiscovery | None = None
    estimated_traffic_mb: float = 0.0
    elapsed_seconds: float = 0.0
    baseline_comparison: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "ranked": [item.to_dict() for item in self.ranked],
            "asia_ranked": [item.to_dict() for item in self.asia_ranked],
            "invalid": self.invalid,
            "discovery": self.discovery.to_dict() if self.discovery else None,
            "estimated_traffic_mb": self.estimated_traffic_mb,
            "elapsed_seconds": self.elapsed_seconds,
            "baseline_comparison": self.baseline_comparison,
        }


@dataclass
class OptimizerResult:
    created_at: str
    mode: str
    operator: str
    requested_family: str
    domain_count: int
    families: list[FamilyRunResult]
    elapsed_seconds: float
    cancelled: bool = False
    version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "created_at": self.created_at,
            "mode": self.mode,
            "operator": self.operator,
            "requested_family": self.requested_family,
            "domain_count": self.domain_count,
            "elapsed_seconds": self.elapsed_seconds,
            "cancelled": self.cancelled,
            "families": [family.to_dict() for family in self.families],
        }
