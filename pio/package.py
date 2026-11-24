"""Package checked normal/minimal images and matching normal symbols for release."""
import argparse
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import zipfile

from platformio.platform.factory import PlatformFactory

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("version")
parser.add_argument("--output", type=Path, default=Path("build_output/release"))
args = parser.parse_args()
if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", args.version):
    parser.error("Invalid version for an artifact filename")
root = Path(__file__).resolve().parents[1]
destination = args.output.resolve()
os.chdir(root)
if subprocess.check_output(["git", "status", "--porcelain"], text=True).strip():
    parser.error("Commit sources before packaging")
if destination.exists():
    parser.error(f"Output already exists: {destination}")
core = Path(PlatformFactory.from_env("wthermostat").get_package_dir("framework-arduinoespressif8266"))
spec = importlib.util.spec_from_file_location("core_image", core / "tools/elf2bin.py")
sdk_image = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sdk_image)
destination.parent.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(dir=destination.parent, prefix=".wthermostat-") as temp:
    output = Path(temp) / "release"
    output.mkdir()
    validation = {}
    for environment in ("wthermostat", "wthermostat-minimal"):
        name = environment + "-" + args.version
        data = (root / "build_output/firmware" / (name + ".bin")).read_bytes()
        firmware_version = args.version + ("-minimal" if environment == "wthermostat-minimal" else "")
        if b"\0" + firmware_version.encode() + b"\0" not in data:
            parser.error(f"{name}: image version or variant mismatch")
        # Both bootloader and application must match the supported 1 MiB DOUT board.
        if data[:4] != bytes([0xE9, 2, 3, 0x20]) or data[4096:4100] != bytes([0xE9, 5, 3, 0x20]):
            parser.error(f"{name}: unexpected ESP8266 image header")
        raw = bytearray(data)
        if len(raw) < 4120:
            parser.error(f"{name}: truncated CRC header")
        size, stored = struct.unpack_from("<II", raw, 4112)
        raw[4112:4120] = bytes(8)
        if size != len(raw) or stored != sdk_image.crc8266(raw):
            parser.error(f"{name}: Arduino CRC/size mismatch")
        checksums = []
        for base in (0, 4096):
            position, checksum = base + 8, 0xEF
            for _ in range(raw[base + 1]):
                if position + 8 > len(raw):
                    parser.error(f"{name}: truncated segment header")
                _, length = struct.unpack_from("<II", raw, position)
                position += 8
                if position + length > len(raw):
                    parser.error(f"{name}: truncated image segment")
                for byte in raw[position:position + length]:
                    checksum ^= byte
                position += length
            checksum_offset = position // 16 * 16 + 15
            if checksum_offset >= len(raw) or raw[checksum_offset] != checksum:
                parser.error(f"{name}: image XOR mismatch")
            checksums.append(hex(checksum))
        validation[environment] = {"image_bytes": size, "arduino_crc32": hex(stored),
                                   "eboot_xor": checksums[0], "app_xor": checksums[1],
                                   "flash_mode": "DOUT", "flash_size": "1 MiB", "flash_frequency": "40 MHz"}
        (output / (name + ".bin")).write_bytes(data)
        compressed = gzip.compress(data, compresslevel=9, mtime=0)
        if gzip.decompress(compressed) != data:
            parser.error(f"{name}: gzip round trip failed")
        (output / (name + ".bin.gz")).write_bytes(compressed)

    with zipfile.ZipFile(output / ("wthermostat-symbols-" + args.version + ".zip"), "w", zipfile.ZIP_DEFLATED) as archive:
        for suffix in (".elf", ".map"):
            filename = "wthermostat-" + args.version + suffix
            archive.write(root / "build_output/map" / filename, arcname=filename)
    files = subprocess.check_output(["git", "ls-files", "-z"], text=True).split("\0")
    source = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
              for name in files if name and (root / name).is_file()}
    (output / "SOURCE-MANIFEST.json").write_text(json.dumps(source, indent=2) + "\n")
    manifest = {"version": args.version,
                "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                "tree": subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], text=True).strip(),
                "image_validation": validation,
                "assets": {p.name: {"bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                           for p in sorted(output.iterdir())}}
    (output / "BUILD-MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (output / "SHA256SUMS").write_text("".join(
        hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
        for p in sorted(output.iterdir()) if p.name != "SHA256SUMS"))
    output.rename(destination)
    print(json.dumps(validation, indent=2))
