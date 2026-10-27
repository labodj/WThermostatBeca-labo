import hashlib
import http.server
import importlib.util
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.request
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("espupload", Path(__file__).resolve().parents[1] / "pio/espupload.py")
UPLOAD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(UPLOAD)


class UploadTests(unittest.TestCase):
    def test_authenticated_upload_and_failed_update(self):
        received = []
        result = [200, b"<html>Update successful.</html>"]

        class Device(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(401)
                self.send_header("WWW-Authenticate", 'Digest realm="thermostat", nonce="test-nonce", qop="auth", algorithm=MD5')
                self.end_headers()

            def do_POST(self):
                auth = self.headers.get("Authorization", "")
                self.server.testcase.assertTrue(auth.startswith("Digest "))
                fields = urllib.request.parse_keqv_list(urllib.request.parse_http_list(auth[7:]))
                digest = lambda text: hashlib.md5(text.encode()).hexdigest()
                expected = digest(":".join([digest("admin:thermostat:test-pass"), "test-nonce", fields["nc"], fields["cnonce"], "auth", digest("POST:/firmware")]))
                if expected != fields["response"]:
                    self.send_response(401)
                    self.end_headers()
                    return
                received.append(self.rfile.read(int(self.headers["Content-Length"])))
                self.send_response(result[0])
                self.end_headers()
                self.wfile.write(result[1])

            def log_message(self, *_):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Device)
        server.testcase = self
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with tempfile.TemporaryDirectory() as temp:
                image = Path(temp) / "firmware.bin"
                image.write_bytes(b"test firmware")
                host = f"127.0.0.1:{server.server_port}"
                self.assertTrue(UPLOAD.upload(host, image, password="test-pass"))
                self.assertIn(b"test firmware", received[0])
                result[:] = [200, b"Update failed"]
                with self.assertRaisesRegex(ValueError, "did not confirm"):
                    UPLOAD.upload(host, image, password="test-pass")
                result[:] = [400, b"invalid image"]
                with self.assertRaises(UPLOAD.urllib.error.HTTPError) as failed:
                    UPLOAD.upload(host, image, password="test-pass")
                failed.exception.close()
                with self.assertRaises(UPLOAD.urllib.error.HTTPError) as failed:
                    UPLOAD.upload(host, image, password="wrong-password")
                failed.exception.close()
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)

    def test_input_and_failure_exit_status(self):
        for host in ["http://user:password@localhost", "http://localhost/other", "file:///tmp/image", "http://localhost/?x"]:
            with self.assertRaises(ValueError):
                UPLOAD.upload(host, "does-not-exist")
        with patch.object(UPLOAD, "upload", side_effect=ValueError("invalid image")):
            self.assertEqual(1, UPLOAD.main(["-u", "localhost", "-f", "image.bin"]))
        with patch.object(UPLOAD, "upload", return_value=True):
            self.assertEqual(0, UPLOAD.main(["-u", "localhost", "-f", "image.bin"]))
