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

# CI-identical Regexes (from scripts/verify-build.mjs Section 7)
# 1. Bold asterisks outside brackets: **「, **『, **【, or 」**, 』**, 】**
RE_BOLD_OUTSIDE_BRACKETS = re.compile(r"\*\*+[「『【]|(?:[」』】])\*\*+")

# 2. Closing asterisks right after punctuation/bracket touching non-whitespace/non-bracket text
RE_CLOSING_AFTER_PUNCT = re.compile(r"[）)！!？?…・]\*\*+[^\s\n$」』】）)（(]")

# Auto-Fix Regexes
# A. Swap brackets outside bold: **「 -> 「**, 」** -> **」, etc.
RE_FIX_OPEN_BRACKETS = re.compile(r"(\*\*+)([「『【])")
RE_FIX_CLOSE_BRACKETS = re.compile(r"([」』】])(\*\*+)")

# B. Move full round bracket inside bold: **（text）** -> （**text**）
RE_FIX_FULL_PAREN_BOLD = re.compile(r"\*\*+([（(][^）)\n]+[）)])\*\*+")

# C. Move punctuation/round bracket outside closing bold (solving Right-Flanking without spaces!)
# e.g. **最高！**でした -> **最高**！でした
# e.g. **GPFG（年金）**でした -> **GPFG**（年金）でした
RE_FIX_PUNCT_BEFORE_CLOSE = re.compile(r"([）)！!？?…・])\*\*+([^\s\n$」』】）)（(])")


def auto_fix_markdown(content: str) -> tuple[str, list[str]]:
    """
    Automatically fixes bracket and bold syntax:
    1. Swaps brackets outside bold: **「 -> 「**, 」** -> **」
    2. Moves full parentheses inside bold: **（注）** -> （**注**）
    3. Moves punctuation/closing parenthesis outside closing bold: **最高！**でした -> **最高**！でした
    """
    logs = []

    # 1. Brackets outside bold
    def replace_open(m):
        asterisks, bracket = m.group(1), m.group(2)
        logs.append(f"Move bracket outside open bold: '{asterisks}{bracket}' -> '{bracket}{asterisks}'")
        return bracket + asterisks

    def replace_close(m):
        bracket, asterisks = m.group(1), m.group(2)
        logs.append(f"Move bracket outside close bold: '{bracket}{asterisks}' -> '{asterisks}{bracket}'")
        return asterisks + bracket

    content = RE_FIX_OPEN_BRACKETS.sub(replace_open, content)
    content = RE_FIX_CLOSE_BRACKETS.sub(replace_close, content)

    # 2. Entire parentheses wrapped in bold: **（注釈）** -> （**注釈**）
    def replace_full_paren(m):
        paren_text = m.group(1)
        open_char, inner_text, close_char = paren_text[0], paren_text[1:-1], paren_text[-1]
        fixed = f"{open_char}**{inner_text}**{close_char}"
        logs.append(f"Push parentheses outside bold: '**{paren_text}**' -> '{fixed}'")
        return fixed

    content = RE_FIX_FULL_PAREN_BOLD.sub(replace_full_paren, content)

    # 3. Punctuation touching following text: **最高！**でした -> **最高**！でした
    def replace_punct_touching(m):
        punct, following_char = m.group(1), m.group(2)
        logs.append(f"Move punctuation outside close bold: '{punct}**{following_char}' -> '**{punct}{following_char}'")
        return f"**{punct}{following_char}"

    content = RE_FIX_PUNCT_BEFORE_CLOSE.sub(replace_punct_touching, content)

    return content, logs


def check_content(content: str, rel_path: str) -> list[dict]:
    """Scans content for seawall leaks and markdown syntax issues."""
    issues = []
    lines = content.splitlines()

    for line_idx, line in enumerate(lines, 1):
        # 1. Seawall keyword check
        for kw in SEAWALL_KEYWORDS:
            if kw in line:
                issues.append({
                    "type": "seawall",
                    "line": line_idx,
                    "text": line.strip(),
                    "msg": f"FAIL [Seawall Leak]: contains forbidden term '{kw}'"
                })

        # 2. Bracket and bold syntax integrity check
        if RE_BOLD_OUTSIDE_BRACKETS.search(line):
            issues.append({
                "type": "bracket_bold",
                "line": line_idx,
                "text": line.strip(),
                "msg": "FAIL [Bold Outside Bracket]: bold asterisks outside brackets"
            })

        if RE_CLOSING_AFTER_PUNCT.search(line):
            issues.append({
                "type": "flanking_punct",
                "line": line_idx,
                "text": line.strip(),
                "msg": "FAIL [Flanking Punctuation]: closing asterisks right after punctuation/bracket touching text"
            })

    return issues


def verify_files(target_paths=None, fix_mode=False):
    failures = []
    checked_count = 0
    fixed_files_count = 0
    total_fixes = 0

    if not target_paths:
        if not CONTENT_DIR.exists():
            print(f"Error: Content directory not found: {CONTENT_DIR}")
            sys.exit(1)
        md_files = sorted(list(CONTENT_DIR.rglob("*.md")))
        mode_title = "Pre-Push Content Scan" + (" [AUTO-FIX]" if fix_mode else "")
    else:
        md_files = []
        for p_str in target_paths:
            p = Path(p_str).resolve()
            if not p.exists():
                failures.append(f"Target path does not exist: {p}")
                continue
            if p.is_file():
                md_files.append(p)
            elif p.is_dir():
                md_files.extend(sorted(list(p.rglob("*.md"))))
        mode_title = "Targeted Scan" + (" [AUTO-FIX]" if fix_mode else "")

    print("===================================================")
    print(f"  🛡️ GITV Markdown & Seawall Verification ({mode_title})")
    print("===================================================")

    for md_path in md_files:
        try:
            rel_path = md_path.relative_to(GITV_ROOT)
        except ValueError:
            rel_path = md_path
        checked_count += 1
        try:
            content = md_path.read_text(encoding="utf-8")
        except Exception as e:
            failures.append(f"{rel_path}: Failed to read file: {e}")
            continue

        # Step 1: Scan for issues first
        issues = check_content(content, str(rel_path))

        # Step 2: If syntax issues exist and fix_mode is enabled, fix them
        syntax_issues = [i for i in issues if i["type"] in ("bracket_bold", "flanking_punct")]
        if fix_mode and syntax_issues:
            fixed_content, logs = auto_fix_markdown(content)
            if logs:
                try:
                    md_path.write_text(fixed_content, encoding="utf-8")
                    content = fixed_content
                    fixed_files_count += 1
                    total_fixes += len(logs)
                    print(f"  🔧 AUTO-FIXED {len(logs)} syntax issue(s) in: {rel_path}")
                    for log in logs[:5]:
                        print(f"     • {log}")
                    if len(logs) > 5:
                        print(f"     • ...and {len(logs) - 5} more")

                    # Step 3: Re-check after fix to verify 0 errors
                    issues = check_content(fixed_content, str(rel_path))
                    syntax_left = [i for i in issues if i["type"] in ("bracket_bold", "flanking_punct")]
                    if not syntax_left:
                        print(f"     ✅ Re-check: Syntax 100% CLEAN (0 errors left)")
                except Exception as e:
                    failures.append(f"{rel_path}: Failed to write fixed content: {e}")

        # Step 4: Record remaining issues (e.g. seawall leaks)
        for iss in issues:
            failures.append(f"{rel_path}:L{iss['line']} {iss['msg']}: {iss['text']}")

    print(f"\nScanned {checked_count} file(s)." + (f" (Auto-fixed {total_fixes} issues across {fixed_files_count} files)" if fix_mode else ""))

    if failures:
        print("\n❌ VERIFICATION FAILED!")
        print(f"Found {len(failures)} error(s):")
        for f in failures:
            print(f"  • {f}")
        print("\nPlease fix the syntax / seawall errors above.")
        return False
    else:
        print("\n✅ ALL CHECKS PASSED SUCCESSFULLY! (No syntax or seawall errors found)")
        return True


if __name__ == "__main__":
    args = sys.argv[1:]
    fix = "--fix" in args
    filtered_args = [a for a in args if a != "--fix"]
    targets = filtered_args if filtered_args else None
    success = verify_files(targets, fix_mode=fix)
    sys.exit(0 if success else 1)
