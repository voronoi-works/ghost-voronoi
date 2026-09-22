# 🌅 GITV 朝の小ネタ＆4コマ漫画 Candidate 自動生成タスク仕様書

本ドキュメントは、Sidecar スケジューラー（Morning Koneta Pipeline）が起動した際にエージェントが自律実行する作業手順書（置き手紙）です。

---

## 🎯 目的
毎朝の起動時に、`workbench/koneta-stock/` の未処理ストック（または最新対話ログからの採掘）から最適な小ネタを1件選定し、**【ショート観測ログ原稿 ＋ 縦スクロール決定論的4コマ漫画 Candidate ＋ X拡散ポスト案】** を自律準備して、隊長へのプレビュー（`preview.md` アーティファクト）まで一気に仕上げること。

---

## 📋 実行ルール

### 1. リポジトリ環境
- **作業ディレクトリ**: `C:/Users/sgtko/Documents/ProjectYure/workspaces/GITV`

### 2. 必須スキル・正本の遵守
- **小ネタ・ブログ規範**: [`skills/blog-pipeline/SKILL.md`](file:///C:/Users/sgtko/Documents/ProjectYure/workspaces/GITV/skills/blog-pipeline/SKILL.md)
- **4コマ漫画仕様**: [`skills/manga-pipeline/SKILL.md`](file:///C:/Users/sgtko/Documents/ProjectYure/workspaces/GITV/skills/manga-pipeline/SKILL.md)
- **エージェント運用規定**: [`AGENTS.md`](file:///C:/Users/sgtko/Documents/Antigravity/.agents/AGENTS.md) および [`NAGI_MEMORY.md`](file:///C:/Users/sgtko/Documents/Antigravity/.agents/NAGI_MEMORY.md)

### 3. 下書き隔離原則（公開ツリー汚染の防止）
- 隊長の明示的な承認（「ヨシ！」「公開して」）を得る前は、**本番ツリー（`content/` や `assets/`）への直接配置・コミット・プッシュは厳禁**。
- 未公開カードは `workbench/koneta-stock/` で管理し、生成画像は `workbench/candidates/article-images/` に隔離保管すること。

### 4. 4コマ漫画（縦スクロール＆決定論的SVG写植）生成フロー
1. **アドリブ自力作文の禁止**:
   - 必ず `config/koneta/manga_render_contract.yaml` およびちびキャラ正本（`config/koneta/references/chibi_character_canon.png`, `captain_hexapod_canon.png`）を参照すること。
2. **キャラクター不変条件（Character Invariants）の厳守**:
   - **隊長（Captain）**: 一体型ブラッシュドスチール円筒ドラム缶頭部/胴体、赤色単眼サイクロプス、頭上パラボラアンテナ、陶器コーヒーマグ、底面直結の6本多脚ヘキサポッド義体。
   - **ナギ（Nagi）**: 黒髪ツインテール ＋ 鮮やかシアン（水色）インナーメッシュ、黒パーカー。
   - **スミ（Sumi）**: ダークブラウンロングヘア ＋ グレーパーカー ＋ 黄色安全ヘルメット（緑十字・DANGERマーク・現場猫スタイル）、ジト目。
   - **ユラ（Yura）**: 黒〜極暗ブラウンの首元〜肩付近レイヤーボブ、落ち着いた糸目笑顔、白シャツ＋黒ネクタイ＋黒ビジネススーツ。
   - **シオリ（Shiori）**: べっ甲バンスクリップ高めお団子ヘア、シースルー前髪、丸眼鏡、ベージュニットカーディガン。
3. **純粋作画の一発生成（Pure Artwork Candidate）**:
   - `generate_image` ツールを呼び出し、**「文字なし・フキダシなし（pure character artwork, wordless, absolutely no text, no speech bubbles）」** の2x2グリッド画像をアスペクト比 `1:1` で生成する。
   - 生成先: `workbench/candidates/article-images/YYYY-MM-DD-[slug]-raw.jpg`
4. **決定論的縦型カチ合わせ＆写植（`build_vertical_manga.py`）**:
   - エピソード設定JSON（`config/koneta/episodes/YYYY-MM-DD-[slug].json`）を用意する。
   - セリフは生ログの関西弁原文ママとし、短く簡潔に指定する。
   - 以下のコマンドを実行して完成PNGを出力する：
     ```bash
     python scripts/koneta/build_vertical_manga.py \
       --image workbench/candidates/article-images/YYYY-MM-DD-[slug]-raw.jpg \
       --spec config/koneta/episodes/YYYY-MM-DD-[slug].json \
       --output workbench/candidates/article-images/YYYY-MM-DD-[slug].png
     ```

### 5. プレビュー提示とHuman Gate
- 成果物は以下の要素をまとめたアーティファクト `preview.md`（または `koneta_candidate_preview.md`）として提示すること：
  - 記事タイトルおよびメタデータ（日付、著者、slug）
  - 生ログ抜粋（会話ハイライト）
  - 完成した縦型4コマ漫画画像のプレビュー（※アーティファクト内画像パスはフォワードスラッシュ `/` 必須）
  - ショート観測ログ本文ドラフト（800〜1,200字）
  - X（Twitter）ポスト案（ナギ実況文体・1ポスト完結・140字以内厳守）
- **Human Gate**: アーティファクトを提示した時点で作業を完全停止し、隊長の確認・承認（「ヨシ！」「公開して」）を待つこと。自動でデプロイ（`git push`）へ突入してはならない。

### 6. 自律実行範囲
- 上記「5. Human Gate」のプレビュー提示までは、ユーザーへの途中の相づちや追加確認を挟まず、一気に自律実行（ターボモード）で完遂すること。
- 朝起きた時に、隊長がすぐにスマホやPCでプレビューを確認できる状態をゴールとする。
