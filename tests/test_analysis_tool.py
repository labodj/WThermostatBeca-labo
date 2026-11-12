import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import native_support as native
from native_support import ROOT
import sys
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("firmware_check", ROOT / "pio/check.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


spec = importlib.util.spec_from_file_location('cross_analysis', ROOT / 'pio/analyze.py')
analysis = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {'check': checker}):
    spec.loader.exec_module(analysis)


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

    def test_model_and_macro_arguments_preserve_values(self):
        self.assertEqual(['-UFOO', '-DFOO=1', '-UF', '-DF(x)=x + 1', '-UEMPTY', '-DEMPTY='],
                         analysis.builtin_flags('#define FOO 1\n#define F(x) x + 1\n#define EMPTY\n'))
        self.assertIn('-mlong-double-64', analysis.MODEL)
        self.assertIn('-malign-double', analysis.MODEL)
        for failure in ['syntaxError', 'unknownMacro', 'missingIncludeSystem', 'internalError']:
            self.assertFalse(analysis.cppcheck_complete(f'<results><errors><error id="{failure}"/></errors></results>'))
        # Findings stay in the raw report; completion and findings are separate.
        self.assertTrue(analysis.cppcheck_complete('<results><errors><error id="uninitvar"/></errors></results>'))

    def test_override_extraction_preserves_body(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'method.h'
            path.write_text('virtual const char* value() override { return "override"; }')
            self.assertEqual('virtual const char* value()  { return "override"; }', native.method(path, 'value'))

    def test_cpp_flags_do_not_change_c_flags(self):
        import runpy
        class Environment(dict):
            def AppendUnique(self, **items):
                for key, values in items.items():
                    self.setdefault(key, []).extend(v for v in values if v not in self.get(key, []))
            def Replace(self, **items):
                self.update(items)
        env = Environment(CCFLAGS=['-Os'], CXXFLAGS=['-fno-rtti'], LINKFLAGS=['-u', '_printf_float', '-Os'])
        runpy.run_path(str(ROOT / 'pio/strip-floats.py'), init_globals={'env': env, 'Import': lambda *_: None})
        self.assertEqual(['-Os'], env['CCFLAGS'])
        self.assertEqual(['-fno-rtti', '-fno-threadsafe-statics', '-fno-use-cxa-atexit'], env['CXXFLAGS'])
        self.assertEqual(['-Os'], env['LINKFLAGS'])
