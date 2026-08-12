import json
import threading
import unittest
import urllib.request
import urllib.error
import os

from forgeguard.web import create_server, validate_bind_security


class FakeService(object):
    def credential_status(self):
        return {"configured": True, "source": "secure_store"}

    def audit_status(self):
        return {"ok": True, "records": 2}


class WebTests(unittest.TestCase):
    def test_remote_bind_requires_admin_token(self):
        with self.assertRaises(ValueError):
            validate_bind_security("0.0.0.0", None)
        validate_bind_security("127.0.0.1", None)
        validate_bind_security("0.0.0.0", "a-long-random-admin-token")

    def test_health_and_status_do_not_disclose_secret(self):
        server = create_server("127.0.0.1", 0, FakeService(), admin_token=None)
        thread = threading.Thread(target=server.serve_forever)
        thread.daemon = True
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        url = "http://127.0.0.1:%s" % server.server_address[1]
        with urllib.request.urlopen(url + "/api/health") as response:
            self.assertEqual(json.load(response)["status"], "ok")
        with urllib.request.urlopen(url + "/api/status") as response:
            body = response.read().decode("utf-8")
        self.assertIn('"configured": true', body)
        self.assertNotIn("api_key", body)

    def test_packaged_index_is_available(self):
        path = os.path.join(os.path.dirname(__file__), "..", "forgeguard", "static", "index.html")
        self.assertTrue(os.path.isfile(os.path.abspath(path)))

    def test_post_rejects_simple_cross_site_content_type(self):
        server = create_server("127.0.0.1", 0, FakeService(), admin_token=None)
        thread = threading.Thread(target=server.serve_forever)
        thread.daemon = True
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        url = "http://127.0.0.1:%s/api/run" % server.server_address[1]
        request = urllib.request.Request(
            url,
            data=b'{"task":"should not run"}',
            headers={"Content-Type": "text/plain"},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request)
        self.assertEqual(caught.exception.code, 400)

    def test_loopback_server_rejects_untrusted_host_header(self):
        server = create_server("127.0.0.1", 0, FakeService(), admin_token=None)
        thread = threading.Thread(target=server.serve_forever)
        thread.daemon = True
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        url = "http://127.0.0.1:%s/api/status" % server.server_address[1]
        request = urllib.request.Request(url, headers={"Host": "attacker.example"})
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request)
        self.assertEqual(caught.exception.code, 403)


if __name__ == "__main__":
    unittest.main()
