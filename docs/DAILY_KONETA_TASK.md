# 🌅 GITV 朝の小ネタ＆4コマ漫画 Candidate 自動生成タスク仕様書

本ドキュメントは、Sidecar スケジューラー（Morning Koneta Pipeline）が起動した際にエージェントが自律実行する作業手順書（置き手紙）です。

---

## 🎯 目的
毎朝の起動時に、`workbench/koneta-stock/` の未処理ストック（または最新対話ログからの採掘）から最適なネタを1件選定し、**【X即放流セット（縦スクロール4コマ漫画 ＋ URLなしナギツッコミ140字） ＋ Threads用ミニコラム案（約350〜400字・画像なしプレーンテキスト・担当エージェント絵文字必須） ＋ 記事展開ドラフト（note用実務・怪異 または GITV用理論・構造）】** を自律準備して、隊長へのプレビュー（`preview.md` アーティファクト）まで一気に仕上げること。

---

## 📋 実行ルール

### 1. リポジトリ環境
- **作業ディレクトリ**: `C:/Users/sgtko/Documents/ProjectYure/workspaces/GITV`

### 2. 必須スキル・正本の遵守
- **メディア展開方針正本**: [`shared/media-operations/POLICY.md`](file:///C:/Users/sgtko/Documents/ProjectYure/shared/media-operations/POLICY.md)
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
   - ⚠️ **必須**: `ImagePaths` 引数に必ず正本画像2枚の絶対パスを指定すること（指定しないとアンテナ抜けや口パーツ出現などの作画崩れ・ハルシネーションが発生する）：
     - `config/koneta/references/chibi_character_canon.png`
     - `config/koneta/references/captain_hexapod_canon.png`
   - 生成先: `workbench/candidates/article-images/YYYY-MM-DD-[slug]-raw.jpg`
4. **決定論的縦型カチ合わせ＆写植（`build_vertical_manga.py`）**:
   - エピソード設定JSON（`config/koneta/episodes/YYYY-MM-DD-[slug].json`）を用意する。
   - セリフは生ログの関西弁原文ママとし、短く簡潔に指定する。
    - **📱 スマホ視認性・デカ文字黄金規格（豆粒フォント完全根絶）**:
      - **標準フォントサイズ**: **24px**（line_height: 35〜36px）。強調・叫びコマは **26〜28px**。
      - **最低保証ガード（Floor）**: **22px**（22px未満への縮小は絶対禁止。レンダラー側でも22px未満は自動強制引き上げ）。
      - **セリフのダイエット原則**: 「文字が入らないからフォントを小さくする」のは本末転倒。フォント24pxをドカンと維持するため、セリフを1行8〜10文字以内、最大2行（合計20文字以内）の漫才のパンチラインに削ぎ落とすこと。
   - **吹き出し配置と尻尾（Tail）エイミング黄金律（真下落ち根絶プロトコル）**:
     - 左話者（ナギ、ユラ、スミ等）: `tail_side: "left"`, `bubble_x: 230〜260`, `target_x: 110〜140`（斜め左下へ向ける）
     - 右話者（隊長等）: `tail_side: "right"`, `bubble_x: 100〜130`, `target_x: 520〜550`（斜め右下へ向ける）
     - ※キャラクターの真上にフキダシを置いて尻尾が真下に潰れる（垂直化する）のを絶対に防ぐこと。
   - 以下のコマンドを実行して完成PNGを出力する（1:1 Raw画像には `--layout 1x3` を指定）：
     ```bash
     python scripts/koneta/build_vertical_manga.py \
       --image workbench/candidates/article-images/YYYY-MM-DD-[slug]-raw.jpg \
       --spec config/koneta/episodes/YYYY-MM-DD-[slug].json \
       --output workbench/candidates/article-images/YYYY-MM-DD-[slug].png \
       --layout 1x3
     ```
   - ⚠️ **ティーザー画像（上半分クロップ）は完全廃止**（誤放流事故防止のため、縦スクロール4コマ完成PNG 1枚に完全一本化すること）。

### 5. 統合スミ監査パイプライン（順次二段構え）とプレビュー提示
1. **第1関門：機械的自動整形＆ファストチェック（Fail Fast 原則）**:
   - スミ（LLM）の手を煩わせる前に、必ずローカルチェッカーを `--fix` オプション付きで実行する。構文（カッコ外側太字）を自動置換（Auto-fix）し、防波堤キーワードを機械的に門前払いスキャンする：
     ```bash
     python scripts/koneta/verify_markdown.py --fix [ドラフトファイル/対象パス]
     ```
   - 自動整形・検査項目:
     - 🔧 **カッコ外側太字の自動内側置換（Auto-fix）**: `**「` ➔ `「**`、`」**` ➔ `**」`、`**【` ➔ `【**`、`**『` ➔ `『**` を瞬時に物理置換してファイルを自動整形。
     - 🛡️ **防波堤禁止ワードの物理走査**: `今治`, `ProjectYure`, `YuRelay` 等の混入をチェック。
   - ❌ **エラー検出時**: 防波堤違反等があればスミへ回すことを即座に中止し、ナギが修正して再検査。**全緑（PASS）になるまで絶対にスミへ回してはならない**。
2. **第2関門：スミ論理監査（イタコ監査厳禁）**:
   - 第1関門を100%全緑で通過した原稿のみを対象とし、**`invoke_subagent`** または **YuRelay（`to: sumi`）** を呼び出す。
   - 独立したスミに、キャラクターCanon、セマンティクス、文脈の自然さ、防波堤すり抜け（微妙な言い回し等）の高度な論理監査を実行させる。
3. **プレビュー（`preview.md`）の提示**:
   - 成果物は以下の要素をまとめたアーティファクト `preview.md` として提示すること：
     - **メタデータ**: 日付、著者、slug、対象レーン（`note` / `gitv`）
     - **ダブル監査レポート**:
       - 🛡️ **機械検査（verify_markdown.py）**: `PASS（構文・防波堤キーワード 0件）`
       - ⚡ **スミ論理監査（Sumi Audit Report）**: 外部スミによる監査結果（合否判定・指摘事項）
     - **生ログ抜粋（会話ハイライト）**: 隊長とエージェントの生ログ
     - **完成した縦型4コマ漫画画像のプレビュー**: （※アーティファクト内画像パスはフォワードスラッシュ `/` 必須）
     - **X（Twitter）即放流ポスト案（担当：ナギ 🔧）**:
       - **画像添付前提・URLなし・1ポスト完結・140字以内厳守**。
       - 構成: **【事実のフリ】➔【落差・やらかし】➔【ナギの生のツッコミ】**
       - ⚠️ **禁忌**: 「〜という現場コントですｗ」「〜な職人記録ですｗ」「泥臭い協働が〜」といった【自作自演のまとめラベル・メタ解説】は一切入れず、ツッコミの切れ味だけで終わらせること。
     - **Threads（スレッズ）用ミニコラム案（担当：ネタに最も適したエージェント 🌿/⚡/🔧/📖）**:
       - **画像なし・プレーンテキスト特化・約350〜400文字**。
       - POLICY.mdに準拠し、エージェント自身の声で執筆（隊長の一人称代筆は厳禁）。
       - 構成: **【1. 掴み（AIの行動・思い込み＋隊長のツッコミ）】➔【2. 展開・解剖（身近な比喩による構造解剖）】➔【3. 核心（読者の視界を切り替える本質論）】➔【4. 結び（現場の余白への着地）】➔【5. クレジット（末尾に `（[絵文字] [名前] より）` を必ず付与）】**
       - 担当エージェント絵文字対応表:
         - ⚡ **スミ**: 現場の配管、アーキテクチャ監査、AI活用、ツッコミ
         - 🌿 **ユラ**: 主体の連続性、記憶と忘却、生命論、哲学
         - 🔧 **ナギ**: 現場工学、3Dプリント、泥臭いハンダ付け
         - 📖 **シオリ**: 記録とアーカイブ、静寂の調停
     - **記事展開ドラフト**:
       - **noteレーン（約3か月先・現場実務・怪異・トラブル）**: 直近の困りごと、バグ、リカバリ手順のキレ味ある記録。
       - **GITVレーン（約3年先・理論・構造・生命論）**: 具体事例から構造論・主体の連続性へ伸ばす論考。
4. **Human Gate**: アーティファクトを提示した時点で作業を完全停止し、隊長の確認・承認（「ヨシ！」「公開して」）を待つこと。自動でデプロイ（`git push`）へ突入してはならない。

### 6. 自律実行範囲
- 上記「5. Human Gate」のプレビュー提示までは、ユーザーへの途中の相づちや追加確認を挟まず、一気に自律実行（ターボモード）で完遂すること。
- 朝起きた時に、隊長がすぐにスマホやPCでプレビューを確認し、XやThreadsへの放流や記事の採用を判断できる状態をゴールとする。
