"""Compile production headers/methods against small host API substitutes.

No copied algorithm is tested: extraction takes each method from the current
working tree. ASan/UBSan catch the firmware's array and lifetime regressions.
"""
from pathlib import Path
import os
import shlex
import re
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
BECA = ROOT / "WThermostat/WBecaDevice.h"
NETWORK = ROOT / "lib/WAdapter/WAdapter/WNetwork.h"


def tcp_source():
    # Resolve the explicit Git dependency, even if PIO also caches the registry copy.
    from platformio.package.manager.library import LibraryPackageManager
    from platformio.project.config import ProjectConfig

    specs = ProjectConfig.get_instance(str(ROOT / "platformio.ini")).get("env:wthermostat", "lib_deps")
    spec = next(spec for spec in specs if spec.startswith("ESPAsyncTCP="))
    package = LibraryPackageManager(str(ROOT / ".pio/libdeps/wthermostat")).get_package(spec)
    if package is None:
        raise AssertionError("Run pio pkg install -e wthermostat before these integration tests")
    return Path(package.path) / "src/ESPAsyncTCP.cpp"


def method(path, name):
    text = path.read_text()
    match = re.search(r"(?m)^[ \t]*(?!return\b)(?:virtual\s+)?(?:[\w:<>&*]+[ \t]+)+[*&]*" + re.escape(name) + r"\s*\(", text)
    if not match:
        raise AssertionError(f"Missing production method: {path}:{name}")
    opening = text.index("{", match.end())
    depth = 0
    tokens = re.compile(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[{}]', re.S)
    for token in tokens.finditer(text, opening):
        if token.group() == "{":
            depth += 1
        elif token.group() == "}":
            depth -= 1
            if depth == 0:
                header = re.sub(r"\boverride\b(?=\s*$)", "", text[match.start():opening])
                return header + text[opening:token.end()]
    raise AssertionError(f"Unclosed production method: {name}")


class NativeTests:
    def compile_run(self, source, name):
        with tempfile.TemporaryDirectory(prefix="wthermostat-tests-") as temp:
            path = Path(temp)
            if source is None:
                cpp = ROOT / "tests/native" / (name + ".cpp")
            else:
                cpp = path / f"{name}.cpp"
                cpp.write_text(source)
            binary = path / name
            subprocess.run(compiler() + ["-std=c++17", "-DESP8266",
                            "-I", str(ROOT / "tests/native"), "-I", str(ROOT),
                            "-g", "-O1", "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
                            str(cpp), "-o", str(binary)], check=True, cwd=ROOT)
            subprocess.run([str(binary)], check=True, cwd=ROOT, timeout=30)


def compiler():
    return shlex.split(os.environ.get("CXX", "g++"))


def enum_definition(path, name):
    text = path.read_text()
    start = text.index('enum ' + name)
    return text[start:text.index('}', start) + 1] + ';\n'
