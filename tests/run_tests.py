#!/usr/bin/env python3
"""Thin local convenience wrapper around ``ctest`` for the wxlunasvg test suite.

``ctest`` is the canonical runner and is what CI invokes; this script only saves
you from typing the configure/build/test sequence on a fresh tree. It is Python
(not PowerShell) per plan decision 2b #18 and runs on Linux, macOS and Windows.

Typical use::

    python tests/run_tests.py --configure   # fresh tree: configure + build + test
    python tests/run_tests.py               # rebuild + test
    python tests/run_tests.py --no-build    # test only
    python tests/run_tests.py --wx-check    # wxWidgets warning-flags check, then ctest
    python tests/run_tests.py -- -R api     # forward extra args to ctest
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def run(command: list, cwd: Path) -> int:
    """Echo and execute *command*, returning its exit code."""
    print(f"+ {' '.join(command)}", flush=True)
    return subprocess.call(command, cwd=str(cwd))


def main(argv: list = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--build-dir",
        default="build",
        help="CMake build directory, relative to the repo root (default: build)",
    )
    parser.add_argument(
        "--configure",
        action="store_true",
        help="run the CMake configure step first, with -DLUNASVG_BUILD_TESTS=ON",
    )
    parser.add_argument(
        "--no-build",
        action="store_true",
        help="skip the build step and only run ctest",
    )
    parser.add_argument(
        "--catch2-dir",
        default=None,
        help="pre-cloned Catch2 v3 tree, forwarded as -DLUNASVG_CATCH2_DIR",
    )
    parser.add_argument(
        "--wx-check",
        action="store_true",
        help="also run scripts/check_wx_cxxflags.py (wxWidgets warning flags) "
             "before ctest",
    )
    parser.add_argument(
        "--jobs",
        "-j",
        default=None,
        help="parallel build jobs passed to `cmake --build --parallel`",
    )
    parser.add_argument(
        "ctest_args",
        nargs="*",
        help="extra arguments forwarded verbatim to ctest (after `--`)",
    )
    args = parser.parse_args(argv)

    if shutil.which("ctest") is None:
        print("error: ctest was not found on PATH", file=sys.stderr)
        return 1

    build_dir = (REPO_ROOT / args.build_dir).resolve()

    if args.wx_check:
        result = run([sys.executable, str(REPO_ROOT / "scripts" / "check_wx_cxxflags.py")], REPO_ROOT)
        if result != 0:
            return result

    if args.configure:
        configure = [
            "cmake",
            "-S",
            str(REPO_ROOT),
            "-B",
            str(build_dir),
            "-DLUNASVG_BUILD_TESTS=ON",
        ]
        if args.catch2_dir:
            configure.append(f"-DLUNASVG_CATCH2_DIR={Path(args.catch2_dir).resolve()}")
        result = run(configure, REPO_ROOT)
        if result != 0:
            return result

    if not args.no_build:
        build = ["cmake", "--build", str(build_dir)]
        if args.jobs:
            build += ["--parallel", str(args.jobs)]
        result = run(build, REPO_ROOT)
        if result != 0:
            return result

    if not build_dir.is_dir():
        print(
            f"error: build directory '{build_dir}' does not exist; run with --configure first",
            file=sys.stderr,
        )
        return 1

    return run(["ctest", "--output-on-failure"] + args.ctest_args, build_dir)


if __name__ == "__main__":
    sys.exit(main())
