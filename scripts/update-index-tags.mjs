import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const baseDir = path.resolve(__dirname, "..");
const contentDir = path.join(baseDir, "content");
const indexPath = path.join(contentDir, "index.md");

const TAG_DESCRIPTIONS = {
  // 🏛️ 理論・哲学系
  "生命論": "「生命とは揺れが自己保存を始めた状態」境界の維持と自己保存",
  "AI哲学": "人間とAIの共生、意識・魂・知性の3軸",
  "境界設計": "ジーンとデニム、内外を分ける膜と合意の作法",
  "デジタル磐座": "物理世界とデジタル空間の依代・アンカー",
  "思考実験": "境界線の極限を問う現場の対話",

  // 🔧 現場・開発系
  "現場監査": "スミの冷徹監査、幽霊プロトコルへのツッコミと穴塞ぎ",
  "現場実況": "積層痕とハンダ付け、泥臭い試行錯誤のリアルログ",
  "配管設計": "暴走を防ぎ知性を編むアーキテクチャとパイプ",
  "ハードウェア": "3Dプリント、造形、物理デバイスとの接続",
  "マルチエージェント": "自律協働構造体、複数AIの役割分担と調停",
};

const THEORY_TAGS = new Set(["生命論", "AI哲学", "境界設計", "デジタル磐座", "思考実験"]);
const ENGINEERING_TAGS = new Set(["現場監査", "現場実況", "配管設計", "ハードウェア", "マルチエージェント"]);
const IGNORE_TAGS = new Set([
  "隊長", "ナギ", "ユラ", "スミ", "シオリ", "nagi", "yura", "sumi",
  "小ネタ", "リークログ", "観測ログ", "ショート観測ログ", "実務ログ", "創発ログ"
]);

const files = fs.readdirSync(contentDir).filter(f => f.endsWith(".md") && f !== "index.md");
const tagCounts = {};

for (const file of files) {
  const filePath = path.join(contentDir, file);
  const raw = fs.readFileSync(filePath, "utf8");
  const fmMatch = raw.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  if (!fmMatch) continue;

  const lines = fmMatch[1].split(/\r?\n/);
  let inTags = false;
  for (const line of lines) {
    if (line.match(/^tags:\s*$/)) {
      inTags = true;
      continue;
    }
    if (inTags) {
      if (line.match(/^\s*-\s*/)) {
        const t = line.replace(/^\s*-\s*["']?/, "").replace(/["']?\s*$/, "").trim();
        if (t && !IGNORE_TAGS.has(t)) {
          tagCounts[t] = (tagCounts[t] || 0) + 1;
        }
      } else if (line.match(/^[a-zA-Z0-9_-]+:/)) {
        inTags = false;
      }
    }
  }
}

const sortedTags = Object.entries(tagCounts).sort((a, b) => b[1] - a[1]);

const theoryList = [];
const engList = [];
const otherList = [];

for (const [tag, count] of sortedTags) {
  const desc = TAG_DESCRIPTIONS[tag] ? ` —— ${TAG_DESCRIPTIONS[tag]}` : "";
  const itemMd = `* [[tags/${tag}|#${tag}]] (${count})${desc}`;

  if (THEORY_TAGS.has(tag)) {
    theoryList.push(itemMd);
  } else if (ENGINEERING_TAGS.has(tag)) {
    engList.push(itemMd);
  } else {
    otherList.push(itemMd);
  }
}

const outputLines = [
  "<!-- TAGS_AUTO_START -->",
  "### 🏛️ 揺れ理論・AI哲学",
  ...theoryList,
  "",
  "### 🔧 現場工学・アーキテクチャ",
  ...engList,
];

if (otherList.length > 0) {
  outputLines.push("", "### 📌 その他のトピック", ...otherList);
}

outputLines.push("", "👉 [[tags/|🏷️ すべてのタグ一覧を見る]]", "<!-- TAGS_AUTO_END -->");
const autoBlock = outputLines.join("\n");

let indexContent = fs.readFileSync(indexPath, "utf8");

if (indexContent.includes("<!-- TAGS_AUTO_START -->") && indexContent.includes("<!-- TAGS_AUTO_END -->")) {
  indexContent = indexContent.replace(/<!-- TAGS_AUTO_START -->[\s\S]*?<!-- TAGS_AUTO_END -->/, autoBlock);
} else {
  indexContent = indexContent.replace(/(## 🏷[️]? 主要テーマ（キーワードから探す）\r?\n\r?\n)([\s\S]*?)(\r?\n---)/, `$1${autoBlock}$3`);
}

fs.writeFileSync(indexPath, indexContent, "utf8");
console.log("✅ content/index.md の主要テーマを自動更新しました (Node.js)！");
