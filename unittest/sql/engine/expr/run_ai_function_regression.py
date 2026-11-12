#!/usr/bin/env python3
"""Build and run native AI regressions using an existing seekdb CMake build."""
import argparse
import json
from pathlib import Path
import shlex
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[4]
    parser.add_argument('--build-dir', type=Path, default=root / 'build_release')
    args = parser.parse_args()
    build = args.build_dir.resolve()
    entries = json.loads((build / 'compile_commands.json').read_text())
    entry = next(e for e in entries if 'unity_ob_sql_ob_sql_engine_expr_15_c___cxx.cxx' in e['file'])
    output = build / 'ai_function_regression'
    output.mkdir(exist_ok=True)
    object_file = output / 'test.o'
    binary = output / 'test_ai_function_regression'
    command = shlex.split(entry['command'])
    command = command[:command.index('-o')]
    command = [arg for arg in command if arg not in ('-c', entry['file'])]
    command += ['-O0', '-g0', '-c', str(Path(__file__).with_name('test_ai_function_regression.cpp')), '-o', str(object_file)]
    subprocess.run(command, cwd=entry['directory'], check=True)
    observer = build / 'src/observer'
    command = shlex.split((observer / 'CMakeFiles/seekdb.dir/link.txt').read_text())
    command = [arg for arg in command if arg not in ('CMakeFiles/ob_main.dir/main.cpp.o', 'CMakeFiles/ob_main.dir/ob_command_line_parser.cpp.o')]
    command[command.index('-o') + 1] = str(binary)
    command.insert(command.index('-o'), str(object_file))
    subprocess.run(command, cwd=observer, check=True)
    subprocess.run([str(binary)], cwd=output, check=True)


if __name__ == '__main__':
    main()
