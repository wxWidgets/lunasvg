#!/usr/bin/env python3
"""Hard-gated upstream sync for wxlunasvg (plan section 6, Phase 6; Goal 3).

``origin/master`` is a strict, fast-forward-only mirror of ``upstream/master``
(plan decision 2b #10); the branch wxWidgets actually consumes is ``wx``.
Pulling a new upstream change therefore means merging upstream into a throwaway
``sync/upstream-*`` branch, normalising the result with
``scripts/post_merge.py``, and building and running the full suite *before*
anything is committed.

Unlike pull-request CI, which is advisory (plan decisions 2b #11 and 2b #13),
this path is a HARD gate: while the suite is red the script does not commit and
therefore cannot push. That is Goal 3's explicit requirement and does not rely
on branch protection.

Steps (plan section 6, Phase 6):

1. ``git fetch <upstream-remote>``
2. create ``sync/upstream-<tag|YYYYMMDD>`` from the base (``wx``)
3. stage a merge of the upstream ref (``--no-ff --no-commit`` - nothing is
   committed yet)
4. run ``scripts/post_merge.py``
5. ``git add -A``
6. build and run the full suite (``tests/run_tests.py``, i.e. cmake + ctest)
7. green: ``git commit`` and, unless ``--no-push``, ``git push origin``
   red:   leave the tree untouched for inspection, commit nothing, exit 2

This is Python, not PowerShell, and gets no ``.ps1`` shim (plan decision 2b #18).

Typical use::

    python scripts/sync_upstream.py                 # sync upstream/master
    python scripts/sync_upstream.py --tag v3.4.0    # sync a release tag
    python scripts/sync_upstream.py --dry-run       # print the plan, change nothing
    python scripts/sync_upstream.py --no-push       # gate locally, push by hand

Exit codes: ``0`` success (synced/up to date), ``1`` tooling or git error,
``2`` suite red (the gate refused to commit), ``3`` upstream advanced and the
suite is green (``--fail-on-drift``, used by the nightly drift workflow).
"""

import argparse
import datetime
import os
import re
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
DEFAULT_BASE = "wx"
DEFAULT_BUILD_DIR = "build"

# Tag/branch suffixes that are legal in a git ref name; anything else is folded
# to a dash so a tag such as "v3.4.0-rc.1" becomes a usable branch name.
REF_UNSAFE_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


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


def branch_exists(root: Path, name: str) -> bool:
    return git_ok(["rev-parse", "--verify", "--quiet", f"refs/heads/{name}"], root)


def rev_exists(root: Path, revision: str) -> bool:
    return git_ok(["rev-parse", "--verify", "--quiet", f"{revision}^{{commit}}"], root)


def merge_in_progress(root: Path) -> bool:
    """Return True while a ``--no-commit`` merge is staged (MERGE_HEAD exists)."""
    return git_ok(["rev-parse", "--verify", "--quiet", "MERGE_HEAD"], root)


def resolve_base(root: Path, base: str) -> str:
    """Resolve the sync branch's base, preferring a local branch over origin's."""
    for candidate in (f"refs/heads/{base}", f"refs/remotes/origin/{base}"):
        if rev_exists(root, candidate):
            return candidate
    raise SyncError(
        f"base ref '{base}' not found (looked for refs/heads/{base} and "
        f"refs/remotes/origin/{base}); fetch origin first"
    )


def normalise_upstream_ref(upstream_remote: str, upstream_ref: str) -> str:
    """Expand a bare ref such as ``master`` to ``<remote>/master``."""
    if upstream_ref.startswith("refs/") or "/" in upstream_ref:
        return upstream_ref
    return f"{upstream_remote}/{upstream_ref}"


def sync_branch_name(args: argparse.Namespace) -> str:
    """``sync/upstream-<tag|YYYYMMDD>`` (plan section 6, Phase 6)."""
    if args.branch:
        return args.branch
    if args.tag:
        suffix = REF_UNSAFE_PATTERN.sub("-", args.tag).strip("-") or "tag"
    else:
        suffix = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d")
    return f"sync/upstream-{suffix}"


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
        "--base",
        default=DEFAULT_BASE,
        help=f"integration branch the sync branch is cut from (default: {DEFAULT_BASE})",
    )
    parser.add_argument(
        "--branch",
        default=None,
        help="explicit sync branch name (default: sync/upstream-<tag|YYYYMMDD>)",
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
        "--suite-command",
        default=None,
        help="advanced/testing override: replace the suite command entirely "
             "(the gate then judges *this* command; the default runs tests/run_tests.py)",
    )
    parser.add_argument(
        "--no-push",
        action="store_true",
        help="commit on green but do not push to origin (used by the drift workflow)",
    )
    parser.add_argument(
        "--fail-on-drift",
        action="store_true",
        help="exit 3 when upstream advanced and the suite is green (drift workflow)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="recreate the sync branch if it already exists",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the resolved plan and exit without touching anything",
    )
    return parser.parse_args(argv)


def print_plan(args: argparse.Namespace, root: Path, base_ref: str, upstream_ref: str,
               branch: str, suite: List[str]) -> None:
    print("sync_upstream.py - hard-gated upstream sync (plan Phase 6, Goal 3)")
    print(f"  repo root     : {root}")
    print(f"  upstream      : {args.upstream_remote} -> {upstream_ref}")
    print(f"  base branch   : {base_ref}")
    print(f"  sync branch   : {branch}")
    print(f"  build dir     : {args.build_dir}")
    print(f"  suite command : {' '.join(suite)}")
    if args.no_push:
        print("  push on green : no (--no-push)")
    else:
        print(f"  push on green : origin/{branch}")
    print("  gate          : commit only when the suite is green (hard gate)")


def report_red(root: Path, branch: str) -> None:
    print("\n=== SUITE RED - the gate refused to commit ===", file=sys.stderr)
    print(f"Upstream changes are staged on '{branch}' but were NOT committed and NOT pushed.",
          file=sys.stderr)
    print("The tree is left untouched so you can inspect the failures.", file=sys.stderr)
    print(f"  inspect : git -C {root} status ; git -C {root} diff --cached", file=sys.stderr)
    print(f"  abort   : git -C {root} reset --hard && git -C {root} clean -fd", file=sys.stderr)


def git_rev_short(root: Path) -> str:
    completed = git(["rev-parse", "--short", "HEAD"], root, capture=True)
    return completed.stdout.strip()


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    try:
        start_dir = Path(args.root).resolve() if args.root else Path(__file__).resolve().parent
        root = detect_repo_root(start_dir)

        upstream_ref = f"refs/tags/{args.tag}" if args.tag else normalise_upstream_ref(
            args.upstream_remote, args.upstream_ref)
        branch = sync_branch_name(args)
        suite = suite_command(args, root)

        # Resolve the base up front so --dry-run reports the same plan the real
        # run would follow; this is read-only.
        base_ref = resolve_base(root, args.base)

        if args.dry_run:
            print_plan(args, root, base_ref, upstream_ref, branch, suite)
            print("\n(dry-run: nothing was fetched, merged, built or committed)")
            return EXIT_OK

        # --- preconditions ---------------------------------------------------
        if not git_ok(["remote", "get-url", args.upstream_remote], root):
            raise SyncError(
                f"remote '{args.upstream_remote}' is not configured; "
                f"git remote add {args.upstream_remote} <url>")
        if not is_clean(root):
            raise SyncError("working tree is dirty; commit or stash first")
        if branch_exists(root, branch):
            if not args.force:
                raise SyncError(f"branch '{branch}' already exists (use --force to recreate it)")
            git(["branch", "-D", branch], root, capture=True)

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

        # --- 2. branch from the base ----------------------------------------
        print(f"\n[2/7] create {branch} from {base_ref}")
        created = git(["checkout", "-b", branch, base_ref], root, capture=False)
        if created.returncode != 0:
            raise SyncError(f"could not create branch '{branch}' from '{base_ref}'")
        # A branch cut from origin/<base> starts out tracking it; drop that so a
        # bare `git push` can never target the base branch by accident.
        git(["branch", "--unset-upstream", branch], root, capture=True)

        # --- 3. stage the merge (no commit yet) ------------------------------
        print(f"\n[3/7] merge {upstream_ref} (staged, not committed)")
        merged = git(["merge", "--no-ff", "--no-commit", "--no-edit", upstream_ref],
                     root, capture=False)
        if merged.returncode != 0:
            raise SyncError(
                "merge failed (conflicts?); resolve them, or abort with "
                "`git merge --abort`, then re-run")

        if not merge_in_progress(root):
            print(f"\nAlready up to date: {base_ref} already contains {upstream_ref}.")
            git(["checkout", "-"], root, capture=True)
            git(["branch", "-D", branch], root, capture=True)
            return EXIT_OK

        # --- 4. post_merge.py ------------------------------------------------
        print("\n[4/7] run scripts/post_merge.py")
        post_merge = run([sys.executable, str(root / "scripts" / "post_merge.py"), "--root", str(root)],
                         root, capture=False)
        if post_merge.returncode != 0:
            raise SyncError("scripts/post_merge.py failed")

        # --- 5. stage everything --------------------------------------------
        print("\n[5/7] git add -A")
        staged = git(["add", "-A"], root, capture=True)
        if staged.returncode != 0:
            raise SyncError("git add -A failed")

        # --- 6. the gate: build + full suite ---------------------------------
        print(f"\n[6/7] build + full suite: {' '.join(suite)}")
        suite_result = run(suite, root, capture=False)
        if suite_result.returncode != 0:
            report_red(root, branch)
            return EXIT_SUITE_RED

        # --- 7. commit (+ push) only on green --------------------------------
        print("\n[7/7] suite green - commit" + (" only" if args.no_push else " and push"))
        message = args.tag or args.upstream_ref
        committed = git(["commit", "-m", f"Sync upstream {message} into {branch}"], root, capture=True)
        if committed.returncode != 0:
            raise SyncError(committed.stderr.strip() or committed.stdout.strip() or "git commit failed")
        print(f"committed on {branch}: {git_rev_short(root)}")

        if args.no_push:
            print("not pushed (--no-push)")
        else:
            pushed = git(["push", "origin", branch], root, capture=False)
            if pushed.returncode != 0:
                raise SyncError(f"git push origin {branch} failed")
            print(f"pushed origin/{branch}")

        print("\nNext steps:")
        print(f"  open a PR: --base {args.base} --head {branch} (origin, never upstream)")

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
