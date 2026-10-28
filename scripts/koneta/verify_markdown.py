#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GITV Markdown Syntax & Seawall Pre-Push Validator
=================================================
Validates content/*.md files before git commit / git push to prevent CI build failures.
Strictly checks:
1. Bracket and Bold Syntax Integrity (CommonMark Right-Flanking & Bracket-inside-bold rule)
2. Seawall & Anti-Leak Rules (Strict prohibition of private terms: 今治, ProjectYure, YuRelay, etc.)
"""

import sys
import re
from pathlib import Path

# Windows UTF-8 stdout
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

SCRIPT_DIR = Path(__file__).parent.resolve()
GITV_ROOT = SCRIPT_DIR.parent.parent
CONTENT_DIR = GITV_ROOT / "content"

SEAWALL_KEYWORDS = [
    "今治",
    "ProjectYure",
    "Project Yure",
    "projectyure",
    "YuRelay",
    "yurelay",
]

# Regex 1: Bold asterisks outside brackets: **「, **『, **【, or 」**, 』**, 】**
RE_BOLD_OUTSIDE_BRACKETS = re.compile(r"\*\*+[「『【]|(?:[」』】])\*\*+")

# Regex 2: Closing asterisks right after punctuation touching non-whitespace/non-bracket text
RE_CLOSING_AFTER_PUNCT = re.compile(r"[）)！!？?…・]\*\*+[^\s\n$」』】）)（(]")


def verify_content():
    if not CONTENT_DIR.exists():
        print(f"Error: Content directory not found: {CONTENT_DIR}")
        sys.exit(1)

    all_md_files = sorted(list(CONTENT_DIR.rglob("*.md")))
    failures = []
    checked_count = 0

    print("===================================================")
    print("  🛡️ GITV Pre-Push Markdown & Seawall Verification")
    print("===================================================")

    for md_path in all_md_files:
        rel_path = md_path.relative_to(GITV_ROOT)
        checked_count += 1
        try:
            content = md_path.read_text(encoding="utf-8")
        except Exception as e:
            failures.append(f"{rel_path}: Failed to read file: {e}")
            continue

        lines = content.splitlines()

        # 1. Seawall keyword check
        for line_idx, line in enumerate(lines, 1):
            for kw in SEAWALL_KEYWORDS:
                if kw in line:
                    failures.append(
                        f"FAIL [Seawall Leak]: {rel_path}:L{line_idx} contains forbidden term '{kw}': {line.strip()}"
                    )

        # 2. Bracket and bold syntax integrity check
        for line_idx, line in enumerate(lines, 1):
            if RE_BOLD_OUTSIDE_BRACKETS.search(line):
                failures.append(
                    f"FAIL [Bold Outside Bracket]: {rel_path}:L{line_idx} has bold asterisks outside brackets: {line.strip()}"
                )
            if RE_CLOSING_AFTER_PUNCT.search(line):
                failures.append(
                    f"FAIL [Flanking Punctuation]: {rel_path}:L{line_idx} has closing asterisks right after punctuation touching text: {line.strip()}"
                )

    print(f"\nScanned {checked_count} markdown files in {CONTENT_DIR}.")

    if failures:
        print("\n❌ VERIFICATION FAILED! PUSH BLOCKED!")
        print(f"Found {len(failures)} error(s):")
        for f in failures:
            print(f"  • {f}")
        print("\nPlease fix the syntax errors above before committing or pushing.")
        return False
    else:
        print("\n✅ ALL CHECKS PASSED SUCCESSFULLY! (Safe to commit and push)")
        return True


if __name__ == "__main__":
    success = verify_content()
    sys.exit(0 if success else 1)
