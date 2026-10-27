"""Run clang-tidy with the ESP8266 data model and reject partial parsing."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def make_overlay(header, directory):
    # GCC permits this SDK void-pointer arithmetic; Clang needs byte arithmetic.
    original = header.read_text()
    old = "pgm_read_dword_with_offset(addr + 4, u.i[1]);"
    new = "pgm_read_dword_with_offset(static_cast<const char*>(addr) + 4, u.i[1]);"
    if original.count(old) != 1:
        raise ValueError("SDK pgmspace.h changed; review the analysis-only compatibility edit")
    copy = directory / "pgmspace.h"
    copy.write_text(original.replace(old, new))
    overlay = directory / "overlay.json"
    overlay.write_text(json.dumps({"version": 0, "roots": [
        {"type": "file", "name": str(header), "external-contents": str(copy)}]}))
    return overlay


def check_failed(returncode, output):
    # PlatformIO accepts clang-tidy's parser-error exit code 1 as success.
    return returncode != 0 or "[clang-diagnostic-error]" in output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-e", "--environment", default="wthermostat")
    args = parser.parse_args()
    from platformio.project.config import ProjectConfig
    config = ProjectConfig.get_instance(str(ROOT / "platformio.ini"))
    flags = config.get("env:" + args.environment, "check_flags")
    flags = " ".join(flag.removeprefix("clangtidy:").strip() for flag in flags)
    metadata = json.loads(subprocess.check_output([
        "pio", "project", "metadata", "-e", args.environment, "--json-output"], cwd=ROOT, text=True))[args.environment]
    toolchain = Path(metadata["cxx_path"]).parent.parent
    header = toolchain / "xtensa-lx106-elf/include/sys/pgmspace.h"
    with tempfile.TemporaryDirectory(prefix="wthermostat-clang-") as temp:
        overlay = make_overlay(header, Path(temp))
        result = subprocess.run(["pio", "check", "-e", args.environment, "-v", "--fail-on-defect", "high", "--flags",
                                 flags + " --vfsoverlay=" + str(overlay)], cwd=ROOT,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(result.stdout, end="")
    if check_failed(result.returncode, result.stdout):
        print("Static analysis incomplete or failed; PASSED alone is not sufficient.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
