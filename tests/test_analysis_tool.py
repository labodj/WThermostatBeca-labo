import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("firmware_check", ROOT / "pio/check.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class AnalysisToolTests(unittest.TestCase):
    def test_overlay_does_not_modify_sdk_and_checks_its_assumption(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            sdk = directory / "sdk.h"
            text = "prefix\npgm_read_dword_with_offset(addr + 4, u.i[1]);\nsuffix\n"
            sdk.write_text(text)
            overlay = checker.make_overlay(sdk, directory)
            self.assertEqual(text, sdk.read_text())
            mapping = json.loads(overlay.read_text())["roots"][0]
            self.assertEqual(str(sdk), mapping["name"])
            patched = Path(mapping["external-contents"]).read_text()
            self.assertIn("static_cast<const char*>(addr) + 4", patched)
            self.assertEqual(text.splitlines()[0], patched.splitlines()[0])
            sdk.write_text("new SDK without that extension")
            with self.assertRaises(ValueError):
                checker.make_overlay(sdk, directory)

    def test_parser_errors_cannot_pass_even_if_platformio_returns_zero(self):
        self.assertFalse(checker.check_failed(0, "analysis complete"))
        self.assertTrue(checker.check_failed(0, "error [clang-diagnostic-error]\nPASSED"))
        self.assertTrue(checker.check_failed(1, "failed"))
