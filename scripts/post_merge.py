#!/usr/bin/env python3
"""
Post-merge script to fix files after pulling from upstream lunasvg repository.
This script makes necessary changes to files so they build correctly within wxWidgets.
"""

import argparse
import re
import sys
from pathlib import Path
from typing import List, Tuple

# Upstream vendors third-party trees (plutovg/) and leaves a build/ directory
# behind; only the fork's own sources are rewritten, so the scan is scoped to
# these two directories instead of the whole checkout.
SCANNED_DIRECTORIES = ('include', 'source')
SOURCE_EXTENSIONS = frozenset({'.c', '.cc', '.cpp', '.cxx', '.h', '.hpp', '.hxx', '.ipp'})

NEWLINE_PATTERN = re.compile(r'\r\n|\n')

# Matches comments, string/char literals, the legacy namespace declaration and
# any legacy namespace qualifier. Comments and literals are listed first so they
# are consumed whole: anything that merely mentions the legacy name in passing
# (for example "namespace lunasvg is the legacy name") is reported as its own
# token and can be handed back verbatim.
CODE_TOKEN_PATTERN = re.compile(
    r"(?P<comment>//[^\n]*|/\*.*?\*/)"
    r"""|(?P<literal>"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*')"""
    r"|(?P<namespace>\bnamespace\s+lunasvg\b)"
    r"|(?P<qualified>\blunasvg\s*::)",
    re.DOTALL,
)

# A comment whose entire body is the namespace declaration is a restatement of
# the declaration itself (upstream writes the closing brace as
# `} // namespace lunasvg`), so it is kept in sync. Prose that only mentions the
# name in passing does not match this and is preserved.
RESTATEMENT_COMMENT_PATTERN = re.compile(r'\s*namespace\s+lunasvg\s*')

NAMESPACE_REPLACEMENT_PATTERN = re.compile(r'\bnamespace(\s+)lunasvg\b')

# The legacy name used as a scope qualifier (`lunasvg::FontFace`) must be renamed
# too: those usages appear outside the namespace block, so leaving them alone
# breaks references to the renamed namespace. The leading word boundary stops an
# already-rewritten `wxlunasvg::x` from being matched a second time.
QUALIFIED_REPLACEMENT_PATTERN = re.compile(r'\blunasvg(\s*::)')


class ChangeTracker:
    """Track and report changes made to files."""

    def __init__(self):
        self.changes = []

    def add(self, file_path: str, description: str):
        """Add a change to track."""
        self.changes.append((file_path, description))

    def print_summary(self):
        """Print summary of all changes."""
        if not self.changes:
            print("No changes needed.")
            return

        print(f"\nSummary: {len(self.changes)} change(s) made:")
        for file_path, description in self.changes:
            print(f"  {file_path}: {description}")


def find_cpp_files(root_dir: Path) -> List[Path]:
    """Find C++ sources under include/ and source/ only, never vendored trees."""
    cpp_files: List[Path] = []

    for directory_name in SCANNED_DIRECTORIES:
        directory = root_dir / directory_name
        if not directory.is_dir():
            continue

        for path in sorted(directory.rglob('*')):
            if path.is_file() and path.suffix.lower() in SOURCE_EXTENSIONS:
                cpp_files.append(path)

    return cpp_files


def detect_line_ending(content: str) -> str:
    """Return the newline sequence the file already uses, defaulting to LF."""
    match = NEWLINE_PATTERN.search(content)
    return match.group(0) if match else '\n'


def read_source_text(file_path: Path) -> Tuple[str, str]:
    """Read a source file as LF-normalised text plus its original line ending."""
    # newline='' disables universal-newline translation on read.
    with open(file_path, 'r', encoding='utf-8', newline='') as handle:
        raw_content = handle.read()

    line_ending = detect_line_ending(raw_content)
    normalized = raw_content.replace('\r\n', '\n').replace('\r', '\n')
    return normalized, line_ending


def write_source_text(file_path: Path, content: str, line_ending: str) -> None:
    """Write text using the file's own line ending, without newline translation."""
    if line_ending != '\n':
        content = content.replace('\n', line_ending)

    # newline='' stops Windows from rewriting every LF as CRLF.
    with open(file_path, 'w', encoding='utf-8', newline='') as handle:
        handle.write(content)


def check_cpp17_error(content: str) -> bool:
    """Check if file already has a C++17 error check."""
    # Look for any #error directive mentioning C++17 or similar version check
    error_pattern = r'#\s*error\s+.*(?:C\+\+17|C\+\+1[7-9]|C\+\+2\d)'
    return bool(re.search(error_pattern, content, re.IGNORECASE))


def add_cpp17_check(content: str) -> Tuple[str, bool]:
    """Add C++17 check before first #include if not present."""
    if check_cpp17_error(content):
        return content, False

    # Find the first #include directive
    include_pattern = r'^#include\s+[<"]'
    lines = content.split('\n')

    for i, line in enumerate(lines):
        if re.match(include_pattern, line):
            # Insert the check before this line
            cpp17_check = [
                '',
                '#if !(__cplusplus >= 201703L || (defined(_MSVC_LANG) && _MSVC_LANG >= 201703L))',
                '    #error "C++17 or later is required for LunaSVG support."',
                '#endif',
                ''
            ]
            lines[i:i] = cpp17_check
            return '\n'.join(lines), True

    return content, False


def check_wx_defines(content: str) -> bool:
    """Check if WX-related defines are present."""
    has_wxmakingdll = 'WXMAKINGDLL' in content
    has_wxbuilding = 'WXBUILDING' in content
    return has_wxmakingdll and has_wxbuilding


def add_wx_defines(content: str) -> Tuple[str, bool]:
    """Add the missing WX define blocks before the extern "C" block.

    Each block is decided separately so a header that already carries one of
    them is never given a second, duplicated copy of the same guard.
    """
    if check_wx_defines(content):
        return content, False

    extern_c_pattern = r'^extern\s+"C"\s*{'
    lines = content.split('\n')

    wx_defines = []
    if 'WXMAKINGDLL' not in content:
        wx_defines.extend([
            '',
            '#ifndef WXMAKINGDLL',
            '    #define LUNASVG_BUILD_STATIC',
            '#endif',
        ])
    if 'WXBUILDING' not in content:
        wx_defines.extend([
            '',
            '#ifdef WXBUILDING',
            '    #define LUNASVG_BUILD',
            '#endif',
        ])

    if not wx_defines:
        return content, False

    wx_defines.append('')

    for i, line in enumerate(lines):
        if re.match(extern_c_pattern, line):
            lines[i:i] = wx_defines
            return '\n'.join(lines), True

    return content, False


def rename_namespace_declarations(text: str) -> str:
    """Rename legacy namespace declarations, preserving original spacing."""
    return NAMESPACE_REPLACEMENT_PATTERN.sub(r'namespace\1wxlunasvg', text)


def rename_namespace_qualifiers(text: str) -> str:
    """Rename legacy namespace qualifiers, preserving original spacing."""
    return QUALIFIED_REPLACEMENT_PATTERN.sub(r'wxlunasvg\1', text)


def is_namespace_restatement_comment(comment: str) -> bool:
    """Report whether a comment is nothing but the namespace declaration."""
    body = comment[2:-2] if comment.startswith('/*') else comment[2:]
    return RESTATEMENT_COMMENT_PATTERN.fullmatch(body) is not None


def fix_namespace(content: str) -> Tuple[str, bool]:
    """Rewrite the legacy namespace declaration and its qualified usages.

    'namespace lunasvg' becomes 'namespace wxlunasvg' and qualifiers such as
    'lunasvg::FontFace' become 'wxlunasvg::FontFace', so code that lives outside
    the namespace block (for example the extern "C" wrappers) still resolves.
    Trailing comments that merely restate the declaration are renamed with it;
    comments and string/char literals that mention the legacy name as prose or
    data are left untouched.
    """

    def replace_token(match: re.Match) -> str:
        if match.lastgroup == 'namespace':
            return rename_namespace_declarations(match.group(0))
        if match.lastgroup == 'qualified':
            return rename_namespace_qualifiers(match.group(0))
        if match.lastgroup == 'comment' and is_namespace_restatement_comment(match.group(0)):
            return rename_namespace_declarations(match.group(0))
        return match.group(0)

    new_content = CODE_TOKEN_PATTERN.sub(replace_token, content)
    return new_content, new_content != content


def process_lunasvg_header(file_path: Path, dry_run: bool, tracker: ChangeTracker) -> bool:
    """Process include/lunasvg.h with specific checks."""
    try:
        content, line_ending = read_source_text(file_path)
    except Exception as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)
        return False

    original_content = content
    changes_made = []

    # Check 1: C++17 error check
    content, changed = add_cpp17_check(content)
    if changed:
        changes_made.append("Added C++17 compiler check")

    # Check 2: WX defines
    content, changed = add_wx_defines(content)
    if changed:
        changes_made.append("Added WX defines")

    # Check 3: Namespace
    content, changed = fix_namespace(content)
    if changed:
        changes_made.append("Fixed namespace (lunasvg -> wxlunasvg)")

    if content != original_content:
        if not dry_run:
            try:
                write_source_text(file_path, content, line_ending)
            except Exception as e:
                print(f"Error writing {file_path}: {e}", file=sys.stderr)
                return False

        for change in changes_made:
            tracker.add(str(file_path), change)
        return True

    return False


def process_cpp_file(file_path: Path, dry_run: bool, tracker: ChangeTracker) -> bool:
    """Process a C++ file to fix namespace."""
    try:
        content, line_ending = read_source_text(file_path)
    except Exception as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)
        return False

    new_content, changed = fix_namespace(content)

    if changed:
        if not dry_run:
            try:
                write_source_text(file_path, new_content, line_ending)
            except Exception as e:
                print(f"Error writing {file_path}: {e}", file=sys.stderr)
                return False

        tracker.add(str(file_path), "Fixed namespace (lunasvg -> wxlunasvg)")
        return True

    return False


def main():
    parser = argparse.ArgumentParser(
        description='Fix files after merging from upstream lunasvg repository.'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be changed without actually modifying files'
    )
    parser.add_argument(
        '--root',
        type=str,
        default='.',
        help='Root directory of the repository (default: current directory)'
    )

    args = parser.parse_args()

    root_dir = Path(args.root).resolve()

    if not root_dir.exists():
        print(f"Error: Root directory '{root_dir}' does not exist.", file=sys.stderr)
        return 1

    tracker = ChangeTracker()

    if args.dry_run:
        print("DRY RUN MODE - No files will be modified\n")

    # Process include/lunasvg.h
    lunasvg_header = root_dir / 'include' / 'lunasvg.h'
    if lunasvg_header.exists():
        print(f"Checking {lunasvg_header}...")
        process_lunasvg_header(lunasvg_header, args.dry_run, tracker)
    else:
        print(f"Warning: {lunasvg_header} not found.", file=sys.stderr)

    # Process all C++ files for namespace changes
    print("\nChecking C++ files for namespace...")
    cpp_files = find_cpp_files(root_dir)

    for cpp_file in cpp_files:
        # Skip the main header since we already processed it
        if cpp_file == lunasvg_header:
            continue

        # Get relative path for cleaner output
        try:
            rel_path = cpp_file.relative_to(root_dir)
        except ValueError:
            rel_path = cpp_file

        process_cpp_file(cpp_file, args.dry_run, tracker)

    # Print summary
    print()
    tracker.print_summary()

    return 0


if __name__ == '__main__':
    sys.exit(main())
