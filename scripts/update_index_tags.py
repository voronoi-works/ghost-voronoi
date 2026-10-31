#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GITV トップページ (content/index.md) の主要テーマ自動更新スクリプト
全記事のタグを集計し、理論・現場の2レーンに分けて記事数つきで自動注入します。
"""

import os
import glob
import re
from collections import Counter

# タグの説明辞書（レキシコン）
TAG_DESCRIPTIONS = {
    # 🏛️ 理論・哲学系
    "生命論": "「生命とは揺れが自己保存を始めた状態」境界の維持と自己保存",
    "AI哲学": "人間とAIの共生、意識・魂・知性の3軸",
    "境界設計": "ジーンとデニム、内外を分ける膜と合意の作法",
    "デジタル磐座": "物理世界とデジタル空間の依代・アンカー",
    "思考実験": "境界線の極限を問う現場の対話",

    # 🔧 現場・開発系
    "現場監査": "スミの冷徹監査、幽霊プロトコルへのツッコミと穴塞ぎ",
    "現場実況": "積層痕とハンダ付け、泥臭い試行錯誤のリアルログ",
    "配管設計": "暴走を防ぎ知性を編むアーキテクチャとパイプ",
    "ハードウェア": "3Dプリント、造形、物理デバイスとの接続",
    "マルチエージェント": "自律協働構造体、複数AIの役割分担と調停",
}

# レーン分類
THEORY_TAGS = {"生命論", "AI哲学", "境界設計", "デジタル磐座", "思考実験"}
ENGINEERING_TAGS = {"現場監査", "現場実況", "配管設計", "ハードウェア", "マルチエージェント"}

# 除外タグ（著者名、記事形式）
IGNORE_TAGS = {
    "隊長", "ナギ", "ユラ", "スミ", "シオリ", "nagi", "yura", "sumi",
    "小ネタ", "リークログ", "観測ログ", "ショート観測ログ", "実務ログ", "創発ログ"
}

def update_index_tags():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    content_dir = os.path.join(base_dir, "content")
    index_path = os.path.join(content_dir, "index.md")

    files = glob.glob(os.path.join(content_dir, "*.md"))
    files = [f for f in files if not f.endswith("index.md")]

    tag_counts = Counter()
    for fpath in files:
        with open(fpath, "r", encoding="utf-8") as fp:
            text = fp.read()
        fm = re.search(r"^---\r?\n([\s\S]*?)\r?\n---", text)
        if not fm:
            continue
        in_tags = False
        for line in fm.group(1).splitlines():
            if re.match(r"^tags:\s*$", line):
                in_tags = True
                continue
            if in_tags:
                if re.match(r"^\s*-\s*", line):
                    t = line.strip().lstrip("-").strip().strip('"').strip("'")
                    if t and t not in IGNORE_TAGS:
                        tag_counts[t] += 1
                elif re.match(r"^[a-zA-Z0-9_-]+:", line):
                    in_tags = False

    # 理論系と現場系に分類して集計
    theory_list = []
    eng_list = []
    other_list = []

    for tag, count in tag_counts.most_common():
        desc = TAG_DESCRIPTIONS.get(tag, "")
        desc_str = f" —— {desc}" if desc else ""
        item_md = f"* [[tags/{tag}|#{tag}]] ({count}){desc_str}"

        if tag in THEORY_TAGS:
            theory_list.append(item_md)
        elif tag in ENGINEERING_TAGS:
            eng_list.append(item_md)
        else:
            other_list.append(item_md)

    # 注入するMarkdownブロックを構築
    output_lines = [
        "<!-- TAGS_AUTO_START -->",
        "### 🏛️ 揺れ理論・AI哲学",
        *theory_list,
        "",
        "### 🔧 現場工学・アーキテクチャ",
        *eng_list,
    ]
    if other_list:
        output_lines.extend(["", "### 📌 その他のトピック", *other_list])

    output_lines.extend([
        "",
        "👉 [[tags/|🏷️ すべてのタグ一覧を見る]]",
        "<!-- TAGS_AUTO_END -->"
    ])
    auto_block = "\n".join(output_lines)

    # index.md の読み込みと置換
    with open(index_path, "r", encoding="utf-8") as fp:
        index_content = fp.read()

    # マーカーが存在するか確認
    if "<!-- TAGS_AUTO_START -->" in index_content and "<!-- TAGS_AUTO_END -->" in index_content:
        pattern = r"<!-- TAGS_AUTO_START -->[\s\S]*?<!-- TAGS_AUTO_END -->"
        new_content = re.sub(pattern, auto_block, index_content)
    elif "## 🏷️ 主要テーマ（キーワードから探す）" in index_content or "## 🏷 主要テーマ（キーワードから探す）" in index_content:
        # 既存の見出しの下にマーカーごと挿入
        pattern = r"(## 🏷[️]? 主要テーマ（キーワードから探す）\r?\n\r?\n)([\s\S]*?)(\r?\n---)"
        new_content = re.sub(pattern, r"\1" + auto_block + r"\3", index_content)
    else:
        print("Error: '主要テーマ' section not found in index.md")
        return False

    with open(index_path, "w", encoding="utf-8", newline="") as fp:
        fp.write(new_content)

    print("✅ content/index.md の主要テーマを自動更新しました！")
    return True

if __name__ == "__main__":
    update_index_tags()
