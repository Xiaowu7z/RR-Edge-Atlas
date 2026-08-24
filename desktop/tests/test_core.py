from __future__ import annotations

import threading
import unittest

from cfopt.models import ASIA_HUNT, BALANCED, BASELINE_DOMAIN, DomainMetric, ProbeResult, Snapshot
from cfopt.pipeline import estimate_traffic_mb, full_schedule, required_full_attempts, run_family
from cfopt.ranges import family_of, is_cloudflare_ip, prefix_of
from cfopt.ranking import address_floor, compare_to_baseline, rank, variation


class CoreRulesTest(unittest.TestCase):
    def test_cloudflare_ranges_and_family(self) -> None:
        self.assertTrue(is_cloudflare_ip("104.16.1.1"))
        self.assertTrue(is_cloudflare_ip("2606:4700::1"))
        self.assertFalse(is_cloudflare_ip("1.1.1.1"))
        self.assertEqual(family_of("2606:4700::1"), "IPv6")
        self.assertEqual(prefix_of("104.16.1.9"), "104.16.1.0/24")
        self.assertEqual(prefix_of("2606:4700:1234::9"), "2606:4700:1234::/48")

    def test_failure_forces_address_floor_to_zero(self) -> None:
        self.assertEqual(address_floor([88.0, 0.0], 1), 0.0)
        self.assertEqual(address_floor([88.0, 64.0], 0), 64.0)
        self.assertGreater(variation([60.0, 0.0]), 100.0)

    def test_full_schedule_covers_all_addresses(self) -> None:
        self.assertEqual(required_full_attempts(4, 3), 4)
        self.assertEqual(full_schedule(["1", "2", "3", "4"], 3), ["1", "2", "3", "4"])
        self.assertEqual(full_schedule(["A", "B"], 3), ["A", "B", "A"])

    def test_rank_chain_uses_success_after_floor(self) -> None:
        a = DomainMetric("a", "IPv4", address_floor_mbps=0.0, success_rate_pct=50.0, avg_complete_mbps=60.0)
        b = DomainMetric("b", "IPv4", address_floor_mbps=0.0, success_rate_pct=100.0, avg_complete_mbps=40.0)
        self.assertEqual(rank([a, b])[0].domain, "b")

    def test_baseline_requires_full_ten_percent_gain(self) -> None:
        baseline = DomainMetric(
            "base", "IPv4", min_complete_mbps=50.0, avg_complete_mbps=50.0,
            success_rate_pct=100.0, variation_pct=10.0,
            address_floor_mbps=50.0, address_success_rate_pct=100.0,
        )
        plus_nine = DomainMetric(
            "plus9", "IPv4", min_complete_mbps=54.5, avg_complete_mbps=54.5,
            success_rate_pct=100.0, variation_pct=10.0,
            address_floor_mbps=54.5, address_success_rate_pct=100.0,
        )
        plus_ten = DomainMetric(
            "plus10", "IPv4", min_complete_mbps=55.0, avg_complete_mbps=55.0,
            success_rate_pct=100.0, variation_pct=10.0,
            address_floor_mbps=55.0, address_success_rate_pct=100.0,
        )
        self.assertNotEqual(compare_to_baseline(plus_nine, baseline).decision, "REPLACE")
        self.assertEqual(compare_to_baseline(plus_ten, baseline).decision, "REPLACE")

    def test_traffic_counts_shared_micro_ip_once(self) -> None:
        snapshot = Snapshot(
            "IPv4",
            {"a.com": ["1", "2"], "b.com": ["1"]},
            {"1": ["a.com", "b.com"], "2": ["a.com"]},
            ["1", "2"],
        )
        expected = (2 * 128_000 + 2 * 2_000_000 + 2 * 10_000_000) / 1_000_000
        self.assertAlmostEqual(estimate_traffic_mb(snapshot, BALANCED, ["a.com", "b.com"], ["a.com"]), expected)


class PipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.ips = {
            BASELINE_DOMAIN: ["104.16.0.1"],
            "fast.example": ["104.16.0.2", "104.16.0.3"],
            "fragile.example": ["104.16.0.4", "104.16.0.5"],
            "hkg.example": ["104.16.0.6"],
        }
        reverse: dict[str, list[str]] = {}
        for domain, ips in self.ips.items():
            for ip in ips:
                reverse.setdefault(ip, []).append(domain)
        self.snapshot = Snapshot("IPv4", self.ips, reverse, list(reverse))

    def fake_probe(self, ip, bytes_target, timeout_sec, include_trace, cancel_event):
        del timeout_sec, cancel_event
        full = bytes_target >= 10_000_000
        if ip == "104.16.0.5" and full:
            return ProbeResult(ok=False, error="mock fail", target_ip=ip)
        speed = {
            "104.16.0.1": 40.0,
            "104.16.0.2": 82.0,
            "104.16.0.3": 76.0,
            "104.16.0.4": 120.0,
            "104.16.0.5": 115.0,
            "104.16.0.6": 69.0,
        }[ip]
        return ProbeResult(
            ok=True,
            target_ip=ip,
            actual_remote_address=ip,
            target_matches_remote=True,
            ttfb_ms=30.0,
            payload_mbps=speed + 4.0,
            complete_mbps=speed,
            colo="HKG" if include_trace and ip == "104.16.0.6" else "",
            loc="HK" if include_trace and ip == "104.16.0.6" else "",
        )

    def fake_trace(self, ip, timeout_sec, cancel_event):
        del timeout_sec, cancel_event
        return ("HKG", "HK") if ip == "104.16.0.6" else ("LAX", "US")

    def test_balanced_pipeline_forces_baseline_and_penalizes_full_failure(self) -> None:
        logs: list[str] = []
        result = run_family(
            self.snapshot,
            BALANCED,
            threading.Event(),
            lambda *_args: None,
            logs.append,
            probe_fn=self.fake_probe,
            trace_fn=self.fake_trace,
            delays=False,
        )
        by_domain = {item.domain: item for item in result.ranked}
        self.assertIn(BASELINE_DOMAIN, by_domain)
        self.assertEqual(result.ranked[0].domain, "fast.example")
        self.assertEqual(by_domain["fragile.example"].address_floor_mbps, 0.0)
        self.assertLess(by_domain["fragile.example"].success_rate_pct, 100.0)
        # 快域名虽然明显更快，但波动比基准多 7.6 个百分点，超过允许的 +5，仍应守擂。
        self.assertEqual(result.baseline_comparison["decision"], "KEEP")
        self.assertEqual(result.baseline_comparison["challenger"], "fast.example")

    def test_asia_pipeline_prioritizes_hkg(self) -> None:
        result = run_family(
            self.snapshot,
            ASIA_HUNT,
            threading.Event(),
            lambda *_args: None,
            lambda _message: None,
            probe_fn=self.fake_probe,
            trace_fn=self.fake_trace,
            delays=False,
        )
        self.assertEqual(result.asia_ranked[0].domain, "hkg.example")
        self.assertEqual(result.asia_ranked[0].primary_pop, "HKG")
        self.assertEqual(result.asia_ranked[0].edge_score, 5)


if __name__ == "__main__":
    unittest.main()
