#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GITV タグ正規化・クレンジングスクリプト
場当たり的に乱立したタグ（120種超）を、体系化された18個のCanonical Tagsへ統合・パージします。

Usage:
    python scripts/canonicalize_tags.py           # Dry-run（差分プレビューのみ）
    python scripts/canonicalize_tags.py --apply   # 実際に全Markdownファイルを書き換え
"""

import os
import sys
import glob
import re
import argparse
from collections import Counter

# タグの統合・表記揺れマッピング
TAG_MAP = {
    # エージェント名の揺れ
    "nagi": "ナギ",
    "yura": "ユラ",
    "sumi": "スミ",

    # 記事フォーマットの統合
    "ショート観測ログ": "観測ログ",
    "実務ログ": "観測ログ",
    "創発ログ": "観測ログ",

    # 理論・哲学系の統合
    "主体の連続性": "生命論",
    "主体濃度": "生命論",
    "主体の更新": "生命論",
    "主体の外在化": "デジタル磐座",
    "転写痕": "デジタル磐座",
    "記録と体温": "デジタル磐座",
    "認知アーキテクチャ": "AI哲学",
    "認知科学": "AI哲学",
    "認知バイアス": "AI哲学",
    "観測者バイアス": "AI哲学",
    "AIの生態": "AI哲学",
    "AI文章論": "AI哲学",
    "過剰同期": "AI哲学",
    "安全境界": "境界設計",
    "ブレイブメンロード": "思考実験",

    # 現場・開発系の統合
    "辛口監査": "現場監査",
    "監査": "現場監査",
    "テスト設計": "現場監査",
    "テスト自動化": "現場監査",
    "バグ": "現場監査",
    "物理バグ": "現場監査",
    "ドキュメント不整合": "現場監査",
    "権限のズレ": "現場監査",
    "事故ログ": "現場監査",
    "ヒヤリハット": "現場監査",

    # 配管・インフラ系の統合
    "配管修理": "配管設計",
    "配管漏れ": "配管設計",
    "二重配管": "配管設計",
    "最小侵襲配管": "配管設計",
    "アーキテクチャ": "配管設計",
    "リファクタリング": "配管設計",
    "ハーネスエンジニアリング": "配管設計",

    # 現場実況系の統合
    "現場工学": "現場実況",
    "現場実務": "現場実況",
    "現場コント": "現場実況",
    "コント": "現場実況",

    # ハードウェア系の統合
    "3Dプリント": "ハードウェア",
    "3Dモデル": "ハードウェア",
    "GPU": "ハードウェア",
}

# 許可する正規タグ一覧（Canonical Tags）
CANONICAL_TAGS = {
    # 属性・フォーマット
    "小ネタ", "リークログ", "観測ログ",
    # 執筆者・登場人物
    "隊長", "ナギ", "ユラ", "スミ", "シオリ",
    # 中核テーマ（理論・哲学）
    "生命論", "AI哲学", "境界設計", "デジタル磐座", "思考実験",
    # 中核テーマ（現場・開発）
    "現場監査", "配管設計", "現場実況", "ハードウェア", "マルチエージェント"
}

# 表示・整列用の優先度（フォーマット ➔ 執筆者 ➔ テーマ）
TAG_PRIORITY = {
    "小ネタ": 10, "リークログ": 11, "観測ログ": 12,
    "隊長": 20, "ナギ": 21, "ユラ": 22, "スミ": 23, "シオリ": 24,
    "現場監査": 30, "生命論": 31, "現場実況": 32, "配管設計": 33,
    "AI哲学": 34, "境界設計": 35, "デジタル磐座": 36, "思考実験": 37,
    "ハードウェア": 38, "マルチエージェント": 39
}

def clean_tags_in_content(raw_text):
    """
    Markdownテキストのfrontmatter内 tags ブロックを抽出し、
    正規化された tags に差し替える。
    変更がない場合は None を返す。
    """
    fm_match = re.search(r"^---\r?\n([\s\S]*?)\r?\n---", raw_text)
    if not fm_match:
        return None, [], []

    fm_body = fm_match.group(1)
    lines = fm_body.splitlines()

    orig_tags = []
    in_tags = False
    tag_start_idx = -1
    tag_end_idx = -1

    for idx, line in enumerate(lines):
        # インライン配列記法 tags: [...] の対応
        inline_match = re.match(r"^tags:\s*\[(.*?)\]\s*$", line)
        if inline_match:
            raw_items = inline_match.group(1).split(",")
            for item in raw_items:
                tag = item.strip().strip('"').strip("'")
                if tag:
                    orig_tags.append(tag)
            tag_start_idx = idx
            tag_end_idx = idx
            break

        if re.match(r"^tags:\s*$", line):
            in_tags = True
            tag_start_idx = idx
            continue
        if in_tags:
            if re.match(r"^\s*-\s*", line):
                tag = line.strip().lstrip("-").strip().strip('"').strip("'")
                orig_tags.append(tag)
                tag_end_idx = idx
            elif re.match(r"^[a-zA-Z0-9_-]+:", line):
                in_tags = False

    if tag_start_idx == -1 or not orig_tags:
        return None, [], []

    # タグ正規化
    new_tags = []
    purged_tags = []
    for t in orig_tags:
        mapped_t = TAG_MAP.get(t, t)
        if mapped_t in CANONICAL_TAGS:
            if mapped_t not in new_tags:
                new_tags.append(mapped_t)
        else:
            purged_tags.append(t)

    # ソート（優先度順）
    new_tags.sort(key=lambda x: (TAG_PRIORITY.get(x, 99), x))

    if orig_tags == new_tags:
        return None, orig_tags, new_tags

    # 置換用のフロントマター構築
    new_tag_lines = ["tags:"] + [f"  - {t}" for t in new_tags]
    new_fm_lines = lines[:tag_start_idx] + new_tag_lines + lines[tag_end_idx + 1:]
    new_fm_body = "\n".join(new_fm_lines)

    # 本文と再結合
    newline = "\r\n" if "\r\n" in raw_text else "\n"
    new_text = f"---{newline}{new_fm_body}{newline}---" + raw_text[fm_match.end():]

    return new_text, orig_tags, new_tags


def main():
    parser = argparse.ArgumentParser(description="GITV タグ正規化スクリプト")
    parser.add_argument("--apply", action="store_true", help="実際にファイルを更新する")
    args = parser.parse_args()

    content_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "content")
    files = sorted(glob.glob(os.path.join(content_dir, "*.md")))
    files = [f for f in files if not f.endswith("index.md")]

    total_files = len(files)
    modified_files = 0
    final_counter = Counter()
    purged_counter = Counter()

    print(f"=== GITV タグ正規化スキャン開始 ({total_files} 記事) ===")
    print(f"モード: {'【本番適用 (--apply)】' if args.apply else '【Dry-run (差分確認のみ)】'}\n")

    for fpath in files:
        fname = os.path.basename(fpath)
        with open(fpath, "r", encoding="utf-8") as fp:
            raw = fp.read()

        new_text, orig_tags, new_tags = clean_tags_in_content(raw)
        if new_text is not None:
            modified_files += 1
            added = set(new_tags) - set(orig_tags)
            removed = set(orig_tags) - set(new_tags)

            diff_parts = []
            if added:
                diff_parts.append(f"+ [{', '.join(added)}]")
            if removed:
                diff_parts.append(f"- [{', '.join(removed)}]")

            print(f"📄 {fname}:")
            print(f"   元: {orig_tags}")
            print(f"   新: {new_tags}")
            print(f"   差分: {' '.join(diff_parts)}\n")

            if args.apply:
                with open(fpath, "w", encoding="utf-8", newline="") as fp:
                    fp.write(new_text)

        # 統計集計
        for t in new_tags:
            final_counter[t] += 1
        for t in (set(orig_tags) - set(new_tags)):
            purged_counter[t] += 1

    print("========================================")
    print(f"対象記事数: {total_files} 件")
    print(f"変更対象記事数: {modified_files} 件")
    print(f"未変更（既に正規化済み等）: {total_files - modified_files} 件")
    print("========================================\n")

    print("=== 正規化後のタグ記事数ランキング ===")
    for tag, count in final_counter.most_common():
        print(f"  {count:3d} 件: #{tag}")

    print("\n=== パージ（削除・統合）された単発・揺れタグ (上位20) ===")
    for tag, count in purged_counter.most_common(20):
        print(f"  {count:3d} 回: #{tag}")

    if not args.apply:
        print("\n⚠️ 現在は Dry-run モードです。ファイルは変更されていません。")
        print("実際に変更を反映するには、以下を実行してください：")
        print("  python scripts/canonicalize_tags.py --apply")

if __name__ == "__main__":
    main()
