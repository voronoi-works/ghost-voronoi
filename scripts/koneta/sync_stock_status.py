"""Sync lifecycle status between content/ articles, workbench/candidates/, and koneta-stock/ cards.

Matches cards in workbench/koneta-stock/ against:
1. Published articles in content/ -> 'status: published'
2. Generated candidate images in workbench/candidates/article-images/ -> 'status: candidate_ready'
3. Unprocessed stock -> 'status: pending'

Enforces monotonic progression: pending -> candidate_ready -> published.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

# Windows UTF-8 stdout
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

SCRIPT_DIR = Path(__file__).parent.resolve()
GITV_ROOT = SCRIPT_DIR.parent.parent
CONTENT_DIR = GITV_ROOT / "content"
STOCK_DIR = GITV_ROOT / "workbench" / "koneta-stock"
CANDIDATES_DIR = GITV_ROOT / "workbench" / "candidates" / "article-images"

# Non-final / intermediate / debug artifact patterns to ignore
IGNORED_CANDIDATE_PATTERNS = {
    "-raw",
    "-teaser",
    "debug_",
    "sample_",
    "oauth_",
    "bubbles_only",
}


def load_published_articles(content_dir: Path) -> list[dict[str, str]]:
    """Load published article info from content/ directory."""
    articles = []
    if not content_dir.exists():
        return articles

    for md_file in sorted(content_dir.glob("*.md")):
        if md_file.name in {"index.md", "llms.txt"}:
            continue
        text = md_file.read_text(encoding="utf-8", errors="replace")
        slug_match = re.search(r"^slug:\s*(.*)$", text, re.M)
        title_match = re.search(r"^title:\s*[\"']?(.*?)[\"']?$", text, re.M)
        date_match = re.search(r"^date:\s*(.*)$", text, re.M)

        slug = slug_match.group(1).strip() if slug_match else md_file.stem
        title = title_match.group(1).strip() if title_match else ""
        date = date_match.group(1).strip() if date_match else ""

        articles.append({
            "path": md_file,
            "stem": md_file.stem,
            "slug": slug,
            "title": title,
            "date": date,
        })
    return articles


def load_candidate_images(candidates_dir: Path) -> list[dict[str, str]]:
    """Load final-quality candidate images from workbench/candidates/article-images/."""
    candidates = []
    if not candidates_dir.exists():
        return candidates

    for img_file in sorted(candidates_dir.glob("*.*")):
        if img_file.is_dir():
            continue
        ext = img_file.suffix.lower()
        if ext not in {".png", ".jpg", ".jpeg"}:
            continue

        stem = img_file.stem
        if any(ign in stem for ign in IGNORED_CANDIDATE_PATTERNS):
            continue

        candidates.append({
            "path": img_file,
            "stem": stem,
            "rel_path": img_file.relative_to(GITV_ROOT).as_posix(),
        })
    return candidates


def match_card_to_items(card_path: Path, card_meta: dict[str, str], items: list[dict[str, str]]) -> dict[str, str] | None:
    """Determine if a stock card matches any target item (article or candidate)."""
    card_stem = card_path.stem
    card_title = card_meta.get("title", "").strip()
    card_slug = card_meta.get("slug", "").strip()

    card_keywords = [
        w for w in re.split(r"[-_]", card_stem)
        if len(w) >= 3 and not re.match(r"^\d{4}$|^\d{2}$", w) and w not in {"nagi", "yura", "sumi", "shiori", "mined", "cross"}
    ]

    for item in items:
        item_stem = item.get("stem", "")
        item_slug = item.get("slug", item_stem)
        item_title = item.get("title", "")

        if card_stem == item_stem or card_slug == item_slug or card_stem == item_slug or card_slug == item_stem:
            return item

        if card_stem in item_stem or item_stem in card_stem:
            return item

        if card_title and item_title:
            if card_title == item_title or card_title in item_title or item_title in card_title:
                return item

        if card_keywords:
            matches_count = sum(1 for kw in card_keywords if kw in item_stem or kw in item_slug)
            if matches_count >= 3:
                return item

    return None


def parse_card_frontmatter(card_text: str) -> dict[str, str]:
    meta = {}
    lines = card_text.splitlines()
    in_fm = False
    fc = 0
    for line in lines:
        stripped = line.strip()
        if stripped == "---":
            fc += 1
            if fc == 1:
                in_fm = True
                continue
            elif fc == 2:
                break
        if in_fm and ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip("'\"")
    return meta


def sync_stock_status(apply: bool = False, lane: str = "all") -> tuple[int, int, int, int]:
    articles = load_published_articles(CONTENT_DIR)
    candidates = load_candidate_images(CANDIDATES_DIR)
    cards = sorted(STOCK_DIR.glob("*.md"))

    print("===================================================")
    print("  📦 Koneta Stock 3-State Lifecycle Synchronizer")
    print("===================================================")
    print(f"Content Directory:    {CONTENT_DIR} ({len(articles)} published articles)")
    print(f"Candidates Directory: {CANDIDATES_DIR} ({len(candidates)} candidate images)")
    print(f"Stock Directory:      {STOCK_DIR} ({len(cards)} cards)")
    print(f"Mode:                 {'APPLY (changes will be written)' if apply else 'CHECK (dry-run)'}")
    print(f"Filter Lane:          {lane}")
    print()

    updated_count = 0
    published_count = 0
    candidate_ready_count = 0
    pending_count = 0

    updates_to_perform = []

    for card in cards:
        if card.name.lower() == "readme.md":
            continue

        text = card.read_text(encoding="utf-8-sig", errors="replace")
        meta = parse_card_frontmatter(text)
        current_status = meta.get("status", "pending").lower().strip()
        agent = meta.get("agent", "unknown")
        title = meta.get("title", card.stem)

        matched_art = match_card_to_items(card, meta, articles)
        matched_cand = match_card_to_items(card, meta, candidates)

        # Monotonic State Evaluation: published > candidate_ready > pending
        target_status = "pending"
        evidence_note = ""

        if matched_art:
            target_status = "published"
            evidence_note = f"Article: content/{matched_art['path'].name} ('{matched_art['title'][:30]}')"
        elif matched_cand:
            target_status = "candidate_ready"
            evidence_note = f"Candidate: {matched_cand['rel_path']}"
        else:
            target_status = "pending"
            evidence_note = "No published article or candidate image found"

        # Check for state changes or anomalies
        if current_status != target_status:
            # Prevent silent demotion from candidate_ready to pending unless explicitly forced
            if current_status == "candidate_ready" and target_status == "pending":
                print(f"[DIAGNOSTIC: Candidate Missing] {card.name}")
                print(f"  • Current: {current_status}, Target: {target_status}")
                print("  • Note: Retaining candidate_ready without demoting automatically.")
                candidate_ready_count += 1
                continue

            # Prevent demotion from published
            if current_status == "published":
                print(f"[DIAGNOSTIC: Published Retained] {card.name}")
                published_count += 1
                continue

            print(f"[UPDATE NEEDED] {card.name}")
            print(f"  • Current status:   {current_status}")
            print(f"  • Target status:    {target_status}")
            print(f"  • Evidence:         {evidence_note}")

            if apply:
                new_text = re.sub(r"(?m)^status:\s*[^\r\n]+", f"status: {target_status}", text, count=1)
                if new_text != text:
                    card.write_text(new_text, encoding="utf-8")
                    print("  -> Status updated successfully! [OK]")
                else:
                    print("  -> Failed to replace status line regex [ERROR]")

            updated_count += 1
            if target_status == "published":
                published_count += 1
            elif target_status == "candidate_ready":
                candidate_ready_count += 1
            else:
                pending_count += 1
        else:
            if current_status == "published":
                published_count += 1
            elif current_status == "candidate_ready":
                candidate_ready_count += 1
            else:
                pending_count += 1

    print("\n===================================================")
    print(f"  📊 Summary:")
    print(f"     • Updated:         {updated_count}")
    print(f"     • Published:       {published_count}")
    print(f"     • Candidate Ready: {candidate_ready_count} (WIP / Ready for Review)")
    print(f"     • Pending Active:  {pending_count} (Unprocessed Fresh Stock)")
    print("===================================================")
    return updated_count, published_count, candidate_ready_count, pending_count


def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronize 3-state lifecycle from content/ and candidates/ to koneta-stock/ cards")
    parser.add_argument("--apply", action="store_true", help="Apply status changes to stock card files")
    parser.add_argument("--lane", choices=["all", "new", "review", "published"], default="all", help="Filter display lane")
    args = parser.parse_args()

    updated, _, _, _ = sync_stock_status(apply=args.apply, lane=args.lane)
    if not args.apply and updated > 0:
        print("\nRun with '--apply' to write these status changes to stock cards.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

