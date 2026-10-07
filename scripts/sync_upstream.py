#!/usr/bin/env python3
"""Hard-gated upstream sync for wxlunasvg.

``origin/master`` is a strict, fast-forward-only mirror of ``upstream/master``
(plan decision 2b #10); the branch wxWidgets actually consumes is ``wx``.
Pulling a new upstream change therefore means merging upstream into the branch
you are currently on, normalising the result with ``scripts/post_merge.py``, and
building and running the full suite. The script NEVER commits and NEVER pushes:
on a green suite the merge is left staged on the current branch so you can add
tests covering any new upstream functionality, fix anything the merge broke, and
only then commit and submit the branch as a PR yourself.

Unlike pull-request CI, which is advisory, this path is a HARD gate: while the
suite is red the script reports it and leaves the tree untouched.

Steps:

1. ``git fetch <upstream-remote>``
2. stage a merge of the upstream ref into the *current* branch
   (``--no-ff --no-commit`` - nothing is committed)
3. run ``scripts/post_merge.py``
4. ``git add -A``
5. compile every library source under wxWidgets' warning flags
   (``scripts/check_wx_cxxflags.py``; a warning - most importantly an
   unused parameter - is fatal here before it reaches a wx build)
6. build and run the full suite (``tests/run_tests.py``, i.e. cmake + ctest)
7. green: leave the merge staged on the current branch and commit nothing, so
   you can add tests for any new upstream functionality and submit the branch
   as a PR once you are satisfied
   red:   leave the tree untouched for inspection, commit nothing, exit 2

Typical use::

    python scripts/sync_upstream.py                 # sync upstream/master into the current branch
    python scripts/sync_upstream.py --tag v3.4.0    # sync a release tag
    python scripts/sync_upstream.py --dry-run       # print the plan, change nothing

Exit codes: ``0`` success (synced/up to date), ``1`` tooling or git error,
``2`` red (the full suite failed, or the wxWidgets warning-flags compile
failed), ``3`` upstream advanced and the suite is green (``--fail-on-drift``,
used by the nightly drift workflow).
"""

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Sequence

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_SUITE_RED = 2
EXIT_DRIFT = 3

DEFAULT_UPSTREAM_REMOTE = "upstream"
DEFAULT_BUILD_DIR = "build"


class SyncError(RuntimeError):
    """A precondition, git command or tooling step failed."""


def run(command: Sequence[str], cwd: Path, capture: bool = False) -> subprocess.CompletedProcess:
    """Execute *command*, echoing the command line unless output is captured."""
    if not capture:
        print(f"+ {' '.join(command)}", flush=True)
    return subprocess.run(
        list(command),
        cwd=str(cwd),
        capture_output=capture,
        text=True,
        check=False,
    )


def git(args: Sequence[str], cwd: Path, capture: bool = True) -> subprocess.CompletedProcess:
    """Run a git subcommand in *cwd*."""
    return run(["git", *args], cwd, capture=capture)


def git_ok(args: Sequence[str], cwd: Path) -> bool:
    """Return True when a git subcommand exits 0."""
    return git(args, cwd, capture=True).returncode == 0


def detect_repo_root(start: Path) -> Path:
    """Return the git top-level containing *start*."""
    completed = run(["git", "rev-parse", "--show-toplevel"], start, capture=True)
    if completed.returncode != 0:
        raise SyncError(f"not inside a git working tree (started at {start})")
    return Path(completed.stdout.strip()).resolve()


def is_clean(root: Path) -> bool:
    """Return True when the working tree has no staged, unstaged or untracked changes."""
    completed = run(["git", "status", "--porcelain"], root, capture=True)
    return completed.returncode == 0 and not completed.stdout.strip()


def rev_exists(root: Path, revision: str) -> bool:
    return git_ok(["rev-parse", "--verify", "--quiet", f"{revision}^{{commit}}"], root)


def merge_in_progress(root: Path) -> bool:
    """Return True while a ``--no-commit`` merge is staged (MERGE_HEAD exists)."""
    return git_ok(["rev-parse", "--verify", "--quiet", "MERGE_HEAD"], root)


def current_branch(root: Path) -> str:
    """Return the checked-out branch, or raise on a detached HEAD."""
    completed = git(["symbolic-ref", "--quiet", "--short", "HEAD"], root, capture=True)
    if completed.returncode != 0:
        raise SyncError(
            "HEAD is detached; check out the branch you want to sync into first")
    return completed.stdout.strip()


def normalise_upstream_ref(upstream_remote: str, upstream_ref: str) -> str:
    """Expand a bare ref such as ``master`` to ``<remote>/master``."""
    if upstream_ref.startswith("refs/") or "/" in upstream_ref:
        return upstream_ref
    return f"{upstream_remote}/{upstream_ref}"


def suite_command(args: argparse.Namespace, root: Path) -> List[str]:
    """The full-suite command: the canonical ``tests/run_tests.py`` wrapper by default."""
    if args.suite_command:
        return shlex.split(args.suite_command, posix=(os.name != "nt"))

    command = [
        sys.executable,
        str(root / "tests" / "run_tests.py"),
        "--configure",
        "--build-dir",
        args.build_dir,
    ]
    if args.catch2_dir:
        command += ["--catch2-dir", args.catch2_dir]
    if args.jobs:
        command += ["--jobs", str(args.jobs)]
    return command


def wx_check_command(args: argparse.Namespace, root: Path) -> List[str]:
    """The wxWidgets warning-flags compile: ``scripts/check_wx_cxxflags.py``."""
    return [
        sys.executable,
        str(root / "scripts" / "check_wx_cxxflags.py"),
        "--cxx",
        args.wx_check_cxx,
    ]


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--root",
        default=None,
        help="repository root (default: the git top-level containing this script)",
    )
    parser.add_argument(
        "--upstream-remote",
        default=DEFAULT_UPSTREAM_REMOTE,
        help=f"git remote holding upstream lunasvg (default: {DEFAULT_UPSTREAM_REMOTE})",
    )
    parser.add_argument(
        "--upstream-ref",
        default="upstream/master",
        help="upstream ref to merge (default: upstream/master)",
    )
    parser.add_argument(
        "--tag",
        default=None,
        help="sync this upstream tag instead of the branch ref",
    )
    parser.add_argument(
        "--build-dir",
        default=DEFAULT_BUILD_DIR,
        help=f"CMake build directory, relative to the repo root (default: {DEFAULT_BUILD_DIR})",
    )
    parser.add_argument(
        "--catch2-dir",
        default=None,
        help="pre-cloned Catch2 v3 tree, forwarded to tests/run_tests.py for offline builds",
    )
    parser.add_argument(
        "--jobs",
        "-j",
        type=int,
        default=None,
        help="parallel build jobs forwarded to tests/run_tests.py",
    )
    parser.add_argument(
        "--wx-check-cxx",
        default="g++",
        help="compiler used by the wxWidgets warning-flags check "
             "(scripts/check_wx_cxxflags.py; default: g++)",
    )
    parser.add_argument(
        "--suite-command",
        default=None,
        help="advanced/testing override: replace the suite command entirely "
             "(the gate then judges *this* command as well as the wx flag check; "
             "the default runs tests/run_tests.py)",
    )
    parser.add_argument(
        "--fail-on-drift",
        action="store_true",
        help="exit 3 when upstream advanced and the suite is green (drift workflow)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the resolved plan and exit without touching anything",
    )
    return parser.parse_args(argv)


def print_plan(args: argparse.Namespace, root: Path, branch: str, upstream_ref: str,
               suite: List[str], wx_check: List[str]) -> None:
    print("sync_upstream.py - hard-gated upstream sync")
    print(f"  repo root     : {root}")
    print(f"  upstream      : {args.upstream_remote} -> {upstream_ref}")
    print(f"  current branch: {branch}")
    print(f"  merge into    : {branch} (staged, never committed)")
    print(f"  build dir     : {args.build_dir}")
    print(f"  wx check      : {args.wx_check_cxx} (scripts/check_wx_cxxflags.py)")
    print(f"  suite command : {' '.join(suite)}")
    print("  push on green : never (pushing is left to you)")
    print("  commit        : never (green leaves the merge staged for you)")


def report_red(root: Path, branch: str) -> None:
    print("\n=== SUITE RED - nothing was committed ===", file=sys.stderr)
    print(f"The upstream merge is staged on '{branch}' but was NOT committed.",
          file=sys.stderr)
    print("The tree is left untouched so you can inspect the failures.", file=sys.stderr)
    print(f"  inspect : git -C {root} status ; git -C {root} diff --cached", file=sys.stderr)
    print(f"  abort   : git -C {root} reset --hard && git -C {root} clean -fd", file=sys.stderr)


def report_wx_check_red(root: Path, branch: str, cxx: str) -> None:
    print("\n=== WX FLAGS RED - nothing was committed ===", file=sys.stderr)
    print(f"{cxx} rejected at least one library source under wxWidgets' warning flags",
          file=sys.stderr)
    print("(-Werror): any warning - most importantly an unused parameter - is fatal",
          file=sys.stderr)
    print("in a wxWidgets --with-lunasvg build. Fix the source (or the post_merge.py",
          file=sys.stderr)
    print("rewrite that should have normalised it) and re-run.", file=sys.stderr)
    print(f"  reproduce: python scripts/check_wx_cxxflags.py --cxx {cxx}", file=sys.stderr)
    print(f"  inspect : git -C {root} status ; git -C {root} diff --cached", file=sys.stderr)
    print(f"  abort   : git -C {root} reset --hard && git -C {root} clean -fd", file=sys.stderr)


def report_green(root: Path, branch: str, upstream: str) -> None:
    print(f"The merge of {upstream} is staged on '{branch}'; nothing was committed.")
    print("Next: add tests for any new upstream functionality and fix anything the")
    print("merge broke, then commit and submit the branch as a PR once satisfied.")
    print(f"  inspect : git -C {root} status ; git -C {root} diff --cached")
    print(f"  commit  : git -C {root} commit   # completes the staged merge")
    print(f"  abort   : git -C {root} reset --hard && git -C {root} clean -fd")


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    try:
        start_dir = Path(args.root).resolve() if args.root else Path(__file__).resolve().parent
        root = detect_repo_root(start_dir)

        upstream_ref = f"refs/tags/{args.tag}" if args.tag else normalise_upstream_ref(
            args.upstream_remote, args.upstream_ref)
        sync_target = current_branch(root)
        suite = suite_command(args, root)
        wx_check = wx_check_command(args, root)

        if args.dry_run:
            print_plan(args, root, sync_target, upstream_ref, suite, wx_check)
            print("\n(dry-run: nothing was fetched, merged, built or committed)")
            return EXIT_OK

        # --- preconditions ---------------------------------------------------
        if not git_ok(["remote", "get-url", args.upstream_remote], root):
            raise SyncError(
                f"remote '{args.upstream_remote}' is not configured; "
                f"git remote add {args.upstream_remote} <url>")
        if not is_clean(root):
            raise SyncError("working tree is dirty; commit or stash first")

        # --- 1. fetch --------------------------------------------------------
        print(f"\n[1/7] fetch {args.upstream_remote}")
        if args.tag:
            fetched = git(["fetch", args.upstream_remote, f"refs/tags/{args.tag}:refs/tags/{args.tag}"],
                          root, capture=False)
        else:
            fetched = git(["fetch", args.upstream_remote], root, capture=False)
        if fetched.returncode != 0:
            raise SyncError(f"git fetch {args.upstream_remote} failed")
        if not rev_exists(root, upstream_ref):
            raise SyncError(f"upstream ref '{upstream_ref}' not found after fetch")

        # --- 2. stage the merge into the current branch (never a commit) -----
        print(f"\n[2/7] merge {upstream_ref} into {sync_target} (staged, not committed)")
        merged = git(["merge", "--no-ff", "--no-commit", "--no-edit", upstream_ref],
                     root, capture=False)
        if merged.returncode != 0:
            raise SyncError(
                "merge failed (conflicts?); resolve them, or abort with "
                "`git merge --abort`, then re-run")

        if not merge_in_progress(root):
            print(f"\nAlready up to date: {sync_target} already contains {upstream_ref}.")
            return EXIT_OK

        # --- 3. post_merge.py ------------------------------------------------
        print("\n[3/7] run scripts/post_merge.py")
        post_merge = run([sys.executable, str(root / "scripts" / "post_merge.py"), "--root", str(root)],
                         root, capture=False)
        if post_merge.returncode != 0:
            raise SyncError("scripts/post_merge.py failed")

        # --- 4. stage everything ---------------------------------------------
        print("\n[4/7] git add -A")
        staged = git(["add", "-A"], root, capture=True)
        if staged.returncode != 0:
            raise SyncError("git add -A failed")

        # --- 5. wxWidgets warning-flags compile (the regression guard) -------
        print(f"\n[5/7] wxWidgets warning-flags compile: {' '.join(wx_check)}")
        wx_result = run(wx_check, root, capture=False)
        if wx_result.returncode == 2:
            raise SyncError(
                f"wxWidgets warning-flags check could not run (compiler "
                f"'{args.wx_check_cxx}' not found); install it or pass "
                f"--wx-check-cxx")
        if wx_result.returncode != 0:
            report_wx_check_red(root, sync_target, args.wx_check_cxx)
            return EXIT_SUITE_RED

        # --- 6. the gate: build + full suite ---------------------------------
        print(f"\n[6/7] build + full suite: {' '.join(suite)}")
        suite_result = run(suite, root, capture=False)
        if suite_result.returncode != 0:
            report_red(root, sync_target)
            return EXIT_SUITE_RED

        # --- 7. green: report and stop - the script never commits ------------
        print("\n[7/7] suite green - the script never commits")
        report_green(root, sync_target, args.tag or args.upstream_ref)

        if args.fail_on_drift:
            print(f"\ndrift: upstream advanced and the suite is green "
                  f"({args.tag or args.upstream_ref})", file=sys.stderr)
            return EXIT_DRIFT
        return EXIT_OK

    except SyncError as error:
        print(f"\nerror: {error}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
