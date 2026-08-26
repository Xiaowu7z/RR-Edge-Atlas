from __future__ import annotations

import base64
import tempfile
import threading
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import patch

from cfopt.domain_sources import DomainSourceError, fetch_domain_subscription, normalize_domain, parse_domain_source
from cfopt.pipeline import load_domains, run_optimizer


class DomainSourceTest(unittest.TestCase):
    def test_plain_text_urls_comments_and_duplicates(self) -> None:
        result = parse_domain_source(
            "# comment\nEXAMPLE.com\nhttps://cdn.Example.net/path\nexample.com\n127.0.0.1\n"
        )
        self.assertEqual(result.source_format, "TXT")
        self.assertEqual(result.domains, ["example.com", "cdn.example.net"])
        self.assertEqual(result.ignored, 1)

    def test_csv_header_is_detected_by_content(self) -> None:
        result = parse_domain_source("label,domain,note\nA,one.example,first\nB,two.example,second\n", "wrong.txt")
        self.assertEqual(result.source_format, "CSV")
        self.assertEqual(result.domains, ["one.example", "two.example"])

    def test_json_supported_shapes(self) -> None:
        result = parse_domain_source(
            '{"data":[{"hostname":"one.example"},{"domain":"two.example"}],"ignored":"not-a-list"}'
        )
        self.assertEqual(result.source_format, "JSON")
        self.assertEqual(result.domains, ["one.example", "two.example"])

    def test_base64_wrapped_text(self) -> None:
        encoded = base64.b64encode(b"one.example\ntwo.example\n").decode("ascii")
        result = parse_domain_source(encoded)
        self.assertEqual(result.source_format, "Base64 + TXT")
        self.assertEqual(result.domains, ["one.example", "two.example"])

    def test_idn_is_normalized_to_punycode(self) -> None:
        self.assertEqual(normalize_domain("例子.测试"), "xn--fsqu00a.xn--0zwm56d")

    def test_cli_custom_file_uses_content_detection_without_reference(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "domains.txt"
            path.write_text('["one.example", "two.example"]', encoding="utf-8")
            self.assertEqual(load_domains(path), ["one.example", "two.example"])

    def test_private_subscription_destination_is_blocked(self) -> None:
        def private_resolver(*_args, **_kwargs):
            return [(2, 1, 6, "", ("127.0.0.1", 443))]

        with self.assertRaisesRegex(DomainSourceError, "本机、内网或保留地址"):
            fetch_domain_subscription("https://example.com/list.txt", resolver=private_resolver)

    def test_public_subscription_text_is_parsed(self) -> None:
        def public_resolver(*_args, **_kwargs):
            return [(2, 1, 6, "", ("93.184.216.34", 443))]

        class Response:
            def __init__(self) -> None:
                self.headers = Message()
                self.headers["Content-Type"] = "text/plain; charset=utf-8"

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _limit):
                return b"one.example\ntwo.example\n"

            def geturl(self):
                return "https://example.com/list.txt"

        class Opener:
            def open(self, _request, timeout):
                self.timeout = timeout
                return Response()

        result, final_url = fetch_domain_subscription(
            "https://example.com/list.txt",
            resolver=public_resolver,
            opener=Opener(),
        )
        self.assertEqual(result.domains, ["one.example", "two.example"])
        self.assertEqual(final_url, "https://example.com/list.txt")

    def test_custom_optimizer_does_not_inject_reference_domain(self) -> None:
        resolved: list[str] = []

        def empty_resolver(domain: str, _family: str) -> list[str]:
            resolved.append(domain)
            return []

        with patch("cfopt.pipeline.network_fingerprint", return_value=("", "")):
            result = run_optimizer(
                family="ipv4",
                domains=["one.example", "two.example"],
                resolver=empty_resolver,
                cancel_event=threading.Event(),
                delays=False,
            )
        self.assertEqual(result.domain_count, 2)
        self.assertEqual(resolved, ["one.example", "two.example"])


if __name__ == "__main__":
    unittest.main()
