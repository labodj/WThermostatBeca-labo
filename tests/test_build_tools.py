import contextlib
import io
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BuildToolsTests(unittest.TestCase):
    def test_firmware_artifact_names_and_debug_symbols(self):
        class Environment:
            def subst(self, value):
                self_outer.assertEqual("$PIOENV", value)
                return "wthermostat"

            def AddPostAction(self, *_):
                pass

        self_outer = self
        namespace = {"env": Environment(), "projenv": Environment(), "Import": lambda *_: None}
        with contextlib.chdir(ROOT), contextlib.redirect_stdout(io.StringIO()):
            exec(compile((ROOT / "pio/name-firmware.py").read_text(), "name-firmware.py", "exec"), namespace)
        with tempfile.TemporaryDirectory() as temp, contextlib.chdir(temp), contextlib.redirect_stdout(io.StringIO()):
            build = Path(temp) / ".pioenvs/wthermostat"
            build.mkdir(parents=True)
            (build / "firmware.bin").write_bytes(b"binary")
            (build / "firmware.elf").write_bytes(b"symbols")
            Path("firmware.map").write_text("map")
            namespace["bin_map_copy"]([], [build / "firmware.bin"], namespace["env"])
            name = "wthermostat-" + namespace["appversion"]
            self.assertEqual(b"binary", Path("build_output/firmware", name + ".bin").read_bytes())
            self.assertEqual(b"symbols", Path("build_output/map", name + ".elf").read_bytes())
            self.assertEqual("map", Path("build_output/map", name + ".map").read_text())

    def test_ci_tag_version_matches_local_firmware_version(self):
        import os
        import subprocess
        import textwrap
        text = (ROOT / '.github/workflows/build.yml').read_text()
        start = text.index('          version="${GITHUB_REF_NAME')
        end = text.index('      - name: Build all firmware variants', start)
        script = 'git(){ printf abc1234; }; date(){ printf 20261027; };\n' + textwrap.dedent(text[start:end])
        for ref, name, expected in [
            ('refs/tags/v1.25.0-labo.1', 'v1.25.0-labo.1', '1.25.0-labo.1'),
            ('refs/heads/feature/wifi', 'feature/wifi', 'feature_wifi-20261027-abc1234'),
        ]:
            with self.subTest(ref=ref), tempfile.TemporaryDirectory() as directory:
                path = Path(directory)
                env = dict(os.environ, GITHUB_REF=ref, GITHUB_REF_NAME=name,
                           GITHUB_ENV=str(path / 'env'), GITHUB_OUTPUT=str(path / 'output'))
                subprocess.run(['bash', '-eu', '-c', script], cwd=path, env=env, check=True)
                self.assertEqual(f'version={expected}\n', (path / 'output').read_text())
                self.assertEqual(f'[common]\nappversion = {expected}\n',
                                 (path / 'platformio_override.ini').read_text())
