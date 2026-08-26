from __future__ import annotations

import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from cfopt.webapp import RuntimeState, make_handler


class CapturingState(RuntimeState):
    submitted_config: dict[str, object] | None = None

    def start(self, config):
        self.submitted_config = config
        return True, "优选已开始"


class WebApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.token = "local-test-token"
        self.state = CapturingState()
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            make_handler(self.state, self.token, {"127.0.0.1"}),
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def _post(self, path: str, body: dict[str, object], token: str | None = None):
        request = urllib.request.Request(
            self.base + path,
            data=json.dumps(body).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json", "X-RR-Request-Token": token or self.token},
        )
        return urllib.request.urlopen(request, timeout=2)

    def test_config_exposes_session_token(self) -> None:
        with urllib.request.urlopen(self.base + "/api/config", timeout=2) as response:
            body = json.load(response)
        self.assertEqual(body["version"], "1.1")
        self.assertEqual(body["request_token"], self.token)

    def test_parse_endpoint(self) -> None:
        with self._post("/api/domains/parse", {"text": "one.example\ntwo.example", "filename": "domains.txt"}) as response:
            body = json.load(response)
        self.assertEqual(body["domains"], ["one.example", "two.example"])

    def test_post_requires_session_token(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as raised:
            self._post("/api/domains/parse", {"text": "one.example"}, token="wrong")
        self.assertEqual(raised.exception.code, 403)

    def test_custom_start_passes_only_normalized_user_domains(self) -> None:
        with self._post(
            "/api/start",
            {
                "mode": "balanced",
                "family": "ipv4",
                "operator": "中国移动",
                "limit": 50,
                "source": "custom",
                "domains": ["ONE.example", "two.example", "one.example"],
            },
        ) as response:
            body = json.load(response)
        self.assertTrue(body["ok"])
        self.assertEqual(self.state.submitted_config["_domains"], ["one.example", "two.example"])
        self.assertEqual(self.state.submitted_config["limit"], 0)
        self.assertNotIn("www.nexusmods.com", self.state.submitted_config["_domains"])


if __name__ == "__main__":
    unittest.main()
