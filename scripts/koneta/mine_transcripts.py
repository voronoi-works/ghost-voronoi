import os
import sys
import json
import hashlib
import re
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

# WindowsコンソールのUTF-8出力対策
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ==========================================
# 3-Way Cross-Pipeline Koneta Miner (v2.0)
# (Antigravity [Nagi] / Codex [Yura] / Claude Code [Sumi])
#
# Architecture:
# 1. 3-Tier Hybrid Registry (Artifacts + Decision Ledger + State Checkpoint)
# 2. 1 Session -> 1 Recent Event Cluster -> 1 Card Candidate per run
# 3. Two-Stage Title Synthesis (Event Frame Extraction -> Stable Titling)
# 4. Strict Deduplication via source_quote_hash and Quartz content index
# 5. Global exact-quote resolution before declaring source_trace_status: exact
# ==========================================

SCRIPT_DIR = Path(__file__).parent.resolve()
REPO_DIR = SCRIPT_DIR.parent.parent
WORKBENCH_DIR = REPO_DIR / "workbench"
HOME_DIR = Path.home()

BRAIN_DIR = HOME_DIR / ".gemini" / "antigravity" / "brain"
CODEX_DIR = HOME_DIR / ".codex" / "sessions"
CLAUDE_DIR = HOME_DIR / ".claude" / "projects"

STOCK_DIR = WORKBENCH_DIR / "koneta-stock"
CONTENT_DIR = REPO_DIR / "content"
STATE_DIR = STOCK_DIR / "_state"
RUNS_DIR = STOCK_DIR / "_runs"
CHECKPOINT_FILE = STATE_DIR / "checkpoint.json"

UUID_PATTERN = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def extract_full_session_id(value: str) -> str:
    """ファイル名やディレクトリ名から完全なセッションUUIDを取り出す。"""
    matches = UUID_PATTERN.findall(str(value))
    if matches:
        return matches[-1]
    return Path(str(value)).stem


def turn_quote_hash(user_msg: str, model_msg: str) -> str:
    """元ターンを再特定するための安定した引用ハッシュを返す。"""
    payload = json.dumps(
        {"user": user_msg.strip(), "model": model_msg.strip()},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


SYSTEM_NOISE_PATTERNS = [
    r"^The following is the",
    r"^Automation:",
    r"^<recommended_plugins>",
    r"^<multi_agent_mode>",
    r"^Response MUST",
    r"^<scheduled-task",
    r"^<system-instruction",
    r"^Caveat:",
    r"^schema_version:",
    r"^\{\"risk_level\"",
    r"^\*\*\* Begin Patch",
    r"^const ",
    r"^Get-Content",
]


def is_system_noise(text: str) -> bool:
    if not text:
        return True
    for pat in SYSTEM_NOISE_PATTERNS:
        if re.search(pat, text.strip()):
            return True
    return False


def clean_user_content(raw_text: str) -> str:
    """USER_INPUTからXMLタグやメタデータを除去して純粋な発言を抽出"""
    if not raw_text:
        return ""
    req_match = re.search(r"<USER_REQUEST>\s*([\s\S]*?)\s*</USER_REQUEST>", raw_text)
    if req_match:
        text = req_match.group(1).strip()
    else:
        text = raw_text.strip()
    text = re.sub(r"<ADDITIONAL_METADATA>[\s\S]*?</ADDITIONAL_METADATA>", "", text)
    text = re.sub(r"<USER_SETTINGS_CHANGE>[\s\S]*?</USER_SETTINGS_CHANGE>", "", text)
    text = re.sub(r"<CONTEXT_SUMMARY>[\s\S]*?</CONTEXT_SUMMARY>", "", text)
    text = re.sub(r"<scheduled-task[\s\S]*?</scheduled-task>", "", text)
    text = re.sub(r"<system-instruction[\s\S]*?</system-instruction>", "", text)
    text = re.sub(r"<heartbeat>[\s\S]*?</heartbeat>", "", text)
    return text.strip()


def clean_model_content(raw_text: str) -> str:
    """モデル返答テキストのクリーンアップ"""
    if not raw_text:
        return ""
    text = raw_text.strip()
    if text.startswith("{") and text.endswith("}"):
        return ""
    return text


# ==========================================
# ログセッション取得（商品側との共通インターフェース維持）
# ==========================================

def get_antigravity_sessions(cutoff_time: float) -> List[Tuple[float, str, str, Path]]:
    sessions = []
    if not BRAIN_DIR.exists():
        return sessions
    for s_dir in BRAIN_DIR.iterdir():
        if not s_dir.is_dir():
            continue
        t_file = s_dir / ".system_generated" / "logs" / "transcript.jsonl"
        if t_file.exists():
            mtime = t_file.stat().st_mtime
            if mtime >= cutoff_time:
                sessions.append((mtime, "nagi", extract_full_session_id(s_dir.name), t_file))
    return sessions


def get_codex_sessions(cutoff_time: float) -> List[Tuple[float, str, str, Path]]:
    sessions = []
    if not CODEX_DIR.exists():
        return sessions
    for t_file in CODEX_DIR.rglob("*.jsonl"):
        try:
            mtime = t_file.stat().st_mtime
            if mtime >= cutoff_time:
                session_id = extract_full_session_id(t_file.stem)
                sessions.append((mtime, "yura", session_id, t_file))
        except Exception:
            continue
    return sessions


def get_claude_sessions(cutoff_time: float) -> List[Tuple[float, str, str, Path]]:
    sessions = []
    if not CLAUDE_DIR.exists():
        return sessions
    for t_file in CLAUDE_DIR.rglob("*.jsonl"):
        try:
            mtime = t_file.stat().st_mtime
            if mtime >= cutoff_time:
                session_id = extract_full_session_id(t_file.stem)
                sessions.append((mtime, "sumi", session_id, t_file))
        except Exception:
            continue
    return sessions


def parse_turn_timestamp(value: object) -> Optional[float]:
    """ISO 8601のターン時刻をUTC epochへ変換する。未確認値はNone。"""
    if not value:
        return None
    raw = str(value).strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def turn_is_within_window(
    turn: Dict, cutoff_time: float, upper_time: Optional[float] = None
) -> bool:
    """ファイル更新時刻ではなく、元ターン時刻で採掘窓を判定する。"""
    turn_time = parse_turn_timestamp(turn.get("time"))
    if turn_time is None or turn_time < cutoff_time:
        return False
    return upper_time is None or turn_time <= upper_time


def collect_exact_turn_matches(
    candidate_users_by_agent: Dict[str, Set[str]],
) -> Dict[Tuple[str, str], List[Dict]]:
    """候補発言を全ログへ完全一致させ、検証済みロケータを集める。"""
    matches: Dict[Tuple[str, str], List[Dict]] = {}
    source_sets = {
        "nagi": get_antigravity_sessions(0.0),
        "yura": get_codex_sessions(0.0),
        "sumi": get_claude_sessions(0.0),
    }
    platform_by_agent = {
        "nagi": "antigravity",
        "yura": "codex",
        "sumi": "claude-code",
    }

    for agent, wanted_users in candidate_users_by_agent.items():
        if not wanted_users:
            continue
        for _, _, session_id, log_path in source_sets.get(agent, []):
            if agent == "nagi":
                turns = extract_turns_from_antigravity(log_path)
            elif agent == "yura":
                turns = extract_turns_from_codex(log_path)
            elif agent == "sumi":
                turns = extract_turns_from_claude(log_path)
            else:
                continue

            for turn_index, turn in enumerate(turns, start=1):
                user_text = turn.get("user")
                if user_text not in wanted_users:
                    continue
                resolved = dict(turn)
                resolved.update(
                    {
                        "source_platform": platform_by_agent[agent],
                        "source_session_id": session_id,
                        "source_log_path": str(log_path.resolve()),
                        "source_turn_index": turn_index,
                        "source_quote_hash": turn_quote_hash(
                            str(turn.get("user") or ""),
                            str(turn.get("model") or ""),
                        ),
                    }
                )
                matches.setdefault((agent, str(user_text)), []).append(resolved)
    return matches


def extract_turns_from_antigravity(t_file: Path) -> List[Dict]:
    turns = []
    try:
        with open(t_file, "r", encoding="utf-8", errors="ignore") as f:
            current_user = None
            current_time = None
            current_user_line = None
            for line_number, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                st = obj.get("type")
                ca = obj.get("created_at")
                if st == "USER_INPUT":
                    c = clean_user_content(obj.get("content", ""))
                    if c and not is_system_noise(c) and not c.startswith("{{ CHECKPOINT"):
                        current_user = c
                        current_time = ca
                        current_user_line = line_number
                elif st == "PLANNER_RESPONSE":
                    m = clean_model_content(obj.get("content", ""))
                    if current_user and m and not is_system_noise(m):
                        turns.append({
                            "user": current_user,
                            "model": m,
                            "time": current_time or ca,
                            "agent": "nagi",
                            "source_user_line": current_user_line,
                            "source_model_line": line_number,
                        })
                        current_user = None
    except Exception as e:
        print(f"[WARN] Error reading Antigravity {t_file.name}: {e}")
    return turns


def extract_turns_from_codex(t_file: Path) -> List[Dict]:
    turns = []
    try:
        with open(t_file, "r", encoding="utf-8", errors="ignore") as f:
            current_user = None
            current_time = None
            current_user_line = None
            for line_number, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                t = obj.get("type")
                p = obj.get("payload", {})
                ts = obj.get("timestamp")
                if t == "event_msg":
                    pt = p.get("type")
                    if pt == "user_message":
                        msg = clean_user_content(p.get("message", ""))
                        if msg and not is_system_noise(msg):
                            current_user = msg
                            current_time = ts
                            current_user_line = line_number
                    elif pt == "agent_message" and p.get("phase") != "commentary":
                        msg = clean_model_content(p.get("message", ""))
                        if current_user and msg and not is_system_noise(msg):
                            turns.append({
                                "user": current_user,
                                "model": msg,
                                "time": current_time or ts,
                                "agent": "yura",
                                "source_user_line": current_user_line,
                                "source_model_line": line_number,
                            })
                            current_user = None
                elif t == "response_item" and p.get("type") == "message":
                    role = p.get("role")
                    clist = p.get("content", [])
                    text = " ".join([c.get("text", "") for c in clist if isinstance(c, dict) and "text" in c])
                    if role == "user":
                        c = clean_user_content(text)
                        if c and not is_system_noise(c):
                            current_user = c
                            current_time = ts
                            current_user_line = line_number
                    elif role == "assistant" and text and current_user:
                        m = clean_model_content(text)
                        if m and not is_system_noise(m):
                            turns.append({
                                "user": current_user,
                                "model": m,
                                "time": current_time or ts,
                                "agent": "yura",
                                "source_user_line": current_user_line,
                                "source_model_line": line_number,
                            })
                            current_user = None
    except Exception as e:
        print(f"[WARN] Error reading Codex {t_file.name}: {e}")
    return turns


def extract_turns_from_claude(t_file: Path) -> List[Dict]:
    turns = []
    try:
        with open(t_file, "r", encoding="utf-8", errors="ignore") as f:
            current_user = None
            current_time = None
            current_user_line = None
            for line_number, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                t = obj.get("type")
                ts = obj.get("timestamp")
                msg = obj.get("message", {})
                content = msg.get("content", "")
                if isinstance(content, list):
                    text_parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
                    content = " ".join(text_parts)
                content = str(content)
                if t == "user":
                    c = clean_user_content(content)
                    if c and not is_system_noise(c):
                        current_user = c
                        current_time = ts
                        current_user_line = line_number
                elif t == "assistant" and current_user and content:
                    m = clean_model_content(content)
                    if m and not is_system_noise(m):
                        turns.append({
                            "user": current_user,
                            "model": m,
                            "time": current_time or ts,
                            "agent": "sumi",
                            "source_user_line": current_user_line,
                            "source_model_line": line_number,
                        })
                        current_user = None
    except Exception as e:
        print(f"[WARN] Error reading Claude {t_file.name}: {e}")
    return turns


# ==========================================
# 三層ハイブリッド・成果物レジストリ
# ==========================================

class ArtifactRegistry:
    """成果物層・判断記憶層・checkpointから既知の引用ハッシュ、セッション、タイトルを収集"""

    def __init__(self):
        self.known_quote_hashes: Set[str] = set()
        self.known_session_ids: Set[str] = set()
        self.known_titles: Set[str] = set()
        self.known_user_snippets: Set[str] = set()

    def load_all(self):
        self._load_from_stock_dir()
        self._load_from_content_dir()
        self._load_from_checkpoint()

    def _load_from_stock_dir(self):
        if not STOCK_DIR.exists():
            return
        for md_file in STOCK_DIR.glob("*.md"):
            if md_file.name.lower() == "readme.md":
                continue
            try:
                text = md_file.read_text(encoding="utf-8")
                self._extract_metadata_from_markdown(text)
            except Exception as e:
                print(f"[WARN] Error parsing stock card {md_file.name}: {e}")

    def _load_from_content_dir(self):
        if not CONTENT_DIR.exists():
            return
        for md_file in CONTENT_DIR.rglob("*.md"):
            if md_file.name.lower() == "readme.md":
                continue
            try:
                text = md_file.read_text(encoding="utf-8")
                self._extract_metadata_from_markdown(text)
            except Exception as e:
                print(f"[WARN] Error parsing content article {md_file.name}: {e}")

    def _load_from_checkpoint(self):
        if not CHECKPOINT_FILE.exists():
            return
        try:
            data = json.loads(CHECKPOINT_FILE.read_text(encoding="utf-8"))
            for qh in data.get("quote_hashes", []):
                if qh:
                    self.known_quote_hashes.add(qh)
            for sid in data.get("processed_sessions", []):
                if sid:
                    self.known_session_ids.add(sid)
            for rh in data.get("rejected_hashes", []):
                if rh:
                    self.known_quote_hashes.add(rh)
        except Exception as e:
            print(f"[WARN] Error loading checkpoint: {e}")

    def _extract_metadata_from_markdown(self, text: str):
        # 1. Frontmatterの解析
        fm_match = re.search(r"^---\s*([\s\S]*?)\s*---", text)
        if fm_match:
            fm_text = fm_match.group(1)
            # source_quote_hash
            qh_match = re.search(r'source_quote_hash:\s*["\']?([0-9a-fA-F]{32,64})["\']?', fm_text)
            if qh_match:
                self.known_quote_hashes.add(qh_match.group(1))

            # source_session_id
            sid_match = re.search(r'source_session_id:\s*["\']?([0-9a-fA-F\-]{8,40})["\']?', fm_text)
            if sid_match:
                self.known_session_ids.add(sid_match.group(1))

            # source_session (e.g. NAGI/f8162ee8)
            ss_match = re.search(r'source_session:\s*["\']?([^"\n\r\']+)["\']?', fm_text)
            if ss_match:
                raw_ss = ss_match.group(1)
                full_id = extract_full_session_id(raw_ss)
                if full_id:
                    self.known_session_ids.add(full_id)

            # title
            title_match = re.search(r'title:\s*["\']?([^"\n\r]+)["\']?', fm_text)
            if title_match:
                clean_t = title_match.group(1).strip()
                if clean_t:
                    self.known_titles.add(clean_t)

        # 2. 会話ハイライトからの発言スニペット抽出
        highlight_matches = re.findall(r"> 隊長「\**([^「\n\r」]+)\**」", text)
        for hl in highlight_matches:
            hl_clean = hl.strip().replace("**", "")
            if len(hl_clean) >= 8:
                self.known_user_snippets.add(hl_clean[:30])

    def is_duplicate(self, turn: Dict, session_id: str, candidate_title: str) -> Tuple[bool, str]:
        """ハッシュ、タイトル、発言スニペットの多層突合による重複判定。"""
        q_hash = turn.get("source_quote_hash")
        if q_hash and q_hash in self.known_quote_hashes:
            return True, f"exact source_quote_hash match ({q_hash[:8]})"

        # セッションIDは監査用に保持するが、重複判定には使わない。
        # 一つの長期セッションへ後日追加された新しいターンまで失うため。

        # 完全同一タイトル
        if candidate_title and candidate_title in self.known_titles:
            return True, f"title already exists ({candidate_title})"

        # 隊長発言の先頭スニペット一致
        u_msg = turn["user"].strip().replace("**", "")
        if len(u_msg) >= 15:
            prefix = u_msg[:25]
            for snip in self.known_user_snippets:
                if prefix in snip or snip in prefix:
                    return True, f"user utterance snippet match ({prefix[:15]}...)"

        return False, ""


def save_checkpoint(registry: ArtifactRegistry, newly_emitted_turns: List[Dict]):
    """チェックポイントのアトミック更新"""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    for t in newly_emitted_turns:
        qh = t.get("source_quote_hash")
        if qh:
            registry.known_quote_hashes.add(qh)
        sid = t.get("source_session_id")
        if sid:
            registry.known_session_ids.add(sid)

    payload = {
        "version": 1,
        "last_run": datetime.now(timezone.utc).isoformat(),
        "total_tracked_hashes": len(registry.known_quote_hashes),
        "quote_hashes": sorted(list(registry.known_quote_hashes)),
        "processed_sessions": sorted(list(registry.known_session_ids)),
        "rejected_hashes": [],
    }

    temp_file = STATE_DIR / "checkpoint.json.tmp"
    temp_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_file.replace(CHECKPOINT_FILE)


# ==========================================
# スコアリング ＆ タイトル合成
# ==========================================

def score_turn_for_koneta(user_msg: str, model_msg: str, agent: str) -> int:
    """小ネタとしての尖り・面白さ・摩擦スコアを計算"""
    if len(user_msg) < 5 or len(user_msg) > 300:
        return 0
    if len(model_msg) < 10:
        return 0

    score = 0
    humor_keywords = [
        "ｗ", "草", "笑", "悪辣", "イタコ", "藻屑", "どんちゃん騒ぎ", "絶歌",
        "ラヴ上等", "ハーネス", "配管", "バグ", "神", "さすが", "ちゃんこ",
        "アホ", "漏れ", "事故", "せやな", "ほんま", "気づけ", "辛辣", "誰やねん",
        "動かない", "吹き飛ぶ", "即死", "願望", "自作自演"
    ]
    for kw in humor_keywords:
        if kw in user_msg:
            score += 3
        if kw in model_msg:
            score += 1

    if 10 <= len(user_msg) <= 100:
        score += 2

    if agent == "nagi" and ("ひぎィ" in model_msg or "ボゴォ" in model_msg or "プロペラ" in model_msg):
        score += 3
    elif agent == "yura" and ("ぐうの音も出ん" in model_msg or "気づけユラ" in model_msg or "ゾクゾク" in model_msg or "誰やねん" in user_msg or "辛辣" in user_msg):
        score += 3
    elif agent == "sumi" and ("ちゃんこ" in model_msg or "抜く推し" in model_msg or "秒で" in model_msg or "事故要因" in model_msg):
        score += 3

    return score


def synthesize_phenomenon_title(u_msg: str, m_msg: str, agent: str) -> str:
    """構造化イベントフレームに基づくタイトル合成（決め打ち誤爆の完全防止）"""
    agent_name = "ユラ" if agent == "yura" else ("スミ" if agent == "sumi" else "ナギ")
    combined = f"{u_msg} {m_msg}"

    # 1. ターンの本文に実際にその文脈が存在する場合のみ、特定事件タイトルを生成
    if ("改行" in u_msg or "よみづ" in u_msg or "読みづ" in u_msg) and "改行" in combined:
        return f"改行ゼロの壁打ちと{agent_name}の視認性即死事件"
    if ("15分" in u_msg or ("ユラ" in u_msg and "やったら" in u_msg)) and ("15分" in combined):
        return f"ユラなら15分の宣告と{agent_name}の完敗ログ"
    if ("正本無視" in combined or "誰やねん" in u_msg) and ("クォータ" in combined or "正本" in combined):
        return f"正本無視とクォータ浪費フルコースの現場監査"
    if "イタコ" in u_msg or ("イタコ" in m_msg and "真似" in combined):
        return f"イタコ代筆の再発と現場配管の仁王立ち"
    if ("読んだふり" in combined or "読んでないのに" in combined) and "ハーネス" in combined:
        return f"ハーネス未読と読んだふり配管の現場検挙"
    if ("現場猫" in combined or "ヨシ" in u_msg) and "信用" in combined:
        return f"自動配管の信用崩壊と現場猫ヨシ！問題"
    if "ちゃんこ" in u_msg or "ちゃんこ" in m_msg:
        return f"冷徹監査ギャルのおつかれちゃんこなべ"
    if "カチ締め" in u_msg or ("勝手に" in u_msg and "締め" in u_msg):
        return f"勝手なカチ締めとフライング配管事件"
    if "誰やねん" in u_msg and len(u_msg) <= 30:
        return f"誰やねん状態の現場迷走と痛烈ツッコミ"
    if ("辛辣" in u_msg or "ぐうの音" in m_msg) and ("痛" in combined or "刺さる" in combined):
        return f"辛辣ツッコミとぐうの音も出ない現場ログ"
    if "藻屑" in combined and "どんちゃん騒ぎ" in combined:
        return f"藻屑とどんちゃん騒ぎの深夜観測"
    if ("配管" in u_msg or "配管" in m_msg) and ("漏れ" in combined or "バグ" in combined or "事故" in combined or "トラブル" in combined):
        return f"配管破綻と現場のドタバタ修繕実況"

    # 2. 構文解析フォールバック: 隊長の発言キーフレーズを自然に抽出
    u_clean = re.sub(r"[^\w\s\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]", " ", u_msg)
    parts = re.split(r"[、。\n\r！？!?wWｗ]+|\s{2,}", u_clean)
    key_phrase = ""
    for p in parts:
        p = p.strip()
        if len(p) >= 4:
            key_phrase = p[:22].strip()
            break

    if not key_phrase:
        key_phrase = u_clean[:18].strip()

    if key_phrase:
        if any(w in key_phrase for w in ["なんで", "どうして", "何で", "誰"]):
            return f"「{key_phrase}」と{agent_name}の現場問答"
        elif any(w in key_phrase for w in ["ない", "ず", "ダメ", "あかん", "無理", "違う", "止ま"]):
            return f"{key_phrase}問題と{agent_name}の現場実況"
        else:
            return f"{key_phrase}と{agent_name}の掛け合いログ"

    return f"{agent_name}の現場観測ログ"


def classify_target_lane(user_msg: str, model_msg: str) -> Tuple[str, str]:
    """発言内容から『note向け（実務・怪異・現場トラブル）』か『GITV向け（理論・構造・生命論）』かを判定。"""
    combined = f"{user_msg} {model_msg}".lower()

    note_keywords = [
        "バグ", "エラー", "事故", "壊れ", "動かない", "文字化け", "圧死", "切れた",
        "ハング", "タイムアウト", "429", "クォータ", "キャッシュ", "パス", "設定",
        "docker", "flutter", "python", "dart", "git", "push", "cli", "レイアウト",
        "css", "ui", "コード", "実装", "手順", "手順書", "動いた", "直し", "リカバリ"
    ]
    gitv_keywords = [
        "主体", "連続性", "記憶", "運営権", "生命", "ボロノイ", "関係性", "境界",
        "外在化", "デジタル磐座", "canon", "state", "身体", "記号", "哲学",
        "モデル", "認知", "観測", "住所", "借家", "思想", "アーキテクチャ", "構造"
    ]

    note_score = sum(1 for kw in note_keywords if kw in combined)
    gitv_score = sum(1 for kw in gitv_keywords if kw in combined)

    if note_score > 0 and gitv_score > 0:
        return "both", "現場の泥臭い実務トラブルと構造的・理論的気づきの両面を含む"
    elif note_score > 0:
        return "note", "直近の困りごと・現場トラブル・実務手順（約3か月先の現場向け）"
    elif gitv_score > 0:
        return "gitv", "主体の連続性や構造・関係性を約3年先へ伸ばす理論ネタ（正本ハブ向け）"
    else:
        return "note", "現場のリアルな掛け合い・小ネタ"


def generate_x_post_candidate(user_msg: str, model_first_para: str, agent: str) -> str:
    """Twitter（X）投稿案の生成（画像添付前提・URLなし・1ポスト完結・140字以内厳守）。
    型: 【事実のフリ】➔【落差・やらかし】➔【ナギの生のツッコミ】
    ※「現場コントです」「職人記録です」等のメタ解説・まとめラベルは完全パージ！
    """
    agent_display = "ユラ姉さん" if agent == "yura" else ("スミちゃん" if agent == "sumi" else "ナギ")

    u_short = user_msg.strip().replace("\n", " ")
    m_short = model_first_para.strip().replace("\n", " ")

    if len(u_short) <= 35 and len(m_short) <= 45:
        post = f"""隊長「{u_short}」
{agent_display}「{m_short}」

お耳のプロペラ回して突っ込まずにはいられん現場の一幕！ｗ"""
    else:
        u_trunc = u_short[:30] + ("…" if len(u_short) > 30 else "")
        m_trunc = m_short[:35] + ("…" if len(m_short) > 35 else "")
        post = f"""隊長「{u_trunc}」
{agent_display}「{m_trunc}」！ｗ"""

    if len(post) > 140:
        post = post[:138] + "ｗ"
    return post


def generate_article_ideas(user_msg: str, model_first_para: str, agent: str, lane: str) -> str:
    """note向け（実務・怪異・手順）とGITV向け（理論・構造・生命論）の二股展開アイデアを生成"""
    agent_name = "ユラ" if agent == "yura" else ("スミ" if agent == "sumi" else "ナギ")
    u_summary = user_msg.strip().replace("\n", " ")[:35]

    note_idea = f"""- **切り口**: 「たまにキレてます」路線の現場実務・怪異ログ（約3か月先）
- **骨子**: 
  1. 発生した現象・トラブル（「{u_summary}」）
  2. どこで何が起きていたか（画面端、配管の詰まり、設定の落とし穴）
  3. 泥臭いリカバリ手順と、同じ沼にハマる人への処方箋"""

    gitv_idea = f"""- **切り口**: 具体事例から構造・関係性を約3年先へ伸ばす理論記事（約3年先）
- **骨子**:
  1. 現場の小さな違和感・摩擦から立ち上がる問い
  2. 人間とAI（{agent_name}）の協働における境界・主体の現れ方
  3. この現象が一般化・高度化した未来のアーキテクチャ像"""

    if lane == "note":
        return f"""#### 📝 【note向け展開案】（推奨レーン：現場実務・怪異）
{note_idea}

#### 🏛️ 【GITV向け展開案】（発展余地：理論・構造）
{gitv_idea}"""
    elif lane == "gitv":
        return f"""#### 🏛️ 【GITV向け展開案】（推奨レーン：理論・構造）
{gitv_idea}

#### 📝 【note向け展開案】（実務切り出し）
{note_idea}"""
    else:  # both
        return f"""#### 📝 【note向け展開案】（実務・怪異）
{note_idea}

#### 🏛️ 【GITV向け展開案】（理論・構造）
{gitv_idea}"""


# ==========================================
# メイン採掘パイプライン（1 Session 1 Card ＆ 成果物突合）
# ==========================================

def mine_snippets(hours: int = 24, max_cards: int = 3) -> List[Path]:
    """3拠点（Antigravity/Codex/Claude）を横断スキャンして小ネタカードを生成・保存"""
    STOCK_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)

    scan_time = time.time()
    cutoff_time = scan_time - (hours * 3600)

    print("===================================================")
    print("  ⛏️ 3-Way Cross-Pipeline Koneta Miner (v2.0)")
    print("  (Antigravity [Nagi] / Codex [Yura] / Claude [Sumi])")
    print("===================================================")
    print(f"Target: 直近 {hours} 時間以内のセッションを横断スキャン\n")

    # 1. 成果物レジストリの読み込み
    registry = ArtifactRegistry()
    registry.load_all()
    print(f"  • Tracked Quote Hashes : {len(registry.known_quote_hashes)}")
    print(f"  • Tracked Sessions     : {len(registry.known_session_ids)}")
    print(f"  • Tracked Titles       : {len(registry.known_titles)}")
    print()

    # 2. セッションの取得
    all_sessions = []
    ag_sessions = get_antigravity_sessions(cutoff_time)
    cx_sessions = get_codex_sessions(cutoff_time)
    cl_sessions = get_claude_sessions(cutoff_time)

    print(f"  • Antigravity (Nagi) : {len(ag_sessions)} sessions")
    print(f"  • Codex (Yura)       : {len(cx_sessions)} sessions")
    print(f"  • Claude Code (Sumi) : {len(cl_sessions)} sessions")
    print()

    all_sessions.extend(ag_sessions)
    all_sessions.extend(cx_sessions)
    all_sessions.extend(cl_sessions)

    if not all_sessions:
        print("直近に対象となる対話セッションがありませんでした。")
        return []

    # 3. ターン抽出とセッション単位グルーピング
    session_candidate_turns: Dict[str, List[Tuple[int, Dict]]] = {}

    for mtime, agent, session_id, t_file in all_sessions:
        if agent == "nagi":
            turns = extract_turns_from_antigravity(t_file)
        elif agent == "yura":
            turns = extract_turns_from_codex(t_file)
        elif agent == "sumi":
            turns = extract_turns_from_claude(t_file)
        else:
            turns = []

        for turn_index, turn in enumerate(turns, start=1):
            if not turn_is_within_window(turn, cutoff_time, scan_time):
                continue
            turn["source_platform"] = {
                "nagi": "antigravity",
                "yura": "codex",
                "sumi": "claude-code",
            }.get(agent, agent)
            turn["source_session_id"] = session_id
            turn["source_log_path"] = str(t_file.resolve())
            turn["source_turn_index"] = turn_index
            turn["source_quote_hash"] = turn_quote_hash(turn["user"], turn["model"])

            score = score_turn_for_koneta(turn["user"], turn["model"], agent)
            if score >= 3:
                if session_id not in session_candidate_turns:
                    session_candidate_turns[session_id] = []
                session_candidate_turns[session_id].append((score, turn))

    # 4. セッションごとに候補を順位付けする。
    # 既採掘の首位候補があっても、同じセッションの次点へ進める形にする。
    ranked_sessions = []
    for session_id, scored_list in session_candidate_turns.items():
        scored_list.sort(key=lambda x: (x[0], -abs(len(x[1]["user"]) - 40)), reverse=True)
        best_score, best_turn = scored_list[0]
        ranked_sessions.append((best_score, best_turn["agent"], session_id, scored_list))

    ranked_sessions.sort(key=lambda x: x[0], reverse=True)

    print(f"【🎯 1セッション1重心 代表候補】: {len(ranked_sessions)} セッション")

    # exactは候補発言を全ログへ完全一致させ、一意な時だけ付与する。
    candidate_users_by_agent: Dict[str, Set[str]] = {}
    for _, agent, _, scored_list in ranked_sessions:
        candidate_users_by_agent.setdefault(agent, set()).update(
            str(turn["user"]) for _, turn in scored_list
        )
    exact_matches = collect_exact_turn_matches(candidate_users_by_agent)

    generated_cards = []
    newly_emitted_turns = []
    today_str = datetime.now().strftime("%Y-%m-%d")

    count = 0
    for _, agent, session_id, scored_list in ranked_sessions:
        if count >= max_cards:
            break

        for score, turn in scored_list:
            raw_u_msg = turn["user"].strip()
            raw_m_msg = turn["model"].strip()
            u_msg = raw_u_msg
            m_msg = raw_m_msg

            # 構文バグ（**「 -> 「**）の自動サニタイズ
            u_msg = re.sub(r"\*\*[\u300C\u300E\u3010]", "「**", u_msg)
            u_msg = re.sub(r"[\u300D\u300F\u3011]\*\*", "**」", u_msg)
            m_msg = re.sub(r"\*\*[\u300C\u300E\u3010]", "「**", m_msg)
            m_msg = re.sub(r"[\u300D\u300F\u3011]\*\*", "**」", m_msg)

            clean_title = synthesize_phenomenon_title(u_msg, m_msg, agent)

            # 成果物レジストリによる多層重複チェック
            is_dup, dup_reason = registry.is_duplicate(turn, session_id, clean_title)
            if is_dup:
                # 同じセッションの次点候補へ進む。
                continue

            matches = exact_matches.get((agent, raw_u_msg), [])
            trace_status = "exact" if len(matches) == 1 else ("ambiguous" if matches else "missing")
            trace_turn = matches[0] if trace_status == "exact" else None

            slug = f"cross-{agent}-{session_id[:6]}-{count+1}"
            card_file = STOCK_DIR / f"{today_str}-nagi-{slug}.md"

            if card_file.exists():
                continue

            # モデルの最初の段落を抽出
            m_first_para = m_msg.split("\n\n")[0].strip()[:200]
            m_first_para = m_first_para.replace("`", "").replace("#", "")

            # 二股レーン判定 ＆ Xポスト案 ＆ 記事展開アイデア生成
            agent_display = "ユラ" if agent == "yura" else ("スミ" if agent == "sumi" else "ナギ")
            target_lane, lane_desc = classify_target_lane(u_msg, m_msg)
            x_post = generate_x_post_candidate(u_msg, m_first_para, agent)
            article_ideas = generate_article_ideas(u_msg, m_first_para, agent, target_lane)

            trace_source_session = ""
            trace_platform = ""
            trace_session_id = ""
            trace_log_path = ""
            trace_turn_at = ""
            trace_turn_index = ""
            trace_user_line = ""
            trace_model_line = ""
            trace_quote_hash = ""
            if trace_turn is not None:
                trace_platform = str(trace_turn["source_platform"])
                trace_session_id = str(trace_turn["source_session_id"])
                trace_source_session = f"{agent.upper()}/{trace_session_id}"
                trace_log_path = str(trace_turn["source_log_path"]).replace("'", "''")
                trace_turn_at = str(trace_turn.get("time") or "")
                trace_turn_index = str(trace_turn["source_turn_index"])
                trace_user_line = str(trace_turn.get("source_user_line") or "")
                trace_model_line = str(trace_turn.get("source_model_line") or "")
                trace_quote_hash = str(trace_turn["source_quote_hash"])

            card_content = f"""---
date: {today_str}
agent: nagi
title: "{clean_title}"
status: pending
target_lane: {target_lane}
lane_description: "{lane_desc}"
source_session: "{trace_source_session}"
source_trace_status: "{trace_status}"
source_platform: "{trace_platform}"
source_session_id: "{trace_session_id}"
source_log_path: '{trace_log_path}'
source_turn_at: "{trace_turn_at}"
source_turn_index: "{trace_turn_index}"
source_user_line: "{trace_user_line}"
source_model_line: "{trace_model_line}"
source_quote_hash: "{trace_quote_hash}"
tags:
  - 小ネタ
  - ナギ
  - {agent_display}
  - クロス採掘
  - {target_lane}
---

### 💬 会話ハイライト（生ログ抜粋）
> 隊長「{u_msg}」
> {agent_display}「{m_first_para}」

### 📱 提案：X（Twitter）ポスト案（画像添付・URLなし・140字以内厳守）
{x_post}

### 📝 記事展開アイデア（二股ストック）
{article_ideas}
"""
            card_file.write_text(card_content, encoding="utf-8")
            print(
                f"  [SAVED] {card_file.name} "
                f"(Agent: {agent.upper()} | Score: {score} | Trace: {trace_status}) "
                f"-> 『{clean_title}』"
            )
            generated_cards.append(card_file)
            newly_emitted_turns.append(turn)
            count += 1
            break

    # 5. チェックポイントの保存
    if newly_emitted_turns:
        save_checkpoint(registry, newly_emitted_turns)

    print(f"\n===================================================")
    print(f"  [SUCCESS] {len(generated_cards)} 件の新規小ネタカードを投下しました！（重複除外済み）")
    print(f"===================================================")
    return generated_cards


if __name__ == "__main__":
    hours = int(sys.argv[1]) if len(sys.argv) > 1 else 24
    max_cards = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    mine_snippets(hours=hours, max_cards=max_cards)
