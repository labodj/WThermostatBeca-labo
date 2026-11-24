import contextlib
import io
import shutil
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class BuildToolsTests(unittest.TestCase):
    def test_serial_decoder_recovers_after_incomplete_lines(self):
        from arduino.espminiterm import ESPStackDecoder

        decoder = ESPStackDecoder()
        for _ in range(32):
            chunk = "x" * 1024
            self.assertEqual(chunk, decoder.rx(chunk))
            self.assertLessEqual(len(decoder.rxbuf), 4096)
        self.assertEqual("\nException ():\n", decoder.rx("\nException ():\n"))
        self.assertEqual("Exception (", decoder.rx("Exception ("))
        self.assertIn("LoadProhibitedCause", decoder.rx("28):\r\n"))
        self.assertEqual("", decoder.rxbuf)

    def test_firmware_artifact_names_and_debug_symbols(self):
        class Environment:
            def GetProjectConfig(self):
                return self

            def get(self, section, name):
                self_outer.assertEqual(("common", "appversion"), (section, name))
                return "custom-build"

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
            name = "wthermostat-custom-build"
            self.assertEqual(b"binary", Path("build_output/firmware", name + ".bin").read_bytes())
            self.assertEqual(b"symbols", Path("build_output/map", name + ".elf").read_bytes())
            self.assertEqual("map", Path("build_output/map", name + ".map").read_text())

    def test_optimized_packaging_rejects_dirty_sources_and_damaged_images(self):
        with tempfile.TemporaryDirectory() as temp:
            caller = Path(temp)
            project = caller / "project"
            subprocess.run(["git", "init", "-q", str(project)], check=True)
            (project / ".git/info/exclude").write_text("/pio/\n/platformio.ini\n/build_output/\n")
            script = project / "pio/package.py"
            script.parent.mkdir()
            shutil.copyfile(ROOT / "pio/package.py", script)
            shutil.copyfile(ROOT / "platformio.ini", project / "platformio.ini")
            images = project / "build_output/firmware"
            images.mkdir(parents=True)
            data = bytearray(4200)
            data[:4] = bytes([0xe9, 2, 3, 0x20])
            data[4096:4100] = bytes([0xe9, 5, 3, 0x20])
            data[48:53] = b"\0dev\0"
            (images / "wthermostat-dev.bin").write_bytes(data)
            dirty = project / "unfinished.cpp"
            dirty.touch()
            command = [sys.executable, "-O", str(script), "dev", "--output", "release"]
            for message in ("Commit sources before packaging", "Arduino CRC/size mismatch"):
                result = subprocess.run(command, cwd=caller, capture_output=True, text=True)
                self.assertNotEqual(0, result.returncode)
                self.assertIn(message, result.stderr)
                self.assertFalse((caller / "release").exists())
                self.assertEqual([], list(caller.glob(".wthermostat-*")))
                dirty.unlink(missing_ok=True)

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
