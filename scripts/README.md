# wxlunasvg Scripts

## post_merge.py

This script makes necessary changes to files after pulling from the upstream lunasvg repository to ensure they build
correctly within wxWidgets.

### Usage

```bash
# Run with actual changes
python scripts/post_merge.py

# Dry-run mode (preview changes without modifying files)
python scripts/post_merge.py --dry-run

# Specify a different root directory
python scripts/post_merge.py --root /path/to/wxlunasvg
```

### Changes Applied

1. **include/lunasvg.h - C++17 Compiler Check**
   - Adds a C++17 version check with `#error` if not present
   - Placed before the first `#include` directive

2. **include/lunasvg.h - WX Defines**
   - Normalizes the `LUNASVG_BUILD_STATIC` / `LUNASVG_BUILD` guards to a single block, so a merge cannot leave a
duplicate `#define LUNASVG_BUILD_STATIC` that warns on every translation unit
   - Placed before the `LUNASVG_EXPORT` selection block

3. **All C++ Files - Namespace Fix**
   - Replaces `namespace lunasvg` with `namespace wxlunasvg`
   - Rewrites qualified usages such as `lunasvg::FontFace` to `wxlunasvg::FontFace`
   - Applied to all files in include/ and sources/ directory

### Manual workflow

`post_merge.py` is normally invoked for you by `scripts/sync_upstream.py` (below), which is the supported way to pull
upstream. It stays runnable by hand:

```bash
python scripts/post_merge.py --dry-run  # preview changes
python scripts/post_merge.py            # apply changes
python scripts/test_post_merge_idempotency.py   # apply-then-re-run must be a no-op
```

The old `git pull upstream master && post_merge.py && git add -u && git commit` sequence is superseded: it could commit
a tree whose tests were broken.

---

## sync_upstream.py - the upstream-sync gate (Goal 3)

`origin/master` is a strict, fast-forward-only mirror of `upstream/master` (decision 2b #10), and the integration branch
is `wx`. Pulling upstream is therefore a merge onto a throwaway `sync/upstream-*` branch, normalised, and committed
**only if the full suite passes**:

```bash
python scripts/sync_upstream.py                 # sync upstream/master
python scripts/sync_upstream.py --tag v3.4.0    # sync a release tag
python scripts/sync_upstream.py --dry-run       # print the plan, change nothing
python scripts/sync_upstream.py --no-push       # gate locally, push by hand
```

The seven steps mirror plan section 6 (Phase 6):

1. `git fetch <upstream-remote>`
2. create `sync/upstream-<tag|YYYYMMDD>` from `wx`
3. stage a merge of the upstream ref (`git merge --no-ff --no-commit` - still nothing committed)
4. run `scripts/post_merge.py`
5. `git add -A`
6. build and run the full suite (`tests/run_tests.py`, i.e. cmake + ctest)
7. green: `git commit` and (unless `--no-push`) `git push origin`; red: leave the tree staged for inspection, commit
   nothing, exit `2`

**This is a HARD gate even though PR CI is advisory** (decision 2b #13): Goal 3 requires the suite to pass before the
sync may commit, and that does not depend on branch protection.

| Exit code | Meaning |
|---|---|
| `0` | success (synced, or already up to date) |
| `1` | tooling / git error (dirty tree, conflict, bad ref, ...) |
| `2` | suite red - refused to commit |
| `3` | upstream advanced and the suite is green (`--fail-on-drift`) |

Options: `--upstream-remote`, `--upstream-ref`, `--tag`, `--base`, `--branch`, `--build-dir`, `--catch2-dir`, `--jobs`,
`--no-push`, `--fail-on-drift`, `--force`, `--dry-run`. `--suite-command` replaces the suite command entirely and exists
only for exercising the gate itself without a full build; normal runs use `tests/run_tests.py`.

Python only, no `.ps1` shim (decision 2b #18).

### Drift detection

`.github/workflows/upstream-drift.yml` runs nightly and on demand.
It executes the same sync path with `--no-push`, so `origin` is never touched: a green run reports that upstream
advanced (the job fails by default so the scheduled run is a visible “time to sync” signal; dispatch with
`fail_on_drift=false` to only report), and a red suite fails the job outright.

### post_merge.py idempotency

`scripts/test_post_merge_idempotency.py` builds a fixture tree, applies `post_merge.py` once, and asserts that a second
`--dry-run` (and a second real run) report `No changes needed.`. It runs in the `structural-lint` CI job.
Without it, a non-idempotent rewrite would keep re-dirtying the checkout, so the sync gate could never reach a clean
tree.

---

## PR path

Test and PR tooling in `origin` is Python, never PowerShell (decision 2b #18). `.tts/` is an untracked local-helper
directory; its `copy_pr.ps1` is ported to `.tts/copy_pr.py`, which copies fresh upstream files from the local
`../lunasvg-tests/lunasvg` checkout, runs `post_merge.py`, and then runs the suite before a branch is considered
PR-ready. The tracked flow is `.github/workflows/tests.yml` on the pull request plus `scripts/sync_upstream.py` for
upstream pulls.

---

## Repository topology (origin-first PR workflow)

Phase 0 of the test-infrastructure plan pins the repository topology so that `origin` is the unambiguous default for
every push and every PR.

| Ref | Role | Push policy |
|---|---|---|
| `origin/master` | Strict mirror of `upstream/master` | Fast-forward only; never commit on it |
| `origin/wx` | Integration branch wxWidgets consumes | **All PRs target `origin/wx`** |
| feature branches | Short-lived topic branches | Cut from `wx`; push to `origin`, PR base `wx` |

- `origin` = `https://github.com/wxWidgets/lunasvg.git` — the fork we push to.
- `upstream` = `https://github.com/sammycage/lunasvg.git` — read-only source of truth; **never push**.

### Per-clone local git config

```bash
git config remote.pushDefault origin      # bare `git push` targets origin
git config push.default current           # push the current branch under its own name
git config branch.wx.pushRemote origin    # `wx` always pushes to origin
git config core.hooksPath scripts/hooks   # use this repo's tracked hooks
gh repo set-default wxWidgets/lunasvg     # gh pr/issue default to the fork, not sammycage
```

### `upstream` push guard

`scripts/hooks/pre-push` (tracked via `core.hooksPath=scripts/hooks`) refuses any push whose remote is `upstream` (or
whose URL points at `sammycage/lunasvg`). Bypassing it requires deliberately overriding the hook path, which is the
point: pushing to `upstream` must be a conscious act, not the default.

> Commit the hook with the executable bit set (`git update-index --chmod=+x scripts/hooks/pre-push`) so the > guard is
> active on Linux/macOS checkouts.
> The optional `remote.upstream.pushurl` sentinel from the plan is > intentionally left unset — the hook is the primary
> guard.

### Deferred

Branch protection and required status checks on `origin/wx` are **deferred** (plan decision 2b #11): CI is advisory
signal, not a merge block, until the suite is green and robust.
