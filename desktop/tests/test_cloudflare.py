from __future__ import annotations

import unittest

from cfopt.cloudflare import CloudflareError, upsert_cname


ZONE_ID = "a" * 32
RECORD_ID = "b" * 32
TOKEN = "test_token_" + "x" * 32


class CloudflareCnameTest(unittest.TestCase):
    def test_create_cname(self) -> None:
        calls: list[tuple[str, str, dict[str, object] | None]] = []

        def transport(method, path, payload):
            calls.append((method, path, payload))
            if method == "GET":
                return {"success": True, "result": []}
            return {"success": True, "result": {"id": RECORD_ID}}

        result = upsert_cname(
            api_token=TOKEN,
            zone_id=ZONE_ID,
            zone_name="example.com",
            record_name="edge",
            target="preferred.example.net",
            transport=transport,
        )
        self.assertEqual(result.operation, "created")
        self.assertEqual(result.name, "edge.example.com")
        self.assertEqual(calls[-1][0], "POST")
        self.assertEqual(calls[-1][2]["proxied"], False)

    def test_existing_cname_is_patched(self) -> None:
        calls: list[tuple[str, str, dict[str, object] | None]] = []

        def transport(method, path, payload):
            calls.append((method, path, payload))
            if method == "GET":
                return {
                    "success": True,
                    "result": [{"id": RECORD_ID, "type": "CNAME", "name": "edge.example.com", "content": "old.example.net", "proxied": False, "ttl": 1}],
                }
            return {"success": True, "result": {"id": RECORD_ID}}

        result = upsert_cname(
            api_token=TOKEN,
            zone_id=ZONE_ID,
            zone_name="example.com",
            record_name="edge.example.com",
            target="new.example.net",
            transport=transport,
        )
        self.assertEqual(result.operation, "updated")
        self.assertEqual(calls[-1][0], "PATCH")
        self.assertTrue(calls[-1][1].endswith(RECORD_ID))

    def test_unchanged_cname_does_not_write(self) -> None:
        calls: list[str] = []

        def transport(method, _path, _payload):
            calls.append(method)
            return {
                "success": True,
                "result": [{"id": RECORD_ID, "type": "CNAME", "name": "edge.example.com", "content": "same.example.net", "proxied": False, "ttl": 1}],
            }

        result = upsert_cname(
            api_token=TOKEN,
            zone_id=ZONE_ID,
            zone_name="example.com",
            record_name="edge.example.com",
            target="same.example.net",
            transport=transport,
        )
        self.assertEqual(result.operation, "unchanged")
        self.assertEqual(calls, ["GET"])

    def test_conflicting_record_is_not_overwritten(self) -> None:
        def transport(_method, _path, _payload):
            return {"success": True, "result": [{"id": RECORD_ID, "type": "A", "name": "edge.example.com", "content": "192.0.2.1"}]}

        with self.assertRaisesRegex(CloudflareError, "同名记录已存在"):
            upsert_cname(
                api_token=TOKEN,
                zone_id=ZONE_ID,
                zone_name="example.com",
                record_name="edge.example.com",
                target="preferred.example.net",
                transport=transport,
            )

    def test_zone_name_lookup(self) -> None:
        def transport(method, path, _payload):
            if method == "GET" and path.startswith("/zones?"):
                return {"success": True, "result": [{"id": ZONE_ID, "name": "example.com"}]}
            if method == "GET":
                return {"success": True, "result": []}
            return {"success": True, "result": {"id": RECORD_ID}}

        result = upsert_cname(
            api_token=TOKEN,
            zone_name="example.com",
            record_name="edge",
            target="preferred.example.net",
            transport=transport,
        )
        self.assertEqual(result.zone_id, ZONE_ID)


if __name__ == "__main__":
    unittest.main()
