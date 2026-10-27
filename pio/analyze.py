"""Cross-check the application TU with current host analyzers and target GCC.

Reports retain all findings, including third-party headers. A successful exit
means analysis completed; findings still require review, not blanket suppression.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

from check import make_overlay

ROOT = Path(__file__).resolve().parents[1]
MODEL = ['-m32', '-funsigned-char', '-fshort-wchar', '-mlong-double-64',
         '-malign-double', '-std=gnu++17', '-fno-exceptions', '-fno-rtti']
CHECKS = '-*,clang-analyzer-*,bugprone-*,cert-*,performance-*,portability-*'
ABI = '''static_assert(sizeof(void*)==4 && sizeof(int)==4 && sizeof(long)==4);
static_assert(sizeof(long long)==8 && sizeof(float)==4 && sizeof(double)==8);
static_assert(sizeof(long double)==8 && sizeof(wchar_t)==2 && char(-1)>0);
static_assert(alignof(double)==8 && alignof(long long)==8 && alignof(long double)==8);
'''


def builtin_flags(text):
    flags = []
    for line in text.splitlines():
        if not line.startswith('#define '):
            continue
        name, _, value = line[8:].partition(' ')
        flags.extend(['-U' + name.split('(')[0], '-D' + name + '=' + value])
    return flags


def cppcheck_complete(text):
    errors = ET.fromstring(text).findall('.//error')
    return not any(e.get('id') in {'syntaxError', 'internalError', 'unknownMacro',
                                  'preprocessorErrorDirective', 'missingInclude',
                                  'missingIncludeSystem'} for e in errors)


def run(command, log):
    log.with_suffix(log.suffix + '.command.json').write_text(json.dumps(command, indent=2))
    with log.open('w') as output, log.with_suffix('.progress.log').open('w') as progress:
        result = subprocess.run(command, cwd=ROOT,
                                stdout=progress if log.suffix == '.xml' else output,
                                stderr=output if log.suffix == '.xml' else subprocess.STDOUT)
    log.with_suffix(log.suffix + '.exit').write_text(str(result.returncode))
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-e', '--environment', action='append')
    parser.add_argument('--tool', choices=['clang', 'cppcheck', 'gcc'], action='append')
    args = parser.parse_args()
    environments = args.environment or ['wthermostat', 'wthermostat-minimal', 'wthermostat-debug']
    tools = args.tool or ['clang', 'cppcheck', 'gcc']
    failed = False
    for environment in environments:
        out = ROOT / 'build_output/validation/static' / environment
        out.mkdir(parents=True, exist_ok=True)
        metadata = json.loads(subprocess.check_output([
            sys.executable, '-m', 'platformio', 'project', 'metadata',
            '-e', environment, '--json-output'], cwd=ROOT, text=True))[environment]
        (out / 'metadata.json').write_text(json.dumps(metadata, indent=2))
        compiler = metadata['cxx_path']
        flags = metadata['cxx_flags']
        target_options = [f for f in flags if f.startswith(('-m', '-f', '-std='))]
        predefined = subprocess.check_output([compiler, *target_options, '-dM', '-E',
                                             '-x', 'c++', '/dev/null'], text=True)
        (out / 'builtins.txt').write_text(predefined)
        builtins = builtin_flags(predefined)
        includes = ['-I' + p for group in ['build', 'toolchain'] for p in metadata['includes'][group]]
        defines = ['-D' + d for d in metadata['defines']]
        source = str(ROOT / 'WThermostat/WThermostat.cpp')
        abi = out / 'abi.cpp'
        abi.write_text(ABI)
        # Assert the actual target and analysis model independently.
        subprocess.run([compiler, *target_options, '-fsyntax-only', str(abi)], check=True)
        if 'clang' in tools:
            subprocess.run(['clang++', *MODEL, '-fsyntax-only', str(abi)], check=True)
            header = Path(compiler).parent.parent / 'xtensa-lx106-elf/include/sys/pgmspace.h'
            overlay = make_overlay(header, out)
            log = out / 'clang-tidy.log'
            code = run(['clang-tidy', '--quiet', '--checks=' + CHECKS,
                        '--header-filter=(WThermostat|lib/WAdapter)/.*',
                        '--vfsoverlay=' + str(overlay), '--export-fixes=' + str(out / 'clang-tidy.yaml'),
                        source, '--', *MODEL, *builtins, *defines, *includes], log)
            failed |= code != 0 or '[clang-diagnostic-error]' in log.read_text()
            frontend = out / 'clang-frontend.log'
            failed |= run(['clang++', '-fsyntax-only', '-Wall', '-Wextra', '-Wformat=2',
                           '-Wconversion', '-Wsign-conversion', *MODEL, *builtins,
                           *defines, *includes, '-ivfsoverlay', str(overlay), source], frontend) != 0
        if 'cppcheck' in tools:
            (out / 'cppcheck-cache').mkdir(exist_ok=True)
            database = out / 'compile_commands.json'
            database.write_text(json.dumps([{'directory': str(ROOT), 'file': source,
                                            'arguments': [compiler, *(f for f in builtins if f.startswith('-D')), *defines, *includes,
                                                          '-std=gnu++17', '-c', source]}], indent=2))
            log = out / 'cppcheck.xml'
            code = run(['cppcheck', '--project=' + str(database),
                        '--platform=' + str(ROOT / 'pio/esp8266.xml'), '--std=c++17',
                        '--library=std', '--library=posix', '--enable=all', '--inconclusive',
                        '--check-level=exhaustive', '--max-ctu-depth=4',
                        '--cppcheck-build-dir=' + str(out / 'cppcheck-cache'),
                        '--checkers-report=' + str(out / 'cppcheck-checkers.txt'),
                        '--xml', '--xml-version=2'], log)
            # Cppcheck emits progress on stdout and XML on stderr: split reliably.
            text = log.read_text()
            start = text.find('<?xml')
            end = text.rfind('</results>')
            if start < 0 or end < start:
                failed = True
            else:
                xml = text[start:end + len('</results>')]
                # Keep the raw mixed output as well as machine-readable XML.
                log.with_suffix('.raw.log').write_text(text)
                log.write_text(xml)
                failed |= code != 0 or not cppcheck_complete(xml)
        if 'gcc' in tools:
            failed |= run([compiler, *flags, *defines, *includes, '-c', '-o', str(out / 'application.o'),
                           '-Wextra', '-Wformat=2', '-Wformat-overflow=2', '-Wformat-truncation=2',
                           '-Wnull-dereference', '-Wduplicated-cond', '-Wduplicated-branches',
                           '-Wlogical-op', '-Wcast-align=strict', '-Wshadow=local',
                           '-Warray-bounds=2', '-Wstringop-overflow=2', '-Wmaybe-uninitialized',
                           '-Wconversion', '-Wsign-conversion', '-fdiagnostics-format=json',
                           source], out / 'gcc.json') != 0
        versions = {}
        for tool in ['clang-tidy', 'clang++', 'cppcheck', compiler]:
            versions[tool] = subprocess.check_output([tool, '--version'], text=True).splitlines()[0]
        (out / 'versions.json').write_text(json.dumps(versions, indent=2))
        print(environment + ': reports saved to ' + str(out), flush=True)
    if failed:
        print('Analysis incomplete: inspect exit codes and parser diagnostics.', file=sys.stderr)
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
