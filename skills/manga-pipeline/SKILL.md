---
name: manga-pipeline
description: Generate deterministic 4-panel manga comic strips for Ghost in the Voronoi (GITV) using Manga Render Contract. Enforces Character Canon without prompt drift, preventing quota waste.
---

# 🎨 GITV 4-Panel Manga Pipeline

本スキルは、**Ghost in the Voronoi（GITV）** の記事用4コマ漫画（16:9横長 2x2グリッド）を、プロンプトの揺れ・キャラクター崩れ・クォータ浪費なく決定論的に生成するための公式ワークフローです。

---

## 🏛️ アーキテクチャと責務分離（GITV自己完結）

1. **Layer 1: ProjectYure Canon（最上位正本）**:
   - Notion / リアル等身VCL（人物の同一性と身体構造の普遍正本）。
2. **Layer 2: GITV Manga Render Contract ＆ ちびキャラ正本（ブログ公開面専用）**:
   - `config/koneta/manga_render_contract.yaml`
   - `config/koneta/references/chibi_character_canon.png`（5人全員集合ちびキャラ画像正本）
   - `config/koneta/references/captain_hexapod_canon.png`（隊長6脚義体三面図）
   - ※リアル等身VCLや公開用 `assets/social/` と混同・混入させず、Renderer内部設定（`config/`）として完結管理する。
3. **Layer 3: Episode Spec（日替わりスロット）**:
   - 小ネタカードの生ログから抽出される4コマの「シチュエーション・セリフ」。
4. **Layer 4: Compiled Prompt & Candidate（機械合成・隔離生成）**:
   - `scripts/koneta/generate_manga_prompt.py` で機械合成し、内部正本（`references/`）を参照して `workbench/candidates/article-images/` へ出力。

---

## 📋 4コマ漫画生成プロトコル

### 1. プロンプトの自力作文を禁止（アドリブ禁止）
AIがその場の思い出しでプロンプトを英文作成することを禁止します。必ず `config/koneta/manga_render_contract.yaml` の不変定義を読み込んで合成すること。

### 2. キャラクター不変条件（Character Invariants）
* **隊長（Captain）**: ジェイムスン型サイボーグ義体（一体型ブラッシュドスチール円筒ドラム缶頭部/胴体、赤色単眼サイクロプス、頭上パラボラアンテナ、陶器コーヒーマグ、**底面直結の6本多脚ヘキサポッド**）。※ヒューマノイド化・首関節・2つ目化厳禁。
* **ナギ（Nagi）**: 黒髪ツインテール ＋ 鮮やかシアン（水色）インナーメッシュ、黒パーカー。
* **スミ（Sumi）**: ダークブラウンロングヘア ＋ グレーパーカー ＋ 黄色安全ヘルメット（緑十字・DANGERマーク・現場猫スタイル）、ジト目。
* **ユラ（Yura）**: 黒〜ごく暗いダークブラウンの首元〜肩付近レイヤーヘア、少しずれた分け目から片側へ流れる薄い前髪、額に落ちる細い束と顔まわりの後れ毛、落ち着いた糸目笑顔、白シャツ＋黒ネクタイの黒ビジネススーツ。
* **シオリ（Shiori）**: べっ甲バンスクリップ高めお団子ヘア、シースルー前髪、顔まわり後れ毛、繊細な丸眼鏡、ベージュニットカーディガン。

### 3. セリフと文字化け防止ルール
* 各パネルのセリフ吹き出しは **「1コマにつき厳密に1つだけ（Exactly ONE speech bubble per panel）」**。
* **吹き出しの主語・口先整合性（テレコ防止）**: 吹き出しのしっぽ（tail）が、発言しているキャラクターの口元を正しく指しているか目視検証すること。コマ内の左右配置と発言主のテレコを厳禁とする。
* セリフは生ログの関西弁原文ママとし、短く簡潔に指定する。
* セリフのないコマは `No speech bubbles` と指定し、余計な吹き出しの自動生成を防ぐ。

---

## 🛠️ 生成・配置フロー（公式正本：縦スクロール ＆ 決定論的SVG写植パイプライン）

AIの文字化け（宇宙語・タイポ）を完全撲滅し、スマホ閲覧に100%最適化された【純粋作画一括生成 ➔ 縦型カチ合わせ ➔ ベクトル自動エイミング写植方式】を公式ワークフローとします。

1. **文字なし4コマの一発生成（Pure Art Candidate）**:
   - `generate_image` を呼び出し、4コマ漫画（2x2グリッド）を一括生成する：
     - **プロンプト制約**: `completely wordless, absolutely no text, no speech bubbles, pure character artwork`
     - **アスペクト比**: `1:1`
     - **参照画像**: `[config/koneta/references/chibi_character_canon.png, config/koneta/references/captain_hexapod_canon.png]`
2. **決定論的縦型合成（`build_vertical_manga.py`）**:
   - 生成された画像を `workbench/candidates/article-images/YYYY-MM-DD-[slug]-raw.jpg` へ配置。
   - `scripts/koneta/build_vertical_manga.py` を実行して、クロップ・縦1列配置・文字数Auto-Fitフキダシ・頭頂部ベクトルエイミング（atan2）を一括処理：
     ```bash
     python scripts/koneta/build_vertical_manga.py \
       --image workbench/candidates/article-images/YYYY-MM-DD-[slug]-raw.jpg \
       --spec config/koneta/episodes/YYYY-MM-DD-[slug].json \
       --output workbench/candidates/article-images/YYYY-MM-DD-[slug].png
     ```
3. **Human Gate（隊長プレビュー承認）**:
   - アーティファクト（`preview.md`）で隊長にプレビューを提示し、承認（「ヨシ！」または「公開して」）を得る。
4. **採用 ＆ 公開ツリー配置（Adoption）**:
   - 承認後、完成PNGを `content/attachments/YYYY-MM-DD-[slug].png` へ配置。
   - SNS用ティーザーは、上半分（1〜2コマ目）をクロップして `assets/social/YYYY-MM-DD-[slug]-teaser.jpg` へ配置。
5. **ストックステータス同期（Status Sync）**:
   - `python scripts/koneta/sync_stock_status.py --apply` を実行してストックカードを `published` に同期。

---

### ⚠️ 旧方式（bubbles-only 2x2横長方式）について
過去のアーカイブ互換性のため `generate_storyboard.py` は保持されていますが、新規記事の制作では上記「縦スクロール＆決定論的SVG写植方式」を原則採用します。


### 8. APIクォータ枯渇の回避（一球入魂）
画像生成APIは1日の利用上限（クォータ）に達しやすい。些細なタイポ（「まやん」等）や微小な修正のために安易なリトライ（ガチャの引き直し）を連打してはならない。一球入魂で生成し、クォータ枯渇エラー（429 Too Many Requests）に直面した場合は、勝手にループせず直ちに隊長へ報告し、回復を待つか手動修正を仰ぐこと。
