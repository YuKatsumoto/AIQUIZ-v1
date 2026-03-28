import os
import pygame
import sys
import random
import json
import time
import re
import unicodedata
import ctypes
import io
import base64
import hashlib
from collections import deque
import threading
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import urllib.request
import urllib.parse
import urllib.error

# ===== 環境変数の読み込み (.envファイル対応) =====
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

# ===== LLM (ONLINE / OFFLINE) =====
try:
    from openai import OpenAI
except Exception:
    OpenAI = None
try:
    import google.generativeai as genai
except Exception:
    genai = None

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
DEBUG_WORKERS = os.getenv("DEBUG_WORKERS", "0") == "1"
try:
    LLM_BATCH_QUESTION_COUNT = max(2, min(6, int(os.getenv("LLM_BATCH_QUESTION_COUNT", "3"))))
except ValueError:
    LLM_BATCH_QUESTION_COUNT = 3
try:
    LLM_BATCH_QUESTION_COUNT_TEN = max(3, min(10, int(os.getenv("LLM_BATCH_QUESTION_COUNT_TEN", "5"))))
except ValueError:
    LLM_BATCH_QUESTION_COUNT_TEN = 5
try:
    LLM_SPLIT_WAIT_SECONDS = max(1.0, min(12.0, float(os.getenv("LLM_SPLIT_WAIT_SECONDS", "6.0"))))
except ValueError:
    LLM_SPLIT_WAIT_SECONDS = 6.0
try:
    LLM_SPLIT_WAIT_SECONDS_TEN = max(0.0, min(3.0, float(os.getenv("LLM_SPLIT_WAIT_SECONDS_TEN", "1.0"))))
except ValueError:
    LLM_SPLIT_WAIT_SECONDS_TEN = 1.0
try:
    LLM_TEMPERATURE = max(0.0, min(1.0, float(os.getenv("LLM_TEMPERATURE", "0.45"))))
except ValueError:
    LLM_TEMPERATURE = 0.45

# ===== APIキー読み込み確認ログ =====
print("=" * 60)
print("【API Key Check】")
if len(OPENAI_API_KEY) > 10:
    print(f"🔑 OpenAI Key Loaded: {OPENAI_API_KEY[:8]}...{OPENAI_API_KEY[-4:]}")
else:
    print("❌ OpenAI Key: Not Found or Too Short")

if len(GEMINI_API_KEY) > 10:
    print(f"🔑 Gemini Key Loaded: {GEMINI_API_KEY[:8]}...{GEMINI_API_KEY[-4:]}")
else:
    print("❌ Gemini Key: Not Found or Too Short")
print("=" * 60)

chatgpt_client = None
if OpenAI and OPENAI_API_KEY and "YOUR" not in OPENAI_API_KEY:
    try:
        chatgpt_client = OpenAI(api_key=OPENAI_API_KEY)
    except Exception as e:
        print(f"OpenAI Clientの初期化に失敗: {e}")
        chatgpt_client = None

gemini_model = None
if genai and GEMINI_API_KEY and "YOUR" not in GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel(GEMINI_MODEL)
    except Exception as e:
        print(f"Gemini Modelの初期化に失敗: {e}")
        gemini_model = None

# 出題モード: ONLINE=ChatGPT+Gemini, OFFLINE=内蔵
LLM_MODE = "ONLINE"

# ===================== 画面・色・フォント =====================
INITIAL_SCREEN_WIDTH = 960
INITIAL_SCREEN_HEIGHT = 720
WHITE=(255,255,255); BLACK=(0,0,0); GRAY=(128,128,128)
LIGHT_GRAY=(192,192,192); BLUE=(100,149,237); GREEN=(50,205,50)
GOLD=(255,215,0); RED=(220,20,60); EXPLANATION_BG=(245,245,245)
LIME=(173,255,47); ORANGE=(255, 165, 0)
NAVY=(0, 0, 128); PINK=(255, 182, 193)

FPS = 60
CORRECT_DISPLAY_MS = 1000

QUESTION_FONT_SIZE = 32
CHOICE_FONT_SIZE = 26
UI_FONT_SIZE_L = 44
UI_FONT_SIZE_M = 30
UI_FONT_SIZE_S = 20

PLAYER_WIDTH_RATIO = 0.06
PLAYER_HEIGHT_RATIO = 0.12
PLAYER_SPEED_RATIO = 0.0075
WALL_HEIGHT_RATIO = 0.18
DOOR_WIDTH_RATIO = 0.22

# --- 速度設定 ---
current_speed_level = "NORMAL"
SPEED_SETTINGS = {"SLOW": 0.003, "NORMAL": 0.005, "FAST": 0.008}
base_wall_speed = SPEED_SETTINGS["NORMAL"]
SPEED_REDUCTION_PER_CHAR = 0.00002
MINIMUM_WALL_SPEED_RATIO = 0.0015

# --- プレイヤー設定管理 ---
DIFFICULTY_LEVELS = ["簡単", "普通", "難しい"]
# 教科ごとの学年(subject_grades)を管理できるように拡張
PLAYER_CONFIGS = {
    1: {
        "name": "Player 1",
        "grade": 3, 
        "subject": "算数",
        "difficulties": {"算数": "普通", "理科": "普通", "国語": "普通"},
        "subject_grades": {"算数": 3, "理科": 3, "国語": 3}
    },
    2: {
        "name": "Player 2",
        "grade": 3,
        "subject": "算数",
        "difficulties": {"算数": "普通", "理科": "普通", "国語": "普通"},
        "subject_grades": {"算数": 3, "理科": 3, "国語": 3}
    }
}

# --- 評価データ管理 ---
RATING_FILE = "quiz_ratings.json"
quiz_ratings = {"good": [], "bad": []}
FIREBASE_DB_URL = os.getenv("FIREBASE_DB_URL", "").strip().rstrip("/")
FIREBASE_AUTH_TOKEN = os.getenv("FIREBASE_AUTH_TOKEN", "").strip()
FIREBASE_RATINGS_PATH = os.getenv("FIREBASE_RATINGS_PATH", "quiz_ratings/shared").strip().strip("/")

def _normalize_ratings(data):
    out = {"good": [], "bad": []}
    if not isinstance(data, dict):
        return out

    good_seen = set()
    raw_good = data.get("good", [])
    if isinstance(raw_good, dict):
        raw_good = list(raw_good.values())
    for item in raw_good:
        if not isinstance(item, dict):
            continue
        q_text = str(item.get("q", "")).strip()
        if not q_text or q_text in good_seen:
            continue
        good_seen.add(q_text)
        out["good"].append(item)

    bad_seen = set()
    raw_bad = data.get("bad", [])
    if isinstance(raw_bad, dict):
        raw_bad = list(raw_bad.values())
    for item in raw_bad:
        if isinstance(item, dict):
            q_text = str(item.get("q", "")).strip()
            subject = str(item.get("subject", "")).strip()
            grade_raw = item.get("grade")
        else:
            q_text = str(item).strip()
            subject = ""
            grade_raw = None
        if not q_text:
            continue
        grade = str(grade_raw).strip() if grade_raw is not None else ""
        bad_key = (q_text, subject, grade)
        if bad_key in bad_seen:
            continue
        bad_seen.add(bad_key)
        bad_entry = {"q": q_text}
        if subject:
            bad_entry["subject"] = subject
        if grade:
            bad_entry["grade"] = int(grade) if grade.isdigit() else grade
        out["bad"].append(bad_entry)

    if len(out["bad"]) > 100:
        out["bad"] = out["bad"][-100:]
    return out

def _merge_ratings(base_data, extra_data):
    base = _normalize_ratings(base_data)
    extra = _normalize_ratings(extra_data)

    merged_good = []
    seen_good = set()
    for src in (base["good"], extra["good"]):
        for q in src:
            q_text = str(q.get("q", "")).strip()
            if not q_text or q_text in seen_good:
                continue
            seen_good.add(q_text)
            merged_good.append(q)

    merged_bad = []
    seen_bad = set()
    for src in (base["bad"], extra["bad"]):
        for item in src:
            if not isinstance(item, dict):
                continue
            q_text = str(item.get("q", "")).strip()
            subject = str(item.get("subject", "")).strip()
            grade_raw = item.get("grade")
            grade = str(grade_raw).strip() if grade_raw is not None else ""
            bad_key = (q_text, subject, grade)
            if not q_text or bad_key in seen_bad:
                continue
            seen_bad.add(bad_key)
            entry = {"q": q_text}
            if subject:
                entry["subject"] = subject
            if grade:
                entry["grade"] = int(grade) if grade.isdigit() else grade
            merged_bad.append(entry)

    if len(merged_bad) > 100:
        merged_bad = merged_bad[-100:]
    return {"good": merged_good, "bad": merged_bad}

def _make_bad_entry(q_text, subject, grade):
    entry = {"q": str(q_text or "").strip()}
    subj = str(subject or "").strip()
    if subj:
        entry["subject"] = subj
    try:
        entry["grade"] = int(grade)
    except Exception:
        if grade is not None and str(grade).strip():
            entry["grade"] = str(grade).strip()
    return entry

def _bad_entry_key(item):
    if not isinstance(item, dict):
        return ("", "", "")
    q_text = str(item.get("q", "")).strip()
    subject = str(item.get("subject", "")).strip()
    grade_raw = item.get("grade")
    grade = str(grade_raw).strip() if grade_raw is not None else ""
    return (q_text, subject, grade)

def _is_bad_question(q_text, subject, grade):
    target = _make_bad_entry(q_text, subject, grade)
    target_q = str(target.get("q", "")).strip()
    if not target_q:
        return False
    target_subject = str(target.get("subject", "")).strip()
    target_grade = str(target.get("grade", "")).strip()
    for item in quiz_ratings.get("bad", []):
        if not isinstance(item, dict):
            continue
        q = str(item.get("q", "")).strip()
        if q != target_q:
            continue
        s = str(item.get("subject", "")).strip()
        g = str(item.get("grade", "")).strip()
        if s and g:
            if s == target_subject and g == target_grade:
                return True
        else:
            # legacy unscoped bad entry
            return True
    return False

def _firebase_ratings_url():
    if not FIREBASE_DB_URL:
        return None
    path = FIREBASE_RATINGS_PATH or "quiz_ratings/shared"
    url = f"{FIREBASE_DB_URL}/{path}.json"
    if FIREBASE_AUTH_TOKEN:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}auth={urllib.parse.quote(FIREBASE_AUTH_TOKEN)}"
    return url

def _firebase_load_ratings():
    url = _firebase_ratings_url()
    if not url:
        return None
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as res:
            payload = res.read().decode("utf-8")
        if not payload:
            return {"good": [], "bad": []}
        data = json.loads(payload)
        return _normalize_ratings(data)
    except Exception as e:
        print(f"[Firebase load error] {e}")
        return None

def _firebase_save_ratings(data):
    url = _firebase_ratings_url()
    if not url:
        return False
    try:
        body = json.dumps(_normalize_ratings(data), ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="PUT")
        req.add_header("Content-Type", "application/json; charset=utf-8")
        with urllib.request.urlopen(req, timeout=5) as res:
            _ = res.read()
        return True
    except Exception as e:
        print(f"[Firebase save error] {e}")
        return False

def load_ratings():
    global quiz_ratings
    local_data = {"good": [], "bad": []}
    if os.path.exists(RATING_FILE):
        try:
            with open(RATING_FILE, 'r', encoding='utf-8') as f:
                local_data = json.load(f)
        except: pass
    quiz_ratings = _normalize_ratings(local_data)

    remote_data = _firebase_load_ratings()
    if remote_data is not None:
        quiz_ratings = _merge_ratings(quiz_ratings, remote_data)
        # ローカルに同期済みキャッシュを残す
        try:
            with open(RATING_FILE, 'w', encoding='utf-8') as f:
                json.dump(quiz_ratings, f, indent=2, ensure_ascii=False)
        except:
            pass

def save_ratings():
    global quiz_ratings
    quiz_ratings = _normalize_ratings(quiz_ratings)
    try:
        with open(RATING_FILE, 'w', encoding='utf-8') as f:
            json.dump(quiz_ratings, f, indent=2, ensure_ascii=False)
    except: pass
    if _firebase_ratings_url():
        # 競合時の取りこぼしを減らすため、保存前に一度リモートとマージしてからPUT
        remote_data = _firebase_load_ratings()
        if remote_data is not None:
            quiz_ratings = _merge_ratings(remote_data, quiz_ratings)
            try:
                with open(RATING_FILE, 'w', encoding='utf-8') as f:
                    json.dump(quiz_ratings, f, indent=2, ensure_ascii=False)
            except:
                pass
        _firebase_save_ratings(quiz_ratings)

load_ratings()

GENERATION_REJECT_LOG_FILE = "quiz_generation_reject_log.jsonl"
RECENT_GRADE_REJECT_WINDOW = 240
recent_grade_fit_rejections = deque(maxlen=RECENT_GRADE_REJECT_WINDOW)

def append_generation_source_log(pid, quiz, subject, grade, difficulty):
    if not isinstance(quiz, dict):
        return
    q_text = str(quiz.get("q") or "").strip()
    if not q_text:
        return
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    src = str(quiz.get("src") or "UNKNOWN")
    preview = q_text[:60] + ("..." if len(q_text) > 60 else "")
    print(
        f"[AI生成] {timestamp} | P{int(pid)} | src={src} | subject={subject} | grade={grade} | diff={difficulty} | q={preview}",
        flush=True
    )

# --- 診断モード設定 ---
def _grade_fit_reason_bucket(reason):
    text = str(reason or "")
    if "one-step word problem" in text:
        return "math_one_step"
    if "simple vocabulary drill" in text:
        return "jp_simple_vocab"
    if "lower-grade math included upper-grade topic" in text:
        return "math_too_advanced_for_low_grade"
    if "grade-fit score" in text:
        return "low_score"
    return "other"

def _record_grade_fit_rejection(subject, grade, reason):
    try:
        grade_value = int(grade)
    except Exception:
        grade_value = grade
    recent_grade_fit_rejections.append({
        "subject": str(subject or ""),
        "grade": grade_value,
        "reason": str(reason or ""),
        "bucket": _grade_fit_reason_bucket(reason),
    })

def _load_recent_grade_fit_rejections():
    recent_grade_fit_rejections.clear()
    if not os.path.exists(GENERATION_REJECT_LOG_FILE):
        return
    try:
        with open(GENERATION_REJECT_LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()[-RECENT_GRADE_REJECT_WINDOW:]
    except Exception:
        return

    for line in lines:
        try:
            item = json.loads(line)
        except Exception:
            continue
        subject = str(item.get("subject") or "")
        grade = item.get("grade")
        reason = str(item.get("reason") or "")
        if not subject or grade is None or not reason:
            continue
        _record_grade_fit_rejection(subject, grade, reason)

def append_generation_reject_log(pid, quiz, subject, grade, difficulty, reason):
    if not isinstance(quiz, dict):
        return
    q_text = str(quiz.get("q") or "").strip()
    if not q_text:
        return
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    src = str(quiz.get("src") or "UNKNOWN")
    preview = q_text[:60] + ("..." if len(q_text) > 60 else "")
    print(
        f"[AI弾き] {timestamp} | P{int(pid)} | src={src} | subject={subject} | grade={grade} | diff={difficulty} | reason={reason} | q={preview}",
        flush=True
    )
    try:
        with open(GENERATION_REJECT_LOG_FILE, "a", encoding="utf-8") as f:
            json.dump({
                "timestamp": timestamp,
                "player_id": int(pid),
                "source": src,
                "subject": subject,
                "grade": grade,
                "difficulty": difficulty,
                "reason": reason,
                "question": q_text,
            }, f, ensure_ascii=False)
            f.write("\n")
    except Exception:
        pass
    _record_grade_fit_rejection(subject, grade, reason)

_load_recent_grade_fit_rejections()

ASSESSMENT_QUESTION_COUNT = 5 # 1教科あたりの問題数
ASSESSMENT_SUBJECTS = ["算数", "理科", "国語"] # 診断する教科の順番

# ----------------- 問題バッファ -----------------
QUIZ_BUFFER_SIZE = 10
quiz_buffers = {1: deque(), 2: deque()}
seen_questions = {1: set(), 2: set()}
play_histories = {1: [], 2: []} # プロンプト生成用の直近履歴

SIMILARITY_RECENT_WINDOW = 14
SIMILARITY_BIGRAM_THRESHOLD = 0.58
MAX_SAME_GENRE_STREAK_IN_BUFFER = 1
IMAGE_QUESTION_INSERT_RATE = 0.22
try:
    AI_IMAGE_QUESTION_RATE = max(0.0, min(0.4, float(os.getenv("AI_IMAGE_QUESTION_RATE", "0.10"))))
except ValueError:
    AI_IMAGE_QUESTION_RATE = 0.10
IMAGE_QUIZ_MODE = os.getenv("IMAGE_QUIZ_MODE", "TEXT_ONLY").upper()
if IMAGE_QUIZ_MODE not in {"AUTO", "PRIORITY", "TEXT_ONLY"}:
    IMAGE_QUIZ_MODE = "TEXT_ONLY"
QUESTION_IMAGE_MAX_WIDTH_RATIO = 0.40
QUESTION_IMAGE_MAX_HEIGHT_RATIO = 0.23
CHOICE_IMAGE_MAX_WIDTH_RATIO = 0.72
CHOICE_IMAGE_MAX_HEIGHT_RATIO = 0.42
question_image_cache = {}
GENERATED_IMAGE_DIR = os.path.join(os.getcwd(), "generated_question_images")

BUILTIN_IMAGE_QUESTIONS = {
    "算数": {
        "4": [
            {
                "q": "画像の色がぬられている部分は、全体の何分のいくつですか。",
                "c": ["3/4", "1/4"],
                "a": 0,
                "e": "4つに分かれたうち、3つがぬられているので 3/4 です。",
                "image": "question_images/fraction_bar_3_4.png"
            }
        ],
        "5": [
            {
                "q": "画像の三角形の面積は何cm2ですか。",
                "c": ["6", "12"],
                "a": 0,
                "e": "三角形の面積は 底辺×高さ÷2 なので、4×3÷2=6 です。",
                "image": "question_images/triangle_area_4_3.png"
            }
        ]
    },
    "理科": {
        "4": [
            {
                "q": "画像の回路で、豆電球を光らせるために必要なのはどれですか。",
                "c": ["回路を1つにつなぐ", "電池をはずす"],
                "a": 0,
                "e": "電池、導線、豆電球が切れ目なく1つの回路になると光ります。",
                "image": "question_images/circuit_closed.png"
            }
        ],
        "5": [
            {
                "q": "画像の植物で、日光を受けて養分をつくる部分はどこですか。",
                "c": ["葉", "根"],
                "a": 0,
                "e": "葉は日光を受けて養分をつくります。",
                "image": "question_images/plant_parts.png"
            }
        ]
    }
}

buffer_lock = threading.Lock()
api_threads = []
stop_event = threading.Event()
NUM_API_WORKERS = 4
generation_inflight = {1: 0, 2: 0}
generation_started_at = {1: None, 2: None}
PRELOAD_ESTIMATED_SECONDS = 5.0
preload_started_at = 0.0
grade_fit_reject_streak = {1: 0, 2: 0}
GRADE_FIT_RELAX_STEP = 0.12
GRADE_FIT_MAX_RELAX = 0.90
FORCE_OFFLINE_FILL_AFTER_SECONDS = 18.0

# UI State
# TITLE -> SELECT -> PRELOAD -> IN_GAME -> RESULTS
GAME_STATE = "TITLE"
current_editing_pid = 1

def _enable_high_dpi_awareness():
    if not sys.platform.startswith("win"):
        return
    os.environ.setdefault("SDL_WINDOWS_DPI_AWARENESS", "permonitorv2")
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

DISPLAY_FLAGS = pygame.RESIZABLE | pygame.DOUBLEBUF
if hasattr(pygame, "HWSURFACE"):
    DISPLAY_FLAGS |= pygame.HWSURFACE

def _create_display(size):
    try:
        return pygame.display.set_mode(size, DISPLAY_FLAGS, vsync=1)
    except TypeError:
        return pygame.display.set_mode(size, DISPLAY_FLAGS)

# ----------------- Pygame 初期化 -----------------
_enable_high_dpi_awareness()
pygame.init(); pygame.font.init()
# 日本語入力対応のため、IMEイベントを許可
pygame.key.start_text_input() 
screen = _create_display((INITIAL_SCREEN_WIDTH, INITIAL_SCREEN_HEIGHT))
pygame.display.set_caption("AI脱出クイズ (Final)")
clock = pygame.time.Clock()

# ===================== テキスト折返し =====================
def render_text_wrapped(text, max_width, font_size, color=BLACK, font_name="Meiryo"):
    try: font = pygame.font.SysFont(font_name, font_size)
    except: font = pygame.font.Font(None, font_size)
    lines, cur = [], ""
    for ch in text:
        test = cur + ch
        if font.size(test)[0] <= int(max_width): cur = test
        else: lines.append(cur); cur = ch
    if cur: lines.append(cur)
    if not lines: return pygame.Surface((1,1), pygame.SRCALPHA)
    rendered = [font.render(line, True, color) for line in lines]
    total_h = sum(r.get_height() for r in rendered)
    out = pygame.Surface((int(max_width), total_h), pygame.SRCALPHA)
    y=0
    for r in rendered: out.blit(r,(0,y)); y+=r.get_height()
    return out

def get_ui_font(size, bold=False):
    preferred = ["Meiryo", "Yu Gothic UI", "Yu Gothic", "MS Gothic"]
    for name in preferred:
        try:
            matched = pygame.font.match_font(name)
            if matched:
                return pygame.font.SysFont(name, size, bold=bold)
        except Exception:
            pass
    return pygame.font.Font(None, size)

def resource_path(rel_path):
    if not rel_path:
        return ""
    if os.path.isabs(rel_path):
        return rel_path
    base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, rel_path)

def _get_quiz_image_ref(quiz):
    if not isinstance(quiz, dict):
        return ""
    image_ref = quiz.get("image") or quiz.get("img") or quiz.get("image_path")
    if isinstance(image_ref, dict):
        return image_ref.get("path") or image_ref.get("url") or ""
    return str(image_ref or "").strip()

def load_question_image(image_ref):
    image_ref = str(image_ref or "").strip()
    if not image_ref:
        return None
    if image_ref in question_image_cache:
        return question_image_cache[image_ref]
    try:
        if image_ref.startswith("http://") or image_ref.startswith("https://"):
            with urllib.request.urlopen(image_ref, timeout=8) as res:
                image_bytes = res.read()
            surf = pygame.image.load(io.BytesIO(image_bytes)).convert_alpha()
        else:
            surf = pygame.image.load(resource_path(image_ref)).convert_alpha()
        question_image_cache[image_ref] = surf
        return surf
    except Exception as e:
        print(f"[Image load error] {image_ref}: {e}")
        question_image_cache[image_ref] = None
        return None

def scale_question_image(surf, max_w, max_h):
    if not surf:
        return None
    sw, sh = surf.get_size()
    if sw <= 0 or sh <= 0:
        return None
    scale = min(max_w / sw, max_h / sh, 1.0)
    new_size = (max(1, int(sw * scale)), max(1, int(sh * scale)))
    if new_size == (sw, sh):
        return surf
    return pygame.transform.smoothscale(surf, new_size)

def _get_choice_image_refs(quiz):
    if not isinstance(quiz, dict):
        return ["", ""]
    refs = quiz.get("choice_images") or quiz.get("choice_image_paths") or []
    if isinstance(refs, dict):
        refs = [refs.get("0") or refs.get("left") or "", refs.get("1") or refs.get("right") or ""]
    if not isinstance(refs, (list, tuple)):
        refs = [refs]
    refs = [str(x or "").strip() for x in refs[:2]]
    while len(refs) < 2:
        refs.append("")
    return refs

def _ensure_generated_image_dir():
    try:
        os.makedirs(GENERATED_IMAGE_DIR, exist_ok=True)
    except Exception as e:
        print(f"[Image dir error] {e}")

def _safe_cache_prefix(prefix):
    prefix = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(prefix or "img"))
    return prefix[:40] or "img"

def _image_extension_from_mime(mime_type):
    mime = str(mime_type or "").lower()
    if "jpeg" in mime or "jpg" in mime:
        return ".jpg"
    if "webp" in mime:
        return ".webp"
    return ".png"

def _extract_generated_inline_image(payload):
    for cand in payload.get("candidates", []) or []:
        content = cand.get("content", {}) or {}
        for part in content.get("parts", []) or []:
            inline = part.get("inlineData") or part.get("inline_data") or {}
            data = inline.get("data")
            if data:
                mime = inline.get("mimeType") or inline.get("mime_type") or "image/png"
                return data, mime
    return None, None

def _generate_gemini_image(prompt, cache_prefix):
    if not GEMINI_API_KEY or "YOUR" in GEMINI_API_KEY:
        return None
    prompt = str(prompt or "").strip()
    if not prompt:
        return None

    _ensure_generated_image_dir()
    digest = hashlib.sha256(f"{GEMINI_IMAGE_MODEL}\n{prompt}".encode("utf-8")).hexdigest()[:24]
    safe_prefix = _safe_cache_prefix(cache_prefix)
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        cached = os.path.join(GENERATED_IMAGE_DIR, f"{safe_prefix}_{digest}{ext}")
        if os.path.exists(cached):
            return os.path.abspath(cached)

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{urllib.parse.quote(GEMINI_IMAGE_MODEL, safe='')}:generateContent"
        f"?key={urllib.parse.quote(GEMINI_API_KEY, safe='')}"
    )
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"]
        }
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as res:
            raw = json.loads(res.read().decode("utf-8"))
        b64_data, mime = _extract_generated_inline_image(raw)
        if not b64_data:
            print(f"[Gemini Image Error] No inline image returned for {safe_prefix}")
            return None
        image_bytes = base64.b64decode(b64_data)
        ext = _image_extension_from_mime(mime)
        out_path = os.path.abspath(os.path.join(GENERATED_IMAGE_DIR, f"{safe_prefix}_{digest}{ext}"))
        with open(out_path, "wb") as f:
            f.write(image_bytes)
        return out_path
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", errors="ignore")
        except Exception:
            detail = str(e)
        print(f"[Gemini Image HTTP Error] {detail[:240]}")
    except Exception as e:
        print(f"[Gemini Image Error] {e}")
    return None

def _image_prompt_style(extra):
    return (
        "Create a clean elementary-school worksheet illustration. "
        "White background. Centered composition. Flat vector style. "
        "Thick black outlines. Clear shapes. No text, no letters, no numbers, "
        "no speech bubbles, no watermark. "
        + str(extra or "").strip()
    )

def _image_mode_label():
    return {
        "AUTO": "AUTO / \u6a19\u6e96",
        "PRIORITY": "PRIORITY / \u753b\u50cf\u512a\u5148",
        "TEXT_ONLY": "TEXT ONLY / \u6587\u5b57\u4e2d\u5fc3",
    }.get(IMAGE_QUIZ_MODE, "AUTO / \u6a19\u6e96")

def _current_ai_image_rate():
    if IMAGE_QUIZ_MODE == "TEXT_ONLY":
        return 0.0
    if IMAGE_QUIZ_MODE == "PRIORITY":
        return max(0.35, AI_IMAGE_QUESTION_RATE)
    return max(0.18, AI_IMAGE_QUESTION_RATE)

def _current_builtin_image_rate():
    if IMAGE_QUIZ_MODE == "TEXT_ONLY":
        return 0.0
    if IMAGE_QUIZ_MODE == "PRIORITY":
        return max(0.45, IMAGE_QUESTION_INSERT_RATE)
    return max(0.30, IMAGE_QUESTION_INSERT_RATE)

AI_IMAGE_QUIZ_TEMPLATES = [
    {
        "id": "math_diag_split",
        "subject": "\u7b97\u6570",
        "min_grade": 4,
        "kind": "choice_images",
        "questions": [
            "\u6b63\u65b9\u5f62\u3092\u5bfe\u89d2\u7dda\u30671\u672c\u5207\u3063\u305f\u3068\u304d\u306b\u3067\u304d\u308b\u56f3\u5f62\u3068\u3057\u3066\u6b63\u3057\u3044\u306e\u306f\u3069\u3061\u3089\u3067\u3059\u304b\u3002",
            "\u5bfe\u89d2\u7dda\u30671\u56de\u3060\u3051\u5207\u3063\u305f\u56f3\u3068\u3057\u3066\u5408\u3063\u3066\u3044\u308b\u306e\u306f\u3069\u3061\u3089\u3067\u3059\u304b\u3002",
        ],
        "choices": ["A", "B"],
        "answer": 0,
        "explanation": "\u6b63\u65b9\u5f62\u3092\u5bfe\u89d2\u7dda\u3067\u5207\u308b\u3068\u30012\u3064\u306e\u5408\u540c\u306a\u76f4\u89d2\u4e8c\u7b49\u8fba\u4e09\u89d2\u5f62\u306b\u5206\u304b\u308c\u307e\u3059\u3002",
        "choice_prompts": [
            _image_prompt_style("Show the result of cutting one square along a single diagonal: two congruent right isosceles triangles separated and easy to understand."),
            _image_prompt_style("Show an incorrect result for cutting one square once: two shapes that are not diagonal halves of a square, such as uneven rectangles or mismatched polygons."),
        ],
    },
    {
        "id": "math_line_symmetry",
        "subject": "\u7b97\u6570",
        "min_grade": 5,
        "kind": "choice_images",
        "questions": [
            "\u7dda\u5bfe\u79f0\u306a\u56f3\u5f62\u306f\u3069\u3061\u3089\u3067\u3059\u304b\u3002",
            "\u771f\u3093\u4e2d\u3067\u6298\u308b\u3068\u91cd\u306a\u308b\u56f3\u5f62\u3092\u9078\u3073\u307e\u3057\u3087\u3046\u3002",
        ],
        "choices": ["A", "B"],
        "answer": 0,
        "explanation": "\u7dda\u5bfe\u79f0\u306a\u56f3\u5f62\u306f\u3001\u5bfe\u79f0\u306e\u8ef8\u3067\u6298\u308b\u3068\u5de6\u53f3\u304c\u91cd\u306a\u308a\u307e\u3059\u3002",
        "choice_prompts": [
            _image_prompt_style("Draw one simple line-symmetric shape for an elementary worksheet, such as a symmetric kite or symmetric polygon."),
            _image_prompt_style("Draw one clearly non-symmetric shape for an elementary worksheet, such as an irregular quadrilateral or uneven polygon."),
        ],
    },
    {
        "id": "science_circuit_compare",
        "subject": "\u7406\u79d1",
        "min_grade": 4,
        "kind": "main_image",
        "questions": [
            "\u753b\u50cf\u306e\u5de6\u53f3\u306e\u56f3\u306e\u3046\u3061\u3001\u8c46\u96fb\u7403\u304c\u5149\u308b\u3064\u306a\u304e\u65b9\u306f\u3069\u3061\u3089\u3067\u3059\u304b\u3002",
            "\u753b\u50cf\u3092\u898b\u3066\u3001\u96fb\u6c17\u304c\u6d41\u308c\u308b\u56de\u8def\u3092\u9078\u3073\u307e\u3057\u3087\u3046\u3002",
        ],
        "choices": ["\u5de6\u306e\u56f3", "\u53f3\u306e\u56f3"],
        "answer": 0,
        "explanation": "\u56de\u8def\u304c\u9014\u5207\u308c\u305a\u306b\u3064\u306a\u304c\u3063\u3066\u3044\u308b\u3068\u96fb\u6c17\u304c\u6d41\u308c\u3001\u8c46\u96fb\u7403\u304c\u5149\u308a\u307e\u3059\u3002",
        "image_prompt": _image_prompt_style(
            "Split the image into a left panel and a right panel. "
            "Left panel: one battery, wires, and one light bulb connected in a fully closed circuit. "
            "Right panel: one battery, wires, and one light bulb with a visible gap so the circuit is open. "
            "Make the two panels easy to compare. No labels."
        ),
    },
    {
        "id": "math_fraction_compare",
        "subject": "\u7b97\u6570",
        "min_grade": 4,
        "kind": "main_image",
        "questions": [
            "\u753b\u50cf\u306e2\u3064\u306e\u5206\u6570\u30d0\u30fc\u3092\u6bd4\u3079\u3066\u3001\u5927\u304d\u3044\u65b9\u3092\u9078\u3073\u307e\u3057\u3087\u3046\u3002",
            "\u56f3\u3092\u898b\u3066\u3001\u3069\u3061\u306e\u65b9\u304c\u3088\u308a\u591a\u304f\u5857\u3089\u308c\u3066\u3044\u308b\u304b\u7b54\u3048\u307e\u3057\u3087\u3046\u3002",
        ],
        "choices": ["\u5de6\u306e\u307b\u3046", "\u53f3\u306e\u307b\u3046"],
        "answer": 1,
        "explanation": "\u5206\u6570\u306f\u3001\u5857\u3089\u308c\u3066\u3044\u308b\u90e8\u5206\u306e\u5927\u304d\u3055\u3092\u6bd4\u3079\u3066\u5224\u65ad\u3057\u307e\u3059\u3002",
        "image_prompt": _image_prompt_style(
            "Split the image into left and right fraction bars. "
            "Left: a bar divided into 4 equal parts with 2 parts shaded. "
            "Right: a bar divided into 4 equal parts with 3 parts shaded. "
            "Make both bars horizontal and easy to compare."
        ),
    },
    {
        "id": "math_angle_compare",
        "subject": "\u7b97\u6570",
        "min_grade": 4,
        "kind": "choice_images",
        "questions": [
            "\u76f4\u89d2\u3088\u308a\u5927\u304d\u3044\u89d2\u306f\u3069\u3061\u3089\u3067\u3059\u304b\u3002",
            "\u920d\u89d2\u3092\u8868\u3057\u3066\u3044\u308b\u56f3\u3092\u9078\u3073\u307e\u3057\u3087\u3046\u3002",
        ],
        "choices": ["A", "B"],
        "answer": 0,
        "explanation": "\u76f4\u89d2\u3088\u308a\u5927\u304d\u304f180\u5ea6\u3088\u308a\u5c0f\u3055\u3044\u89d2\u3092\u920d\u89d2\u3068\u3044\u3044\u307e\u3059\u3002",
        "choice_prompts": [
            _image_prompt_style("Draw one clear obtuse angle around 120 degrees using two black rays from one vertex."),
            _image_prompt_style("Draw one clear acute angle around 45 degrees using two black rays from one vertex."),
        ],
    },
    {
        "id": "science_magnet_compare",
        "subject": "\u7406\u79d1",
        "min_grade": 3,
        "kind": "choice_images",
        "questions": [
            "\u78c1\u77f3\u306b\u304f\u3063\u3064\u304f\u3082\u306e\u306f\u3069\u3061\u3089\u3067\u3059\u304b\u3002",
            "\u78c1\u77f3\u3067\u5f15\u304d\u3064\u3051\u3089\u308c\u308b\u3082\u306e\u3092\u9078\u3073\u307e\u3057\u3087\u3046\u3002",
        ],
        "choices": ["A", "B"],
        "answer": 0,
        "explanation": "\u9244\u3067\u3067\u304d\u305f\u3082\u306e\u306f\u78c1\u77f3\u306b\u304f\u3063\u3064\u304d\u3084\u3059\u3044\u3067\u3059\u3002",
        "choice_prompts": [
            _image_prompt_style("Draw a simple metal paper clip alone on a white background."),
            _image_prompt_style("Draw a wooden block alone on a white background."),
        ],
    },
    {
        "id": "science_plant_compare",
        "subject": "\u7406\u79d1",
        "min_grade": 3,
        "kind": "choice_images",
        "questions": [
            "\u7a2e\u304b\u3089\u82bd\u304c\u51fa\u305f\u76f4\u5f8c\u306e\u69d8\u5b50\u306b\u8fd1\u3044\u306e\u306f\u3069\u3061\u3089\u3067\u3059\u304b\u3002",
            "\u767a\u82bd\u3057\u305f\u3070\u304b\u308a\u306e\u690d\u7269\u3092\u8868\u3057\u3066\u3044\u308b\u56f3\u3092\u9078\u3073\u307e\u3057\u3087\u3046\u3002",
        ],
        "choices": ["A", "B"],
        "answer": 0,
        "explanation": "\u767a\u82bd\u3057\u305f\u3070\u304b\u308a\u306e\u690d\u7269\u306f\u3001\u5c0f\u3055\u3044\u82bd\u3068\u5b50\u8449\u304c\u898b\u3048\u307e\u3059\u3002",
        "choice_prompts": [
            _image_prompt_style("Draw a newly sprouted bean seedling with two small cotyledons and a short stem."),
            _image_prompt_style("Draw a mature flowering plant with many leaves and blossoms."),
        ],
    },
    {
        "id": "japanese_scene_match",
        "subject": "\u56fd\u8a9e",
        "min_grade": 1,
        "kind": "main_image",
        "questions": [
            "\u753b\u50cf\u306e\u69d8\u5b50\u306b\u5408\u3046\u6587\u3092\u9078\u3073\u307e\u3057\u3087\u3046\u3002",
            "\u7d75\u3068\u3042\u3063\u3066\u3044\u308b\u3076\u3093\u306f\u3069\u3061\u3089\u3067\u3059\u304b\u3002",
        ],
        "choices": ["\u304a\u3068\u3053\u306e\u3053\u304c\u307b\u3093\u3092\u3088\u3093\u3067\u3044\u308b\u3002", "\u304a\u3068\u3053\u306e\u3053\u304c\u307c\u30fc\u308b\u3092\u3051\u3063\u3066\u3044\u308b\u3002"],
        "answer": 0,
        "explanation": "\u7d75\u306e\u4eba\u7269\u304c\u3057\u3066\u3044\u308b\u3053\u3068\u3068\u3001\u6587\u306e\u52d5\u4f5c\u304c\u4e00\u81f4\u3059\u308b\u304b\u3092\u898b\u307e\u3059\u3002",
        "image_prompt": _image_prompt_style(
            "Draw one elementary-school boy sitting and reading a book quietly at a desk. "
            "No ball, no sports equipment, no text."
        ),
    },
    {
        "id": "japanese_emotion_scene",
        "subject": "\u56fd\u8a9e",
        "min_grade": 2,
        "kind": "main_image",
        "questions": [
            "\u753b\u50cf\u306e\u4eba\u7269\u306e\u6c17\u6301\u3061\u3068\u3057\u3066\u3088\u308a\u5408\u3046\u3082\u306e\u3092\u9078\u3073\u307e\u3057\u3087\u3046\u3002",
            "\u7d75\u3092\u898b\u3066\u3001\u4eba\u7269\u306e\u3088\u3046\u3059\u306b\u3042\u3063\u3066\u3044\u308b\u8a00\u8449\u3092\u9078\u3073\u307e\u3057\u3087\u3046\u3002",
        ],
        "choices": ["\u3046\u308c\u3057\u305d\u3046", "\u3068\u3066\u3082\u304a\u3053\u3063\u3066\u3044\u308b"],
        "answer": 0,
        "explanation": "\u8868\u60c5\u3084\u69d8\u5b50\u304b\u3089\u3001\u4eba\u7269\u306e\u6c17\u6301\u3061\u3092\u8aad\u307f\u53d6\u308b\u554f\u984c\u3067\u3059\u3002",
        "image_prompt": _image_prompt_style(
            "Draw one child happily receiving a small star sticker from a teacher. "
            "Show a clear smile and relaxed body language."
        ),
    },
]

def _pick_ai_image_template(subject, grade):
    candidates = [
        t for t in AI_IMAGE_QUIZ_TEMPLATES
        if t.get("subject") == subject and grade >= int(t.get("min_grade", 1))
    ]
    if not candidates:
        return None
    return random.choice(candidates)

def _build_ai_image_quiz(subject, grade, difficulty):
    template = _pick_ai_image_template(subject, grade)
    if not template:
        return None

    quiz = {
        "q": random.choice(template["questions"]),
        "c": list(template["choices"]),
        "a": int(template["answer"]),
        "e": template["explanation"],
        "src": "GeminiImage",
    }
    cache_base = f"{template['id']}_g{grade}"

    if template["kind"] == "choice_images":
        image_paths = []
        for idx, prompt in enumerate(template.get("choice_prompts", [])):
            path = _generate_gemini_image(prompt, f"{cache_base}_choice{idx}")
            if not path:
                return None
            image_paths.append(path)
        if len(image_paths) != 2:
            return None
        quiz["choice_images"] = image_paths
        return quiz

    if template["kind"] == "main_image":
        image_path = _generate_gemini_image(template.get("image_prompt", ""), f"{cache_base}_main")
        if not image_path:
            return None
        quiz["image"] = image_path
        return quiz

    return None

def _materialize_llm_image_quiz(quiz, cache_prefix):
    if not isinstance(quiz, dict):
        return None

    if IMAGE_QUIZ_MODE == "TEXT_ONLY":
        quiz.pop("image_prompt", None)
        quiz.pop("choice_image_prompts", None)
        quiz.pop("choice_image_prompt", None)
        quiz.pop("image", None)
        quiz.pop("choice_images", None)
        return quiz

    image_prompt = str(quiz.get("image_prompt") or "").strip()
    choice_prompts = quiz.get("choice_image_prompts") or quiz.get("choice_image_prompt") or []
    if isinstance(choice_prompts, dict):
        choice_prompts = [choice_prompts.get("0") or choice_prompts.get("left") or "", choice_prompts.get("1") or choice_prompts.get("right") or ""]
    if isinstance(choice_prompts, str):
        choice_prompts = [choice_prompts]
    if not isinstance(choice_prompts, (list, tuple)):
        choice_prompts = []
    choice_prompts = [str(x or "").strip() for x in choice_prompts[:2]]

    made_image = False
    if image_prompt:
        image_path = _generate_gemini_image(image_prompt, f"{cache_prefix}_main")
        if not image_path:
            return None
        quiz["image"] = image_path
        made_image = True

    if len(choice_prompts) == 2 and all(choice_prompts):
        choice_images = []
        for idx, prompt in enumerate(choice_prompts):
            image_path = _generate_gemini_image(prompt, f"{cache_prefix}_choice{idx}")
            if not image_path:
                return None
            choice_images.append(image_path)
        quiz["choice_images"] = choice_images
        made_image = True

    quiz.pop("image_prompt", None)
    quiz.pop("choice_image_prompts", None)
    quiz.pop("choice_image_prompt", None)
    return quiz if made_image else quiz

def _postprocess_llm_quizzes(quizzes, require_image=False):
    if not isinstance(quizzes, list):
        return None

    processed = []
    for idx, quiz in enumerate(quizzes):
        if not isinstance(quiz, dict):
            continue
        cache_prefix = f"llm_{quiz.get('src', 'quiz').lower()}_{idx}_{_safe_cache_prefix(quiz.get('q', 'q')[:24])}"
        quiz = _materialize_llm_image_quiz(quiz, cache_prefix)
        if not quiz:
            continue
        has_image = bool(_get_quiz_image_ref(quiz) or any(_get_choice_image_refs(quiz)))
        if require_image and not has_image:
            continue
        processed.append(quiz)
    return processed or None

# ===================== パーティクルクラス =====================
class Particle:
    def __init__(self, x, y, color):
        self.x = x; self.y = y; self.vx = random.uniform(-12, 12); self.vy = random.uniform(-18, -6)
        self.gravity = 0.6; self.size = random.randint(4, 12); self.color = color
        self.life = 1.0; self.decay = random.uniform(0.01, 0.03)
        self.angle = random.uniform(0, 360); self.spin = random.uniform(-20, 20)
    def update(self):
        self.x += self.vx; self.y += self.vy; self.vy += self.gravity; self.life -= self.decay; self.angle += self.spin; return self.life > 0
    def draw(self, surf):
        if self.life <= 0: return
        alpha = int(255 * self.life); s = pygame.Surface((self.size, self.size), pygame.SRCALPHA)
        pygame.draw.rect(s, (*self.color, alpha), (0,0,self.size,self.size))
        rotated_s = pygame.transform.rotate(s, self.angle); rect = rotated_s.get_rect(center=(self.x, self.y)); surf.blit(rotated_s, rect)

# ===================== オフライン問題 =====================
def load_offline_bank():
    try:
        with open("offline_bank.json", "r", encoding="utf-8") as f: return json.load(f)
    except: return {}

OFFLINE_BANK = load_offline_bank()

def offline_pick(subject, grade, prefer_image=False):
    grade_str = str(grade)
    arr = [dict(q, _local_src="OFFLINE") for q in OFFLINE_BANK.get(subject, {}).get(grade_str, [])]
    image_arr = [dict(q, _local_src="IMAGE") for q in BUILTIN_IMAGE_QUESTIONS.get(subject, {}).get(grade_str, [])]
    good_arr = [
        dict(q, _local_src="OFFLINE(???)")
        for q in quiz_ratings.get("good", [])
        if q.get("subject") == subject and str(q.get("grade")) == grade_str
    ]

    if prefer_image and image_arr:
        combined_arr = image_arr + arr + good_arr
    else:
        combined_arr = arr + image_arr + good_arr

    if not combined_arr:
        a = random.randint(2, 20)
        b = random.randint(1, 10)
        ans = a + b
        wrong = ans + random.choice([-2, -1, 1, 2])
        c = [str(ans), str(wrong)]
        random.shuffle(c)
        return {"q": f"?????? {a}+{b}", "c": c, "a": c.index(str(ans)), "e": f"{a}+{b}={ans}", "src": "OFFLINE"}

    ret = random.choice(combined_arr).copy()
    ret["src"] = ret.pop("_local_src", "OFFLINE")
    return ret

# ===================== LLM 出題設定 =====================
QUESTION_TYPES = {
    "算数": { 
        1: ["足し算", "引き算", "時計の読み方", "図形", "長さ比べ", "数の数え方"], 
        2: ["九九", "長さの単位(cm, m)", "かさ(L, dL)", "時刻と時間", "筆算", "簡単な分数"], 
        3: ["割り算", "小数", "分数", "円と球", "重さ(g, kg)", "表とグラフ"], 
        4: ["面積", "角度", "大きな数", "小数の計算", "分数の計算", "立方体と直方体"], 
        5: ["割合", "小数の掛け算・割り算", "分数の足し算・引き算", "体積", "平均", "合同な図形"], 
        6: ["比", "分数の掛け算・割り算", "速さ", "比例と反比例", "立体の体積", "データの活用"] 
    },
    "理科": { 
        1: ["身近な植物", "身近な生き物", "季節の草花", "虫", "どんぐりなどの木の実"], 
        2: ["野菜の育ち方", "ダンゴムシなどの虫", "季節の生き物", "天気", "おもちゃの仕組み"], 
        3: ["磁石の性質", "電気の通り道", "昆虫の体のつくり", "植物の育ち方", "太陽と影", "物の重さ"], 
        4: ["星と星座", "月の動き", "季節と生き物", "人の体のつくり(骨と筋肉)", "空気と水の性質", "乾電池と豆電球"], 
        5: ["メダカの誕生", "植物の発芽と成長", "天気の変化", "振り子の動き", "電磁石の性質", "流れる水の働き"], 
        6: ["人体のつくりと働き(呼吸・血液など)", "植物の養分(光合成)", "水溶液の性質", "物の燃え方", "てこの規則性", "地球と環境"] 
    },
    "国語": { 
        1: ["ひらがな", "カタカナ", "簡単な漢字", "物の名前", "挨拶の言葉", "数え方"], 
        2: ["漢字の読み書き", "反対の意味の言葉", "似た意味の言葉", "主語と述語", "様子を表す言葉"], 
        3: ["ローマ字", "ことわざ", "部首", "国語辞典の使い方", "修飾語", "送り仮名"], 
        4: ["慣用句", "敬語の基本", "つなぎ言葉(接続語)", "熟語の構成", "漢字の部首と意味"], 
        5: ["敬語(尊敬語・謙譲語・丁寧語)", "四字熟語", "同音異義語", "古典(竹取物語など)", "類義語と対義語"], 
        6: ["座右の銘", "短歌・俳句", "歴史的仮名遣い", "難しい熟語", "表現の工夫(比喩など)", "言葉の由来"] 
    }
}

GRADE_SCOPE_GUIDES = {
    "算数": {
        1: {
            "must": "20までのたし算・ひき算、数の大小、簡単な時計や図形",
            "avoid": "分数・小数・割合・速さ・体積のような上級内容",
        },
        2: {
            "must": "九九、長さ・かさ、時刻、簡単な表の読み取り",
            "avoid": "割合・速さ・体積・比のような高学年中心の内容",
        },
        3: {
            "must": "かけ算、わり算、分数の入口、円と球、長さ・重さ",
            "avoid": "割合・比・複雑な速さや高難度の面積問題",
        },
        4: {
            "must": "大きな数、面積、角、折れ線グラフ、小数・分数",
            "avoid": "比や高度な割合など高学年中心の内容",
        },
        5: {
            "must": "小数と分数の計算、割合、平均、単位量あたり、体積、図形の性質",
            "avoid": "中学レベルの方程式や座標",
        },
        6: {
            "must": "比、割合、速さ、拡大図と縮図、円の面積、資料の見方、複数段階の判断",
            "avoid": "低学年向けの一桁計算や単純な個数計算だけの問題",
        },
    },
    "理科": {
        3: {
            "must": "植物やこん虫、光、音、磁石、電気など身近な観察内容",
            "avoid": "人体のしくみや水よう液など高学年中心の内容",
        },
        4: {
            "must": "電流、天気、月や星、温度、金属や空気と水の変化",
            "avoid": "消化や血液循環、地層など6年寄りの内容",
        },
        5: {
            "must": "発芽と成長、流れる水、天気、ふりこ、てこ、電磁石、ものの溶け方",
            "avoid": "中学理科レベルの化学式や専門用語",
        },
        6: {
            "must": "人体、水よう液、月と太陽、土地のつくり、てこ、発電や電気の利用",
            "avoid": "中学以降の専門計算や抽象理論",
        },
    },
    "国語": {
        1: {
            "must": "ひらがな、かたかな、やさしい言葉、短い文の読解",
            "avoid": "敬語や抽象的な文法用語",
        },
        2: {
            "must": "語彙、短文読解、主語と述語の入口、漢字の基本",
            "avoid": "高度な敬語や長文要旨問題",
        },
        3: {
            "must": "漢字、ことわざ・慣用句の入口、段落の読み取り、修飾語の基本",
            "avoid": "難しい敬語運用や抽象的な評論読解",
        },
        4: {
            "must": "文法の基本、漢字、要点把握、段落や接続の理解",
            "avoid": "中学寄りの古典文法や難解な評論",
        },
        5: {
            "must": "敬語、文の組み立て、熟語、資料や文章の読み取り、理由説明",
            "avoid": "低学年向けの単純な語句暗記だけの問題",
        },
        6: {
            "must": "敬語、表現の効果、文章構成、要旨把握、漢字や語句の使い分け",
            "avoid": "低学年向けの単純な読みだけの問題",
        },
    },
}

SCIENCE_GRADE_KEYWORDS = {
    3: ["植物", "昆虫", "チョウ", "ゴム", "風", "光", "音", "磁石", "電気", "日なた", "日かげ"],
    4: ["電流", "乾電池", "直列", "並列", "天気", "月", "星", "空気", "水", "温度", "金属"],
    5: ["発芽", "受粉", "流れる水", "天気の変化", "ふりこ", "てこ", "電磁石", "ものの溶け方"],
    6: ["消化", "呼吸", "血液", "水よう液", "月と太陽", "地層", "火山", "発電", "電気の利用", "てこ"],
}

JAPANESE_GRADE_KEYWORDS = {
    1: ["ひらがな", "カタカナ", "ことば", "文", "漢字"],
    2: ["漢字", "主語", "述語", "ことば", "文しょう"],
    3: ["漢字", "ことわざ", "慣用句", "段落", "修飾語", "こそあど"],
    4: ["漢字", "段落", "要点", "接続語", "修飾語", "文法"],
    5: ["敬語", "熟語", "主語", "述語", "修飾語", "要旨", "段落", "資料", "理由", "文脈"],
    6: ["敬語", "要旨", "文章構成", "表現", "熟語", "漢字", "理由", "文脈", "心情", "筆者"],
}

GRADE_FIT_SCORE_THRESHOLDS = {
    "算数": {1: 0.00, 2: 0.15, 3: 0.55, 4: 0.85, 5: 1.10, 6: 1.28},
    "理科": {1: 0.00, 2: 0.00, 3: 0.30, 4: 0.46, 5: 0.60, 6: 0.68},
    "国語": {1: 0.05, 2: 0.15, 3: 0.25, 4: 0.42, 5: 0.62, 6: 0.70},
}

GRADE_FIT_BUCKET_BOOSTS = {
    "math_one_step": 0.08,
    "jp_simple_vocab": 0.06,
    "math_too_advanced_for_low_grade": 0.05,
    "low_score": 0.03,
}

def _adaptive_grade_fit_threshold_boost(subject, grade, reason_bucket):
    try:
        g_int = int(grade)
    except Exception:
        return 0.0

    subject_key = str(subject or "")
    bucket_key = str(reason_bucket or "other")
    same_grade_rejects = 0
    same_bucket_rejects = 0
    for item in recent_grade_fit_rejections:
        if item.get("subject") != subject_key:
            continue
        try:
            item_grade = int(item.get("grade", -999))
        except Exception:
            continue
        if item_grade != g_int:
            continue
        same_grade_rejects += 1
        if item.get("bucket") == bucket_key:
            same_bucket_rejects += 1

    grade_boost = min(0.08, 0.02 * (same_grade_rejects // 4))
    bucket_boost = min(0.10, 0.025 * (same_bucket_rejects // 3))
    base_boost = GRADE_FIT_BUCKET_BOOSTS.get(bucket_key, 0.0)
    return min(0.18, base_boost + grade_boost + bucket_boost)

def _current_grade_fit_relaxation(pid):
    streak = int(grade_fit_reject_streak.get(pid, 0))
    relax = min(GRADE_FIT_MAX_RELAX, (streak // 6) * GRADE_FIT_RELAX_STEP)
    if GAME_STATE == "PRELOAD" and preload_started_at > 0:
        elapsed = max(0.0, time.time() - preload_started_at)
        if elapsed >= 12.0:
            relax += min(0.30, ((elapsed - 12.0) // 6.0) * 0.10)
    return min(GRADE_FIT_MAX_RELAX, relax)

def _should_force_offline_fill():
    if GAME_STATE != "PRELOAD" or preload_started_at <= 0:
        return False
    return (time.time() - preload_started_at) >= FORCE_OFFLINE_FILL_AFTER_SECONDS

def _difficulty_index(difficulty):
    try:
        return DIFFICULTY_LEVELS.index(difficulty)
    except Exception:
        return 1

def _safe_grade_int(grade, default=3):
    try:
        return max(1, min(6, int(grade)))
    except Exception:
        return default

SUBJECT_GRADE_RECOMMENDED_DIFFICULTY = {
    "算数": {1: "簡単", 2: "簡単", 3: "普通", 4: "普通", 5: "難しい", 6: "難しい"},
    "理科": {1: "簡単", 2: "簡単", 3: "普通", 4: "普通", 5: "難しい", 6: "難しい"},
    "国語": {1: "簡単", 2: "簡単", 3: "普通", 4: "普通", 5: "普通", 6: "難しい"},
}

def _recommended_difficulty(subject, grade):
    g_int = _safe_grade_int(grade, default=3)
    subject_table = SUBJECT_GRADE_RECOMMENDED_DIFFICULTY.get(subject, {})
    if g_int in subject_table:
        return subject_table[g_int]
    if g_int <= 2:
        return "簡単"
    if g_int <= 4:
        return "普通"
    return "難しい"

def _effective_difficulty(subject, grade, requested_difficulty):
    """
    学年・教科に対して不自然な難易度を避けるため、設定値を妥当な範囲に補正する。
    """
    g_int = _safe_grade_int(grade, default=3)
    req_idx = _difficulty_index(requested_difficulty)
    rec_idx = _difficulty_index(_recommended_difficulty(subject, g_int))
    max_idx = len(DIFFICULTY_LEVELS) - 1

    # 基本は推奨難易度の ±1 段階まで許可しつつ、低学年・高学年の極端値を防ぐ
    min_allowed = max(0, rec_idx - 1)
    max_allowed = min(max_idx, rec_idx + 1)
    if g_int <= 2:
        max_allowed = min(max_allowed, 1)  # 低学年は「難しい」を抑制
    elif g_int >= 5:
        min_allowed = max(min_allowed, 1)  # 高学年は「簡単」に寄りすぎない

    eff_idx = min(max(req_idx, min_allowed), max_allowed)
    return DIFFICULTY_LEVELS[eff_idx]

def _grade_scope_prompt_lines(grade, subject):
    try:
        g_int = int(grade)
    except Exception:
        g_int = grade

    lines = []
    allowed_topics = QUESTION_TYPES.get(subject, {}).get(g_int, [])
    if allowed_topics:
        lines.append(f"IMPORTANT: Allowed curriculum topics for this exact grade: {', '.join(allowed_topics)}.")
        lines.append("IMPORTANT: Every quiz must clearly belong to one of the allowed curriculum topics above.")

    guide = GRADE_SCOPE_GUIDES.get(subject, {}).get(g_int, {})
    must = guide.get("must", "").strip()
    avoid = guide.get("avoid", "").strip()
    if must:
        lines.append(f"IMPORTANT: Target this grade feel: {must}.")
    if avoid:
        lines.append(f"IMPORTANT: Avoid level mismatch such as: {avoid}.")

    if subject == "算数" and g_int >= 5:
        lines.append(
            "IMPORTANT: For upper-elementary math, avoid low-grade one-step word problems such as simple "
            "'1袋に5個、3袋で何個' patterns unless the question also requires ratio, percentage, speed, "
            "area, volume, graph reading, or multi-step reasoning."
        )
    if subject == "国語" and g_int >= 5:
        lines.append(
            "IMPORTANT: For grade 5-6 Japanese, prefer passage interpretation, grammar, kanji usage, "
            "敬語, or reasoning about wording over very short single-word meaning drills."
        )
    if subject == "理科" and g_int >= 5:
        lines.append(
            "IMPORTANT: For grade 5-6 science, prefer observation, experiment, comparison, explanation of "
            "cause/effect, or curriculum concepts over simple fact recall only."
        )
    return lines

def _grade_fit_prompt_lines(grade, subject, difficulty):
    idx = _difficulty_index(difficulty)
    lines = [
        "IMPORTANT: Match the requested grade and subject exactly. Do not downgrade to lower-grade content.",
        "IMPORTANT: Use age-appropriate terms, units, and curriculum-style phrasing for the specified grade."
    ]

    if idx == 1:
        lines.extend([
            "For NORMAL difficulty, generate textbook-middle level questions for that grade (not introductory or review-only lower-grade questions).",
            "For NORMAL difficulty, include at least one reasoning step (comparison, interpretation, calculation, or cause/effect), not pure recall only.",
            "Make wrong choices plausible for students of that grade and subject."
        ])
        if grade >= 3:
            lines.append("If grade >= 3, avoid overly easy lower-grade items such as obvious single-step one-digit arithmetic or simple word guessing.")
        if grade >= 5:
            lines.append("If grade >= 5, prefer questions requiring organizing information, intermediate steps, or checking evidence/reasoning.")
    elif idx == 2:
        lines.extend([
            "For HARD difficulty, stay within grade scope but use application-oriented or multi-step questions.",
            "Combine multiple learned points from the same grade when possible."
        ])
    else:
        lines.append("For EASY difficulty, keep it basic but still within the specified grade and subject scope.")

    return lines

def _base_prompt(grade, subject, difficulty, history, prefer_image_quiz=False, batch_count=LLM_BATCH_QUESTION_COUNT):
    history = history or []
    try:
        batch_count = max(2, min(6, int(batch_count)))
    except Exception:
        batch_count = LLM_BATCH_QUESTION_COUNT
    # トピックをランダムに選択して出題の幅を広げる
    topics = QUESTION_TYPES.get(subject, {}).get(grade, ["一般"])
    topic = random.choice(topics)
    topic_batch = list(topics)
    if len(topic_batch) > batch_count:
        topic_batch = random.sample(topic_batch, batch_count)
    
    # まとめて生成するための例
    example = [{"q":"問題文1","c":["選択肢A","選択肢B"],"a":0,"e":"解説1"}, {"q":"問題文2","c":["選択肢C","選択肢D"],"a":1,"e":"解説2"}]
    example_json = json.dumps(example, ensure_ascii=False)
    
    # 難易度に応じた指示の追加
    diff_instruction = ""
    if difficulty == "簡単":
        diff_instruction = "・基礎的な知識を問う問題にしてください。\n・ひねりは加えず、ストレートな問題にしてください。"
    elif difficulty == "難しい":
        diff_instruction = "・応用力や思考力を問う少し難しい問題にしてください。\n・引っかけ問題や、複数のステップを要する問題を含めても構いません。"
    else: # 普通
        diff_instruction = "・標準的なレベルの問題にしてください。\n・教科書の練習問題レベルを意識してください。"

    lines = [
        f"日本の小学校{grade}年生向け、{subject}の『{topic}』に関する二択クイズを3問作成してください。",
        f"難易度設定: {difficulty}",
        diff_instruction,
        "ルール1: 問題文に絵文字や記号を入れないこと",
        "ルール2: JSONの配列(List)形式のみ出力してください。選択肢は2つ。子供向けの言葉で。",
        f"例: {example_json}"
    ]
    lines.extend([
        f"IMPORTANT: Return exactly {batch_count} quiz objects in one JSON array.",
        "IMPORTANT: Output JSON only, with no markdown and no extra prose.",
        "IMPORTANT: Within one response, diversify sub-topics and avoid repeating the same unit-conversion pattern/template.",
        f"IMPORTANT: Candidate topics for this batch are: {', '.join(topic_batch)}.",
        "IMPORTANT: Spread the quizzes across different candidate topics when possible."
    ])
    if prefer_image_quiz:
        lines.extend([
            "IMPORTANT: Prefer image-based quiz formats over plain text-only formats.",
            "At least one quiz must include either image_prompt or choice_image_prompts.",
            "If using image_prompt, return one prompt string for a single worksheet illustration and keep normal text choices in c.",
            "If using choice_image_prompts, return exactly two prompt strings aligned to choice 0 and choice 1.",
            "Image prompts must describe simple elementary worksheet illustrations with white background and no text, no letters, and no numbers in the image.",
            "Allowed optional fields: image_prompt (string), choice_image_prompts (array of 2 strings)."
        ])
    if subject == "国語" and grade >= 5:
        lines.extend([
            "IMPORTANT (Japanese grade 5-6): Avoid generating consecutive vocabulary-meaning items.",
            "When outputting multiple quizzes, each quiz must use a different sub-genre (reading comprehension, grammar, kanji/notation, vocabulary usage, honorific/polite forms).",
            "Do not output two questions in the same 'word meaning / phrase meaning' format in one response."
        ])
    lines.extend(_grade_fit_prompt_lines(grade, subject, difficulty))
    lines.extend(_grade_scope_prompt_lines(grade, subject))

    if grade in [1, 2]:
        lines.insert(3, "特別ルール: 小学1・2年生向けなので、漢字は使わず「ひらがな」を多くしてください。")
        lines.insert(4, "特別ルール: 難しい言葉は使わず、子供がわかるやさしい言葉で書いてください。")
    
    # 評価データベース(良い問題)を参考資料としてAIに渡す
    good_samples = [q for q in quiz_ratings.get("good", []) if q.get("subject") == subject and str(q.get("grade")) == str(grade)]
    if good_samples:
        sample_q = random.choice(good_samples)
        lines.append(f"※参考: 過去に高く評価された良問のテイストや難易度を参考にしてください -> Q:{sample_q['q']}")
    
    # 履歴を渡して重複を避ける指示を追加
    if history:
        lines.append("※以下の問題とは内容・数値を必ず変えて作成してください:")
        for h in history:
            lines.append(f"- {h}")
            
    # 評価データベース(悪い問題)を避ける指示
    if quiz_ratings["bad"]:
        scoped_bad = [
            b for b in quiz_ratings["bad"]
            if isinstance(b, dict)
            and b.get("q")
            and (
                (str(b.get("subject", "")).strip() == subject and str(b.get("grade", "")).strip() == str(grade))
                or (not str(b.get("subject", "")).strip() and not str(b.get("grade", "")).strip())
            )
        ]
        bad_pool = scoped_bad if scoped_bad else [b for b in quiz_ratings["bad"] if isinstance(b, dict) and b.get("q")]
        bad_samples = random.sample(bad_pool, min(3, len(bad_pool))) if bad_pool else []
        lines.append("※以下の問題は以前「悪い」と評価されたので、似た形式や内容の問題は絶対に出題しないでください:")
        for bq in bad_samples:
            lines.append(f"- {bq.get('q', '')}")
            
    return "\n".join(lines)

def _extract_quiz_list_from_llm_text(raw_text, src_name):
    raw = str(raw_text or "")
    decoder = json.JSONDecoder()
    for idx, ch in enumerate(raw):
        if ch not in "[{":
            continue
        try:
            data, _ = decoder.raw_decode(raw[idx:])
        except Exception:
            continue
        if isinstance(data, dict):
            data["src"] = src_name
            return [data]
        if isinstance(data, list):
            for d in data:
                if isinstance(d, dict):
                    d["src"] = src_name
            return data
    return None

def _normalize_batch_count(batch_count):
    try:
        return max(1, min(6, int(batch_count)))
    except Exception:
        return LLM_BATCH_QUESTION_COUNT

def _trim_quiz_batch(quizzes, batch_count):
    if not isinstance(quizzes, list):
        return None
    n = _normalize_batch_count(batch_count)
    valid = [q for q in quizzes if isinstance(q, dict)]
    if not valid:
        return None
    return valid[:n]

def _merge_two_provider_batches(batch_a, batch_b, batch_count, first_source="A"):
    a = _trim_quiz_batch(batch_a, batch_count) or []
    b = _trim_quiz_batch(batch_b, batch_count) or []
    if not a and not b:
        return None

    n = _normalize_batch_count(batch_count)
    out = []
    ia = 0
    ib = 0
    turn = "A" if first_source == "A" else "B"

    while len(out) < n and (ia < len(a) or ib < len(b)):
        if turn == "A":
            if ia < len(a):
                out.append(a[ia]); ia += 1
            elif ib < len(b):
                out.append(b[ib]); ib += 1
            turn = "B"
        else:
            if ib < len(b):
                out.append(b[ib]); ib += 1
            elif ia < len(a):
                out.append(a[ia]); ia += 1
            turn = "A"
    return out or None

def _preferred_llm_source_for_pid(pid):
    if chatgpt_client is None or gemini_model is None:
        return None
    with buffer_lock:
        gpt_c = sum(1 for item in quiz_buffers[pid] if item.get("src") == "ChatGPT")
        gem_c = sum(1 for item in quiz_buffers[pid] if item.get("src") == "Gemini")
    return "ChatGPT" if gpt_c <= gem_c else "Gemini"

def fetch_quiz_from_chatgpt(grade, subject, difficulty, history, prefer_image_quiz=False, batch_count=LLM_BATCH_QUESTION_COUNT):
    if not chatgpt_client: return None
    batch_count = _normalize_batch_count(batch_count)
    try:
        r = chatgpt_client.chat.completions.create(model=OPENAI_MODEL, messages=[{"role":"user", "content":_base_prompt(grade, subject, difficulty, history, prefer_image_quiz=prefer_image_quiz, batch_count=batch_count)}], temperature=LLM_TEMPERATURE, timeout=20)
        raw = r.choices[0].message.content
        parsed = _extract_quiz_list_from_llm_text(raw, "ChatGPT")
        if parsed:
            processed = _postprocess_llm_quizzes(parsed, require_image=prefer_image_quiz)
            return _trim_quiz_batch(processed, batch_count)
        s, e = raw.find('['), raw.rfind(']') + 1
        if s == -1 or e <= 0:
            # 配列で見つからなければオブジェクトとして探すフォールバック
            s, e = raw.find('{'), raw.rfind('}') + 1
            if s != -1 and e > 0:
                data = json.loads(raw[s:e])
                data["src"] = "ChatGPT"
                processed = _postprocess_llm_quizzes([data], require_image=prefer_image_quiz)
                return _trim_quiz_batch(processed, batch_count)
        if s != -1 and e > 0:
            data = json.loads(raw[s:e])
            for d in data: d["src"] = "ChatGPT"
            processed = _postprocess_llm_quizzes(data, require_image=prefer_image_quiz)
            return _trim_quiz_batch(processed, batch_count)
    except Exception as e: print(f"[ChatGPT Error] {e}")
    return None

def fetch_quiz_from_gemini(grade, subject, difficulty, history, prefer_image_quiz=False, batch_count=LLM_BATCH_QUESTION_COUNT):
    if not gemini_model: return None
    batch_count = _normalize_batch_count(batch_count)
    try:
        r = gemini_model.generate_content(
            _base_prompt(grade, subject, difficulty, history, prefer_image_quiz=prefer_image_quiz, batch_count=batch_count),
            generation_config={"temperature": LLM_TEMPERATURE},
        )
        raw = r.text
        parsed = _extract_quiz_list_from_llm_text(raw, "Gemini")
        if parsed:
            processed = _postprocess_llm_quizzes(parsed, require_image=prefer_image_quiz)
            return _trim_quiz_batch(processed, batch_count)
        s, e = raw.find('['), raw.rfind(']') + 1
        if s == -1 or e <= 0:
            s, e = raw.find('{'), raw.rfind('}') + 1
            if s != -1 and e > 0:
                data = json.loads(raw[s:e])
                data["src"] = "Gemini"
                processed = _postprocess_llm_quizzes([data], require_image=prefer_image_quiz)
                return _trim_quiz_batch(processed, batch_count)
        if s != -1 and e > 0:
            data = json.loads(raw[s:e])
            for d in data: d["src"] = "Gemini"
            processed = _postprocess_llm_quizzes(data, require_image=prefer_image_quiz)
            return _trim_quiz_batch(processed, batch_count)
    except Exception as e: print(f"[Gemini Error] {e}")
    return None

def fetch_quiz_from_online_llms_parallel(grade, subject, difficulty, history, prefer_image_quiz=False, batch_count=LLM_BATCH_QUESTION_COUNT, preferred_source=None, split_wait_seconds=None):
    if split_wait_seconds is None:
        split_wait_seconds = LLM_SPLIT_WAIT_SECONDS
    can_use_gpt = (chatgpt_client is not None)
    can_use_gemini = (gemini_model is not None)
    if not can_use_gpt and not can_use_gemini:
        return None
    if can_use_gpt and not can_use_gemini:
        return fetch_quiz_from_chatgpt(grade, subject, difficulty, history, prefer_image_quiz=prefer_image_quiz, batch_count=batch_count)
    if can_use_gemini and not can_use_gpt:
        return fetch_quiz_from_gemini(grade, subject, difficulty, history, prefer_image_quiz=prefer_image_quiz, batch_count=batch_count)

    pool = ThreadPoolExecutor(max_workers=2)
    futures = {
        pool.submit(fetch_quiz_from_chatgpt, grade, subject, difficulty, history, prefer_image_quiz, batch_count): "ChatGPT",
        pool.submit(fetch_quiz_from_gemini, grade, subject, difficulty, history, prefer_image_quiz, batch_count): "Gemini",
    }
    pending = set(futures.keys())
    results = {"ChatGPT": None, "Gemini": None}
    try:
        # まず先着を確保
        first_done, pending = wait(pending, return_when=FIRST_COMPLETED)
        for fut in first_done:
            src_name = futures[fut]
            try:
                results[src_name] = fut.result()
            except Exception as e:
                if DEBUG_WORKERS:
                    print(f"[Parallel {src_name} Error] {e}")
                results[src_name] = None

        # もう片方が間に合えば短時間だけ待って混合採用
        if pending:
            second_done, _ = wait(pending, timeout=split_wait_seconds)
            for fut in second_done:
                src_name = futures[fut]
                try:
                    results[src_name] = fut.result()
                except Exception as e:
                    if DEBUG_WORKERS:
                        print(f"[Parallel {src_name} Error] {e}")
                    results[src_name] = None

        gpt_res = results.get("ChatGPT")
        gem_res = results.get("Gemini")
        if gpt_res and gem_res:
            start = "A"
            if preferred_source == "Gemini":
                start = "B"
            merged = _merge_two_provider_batches(gpt_res, gem_res, batch_count, first_source=start)
            if merged:
                return merged
        if gpt_res:
            return gpt_res
        if gem_res:
            return gem_res
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return None

def _normalize_question_text(text):
    t = unicodedata.normalize("NFKC", str(text or "")).strip().lower()
    t = "".join(ch for ch in t if not ch.isspace())
    # ???/???Unicode?????????????????
    out = []
    for ch in t:
        cat = unicodedata.category(ch)
        if cat.startswith("P") or cat.startswith("S"):
            continue
        if ch.isalnum() or ("぀" <= ch <= "ヿ") or ("一" <= ch <= "鿿"):
            out.append(ch)
    return "".join(out)

def _question_pattern_key(text):
    t = _normalize_question_text(text)
    t = re.sub(r"\d+(?:\.\d+)?", "#", t)
    t = re.sub(r"#+", "#", t)
    return t

def _char_bigrams(text):
    t = _normalize_question_text(text)
    if not t:
        return set()
    if len(t) == 1:
        return {t}
    return {t[i:i+2] for i in range(len(t)-1)}

def _question_similarity(a, b):
    sa = _char_bigrams(a)
    sb = _char_bigrams(b)
    if not sa or not sb:
        return 0.0
    union = len(sa | sb)
    if union == 0:
        return 0.0
    return len(sa & sb) / union

def _is_similar_question_for_pid(pid, q_text):
    raw = str(q_text or "")
    if not raw.strip():
        return True

    recent_candidates = []
    recent_candidates.extend(play_histories.get(pid, [])[-SIMILARITY_RECENT_WINDOW:])
    for item in list(quiz_buffers.get(pid, []))[-SIMILARITY_RECENT_WINDOW:]:
        if isinstance(item, dict):
            prev_q = item.get("q", "")
            if prev_q:
                recent_candidates.append(prev_q)

    norm = _normalize_question_text(raw)
    pattern = _question_pattern_key(raw)
    pattern_head = pattern[:18]
    for prev in recent_candidates:
        prev_norm = _normalize_question_text(prev)
        if not prev_norm:
            continue
        prev_pattern = _question_pattern_key(prev)
        if norm == prev_norm:
            return True
        if pattern == prev_pattern:
            return True
        if pattern_head and pattern_head == prev_pattern[:18]:
            return True
        if len(pattern) >= 12 and len(prev_pattern) >= 12 and (pattern in prev_pattern or prev_pattern in pattern):
            return True
        if _question_similarity(raw, prev) >= SIMILARITY_BIGRAM_THRESHOLD:
            return True
    return False

def _infer_subgenre(subject, grade, q_text):
    text = str(q_text or "")
    if subject != "国語" or int(grade) < 5:
        return "other"

    has_quote_term = bool(re.search(r"「[^」]{1,24}」", text))
    if has_quote_term and any(k in text for k in ["意味", "とは", "どういうこと", "どんな", "使う言葉", "言いかえ"]):
        return "jp_vocab_meaning"
    if any(k in text for k in ["漢字", "部首", "音読み", "訓読み", "書き順", "同音異義"]):
        return "jp_kanji"
    if any(k in text for k in ["主語", "述語", "修飾語", "文節", "助詞", "接続語", "文法"]):
        return "jp_grammar"
    if any(k in text for k in ["筆者", "要旨", "段落", "理由", "心情", "読み取", "場面"]):
        return "jp_reading"
    if any(k in text for k in ["敬語", "尊敬語", "謙譲語", "丁寧語"]):
        return "jp_honorific"
    return "jp_other"

def _infer_generic_topic_key(q_text):
    text = unicodedata.normalize("NFKC", str(q_text or ""))
    if not text:
        return "other"
    lower = text.lower()

    has_kg = bool(re.search(r"(?<![a-z])kg(?![a-z])", lower)) or ("キログラム" in text)
    has_g = bool(re.search(r"(?<![a-z])g(?![a-z])", lower)) or ("グラム" in text)
    if has_kg and has_g:
        return "unit_weight_conversion"

    if "分数" in text or "約分" in text or "通分" in text:
        return "fraction"
    if "割合" in text or "％" in text or "%" in text or "パーセント" in text:
        return "percentage_ratio"

    length_hint = 0
    for u in ("mm", "cm", "km", "m"):
        if re.search(rf"(?<![a-z]){u}(?![a-z])", lower):
            length_hint += 1
    if any(k in text for k in ["ミリメートル", "センチメートル", "メートル", "キロメートル"]):
        length_hint += 1
    if length_hint >= 2:
        return "unit_length_conversion"

    volume_hint = 0
    for u in ("ml", "dl", "l"):
        if re.search(rf"(?<![a-z]){u}(?![a-z])", lower):
            volume_hint += 1
    if any(k in text for k in ["ミリリットル", "デシリットル", "リットル"]):
        volume_hint += 1
    if volume_hint >= 2:
        return "unit_volume_conversion"

    return "other"

def _is_same_subgenre_streak_for_pid(pid, q_text, subject, grade):
    candidate = _infer_subgenre(subject, grade, q_text)
    if candidate in ("other", "jp_other"):
        candidate = _infer_generic_topic_key(q_text)
        if candidate == "other":
            return False
        infer_prev = _infer_generic_topic_key
    else:
        infer_prev = lambda prev_q: _infer_subgenre(subject, grade, prev_q)

    recent_hist = play_histories.get(pid, [])
    if recent_hist:
        if infer_prev(recent_hist[-1]) == candidate:
            return True

    pending = list(quiz_buffers.get(pid, []))
    if not pending:
        return False

    streak = 0
    for item in reversed(pending):
        if not isinstance(item, dict):
            break
        prev = item.get("q", "")
        prev_genre = infer_prev(prev)
        if prev_genre == candidate:
            streak += 1
            if streak >= MAX_SAME_GENRE_STREAK_IN_BUFFER:
                return True
        else:
            break
    return False

    try:
        g_int = int(grade)
    except Exception:
        g_int = 0

    if subject == "国語" and g_int >= 5:
        candidate = _infer_subgenre(subject, grade, q_text)
        if candidate in ("other", "jp_other"):
            return False
        infer_prev = lambda prev_q: _infer_subgenre(subject, grade, prev_q)
    else:
        candidate = _infer_generic_topic_key(q_text)
        if candidate == "other":
            return False
        infer_prev = _infer_generic_topic_key

    pending = list(quiz_buffers.get(pid, []))
    if not pending:
        return False

    streak = 0
    for item in reversed(pending):
        if not isinstance(item, dict):
            break
        prev = item.get("q", "")
        prev_genre = infer_prev(prev)
        if prev_genre == candidate:
            streak += 1
            if streak >= MAX_SAME_GENRE_STREAK_IN_BUFFER:
                return True
        else:
            break
    return False
    if subject != "国語" or int(grade) < 5:
        return False
    candidate = _infer_subgenre(subject, grade, q_text)
    if candidate in ("other", "jp_other"):
        return False

    pending = list(quiz_buffers.get(pid, []))
    if not pending:
        return False

    streak = 0
    for item in reversed(pending):
        if not isinstance(item, dict):
            break
        prev = item.get("q", "")
        prev_genre = _infer_subgenre(subject, grade, prev)
        if prev_genre == candidate:
            streak += 1
            if streak >= MAX_SAME_GENRE_STREAK_IN_BUFFER:
                return True
        else:
            break
    return False

def _estimate_thinking_load(quiz, difficulty=None):
    q_text = str((quiz or {}).get("q", ""))
    choices = (quiz or {}).get("c", []) or []
    choices = [str(c) for c in choices]

    q_len = len(q_text)
    choice_avg_len = (sum(len(c) for c in choices) / max(1, len(choices))) if choices else 0
    choice_max_len = max([len(c) for c in choices], default=0)

    digit_count = len(re.findall(r"[0-9０-９]", q_text))
    op_count = len(re.findall(r"[+\-*/×÷％%＝=]", q_text))
    paren_count = len(re.findall(r"[()（）]", q_text))
    unit_count = len(re.findall(r"(cm|mm|km|m|kg|g|L|dL|mL|分|秒|時間|円|%)", q_text, flags=re.IGNORECASE))

    # 「読む量」「選択肢比較」「計算/処理負荷」をまとめた簡易スコア
    load = 0.0
    load += min(1.5, q_len / 42.0)
    load += min(0.8, choice_avg_len / 36.0)
    load += min(1.2, choice_max_len / 55.0)
    load += min(1.6, digit_count * 0.10 + op_count * 0.33 + paren_count * 0.20 + unit_count * 0.12)
    if digit_count >= 4 and op_count >= 1:
        load += 0.35
    if op_count >= 2:
        load += 0.30

    diff_idx = _difficulty_index(difficulty)
    if diff_idx == 0:   # easy
        load -= 0.35
    elif diff_idx == 1: # normal
        load += 0.20
    else:               # hard
        load += 0.55

    return max(0.2, load)

def _compute_wall_speed_ratio_for_quiz(quiz, difficulty):
    load = _estimate_thinking_load(quiz, difficulty)
    # 負荷が高いほど壁を遅くする。軽い問題は少し速くする。
    speed_multiplier = 1.22 - (load * 0.17)
    max_speed_ratio = max(base_wall_speed * 1.35, MINIMUM_WALL_SPEED_RATIO + 0.001)
    return max(MINIMUM_WALL_SPEED_RATIO, min(max_speed_ratio, base_wall_speed * speed_multiplier))

def _quiz_text_blob(quiz):
    if not isinstance(quiz, dict):
        return ""
    parts = [str(quiz.get("q", "")).strip(), str(quiz.get("e", "")).strip()]
    for choice in (quiz.get("c") or []):
        parts.append(str(choice).strip())
    return unicodedata.normalize("NFKC", " ".join(p for p in parts if p))

def _looks_like_single_step_rate_problem(text):
    t = unicodedata.normalize("NFKC", str(text or ""))
    if not t:
        return False
    if re.search(r"(割合|百分率|歩合|比(?!較)|速さ|時速|分速|秒速|面積|体積|グラフ|資料|平均|分数|小数)", t):
        return False
    if re.search(r"(毎分|毎時|1分間に|1時間に|1日で|1こあたり|1個あたり|1本あたり|1袋に|1人あたり)", t):
        return True
    if re.search(r"(全部で|合わせて).*(何(個|本|枚|袋|台|人|円|分|時間|秒|m|cm|mm|km|L|mL|dL|kg|g|リットル|グラム|メートル))", t):
        return True
    return False

def _math_grade_fit_score(text):
    t = unicodedata.normalize("NFKC", str(text or ""))
    lower = t.lower()
    score = 0.0

    pattern_scores = [
        (r"(分数|約分|通分|\d+\s*/\s*\d+)", 0.95),
        (r"(小数|\d+\.\d+)", 0.85),
        (r"(割合|百分率|歩合|比(?!較)|％|%)", 1.00),
        (r"(速さ|時速|分速|秒速)", 0.90),
        (r"(面積|体積|立方|cm3|cm³|m3|m³)", 0.85),
        (r"(表|グラフ|資料|平均)", 0.70),
        (r"(角|平行|垂直|半径|直径|円周|対称|拡大図|縮図)", 0.60),
        (r"(単位量あたり|1あたり|1個あたり|1人あたり)", 0.70),
    ]
    for pattern, value in pattern_scores:
        if re.search(pattern, t):
            score += value

    unit_hits = set()
    for unit in ("mm", "cm", "m", "km", "g", "kg", "ml", "dl", "l", "円", "分", "時間", "秒", "メートル", "グラム", "リットル"):
        if unit in lower or unit in t:
            unit_hits.add(unit)
    if len(unit_hits) >= 2:
        score += 0.25
    if len(unit_hits) >= 4:
        score += 0.15

    numbers = re.findall(r"\d+(?:\.\d+)?", t)
    if len(numbers) >= 3:
        score += 0.20
    if len(numbers) >= 5:
        score += 0.15
    if any(len(n.split(".")[0]) >= 3 for n in numbers):
        score += 0.20

    op_count = len(re.findall(r"[+\-×÷*/＝=]", t))
    if op_count >= 1:
        score += 0.15
    if op_count >= 2:
        score += 0.20

    if re.search(r"(比べて|ちがい|残り|それぞれ|何倍|順番|組み合わせ|理由|もっとも|あてはまる)", t):
        score += 0.20

    if _looks_like_single_step_rate_problem(t):
        score -= 0.45

    return max(0.0, score)

def _science_grade_fit_score(text, grade):
    t = unicodedata.normalize("NFKC", str(text or ""))
    try:
        g_int = int(grade)
    except Exception:
        g_int = 0

    score = 0.0
    exact_hits = sum(1 for kw in SCIENCE_GRADE_KEYWORDS.get(g_int, []) if kw in t)
    if exact_hits:
        score += min(0.75, exact_hits * 0.30)

    neighbor_hits = 0
    for near_grade in (g_int - 1, g_int + 1):
        neighbor_hits += sum(1 for kw in SCIENCE_GRADE_KEYWORDS.get(near_grade, []) if kw in t)
    if neighbor_hits:
        score += min(0.20, neighbor_hits * 0.10)

    if re.search(r"(観察|実験|結果|予想|理由|比べる|変化|どのように|なぜ|説明)", t):
        score += 0.25
    if len(t) >= 28:
        score += 0.10

    return score

def _looks_like_simple_vocab_quiz(text):
    t = unicodedata.normalize("NFKC", str(text or ""))
    if len(t) > 40:
        return False
    return bool(re.search(r"(意味|読み|何と読み|ひらがな|カタカナ)", t))

def _japanese_grade_fit_score(text, grade):
    t = unicodedata.normalize("NFKC", str(text or ""))
    try:
        g_int = int(grade)
    except Exception:
        g_int = 0

    score = 0.0
    exact_hits = sum(1 for kw in JAPANESE_GRADE_KEYWORDS.get(g_int, []) if kw in t)
    if exact_hits:
        score += min(0.75, exact_hits * 0.25)

    neighbor_hits = 0
    for near_grade in (g_int - 1, g_int + 1):
        neighbor_hits += sum(1 for kw in JAPANESE_GRADE_KEYWORDS.get(near_grade, []) if kw in t)
    if neighbor_hits:
        score += min(0.20, neighbor_hits * 0.08)

    if "「" in t and "」" in t:
        score += 0.15
    if re.search(r"(理由|要旨|文脈|主語|述語|修飾語|敬語|段落|筆者|心情|最も適切)", t):
        score += 0.25
    if len(t) >= 30:
        score += 0.10
    if _looks_like_simple_vocab_quiz(t) and g_int >= 5:
        score -= 0.25

    return max(0.0, score)

def _grade_fit_reject_reason(quiz, subject, grade, difficulty, threshold_relax=0.0):
    try:
        g_int = int(grade)
    except Exception:
        return None

    text = _quiz_text_blob(quiz)
    if not text:
        return "empty quiz text"

    if subject == "算数":
        if g_int <= 2 and re.search(r"(分数|小数|割合|百分率|比(?!較)|速さ|面積|体積)", text):
            return "lower-grade math included upper-grade topic"
        score = _math_grade_fit_score(text)
        one_step_threshold = max(
            0.35,
            1.10 + _adaptive_grade_fit_threshold_boost(subject, g_int, "math_one_step") - threshold_relax
        )
        if g_int >= 5 and _looks_like_single_step_rate_problem(text) and score < one_step_threshold:
            return "upper-grade math fell back to a low-grade one-step word problem"
    elif subject == "理科":
        score = _science_grade_fit_score(text, g_int)
    elif subject == "国語":
        score = _japanese_grade_fit_score(text, g_int)
        vocab_threshold = max(
            0.25,
            0.70 + _adaptive_grade_fit_threshold_boost(subject, g_int, "jp_simple_vocab") - threshold_relax
        )
        if g_int >= 5 and _looks_like_simple_vocab_quiz(text) and score < vocab_threshold:
            return "upper-grade Japanese was too close to a simple vocabulary drill"
    else:
        return None

    threshold = GRADE_FIT_SCORE_THRESHOLDS.get(subject, {}).get(g_int)
    if threshold is None:
        return None
    threshold += _adaptive_grade_fit_threshold_boost(subject, g_int, "low_score")
    threshold = max(0.0, threshold - threshold_relax)
    if difficulty == "簡単":
        threshold = max(0.0, threshold - 0.15)
    elif difficulty == "難しい":
        threshold += 0.15

    if score < threshold:
        return f"grade-fit score {score:.2f} < {threshold:.2f}"
    return None

def api_worker(worker_id):
    while not stop_event.is_set():
        if g_game_mode == "TEN_QUESTIONS" and GAME_STATE == "IN_GAME":
            time.sleep(0.5)
            continue
            
        target_pid = 0
        min_len = 9999
        active_pids = [1] if player_count == 1 else [1, 2]
        reserved_slot = False
        
        with buffer_lock:
            for pid in active_pids:
                if generation_inflight.get(pid, 0) >= 1:
                    continue
                l = len(quiz_buffers[pid])
                limit = 10 * 1 if g_game_mode == "TEN_QUESTIONS" else QUIZ_BUFFER_SIZE
                effective_len = l + generation_inflight.get(pid, 0)
                if effective_len < limit and effective_len < min_len:
                    min_len = effective_len
                    target_pid = pid
            if target_pid:
                generation_inflight[target_pid] = generation_inflight.get(target_pid, 0) + 1
                generation_started_at[target_pid] = time.time()
                reserved_slot = True
        
        if target_pid == 0:
            time.sleep(0.5); continue

        try:
            conf = PLAYER_CONFIGS[target_pid]
            subject = conf["subject"]
            # 教科ごとの学年設定を使用。なければ代表学年
            grade = conf.get("subject_grades", {}).get(subject, conf["grade"])
            requested_diff = conf["difficulties"].get(subject, "普通")
            diff = _effective_difficulty(subject, grade, requested_diff)
            
            # 履歴を直近10件取得してAIに渡す（重複回避）
            with buffer_lock:
                hist_window = 6 if g_game_mode == "TEN_QUESTIONS" else 10
                hist = play_histories[target_pid][-hist_window:]
                target_limit = 10 if g_game_mode == "TEN_QUESTIONS" else QUIZ_BUFFER_SIZE
                remaining_slots = max(1, target_limit - len(quiz_buffers[target_pid]))
                batch_base = LLM_BATCH_QUESTION_COUNT_TEN if g_game_mode == "TEN_QUESTIONS" else LLM_BATCH_QUESTION_COUNT
                llm_batch_count = max(1, min(batch_base, remaining_slots))

            questions = None
            if LLM_MODE == "OFFLINE": 
                questions = [offline_pick(subject, grade)]
            else:
                if _should_force_offline_fill():
                    questions = [offline_pick(subject, grade) for _ in range(max(1, llm_batch_count))]
                prefer_llm_image = (IMAGE_QUIZ_MODE == "PRIORITY")
                ai_image_rate = _current_ai_image_rate()
                builtin_image_rate = _current_builtin_image_rate()
                preferred_source = _preferred_llm_source_for_pid(target_pid)
                split_wait_seconds = LLM_SPLIT_WAIT_SECONDS_TEN if g_game_mode == "TEN_QUESTIONS" else LLM_SPLIT_WAIT_SECONDS
                if questions is None and prefer_llm_image:
                    questions = fetch_quiz_from_online_llms_parallel(
                        grade, subject, diff, hist,
                        prefer_image_quiz=True,
                        batch_count=llm_batch_count,
                        preferred_source=preferred_source,
                        split_wait_seconds=split_wait_seconds
                    )

                if questions is None and random.random() < ai_image_rate:
                    ai_image_quiz = _build_ai_image_quiz(subject, grade, diff)
                    if ai_image_quiz:
                        questions = [ai_image_quiz]
                if questions is None and BUILTIN_IMAGE_QUESTIONS.get(subject, {}).get(str(grade)) and random.random() < builtin_image_rate:
                    questions = [offline_pick(subject, grade, prefer_image=True)]
                if questions is None:
                    questions = fetch_quiz_from_online_llms_parallel(
                        grade, subject, diff, hist,
                        prefer_image_quiz=False,
                        batch_count=llm_batch_count,
                        preferred_source=preferred_source,
                        split_wait_seconds=split_wait_seconds
                    )
            
            if questions and isinstance(questions, list):
                accepted_questions = []
                with buffer_lock:
                    target_limit = 10 if g_game_mode == "TEN_QUESTIONS" else QUIZ_BUFFER_SIZE
                    for q in questions:
                        if len(quiz_buffers[target_pid]) >= target_limit:
                            break
                        if "q" in q and q['q'] not in seen_questions[target_pid]:
                            threshold_relax = _current_grade_fit_relaxation(target_pid)
                            reject_reason = _grade_fit_reject_reason(
                                q, subject, grade, diff, threshold_relax=threshold_relax
                            )
                            if reject_reason:
                                grade_fit_reject_streak[target_pid] = min(
                                    999, grade_fit_reject_streak.get(target_pid, 0) + 1
                                )
                                append_generation_reject_log(
                                    target_pid, q, subject, grade, diff, reject_reason
                                )
                                if DEBUG_WORKERS:
                                    print(
                                        f"[Worker {worker_id}] Skipped grade-mismatch for P{target_pid}: "
                                        f"{str(q.get('q',''))[:18]}... ({reject_reason})"
                                    )
                                continue
                            if _is_same_subgenre_streak_for_pid(target_pid, q.get("q", ""), subject, grade):
                                if DEBUG_WORKERS:
                                    print(f"[Worker {worker_id}] Skipped same subgenre for P{target_pid}: {str(q.get('q',''))[:18]}...")
                                continue
                            if _is_similar_question_for_pid(target_pid, q.get("q", "")):
                                if DEBUG_WORKERS:
                                    print(f"[Worker {worker_id}] Skipped similar for P{target_pid}: {str(q.get('q',''))[:18]}...")
                                continue
                            seen_questions[target_pid].add(q['q'])
                            quiz_buffers[target_pid].append(q)
                            play_histories[target_pid].append(q['q'])
                            grade_fit_reject_streak[target_pid] = 0
                            accepted_questions.append(q)
                            # 履歴リストが大きくなりすぎないように調整（プロンプト用）
                            if len(play_histories[target_pid]) > 20: play_histories[target_pid].pop(0)
                            if DEBUG_WORKERS:
                                print(f"[Worker {worker_id}] Added for P{target_pid}: {q['q'][:10]}... (Diff:{diff})")
                if not accepted_questions:
                    time.sleep(0.15 if LLM_MODE == "ONLINE" else 0.05)
                for accepted_q in accepted_questions:
                    append_generation_source_log(target_pid, accepted_q, subject, grade, diff)
            else:
                time.sleep(1 if LLM_MODE=="ONLINE" else 0.05)
        finally:
            if reserved_slot:
                with buffer_lock:
                    generation_inflight[target_pid] = max(0, generation_inflight.get(target_pid, 0) - 1)
                    if generation_inflight[target_pid] == 0:
                        generation_started_at[target_pid] = None

# ===================== プレイヤー =====================
class Player:
    def __init__(self, pid:int, viewport:pygame.Rect, left_key:int, right_key:int):
        self.pid = pid; self.viewport = viewport
        self.left_key = left_key; self.right_key = right_key
        self.reset_geometry()
        self.current_quiz = {"q":"Loading...","c":[" "," "],"a":0,"e":"", "src": ""}
        self.state = "PRELOADING"; self.correct_flash_start = 0
        self.question_count = 0; self.history = []
        self.fixed_questions = []
        self.fixed_question_index = 0
        self.last_incorrect = None; self.finished = False
        self.finish_time = None; self.pending_clear = False
        self.particles = []
        
        # 診断モード用
        self.in_assessment = False
        self.assessment_stage = 0 # 1教科内での問題数カウント
        self.current_assessment_subject_idx = 0
        self.current_assessment_grade = 3
        self.assessment_results = {} # 教科ごとの確定レベル
        self.assessment_correct_count = 0 # 正解数カウント

    def reset_geometry(self):
        v=self.viewport
        self.player = pygame.Rect(0,0,int(v.w*PLAYER_WIDTH_RATIO), int(v.h*PLAYER_HEIGHT_RATIO))
        self.player.midbottom = (v.centerx, v.bottom-20)
        self.wall = pygame.Rect(v.left, v.top-int(v.h*WALL_HEIGHT_RATIO), v.w, int(v.h*WALL_HEIGHT_RATIO))
        dw = int(v.w*DOOR_WIDTH_RATIO)
        self.door1 = pygame.Rect(v.left + v.w*0.25 - dw//2, self.wall.y, dw, self.wall.h)
        self.door2 = pygame.Rect(v.left + v.w*0.75 - dw//2, self.wall.y, dw, self.wall.h)
        self.q_surf=self.c1_surf=self.c2_surf=None
        self.q_rect=self.c1_rect=self.c2_rect=None
        self.quiz_image_surf = None
        self.quiz_image_rect = None
        self.choice_image_surfs = [None, None]
        self.choice_image_rects = [None, None]
        self.wall_speed_ratio = base_wall_speed

    def _layout_choice_content(self):
        for idx, (door, text_surf) in enumerate(((self.door1, self.c1_surf), (self.door2, self.c2_surf))):
            image_surf = self.choice_image_surfs[idx]
            image_rect = None
            text_rect = None
            if image_surf:
                image_rect = image_surf.get_rect(midtop=(door.centerx, door.top + 10))
                if text_surf:
                    text_rect = text_surf.get_rect(midtop=(door.centerx, image_rect.bottom + 8))
                    if text_rect.bottom > door.bottom - 8:
                        text_rect.bottom = door.bottom - 8
            elif text_surf:
                text_rect = text_surf.get_rect(center=door.center)

            self.choice_image_rects[idx] = image_rect
            if idx == 0:
                self.c1_rect = text_rect
            else:
                self.c2_rect = text_rect

    def _move_choice_content(self, dy):
        if dy == 0:
            return
        if self.c1_rect:
            self.c1_rect.move_ip(0, dy)
        if self.c2_rect:
            self.c2_rect.move_ip(0, dy)
        for rect in self.choice_image_rects:
            if rect:
                rect.move_ip(0, dy)

    def prepare_surfaces(self):
        v = self.viewport
        q_text = self.current_quiz.get("q", "")
        conf = PLAYER_CONFIGS.get(self.pid, {})
        subj = conf.get("subject")
        diff = None
        if subj:
            grade = conf.get("subject_grades", {}).get(subj, conf.get("grade", 3))
            requested_diff = conf.get("difficulties", {}).get(subj, "普通")
            diff = _effective_difficulty(subj, grade, requested_diff)
        self.wall_speed_ratio = _compute_wall_speed_ratio_for_quiz(self.current_quiz, diff)
        qlen = len(q_text)
        
        fsize = QUESTION_FONT_SIZE
        if qlen > 80: fsize = int(fsize * 0.7)
        elif qlen > 50: fsize = int(fsize * 0.85)

        self.quiz_image_surf = None
        self.quiz_image_rect = None
        image_ref = _get_quiz_image_ref(self.current_quiz)
        if image_ref:
            raw_img = load_question_image(image_ref)
            self.quiz_image_surf = scale_question_image(
                raw_img,
                v.w * QUESTION_IMAGE_MAX_WIDTH_RATIO,
                v.h * QUESTION_IMAGE_MAX_HEIGHT_RATIO
            )
            if self.quiz_image_surf:
                self.quiz_image_rect = self.quiz_image_surf.get_rect(center=(v.centerx, v.top + int(v.h * 0.18)))

        self.q_surf = render_text_wrapped(q_text, v.w * 0.9, fsize)
        if self.quiz_image_rect:
            self.q_rect = self.q_surf.get_rect(midtop=(v.centerx, self.quiz_image_rect.bottom + 18))
        else:
            self.q_rect = self.q_surf.get_rect(center=(v.centerx, v.top + int(v.h * 0.08)))
        choice_refs = _get_choice_image_refs(self.current_quiz)
        self.choice_image_surfs = [None, None]
        self.choice_image_rects = [None, None]
        for idx, ref in enumerate(choice_refs):
            if not ref:
                continue
            raw_choice = load_question_image(ref)
            scaled = scale_question_image(
                raw_choice,
                self.door1.w * CHOICE_IMAGE_MAX_WIDTH_RATIO,
                self.door1.h * CHOICE_IMAGE_MAX_HEIGHT_RATIO
            )
            self.choice_image_surfs[idx] = scaled

        choice_font_size = CHOICE_FONT_SIZE if not any(self.choice_image_surfs) else max(18, CHOICE_FONT_SIZE - 4)
        self.c1_surf = render_text_wrapped(self.current_quiz["c"][0], self.door1.w * 0.86, choice_font_size)
        self.c2_surf = render_text_wrapped(self.current_quiz["c"][1], self.door2.w * 0.86, choice_font_size)
        self._layout_choice_content()

    def set_new_question(self):
        if g_game_mode == "TEN_QUESTIONS" and not self.in_assessment:
            if self.fixed_question_index < len(self.fixed_questions):
                self.current_quiz = self.fixed_questions[self.fixed_question_index]
                self.fixed_question_index += 1
                self.prepare_surfaces()
                self.state = "PLAYING"
                self.wall.top = self.viewport.top - self.wall.h
                self.door1.y = self.door2.y = self.wall.y
                self._layout_choice_content()
                return True
            else:
                return False
        else:
            with buffer_lock:
                if not quiz_buffers[self.pid]:
                    self.current_quiz = {"q":"問題を取得中...","c":[" "," "],"a":0,"e":"", "src": ""}
                    self.state = "PRELOADING"; self.prepare_surfaces(); return False
                self.current_quiz = quiz_buffers[self.pid].popleft()
            
            self.prepare_surfaces(); self.state = "PLAYING"
            self.wall.top = self.viewport.top - self.wall.h
            self.door1.y = self.door2.y = self.wall.y
            self._layout_choice_content()
            return True

    def set_assessment_question(self):
        # 診断用：オフラインバンクから即座に取得
        subj = ASSESSMENT_SUBJECTS[self.current_assessment_subject_idx]
        q = offline_pick(subj, self.current_assessment_grade)
        q["src"] = "診断"
        self.current_quiz = q
        self.prepare_surfaces()
        self.state = "PLAYING"
        self.wall.top = self.viewport.top - self.wall.h
        self.door1.y = self.door2.y = self.wall.y
        self._layout_choice_content()

    def spawn_break_particles(self):
        w, h = self.player.width, self.player.height
        div_x, div_y = 10, 10
        pw, ph = w / div_x, h / div_y
        for r in range(div_y):
            for c in range(div_x):
                x = self.player.x + c * pw + pw/2
                y = self.player.y + r * ph + ph/2
                val = random.randint(0, 60); color = (val, val, val)
                self.particles.append(Particle(x, y, color))

    def adjust_difficulty(self, correct: bool):
        """ゲーム中の難易度自動調整"""
        if g_game_mode == "TEN_QUESTIONS":
            return # 10問モードでは難易度調整とバッファ破棄を行わない
            
        conf = PLAYER_CONFIGS[self.pid]
        subj = conf["subject"]
        grade = conf.get("subject_grades", {}).get(subj, conf.get("grade", 3))
        current_diff = _effective_difficulty(subj, grade, conf["difficulties"].get(subj, "普通"))
        conf["difficulties"][subj] = current_diff
        
        levels = ["簡単", "普通", "難しい"]
        try:
            idx = levels.index(current_diff)
        except: idx = 1
        
        new_idx = idx
        if correct:
            if idx < 2: new_idx = idx + 1 # 正解なら難しく
        else:
            if idx > 0: new_idx = idx - 1 # 不正解なら易しく
            
        if new_idx != idx:
            new_diff = _effective_difficulty(subj, grade, levels[new_idx])
            conf["difficulties"][subj] = new_diff
            print(f"P{self.pid} Difficulty changed: {current_diff} -> {new_diff}")
            
            # バッファをクリアして次の問題から新難易度を適用
            with buffer_lock:
                quiz_buffers[self.pid].clear()

    def update(self, keys):
        self.particles = [p for p in self.particles if p.update()]
        v=self.viewport
        
        if self.state == "ASSESSMENT_WRONG":
             if pygame.time.get_ticks() - self.correct_flash_start > 1000:
                 self.advance_assessment()
             return

        if self.state in ["PRELOADING", "CORRECT"] and pygame.time.get_ticks() - self.correct_flash_start < CORRECT_DISPLAY_MS and self.state == "CORRECT":
            return
        
        if self.state == "CORRECT":
            if self.in_assessment:
                 self.advance_assessment()
                 return
            elif self.pending_clear:
                self.state = "CLEAR"; self.finished = True; self.finish_time = time.time(); self.pending_clear = False
            else: self.set_new_question()
            return
            
        if self.state in ("GAME_OVER","CLEAR", "WAITING"): return
        if self.state == "PRELOADING": self.set_new_question(); return

        speed = int(v.w*PLAYER_SPEED_RATIO)
        if keys[self.left_key]: self.player.x -= speed
        if keys[self.right_key]: self.player.x += speed
        self.player.left = max(v.left, self.player.left); self.player.right = min(v.right, self.player.right)

        dy = int(v.h * self.wall_speed_ratio)
        self.wall.y += dy; self.door1.y = self.door2.y = self.wall.y
        self._move_choice_content(dy)

        if self.player.top <= self.wall.bottom and self.player.bottom >= self.wall.top:
            if self.player.colliderect(self.wall):
                choice=-1
                if self.player.colliderect(self.door1): choice=0
                elif self.player.colliderect(self.door2): choice=1
                
                ans = self.current_quiz.get('a', -1)
                
                if choice == ans:
                    # 正解
                    self.history.append({"quiz":self.current_quiz, "was_correct":True, "player_choice":choice})
                    
                    if self.in_assessment:
                        self.state = "CORRECT"
                        self.correct_flash_start = pygame.time.get_ticks()
                        self.assessment_correct_count += 1
                        self.current_assessment_grade = min(6, self.current_assessment_grade + 1)
                        self.assessment_stage += 1
                    else:
                        # ゲーム本番：難易度調整
                        self.adjust_difficulty(True)
                        
                        self.question_count += 1; self.state = "CORRECT"; self.correct_flash_start = pygame.time.get_ticks()
                        if g_game_mode == "TEN_QUESTIONS" and self.question_count >= 10: self.pending_clear = True
                else:
                    # 不正解
                    self.last_incorrect = {"quiz":self.current_quiz, "choice":choice}
                    self.history.append({"quiz":self.current_quiz, "was_correct":False, "player_choice":choice})
                    
                    if self.in_assessment:
                        self.state = "ASSESSMENT_WRONG"
                        self.correct_flash_start = pygame.time.get_ticks()
                        self.current_assessment_grade = max(1, self.current_assessment_grade - 1)
                        self.assessment_stage += 1
                    else:
                        # ゲーム本番：難易度調整
                        self.adjust_difficulty(False)
                        
                        self.state = "GAME_OVER"; self.finished = True; self.finish_time = time.time()
                        self.spawn_break_particles()

    def advance_assessment(self):
        if self.assessment_stage >= ASSESSMENT_QUESTION_COUNT:
            subj = ASSESSMENT_SUBJECTS[self.current_assessment_subject_idx]
            self.assessment_results[subj] = self.current_assessment_grade
            
            # 正解率で難易度決定 (5問中)
            # 4-5問正解: 難しい, 2-3問: 普通, 0-1問: 簡単
            if self.assessment_correct_count >= 4:
                diff = "難しい"
            elif self.assessment_correct_count >= 2:
                diff = "普通"
            else:
                diff = "簡単"
            diff = _effective_difficulty(subj, self.current_assessment_grade, diff)
            PLAYER_CONFIGS[self.pid]["difficulties"][subj] = diff
            
            self.current_assessment_subject_idx += 1
            if self.current_assessment_subject_idx >= len(ASSESSMENT_SUBJECTS):
                PLAYER_CONFIGS[self.pid]["subject_grades"] = self.assessment_results.copy()
                PLAYER_CONFIGS[self.pid]["grade"] = self.assessment_results.get("算数", 3)
                self.finished = True
                self.state = "WAITING"
            else:
                self.assessment_stage = 0
                self.assessment_correct_count = 0
                self.current_assessment_grade = 3 
                self.set_assessment_question()
        else:
            self.set_assessment_question()

    def draw(self, surf:pygame.Surface):
        v=self.viewport
        pygame.draw.rect(surf, (230,230,230), v, 0); pygame.draw.rect(surf, BLACK, v, 2)
        pygame.draw.rect(surf, GRAY, self.wall); pygame.draw.rect(surf, WHITE, self.door1); pygame.draw.rect(surf, WHITE, self.door2)
        if self.state != "GAME_OVER": pygame.draw.rect(surf, BLACK, self.player)
        for p in self.particles: p.draw(surf)
        
        # 問題文が見やすいように背景を追加
        if self.quiz_image_surf and self.quiz_image_rect:
            img_bg = self.quiz_image_rect.inflate(20, 20)
            bg_surf = pygame.Surface((img_bg.width, img_bg.height), pygame.SRCALPHA)
            bg_surf.fill((255, 255, 255, 235))
            surf.blit(bg_surf, img_bg.topleft)
            pygame.draw.rect(surf, BLACK, img_bg, 2, border_radius=10)
            surf.blit(self.quiz_image_surf, self.quiz_image_rect)
        if self.q_surf: 
            bg_rect = self.q_rect.inflate(20, 20)
            bg_surf = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
            bg_surf.fill((255, 255, 255, 230))
            surf.blit(bg_surf, bg_rect.topleft)
            pygame.draw.rect(surf, BLACK, bg_rect, 2, border_radius=8)
            surf.blit(self.q_surf, self.q_rect)

        for idx, image_surf in enumerate(self.choice_image_surfs):
            image_rect = self.choice_image_rects[idx]
            if not image_surf or not image_rect:
                continue
            frame = image_rect.inflate(12, 12)
            pygame.draw.rect(surf, (248, 248, 248), frame, border_radius=10)
            pygame.draw.rect(surf, GRAY, frame, 1, border_radius=10)
            surf.blit(image_surf, image_rect)
        if self.c1_surf and self.c1_rect: surf.blit(self.c1_surf, self.c1_rect)
        if self.c2_surf and self.c2_rect: surf.blit(self.c2_surf, self.c2_rect)
        
        if self.in_assessment and self.state != "WAITING":
            subj = ASSESSMENT_SUBJECTS[self.current_assessment_subject_idx]
            q_num = min(self.assessment_stage + 1, ASSESSMENT_QUESTION_COUNT)
            header_text = f"【診断中】{subj} Q{q_num}/{ASSESSMENT_QUESTION_COUNT}"
            f_head = pygame.font.SysFont("Meiryo", 24)
            h_surf = f_head.render(header_text, True, RED)
            # 診断ヘッダーも見やすく背景追加
            h_bg_rect = h_surf.get_rect(topleft=(v.left + 20, v.top + 20)).inflate(10, 10)
            pygame.draw.rect(surf, (255,255,255,200), h_bg_rect, border_radius=4)
            surf.blit(h_surf, (v.left + 20, v.top + 20))

        if self.state == "CORRECT":
            f=pygame.font.SysFont("Meiryo", 56); s=f.render("正解！", True, GREEN)
            r=s.get_rect(center=v.center); pygame.draw.rect(surf, WHITE, r.inflate(24,16), border_radius=12); surf.blit(s, r)
        elif self.state == "ASSESSMENT_WRONG":
            f=pygame.font.SysFont("Meiryo", 80); s=f.render("×", True, RED)
            r=s.get_rect(center=v.center); surf.blit(s, r)
        elif self.state == "WAITING":
            f=pygame.font.SysFont("Meiryo", 40); s=f.render("判定待ち...", True, GRAY)
            r=s.get_rect(center=v.center); surf.blit(s, r)
        elif self.state == "GAME_OVER":
            overlay = pygame.Surface((v.w, v.h), pygame.SRCALPHA); overlay.fill((0,0,0,120)); surf.blit(overlay, v.topleft)
            title = pygame.font.SysFont("Meiryo", 44).render("GAME OVER", True, GOLD)
            tr = title.get_rect(center=(v.centerx, v.top+int(v.h*0.15))); surf.blit(title, tr)
            if self.last_incorrect:
                panel_rect = pygame.Rect(v.left + v.w * 0.05, tr.bottom + 20, v.w * 0.9, v.h * 0.5)
                pygame.draw.rect(surf, EXPLANATION_BG, panel_rect, border_radius=15); pygame.draw.rect(surf, GRAY, panel_rect, 2, border_radius=15)
                q = self.last_incorrect["quiz"]; ans_idx = q.get('a', 0); padding = 15; current_y = panel_rect.top + padding; panel_inner_width = panel_rect.width - padding * 2
                font_header = pygame.font.SysFont("Meiryo", 24); font_body = pygame.font.SysFont("Meiryo", 22)
                q_header_surf = font_header.render("問題", True, BLACK); surf.blit(q_header_surf, (panel_rect.left + padding, current_y)); current_y += q_header_surf.get_height()
                q_body_surf = render_text_wrapped(q.get('q', ''), panel_inner_width, 22, GRAY); surf.blit(q_body_surf, (panel_rect.left + padding, current_y)); current_y += q_body_surf.get_height() + padding
                a_header_surf = font_header.render("正解", True, GREEN); surf.blit(a_header_surf, (panel_rect.left + padding, current_y)); current_y += a_header_surf.get_height()
                correct_text = q.get('c', ["", ""])[ans_idx]; a_body_surf = render_text_wrapped(correct_text, panel_inner_width, 22, GREEN); surf.blit(a_body_surf, (panel_rect.left + padding, current_y)); current_y += a_body_surf.get_height() + padding
                e_header_surf = font_header.render("解説", True, BLACK); surf.blit(e_header_surf, (panel_rect.left + padding, current_y)); current_y += e_header_surf.get_height()
                exp_text = q.get('e') or q.get('exp') or "解説なし"; e_body_surf = render_text_wrapped(exp_text, panel_inner_width, 20, GRAY); surf.blit(e_body_surf, (panel_rect.left + padding, current_y))
        elif self.state == "CLEAR":
            f=pygame.font.SysFont("Meiryo", 40); s=f.render("CLEAR! おめでとう", True, GOLD); surf.blit(s, s.get_rect(center=v.center))

# ===================== メニュー/UI =====================
MODE_TEN = "TEN_QUESTIONS"; MODE_ENDLESS = "ENDLESS"
g_game_mode = MODE_TEN; player_count = 1
title_buttons = {}; back_to_title_button_rect = pygame.Rect(0,0,0,0)
start_button_rect = pygame.Rect(0,0,0,0); grade_buttons, subject_buttons = {}, {}

results_return_rect = pygame.Rect(0,0,0,0); results_retry_rect = pygame.Rect(0,0,0,0)
results_history_button_rect = pygame.Rect(0,0,0,0)
goto_result_button_rect = pygame.Rect(0,0,0,0)
history_back_button_rect = pygame.Rect(0,0,0,0)
history_p1_tab = pygame.Rect(0,0,0,0)
history_p2_tab = pygame.Rect(0,0,0,0)
history_scroll_y = 0; history_viewing_pid = 1; total_content_height = 0

toggle_players_rect, toggle_llm_rect, toggle_speed_rect = None, None, None
title_settings_button_rect = pygame.Rect(0,0,0,0)
assessment_ok_button_rect = pygame.Rect(0,0,0,0)

settings_back_button_rect = pygame.Rect(0,0,0,0)
difficulty_toggle_rects = {} 

config_p1_tab = pygame.Rect(0,0,0,0)
config_p2_tab = pygame.Rect(0,0,0,0)

# 評価UI用
rating_target_quiz = None
rating_done = False
button_good_rect = pygame.Rect(0,0,0,0)
button_bad_rect = pygame.Rect(0,0,0,0)

# 履歴画面の評価ボタン管理用
history_eval_buttons = []

def draw_player_tabs(y_pos, w, x=None):
    global config_p1_tab, config_p2_tab
    if player_count == 1:
        return

    tab_w, tab_h = 170, 44
    left_x = x if x is not None else max(36, int(w * 0.07))
    config_p1_tab = pygame.Rect(left_x, y_pos, tab_w, tab_h)
    config_p2_tab = pygame.Rect(left_x + tab_w + 14, y_pos, tab_w, tab_h)

    active_bg = (34, 38, 42)
    inactive_bg = (230, 224, 210)
    border = (214, 204, 183)
    font = get_ui_font(22, bold=True)

    for pid, rect in ((1, config_p1_tab), (2, config_p2_tab)):
        active = current_editing_pid == pid
        pygame.draw.rect(screen, active_bg if active else inactive_bg, rect, border_radius=14)
        pygame.draw.rect(screen, border, rect, width=2, border_radius=14)
        label = PLAYER_CONFIGS[pid]["name"]
        surf = font.render(label, True, WHITE if active else (34, 38, 42))
        screen.blit(surf, surf.get_rect(center=rect.center))

def draw_title():
    w, h = screen.get_size()
    screen.fill((244, 240, 232))

    left_x = max(36, int(w * 0.07))
    compact_layout = w < 1080
    if compact_layout:
        content_w = w - left_x * 2
        panel_x = left_x
        panel_w = content_w
    else:
        content_w = min(int(w * 0.48), 520)
        panel_x = max(32, int(w * 0.58))
        panel_w = min(w - panel_x - 36, 380)

    font_title = get_ui_font(58, bold=True)
    font_section = get_ui_font(18, bold=True)
    font_button = get_ui_font(26, bold=True)
    font_chip_value = get_ui_font(22)
    font_meta = get_ui_font(18)
    font_small = get_ui_font(16)

    title_main = font_title.render("AI\u8131\u51fa\u30af\u30a4\u30ba", True, (34, 38, 42))
    screen.blit(title_main, (left_x, int(h * 0.08)))

    user_info = PLAYER_CONFIGS[1]["name"]
    if player_count == 2:
        user_info += f" / {PLAYER_CONFIGS[2]['name']}"
    badge = pygame.Rect(0, 0, min(300, w // 3), 44)
    badge.topright = (w - 28, 24)
    pygame.draw.rect(screen, (34, 38, 42), badge, border_radius=22)
    badge_text = font_meta.render(user_info, True, (245, 242, 232))
    screen.blit(badge_text, badge_text.get_rect(center=badge.center))

    hero_top = int(h * 0.19)
    hero_card_h = int(h * (0.40 if compact_layout else 0.50))
    hero_card = pygame.Rect(left_x, hero_top, content_w, hero_card_h)
    pygame.draw.rect(screen, (255, 252, 245), hero_card, border_radius=26)
    pygame.draw.rect(screen, (214, 204, 183), hero_card, width=2, border_radius=26)

    section_label = font_section.render("PLAY MODE", True, (165, 88, 42))
    screen.blit(section_label, (hero_card.x + 26, hero_card.y + 22))

    title_buttons.clear()
    mode_gap = 18
    mode_y = hero_card.y + 62
    mode_w = hero_card.w - 52
    mode_h = 96
    title_buttons[MODE_TEN] = pygame.Rect(hero_card.x + 26, mode_y, mode_w, mode_h)
    title_buttons[MODE_ENDLESS] = pygame.Rect(hero_card.x + 26, mode_y + mode_h + mode_gap, mode_w, mode_h)

    mode_desc = {
        MODE_TEN: ("10\u554f\u30c1\u30e3\u30ec\u30f3\u30b8", "10\u554f\u3067\u30b9\u30b3\u30a2\u3092\u7af6\u3046\u77ed\u671f\u6c7a\u6226"),
        MODE_ENDLESS: ("\u30a8\u30f3\u30c9\u30ec\u30b9", "\u554f\u984c\u3092\u89e3\u304d\u7d9a\u3051\u308b\u7d99\u7d9a\u30d7\u30ec\u30a4")
    }
    mode_colors = {
        MODE_TEN: ((29, 78, 137), (237, 244, 252)),
        MODE_ENDLESS: ((168, 73, 43), (252, 240, 232))
    }
    for mode, rect in title_buttons.items():
        accent, bg = mode_colors[mode]
        pygame.draw.rect(screen, bg, rect, border_radius=22)
        pygame.draw.rect(screen, accent, rect, width=3, border_radius=22)
        pygame.draw.rect(screen, accent, (rect.x + 16, rect.y + 16, 10, rect.h - 32), border_radius=5)
        cap, desc = mode_desc[mode]
        cap_surf = font_button.render(cap, True, (28, 32, 36))
        desc_surf = font_meta.render(desc, True, (96, 101, 106))
        screen.blit(cap_surf, (rect.x + 42, rect.y + 18))
        screen.blit(desc_surf, (rect.x + 44, rect.y + 56))

    global title_settings_button_rect
    title_settings_button_rect = pygame.Rect(hero_card.x + 26, hero_card.bottom - 72, mode_w, 52)
    pygame.draw.rect(screen, (241, 163, 72), title_settings_button_rect, border_radius=16)
    settings_text = font_button.render("\u96e3\u6613\u5ea6\u30fb\u8a73\u7d30\u8a2d\u5b9a", True, WHITE)
    screen.blit(settings_text, settings_text.get_rect(center=title_settings_button_rect.center))

    side_panel_y = hero_card.bottom + 22 if compact_layout else hero_top
    side_panel_h = int(h * 0.40) if compact_layout else int(h * 0.58)
    side_panel = pygame.Rect(panel_x, side_panel_y, panel_w, side_panel_h)
    pygame.draw.rect(screen, (255, 250, 240), side_panel, border_radius=26)
    pygame.draw.rect(screen, (219, 210, 190), side_panel, width=2, border_radius=26)

    panel_title = font_section.render("QUICK SETTINGS", True, (75, 79, 84))
    screen.blit(panel_title, (side_panel.x + 22, side_panel.y + 20))

    chip_x = side_panel.x + 22
    chip_w = side_panel.w - 44
    chip_h = 74
    chip_gap = 18

    def draw_chip(rect, label, value, bg, fg):
        pygame.draw.rect(screen, bg, rect, border_radius=18)
        pygame.draw.rect(screen, (214, 204, 183), rect, width=2, border_radius=18)
        label_surf = font_meta.render(label, True, (92, 97, 103))
        screen.blit(label_surf, (rect.x + 16, rect.y + 10))

        arrow_surf = font_small.render("\u30af\u30ea\u30c3\u30af\u3067\u5909\u66f4", True, (120, 124, 129))
        screen.blit(arrow_surf, arrow_surf.get_rect(topright=(rect.right - 16, rect.y + 12)))

        value_max_w = rect.w - 32
        value_surf = render_text_wrapped(value, value_max_w, 22, fg, "Meiryo")
        value_y = rect.y + 34
        screen.blit(value_surf, (rect.x + 16, value_y))

    toggle_players_bg_rect = pygame.Rect(chip_x, side_panel.y + 58, chip_w, chip_h)
    draw_chip(toggle_players_bg_rect, "\u30d7\u30ec\u30a4\u30e4\u30fc\u6570", f"{player_count}\u4eba", (239, 243, 246), (32, 37, 42))

    spd_labels = {"SLOW": "\u3086\u3063\u304f\u308a", "NORMAL": "\u6a19\u6e96", "FAST": "\u306f\u3084\u3044"}
    toggle_speed_bg_rect = pygame.Rect(chip_x, toggle_players_bg_rect.bottom + chip_gap, chip_w, chip_h)
    draw_chip(toggle_speed_bg_rect, "\u30b9\u30d4\u30fc\u30c9", spd_labels[current_speed_level], (242, 239, 231), (32, 37, 42))

    llm_value = "ONLINE / AI\u751f\u6210" if LLM_MODE == "ONLINE" else "OFFLINE / \u5185\u8535\u554f\u984c"
    toggle_llm_bg_rect = pygame.Rect(chip_x, toggle_speed_bg_rect.bottom + chip_gap, chip_w, chip_h)
    draw_chip(toggle_llm_bg_rect, "\u51fa\u984c\u65b9\u5f0f", llm_value, (234, 242, 236), (32, 37, 42))

    return toggle_players_bg_rect, toggle_llm_bg_rect, toggle_speed_bg_rect

def draw_settings():
    w, h = screen.get_size()
    screen.fill((244, 240, 232))

    left_x = max(36, int(w * 0.07))
    card_w = min(w - left_x * 2, 980)
    card_x = (w - card_w) // 2
    card_y = int(h * 0.16)
    card_h = int(h * 0.68)

    title_font = get_ui_font(46, bold=True)
    section_font = get_ui_font(18, bold=True)
    body_font = get_ui_font(28, bold=True)
    meta_font = get_ui_font(18)

    title = title_font.render("\u96e3\u6613\u5ea6\u8a2d\u5b9a", True, (34, 38, 42))
    screen.blit(title, (card_x, int(h * 0.07)))

    global settings_back_button_rect
    settings_back_button_rect = pygame.Rect(card_x + card_w - 150, int(h * 0.07), 150, 46)
    pygame.draw.rect(screen, (230, 224, 210), settings_back_button_rect, border_radius=16)
    pygame.draw.rect(screen, (214, 204, 183), settings_back_button_rect, width=2, border_radius=16)
    back_surf = get_ui_font(22, bold=True).render("\u623b\u308b", True, (34, 38, 42))
    screen.blit(back_surf, back_surf.get_rect(center=settings_back_button_rect.center))

    pygame.draw.rect(screen, (255, 252, 245), (card_x, card_y, card_w, card_h), border_radius=26)
    pygame.draw.rect(screen, (214, 204, 183), (card_x, card_y, card_w, card_h), width=2, border_radius=26)

    section = section_font.render("SUBJECT SETTINGS", True, (165, 88, 42))
    screen.blit(section, (card_x + 26, card_y + 22))
    draw_player_tabs(card_y + 56, w, card_x + 26)

    difficulty_toggle_rects.clear()
    subjects = ["算数", "理科", "国語"]
    row_x = card_x + 26
    row_y = card_y + 126
    row_w = card_w - 52
    row_h = 88
    row_gap = 20

    color_map = {
        "簡単": ((228, 243, 217), (96, 141, 67)),
        "普通": ((237, 244, 252), (29, 78, 137)),
        "難しい": ((252, 234, 228), (168, 73, 43)),
    }

    for i, subj in enumerate(subjects):
        y = row_y + i * (row_h + row_gap)
        row_rect = pygame.Rect(row_x, y, row_w, row_h)
        pygame.draw.rect(screen, (248, 245, 238), row_rect, border_radius=20)
        pygame.draw.rect(screen, (214, 204, 183), row_rect, width=2, border_radius=20)

        subj_surf = body_font.render(subj, True, (34, 38, 42))
        screen.blit(subj_surf, (row_rect.x + 22, row_rect.y + 18))

        desc_surf = meta_font.render("\u30af\u30ea\u30c3\u30af\u3067\u5207\u308a\u66ff\u3048", True, (120, 124, 129))
        screen.blit(desc_surf, (row_rect.x + 24, row_rect.y + 52))

        diff = PLAYER_CONFIGS[current_editing_pid]["difficulties"].get(subj, "普通")
        chip_bg, chip_border = color_map.get(diff, ((237, 244, 252), (29, 78, 137)))
        btn_rect = pygame.Rect(row_rect.right - 190, row_rect.y + 16, 168, 56)
        difficulty_toggle_rects[subj] = btn_rect
        pygame.draw.rect(screen, chip_bg, btn_rect, border_radius=16)
        pygame.draw.rect(screen, chip_border, btn_rect, width=2, border_radius=16)
        diff_surf = get_ui_font(24, bold=True).render(diff, True, chip_border)
        screen.blit(diff_surf, diff_surf.get_rect(center=btn_rect.center))

def draw_select():
    w, h = screen.get_size()
    layout_select()
    screen.fill((244, 240, 232))

    left_x = max(36, int(w * 0.07))
    card_w = min(w - left_x * 2, 980)
    card_x = (w - card_w) // 2
    card_y = int(h * 0.16)
    card_h = int(h * 0.68)

    title_font = get_ui_font(46, bold=True)
    section_font = get_ui_font(18, bold=True)
    chip_font = get_ui_font(24, bold=True)
    meta_font = get_ui_font(18)
    small_font = get_ui_font(20)

    title = title_font.render("\u5b66\u5e74\u3068\u6559\u79d1\u3092\u9078\u629e", True, (34, 38, 42))
    screen.blit(title, (card_x, int(h * 0.07)))

    pygame.draw.rect(screen, (255, 252, 245), (card_x, card_y, card_w, card_h), border_radius=26)
    pygame.draw.rect(screen, (214, 204, 183), (card_x, card_y, card_w, card_h), width=2, border_radius=26)

    pygame.draw.rect(screen, (230, 224, 210), back_to_title_button_rect, border_radius=16)
    pygame.draw.rect(screen, (214, 204, 183), back_to_title_button_rect, width=2, border_radius=16)
    back_surf = get_ui_font(22, bold=True).render("\u623b\u308b", True, (34, 38, 42))
    screen.blit(back_surf, back_surf.get_rect(center=back_to_title_button_rect.center))

    curr_conf = PLAYER_CONFIGS[1]

    section1 = section_font.render("GRADE", True, (165, 88, 42))
    screen.blit(section1, (card_x + 26, card_y + 24))

    for g, r in grade_buttons.items():
        active = curr_conf["grade"] == g
        bg = (34, 38, 42) if active else (248, 245, 238)
        fg = WHITE if active else (34, 38, 42)
        pygame.draw.rect(screen, bg, r, border_radius=18)
        pygame.draw.rect(screen, (214, 204, 183), r, width=2, border_radius=18)
        lab = chip_font.render(f"{g}\u5e74\u751f", True, fg)
        screen.blit(lab, lab.get_rect(center=r.center))

    section2 = section_font.render("SUBJECT", True, (165, 88, 42))
    screen.blit(section2, (card_x + 26, card_y + int(card_h * 0.48)))

    for s, r in subject_buttons.items():
        active = curr_conf["subject"] == s
        bg = (34, 38, 42) if active else (248, 245, 238)
        fg = WHITE if active else (34, 38, 42)
        pygame.draw.rect(screen, bg, r, border_radius=18)
        pygame.draw.rect(screen, (214, 204, 183), r, width=2, border_radius=18)
        lab = chip_font.render(s, True, fg)
        screen.blit(lab, lab.get_rect(center=r.center))

    if player_count == 2:
        hint1 = small_font.render("1P\u79fb\u52d5: A / D", True, (96, 101, 106))
        hint2 = small_font.render("2P\u79fb\u52d5: \u2190 / \u2192", True, (96, 101, 106))
        hint_y = start_button_rect.y - 56
        screen.blit(hint1, (card_x + 26, hint_y))
        screen.blit(hint2, (card_x + 280, hint_y))

    start_note = meta_font.render("\u9078\u629e\u3057\u305f\u8a2d\u5b9a\u3067\u30b2\u30fc\u30e0\u3092\u958b\u59cb", True, (120, 124, 129))
    note_y = start_button_rect.y - 28 if player_count == 1 else start_button_rect.y - 30
    screen.blit(start_note, (start_button_rect.x, note_y))
    pygame.draw.rect(screen, (241, 163, 72), start_button_rect, border_radius=18)
    start_surf = get_ui_font(34, bold=True).render("\u30b2\u30fc\u30e0\u958b\u59cb", True, WHITE)
    screen.blit(start_surf, start_surf.get_rect(center=start_button_rect.center))

def draw_assessment_result():
    w, h = screen.get_size()
    screen.fill(WHITE)
    fontL = pygame.font.SysFont("Meiryo", 48)
    title = fontL.render("診断結果", True, BLACK)
    screen.blit(title, title.get_rect(center=(w // 2, int(h * 0.15))))
    fontM = pygame.font.SysFont("Meiryo", 28)
    p_ids = [1] if player_count == 1 else [1, 2]
    base_y = int(h * 0.3)
    
    area_width = w // len(p_ids)
    
    for i, pid in enumerate(p_ids):
        res = PLAYER_CONFIGS[pid].get("subject_grades", {})
        center_x = area_width * i + area_width // 2
        p_name = fontM.render(PLAYER_CONFIGS[pid]['name'], True, BLUE)
        screen.blit(p_name, p_name.get_rect(center=(center_x, base_y)))
        y_off = 50
        for subj in ASSESSMENT_SUBJECTS:
            gr = res.get(subj, 3)
            diff = PLAYER_CONFIGS[pid]["difficulties"].get(subj, "普通")
            txt = f"{subj}: {gr}年生 ({diff})"
            s_surf = fontM.render(txt, True, BLACK)
            screen.blit(s_surf, s_surf.get_rect(center=(center_x, base_y + y_off)))
            y_off += 40
    
    global assessment_ok_button_rect
    assessment_ok_button_rect = pygame.Rect(w//2 - 120, h - 150, 240, 70)
    pygame.draw.rect(screen, RED, assessment_ok_button_rect, border_radius=12)
    ok_txt = fontM.render("設定して次へ", True, WHITE)
    screen.blit(ok_txt, ok_txt.get_rect(center=assessment_ok_button_rect.center))

def layout_select():
    w, h = screen.get_size()
    grade_buttons.clear()
    subject_buttons.clear()
    global back_to_title_button_rect, start_button_rect

    left_x = max(36, int(w * 0.07))
    card_w = min(w - left_x * 2, 980)
    card_x = (w - card_w) // 2
    card_y = int(h * 0.16)
    card_h = int(h * 0.68)

    back_to_title_button_rect = pygame.Rect(card_x + card_w - 150, int(h * 0.07), 150, 46)

    grade_area_x = card_x + 26
    grade_area_y = card_y + 58
    gap_x = 18
    gap_y = 18
    btn_w = int((card_w - 52 - gap_x * 2) / 3)
    btn_h = 72
    for i, g in enumerate([1, 2, 3, 4, 5, 6]):
        x = grade_area_x + (i % 3) * (btn_w + gap_x)
        y = grade_area_y + (i // 3) * (btn_h + gap_y)
        grade_buttons[g] = pygame.Rect(x, y, btn_w, btn_h)

    subject_area_y = card_y + int(card_h * 0.56)
    subj_gap = 18
    subj_w = int((card_w - 52 - subj_gap * 2) / 3)
    subj_h = 76
    subjects = ["算数", "理科", "国語"]
    for i, s in enumerate(subjects):
        x = grade_area_x + i * (subj_w + subj_gap)
        subject_buttons[s] = pygame.Rect(x, subject_area_y, subj_w, subj_h)

    start_button_rect = pygame.Rect(card_x + 26, card_y + card_h - 58, card_w - 52, 54)

def draw_history():
    global total_content_height, history_back_button_rect, history_p1_tab, history_p2_tab, history_eval_buttons
    history_eval_buttons.clear()
    
    w, h = screen.get_size()
    screen.fill(WHITE)
    header_h = int(h * 0.15)
    pygame.draw.rect(screen, WHITE, (0, 0, w, header_h))
    title_font = pygame.font.SysFont("Meiryo", 40)
    title_str = "出題記録"
    if player_count > 1: title_str += f" ({PLAYER_CONFIGS[history_viewing_pid]['name']})"
    title = title_font.render(title_str, True, BLACK)
    screen.blit(title, title.get_rect(center=(w // 2, 40)))
    if player_count > 1:
        tab_w, tab_h = 200, 40
        history_p1_tab = pygame.Rect(w // 2 - tab_w - 10, 80, tab_w, tab_h)
        history_p2_tab = pygame.Rect(w // 2 + 10, 80, tab_w, tab_h)
        col1 = BLUE if history_viewing_pid == 1 else LIGHT_GRAY
        col2 = BLUE if history_viewing_pid == 2 else LIGHT_GRAY
        pygame.draw.rect(screen, col1, history_p1_tab, border_radius=8)
        pygame.draw.rect(screen, col2, history_p2_tab, border_radius=8)
        t1 = pygame.font.SysFont("Meiryo", 24).render("Player 1", True, WHITE if history_viewing_pid==1 else BLACK)
        t2 = pygame.font.SysFont("Meiryo", 24).render("Player 2", True, WHITE if history_viewing_pid==2 else BLACK)
        screen.blit(t1, t1.get_rect(center=history_p1_tab.center))
        screen.blit(t2, t2.get_rect(center=history_p2_tab.center))
    history_back_button_rect = pygame.Rect(20, 20, 100, 40)
    pygame.draw.rect(screen, LIGHT_GRAY, history_back_button_rect, border_radius=8)
    back_txt = pygame.font.SysFont("Meiryo", 24).render("戻る", True, BLACK)
    screen.blit(back_txt, back_txt.get_rect(center=history_back_button_rect.center))
    pygame.draw.line(screen, GRAY, (0, header_h), (w, header_h), 2)
    content_area = pygame.Rect(0, header_h, w, h - header_h)
    screen.set_clip(content_area)
    target_history = []
    if players:
        for p in players:
            if p.pid == history_viewing_pid: target_history = p.history; break
    if not target_history:
        no_data = pygame.font.SysFont("Meiryo", 32).render("履歴はありません", True, GRAY)
        screen.blit(no_data, no_data.get_rect(center=content_area.center))
        screen.set_clip(None)
        return
    y_offset = header_h + 20 + history_scroll_y
    card_width = int(w * 0.8)
    card_x = (w - card_width) // 2
    padding = 15
    font_q = pygame.font.SysFont("Meiryo", 24)
    font_a = pygame.font.SysFont("Meiryo", 22)
    
    for record in reversed(target_history):
        q_data = record["quiz"]
        was_correct = record["was_correct"]
        p_choice_idx = record.get("player_choice", -1)
        q_text_surf = render_text_wrapped(f"Q. {q_data.get('q','')}", card_width - padding*2, 24, BLACK)
        ans_str = q_data['c'][p_choice_idx] if 0 <= p_choice_idx < len(q_data['c']) else "未回答"
        result_str = "正解" if was_correct else "不正解"
        result_color = GREEN if was_correct else RED
        res_surf = font_a.render(f"あなたの答え: {ans_str} ({result_str})", True, result_color)
        exp_txt = q_data.get('e') or q_data.get('exp') or "解説なし"
        exp_surf = render_text_wrapped(f"解説: {exp_txt}", card_width - padding*2, 20, GRAY)
        
        btn_area_h = 40
        card_h = padding + q_text_surf.get_height() + 10 + res_surf.get_height() + 10 + exp_surf.get_height() + 10 + btn_area_h + padding
        
        if y_offset + card_h > 0 and y_offset < h:
            card_rect = pygame.Rect(card_x, y_offset, card_width, card_h)
            pygame.draw.rect(screen, EXPLANATION_BG, card_rect, border_radius=10)
            pygame.draw.rect(screen, GRAY, card_rect, 1, border_radius=10)
            cur_y = y_offset + padding
            screen.blit(q_text_surf, (card_x + padding, cur_y))
            cur_y += q_text_surf.get_height() + 10
            screen.blit(res_surf, (card_x + padding, cur_y))
            cur_y += res_surf.get_height() + 10
            screen.blit(exp_surf, (card_x + padding, cur_y))
            cur_y += exp_surf.get_height() + 10
            
            # 各履歴カードに評価ボタンを追加
            good_btn = pygame.Rect(card_x + padding, cur_y, 100, 36)
            bad_btn = pygame.Rect(card_x + padding + 110, cur_y, 100, 36)
            
            is_good = any(q.get("q") == q_data.get("q") for q in quiz_ratings["good"])
            is_bad = _is_bad_question(
                q_data.get("q", ""),
                PLAYER_CONFIGS[history_viewing_pid]["subject"],
                PLAYER_CONFIGS[history_viewing_pid]["grade"],
            )
            
            if is_good:
                pygame.draw.rect(screen, ORANGE, good_btn, border_radius=6)
                t_g = font_a.render("★ 良い", True, WHITE)
                screen.blit(t_g, t_g.get_rect(center=good_btn.center))
            elif is_bad:
                pygame.draw.rect(screen, NAVY, bad_btn, border_radius=6)
                t_b = font_a.render("× 悪い", True, WHITE)
                screen.blit(t_b, t_b.get_rect(center=bad_btn.center))
            else:
                pygame.draw.rect(screen, LIGHT_GRAY, good_btn, border_radius=6)
                pygame.draw.rect(screen, LIGHT_GRAY, bad_btn, border_radius=6)
                t_g = font_a.render("◯ 良い", True, BLACK)
                t_b = font_a.render("× 悪い", True, BLACK)
                screen.blit(t_g, t_g.get_rect(center=good_btn.center))
                screen.blit(t_b, t_b.get_rect(center=bad_btn.center))
                history_eval_buttons.append((good_btn, bad_btn, q_data))
                
        y_offset += card_h + 20
        
    total_content_height = (y_offset - history_scroll_y) - header_h
    screen.set_clip(None)

# ===================== ゲーム実体 =====================
players=[]; 

def build_players():
    global players; players = []
    w,h = screen.get_size()
    if player_count == 1:
        players.append(Player(1, pygame.Rect(0,0,w,h), pygame.K_LEFT, pygame.K_RIGHT))
    else:
        players.append(Player(1, pygame.Rect(0,0,w//2,h), pygame.K_a, pygame.K_d))
        players.append(Player(2, pygame.Rect(w//2,0,w-w//2,h), pygame.K_LEFT, pygame.K_RIGHT))

def start_preload():
    global preload_started_at
    stop_event.clear()
    preload_started_at = time.time()
    with buffer_lock:
        quiz_buffers[1].clear(); quiz_buffers[2].clear()
        seen_questions[1].clear(); seen_questions[2].clear()
        play_histories[1].clear(); play_histories[2].clear()
        generation_inflight[1] = 0; generation_inflight[2] = 0
        generation_started_at[1] = None; generation_started_at[2] = None
        grade_fit_reject_streak[1] = 0; grade_fit_reject_streak[2] = 0
        
    if not any(t.is_alive() for t in api_threads):
        api_threads.clear()
        for i in range(NUM_API_WORKERS):
            t = threading.Thread(target=api_worker, args=(i + 1,), daemon=True); api_threads.append(t); t.start()

def start_assessment():
    stop_event.clear()
    # 診断モード用にプレイヤー作成
    build_players()
    for p in players:
        p.in_assessment = True
        p.assessment_stage = 0
        p.current_assessment_subject_idx = 0
        p.current_assessment_grade = 3 # スタート
        p.assessment_results = {}
        p.assessment_correct_count = 0 # 初期化
        p.finished = False
        p.set_assessment_question()

def assign_initial_questions():
    ready = True
    for p in players:
        if g_game_mode == "TEN_QUESTIONS":
            with buffer_lock:
                p.fixed_questions = list(quiz_buffers[p.pid])[:10]
            p.fixed_question_index = 0
        if not p.set_new_question(): ready = False
    return ready

def _score(p:Player): return p.question_count
def _ranking(players_list):
    arr=[{'pid':p.pid,'score':_score(p),'finish':p.finish_time or time.time(),'state':p.state} for p in players_list]
    arr.sort(key=lambda x: (-x['score'], x['finish'])); return arr

# ===================== メインループ =====================
running=True
while running:
    w,h = screen.get_size()
    for e in pygame.event.get():
        if e.type == pygame.QUIT: running=False
        elif e.type == pygame.VIDEORESIZE:
            screen = _create_display((e.w, e.h))
            if players:
                for p in players:
                    old_h = p.viewport.height if p.viewport.height > 0 else 1
                    old_w = p.viewport.width if p.viewport.width > 0 else 1
                    wall_ratio = (p.wall.y - p.viewport.top) / old_h
                    player_ratio = (p.player.centerx - p.viewport.left) / old_w
                    if player_count == 1: p.viewport = pygame.Rect(0, 0, e.w, e.h)
                    else: p.viewport = pygame.Rect(0, 0, e.w // 2, e.h) if p.pid==1 else pygame.Rect(e.w // 2, 0, e.w - e.w // 2, e.h)
                    p.reset_geometry()
                    new_wall_y = int(p.viewport.top + wall_ratio * p.viewport.height)
                    p.wall.y = new_wall_y; p.door1.y = p.door2.y = new_wall_y
                    p.player.centerx = int(p.viewport.left + player_ratio * p.viewport.width)
                    p.player.left = max(p.viewport.left, p.player.left)
                    p.player.right = min(p.viewport.right, p.player.right)
                    p.prepare_surfaces()

        elif e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE: running=False
        
        if GAME_STATE == "HISTORY" and e.type == pygame.MOUSEWHEEL:
            history_scroll_y += e.y * 30
            header_h = int(h * 0.15)
            min_scroll = -(total_content_height - (h - header_h)) - 50
            if min_scroll > 0: min_scroll = 0
            if history_scroll_y > 0: history_scroll_y = 0
            if history_scroll_y < min_scroll: history_scroll_y = min_scroll

        if GAME_STATE == "TITLE":
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if toggle_players_rect and toggle_players_rect.collidepoint(e.pos):
                    player_count = 2 if player_count==1 else 1
                    current_editing_pid = 1 
                if toggle_llm_rect and toggle_llm_rect.collidepoint(e.pos): LLM_MODE = "OFFLINE" if LLM_MODE=="ONLINE" else "ONLINE"
                
                if toggle_speed_rect and toggle_speed_rect.collidepoint(e.pos):
                    if current_speed_level == "NORMAL": current_speed_level = "FAST"
                    elif current_speed_level == "FAST": current_speed_level = "SLOW"
                    else: current_speed_level = "NORMAL"
                    base_wall_speed = SPEED_SETTINGS[current_speed_level]

                for k, r in title_buttons.items():
                    if r.collidepoint(e.pos): g_game_mode = k; GAME_STATE = "SELECT"; current_editing_pid = 1
                
                if title_settings_button_rect.collidepoint(e.pos):
                    GAME_STATE = "SETTINGS"; current_editing_pid = 1
                

        elif GAME_STATE == "SETTINGS":
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if settings_back_button_rect.collidepoint(e.pos):
                    GAME_STATE = "TITLE"
                
                if player_count == 2:
                    if config_p1_tab.collidepoint(e.pos): current_editing_pid = 1
                    elif config_p2_tab.collidepoint(e.pos): current_editing_pid = 2

                for subj, rect in difficulty_toggle_rects.items():
                    if rect.collidepoint(e.pos):
                        player_conf = PLAYER_CONFIGS[current_editing_pid]
                        conf = player_conf["difficulties"]
                        current = conf.get(subj, "普通")
                        idx = DIFFICULTY_LEVELS.index(current)
                        next_idx = (idx + 1) % len(DIFFICULTY_LEVELS)
                        grade = player_conf.get("subject_grades", {}).get(subj, player_conf.get("grade", 3))
                        conf[subj] = _effective_difficulty(subj, grade, DIFFICULTY_LEVELS[next_idx])

        elif GAME_STATE == "SELECT":
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if back_to_title_button_rect.collidepoint(e.pos): GAME_STATE = "TITLE"
                
                # 学年と教科は 1P, 2P 共通で設定を反映
                for g, r in grade_buttons.items():
                    if r.collidepoint(e.pos):
                        for pid in [1, 2]:
                            PLAYER_CONFIGS[pid]["grade"] = g
                            for s in PLAYER_CONFIGS[pid]["subject_grades"]: 
                                PLAYER_CONFIGS[pid]["subject_grades"][s] = g
                            for s, d in PLAYER_CONFIGS[pid]["difficulties"].items():
                                PLAYER_CONFIGS[pid]["difficulties"][s] = _effective_difficulty(s, g, d)
                
                for s, r in subject_buttons.items():
                    if r.collidepoint(e.pos):
                        for pid in [1, 2]:
                            PLAYER_CONFIGS[pid]["subject"] = s
                
                if start_button_rect.collidepoint(e.pos):
                    build_players(); start_preload(); GAME_STATE = "PRELOAD"

        elif GAME_STATE == "HISTORY":
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if history_back_button_rect.collidepoint(e.pos):
                    GAME_STATE = "RESULTS"
                elif player_count > 1:
                    if history_p1_tab.collidepoint(e.pos): history_viewing_pid = 1; history_scroll_y = 0
                    elif history_p2_tab.collidepoint(e.pos): history_viewing_pid = 2; history_scroll_y = 0

                # 履歴画面内の各評価ボタンクリック判定
                for g_rect, b_rect, q_data in history_eval_buttons:
                    if g_rect.collidepoint(e.pos):
                        q_data["grade"] = PLAYER_CONFIGS[history_viewing_pid]["grade"]
                        q_data["subject"] = PLAYER_CONFIGS[history_viewing_pid]["subject"]
                        # 重複登録防止
                        if not any(q.get("q") == q_data.get("q") for q in quiz_ratings["good"]):
                            quiz_ratings["good"].append(q_data)
                            save_ratings()
                        break
                    elif b_rect.collidepoint(e.pos):
                        bad_entry = _make_bad_entry(
                            q_data.get("q", ""),
                            PLAYER_CONFIGS[history_viewing_pid]["subject"],
                            PLAYER_CONFIGS[history_viewing_pid]["grade"],
                        )
                        bad_key = _bad_entry_key(bad_entry)
                        existing_bad_keys = {
                            _bad_entry_key(item) for item in quiz_ratings["bad"] if isinstance(item, dict)
                        }
                        if bad_key[0] and bad_key not in existing_bad_keys:
                            quiz_ratings["bad"].append(bad_entry)
                            if len(quiz_ratings["bad"]) > 100: quiz_ratings["bad"].pop(0)
                            save_ratings()
                        break

        elif GAME_STATE == "IN_GAME":
            if all(p.finished for p in players):
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    if goto_result_button_rect.collidepoint(e.pos): 
                        GAME_STATE = "RESULTS"
                        # 評価用問題の抽出
                        rating_done = False
                        all_hist = []
                        for p in players:
                            all_hist.extend([h["quiz"] for h in p.history if "quiz" in h])
                        if all_hist:
                            rating_target_quiz = random.choice(all_hist)
                        else:
                            rating_target_quiz = None
        
        

        elif GAME_STATE == "RESULTS":
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                # 評価ボタンの処理
                if rating_target_quiz and not rating_done:
                    if button_good_rect.collidepoint(e.pos):
                        rating_target_quiz["grade"] = PLAYER_CONFIGS[current_editing_pid]["grade"]
                        rating_target_quiz["subject"] = PLAYER_CONFIGS[current_editing_pid]["subject"]
                        # 重複登録防止
                        if not any(q.get("q") == rating_target_quiz.get("q") for q in quiz_ratings["good"]):
                            quiz_ratings["good"].append(rating_target_quiz)
                            save_ratings()
                        rating_done = True
                    elif button_bad_rect.collidepoint(e.pos):
                        bad_entry = _make_bad_entry(
                            rating_target_quiz.get("q", ""),
                            PLAYER_CONFIGS[current_editing_pid]["subject"],
                            PLAYER_CONFIGS[current_editing_pid]["grade"],
                        )
                        bad_key = _bad_entry_key(bad_entry)
                        existing_bad_keys = {
                            _bad_entry_key(item) for item in quiz_ratings["bad"] if isinstance(item, dict)
                        }
                        if bad_key[0] and bad_key not in existing_bad_keys:
                            quiz_ratings["bad"].append(bad_entry)
                            if len(quiz_ratings["bad"]) > 100: quiz_ratings["bad"].pop(0)
                            save_ratings()
                        rating_done = True

                # 各種ボタンへの画面遷移
                if results_return_rect.collidepoint(e.pos):
                    GAME_STATE = "TITLE"; players.clear()
                elif results_retry_rect.collidepoint(e.pos):
                    build_players(); start_preload(); GAME_STATE = "PRELOAD"
                elif results_history_button_rect.collidepoint(e.pos):
                    GAME_STATE = "HISTORY"; history_scroll_y = 0; history_viewing_pid = 1

    if GAME_STATE == "TITLE":
        toggle_players_rect, toggle_llm_rect, toggle_speed_rect = draw_title()
    elif GAME_STATE == "SETTINGS":
        draw_settings()
    elif GAME_STATE == "SELECT":
        draw_select()
    elif GAME_STATE == "PRELOAD":
        total_needed = 0
        total_loaded = 0
        estimated_inflight = 0.0
        per_player = 10 if g_game_mode == "TEN_QUESTIONS" else 1
        now_ts = time.time()
        ready = True
        with buffer_lock:
            for p in players:
                pid = p.pid
                loaded = len(quiz_buffers[pid])
                total_loaded += loaded
                total_needed += per_player
                if loaded < per_player:
                    ready = False
                inflight = generation_inflight.get(pid, 0)
                started_at = generation_started_at.get(pid)
                if inflight > 0 and started_at is not None:
                    elapsed = max(0.0, now_ts - started_at)
                    estimated_inflight += min(float(inflight), elapsed / PRELOAD_ESTIMATED_SECONDS)
        progress_items = min(float(total_needed), float(total_loaded) + estimated_inflight)
        prog = min(1.0, progress_items / max(1, total_needed))
        if not ready:
            prog = min(prog, 0.99)
        progress_percent = 100 if ready else max(0, min(99, int(prog * 100)))
        prog = progress_percent / 100.0
        loading_text = f"クイズを準備中... ({total_loaded}/{total_needed})" if g_game_mode == "TEN_QUESTIONS" else "クイズを準備中..."
        screen.fill(WHITE)
        f = pygame.font.SysFont("Meiryo", 48); s = f.render(loading_text, True, BLACK)
        screen.blit(s, s.get_rect(center=(w // 2, int(h * 0.4))))
        bar_w, bar_h = int(w * 0.6), 44; bar_x, bar_y = (w - bar_w) // 2, int(h * 0.55)
        pygame.draw.rect(screen, BLACK, (bar_x, bar_y, bar_w, bar_h), 3)
        pygame.draw.rect(screen, LIME, (bar_x+3, bar_y+3, int((bar_w-6) * prog), bar_h-6))
        fontS = pygame.font.SysFont("Meiryo", 24); percent_text = f"{progress_percent}%"
        percent_surf = fontS.render(percent_text, True, BLACK); screen.blit(percent_surf, percent_surf.get_rect(center=(w // 2, bar_y + bar_h // 2)))
        if ready and assign_initial_questions(): GAME_STATE = "IN_GAME"

    elif GAME_STATE == "IN_GAME":
        screen.fill(WHITE)
        keys = pygame.key.get_pressed()
        for p in players: p.update(keys); p.draw(screen)
        if all(p.finished for p in players):
             btn_w, btn_h = 300, 70
             goto_result_button_rect = pygame.Rect((w - btn_w)//2, h - 120, btn_w, btn_h)
             pygame.draw.rect(screen, BLUE, goto_result_button_rect, border_radius=15)
             pygame.draw.rect(screen, WHITE, goto_result_button_rect, 4, border_radius=15)
             font_btn = pygame.font.SysFont("Meiryo", 32)
             txt = font_btn.render("結果を見る", True, WHITE)
             screen.blit(txt, txt.get_rect(center=goto_result_button_rect.center))

    elif GAME_STATE == "RESULTS":
        screen.fill(WHITE)
        ranks = _ranking(players); title = pygame.font.SysFont("Meiryo", 52).render("リザルト", True, BLACK)
        screen.blit(title, title.get_rect(center=(w//2, int(h*0.18)))); f = pygame.font.SysFont("Meiryo", 32)
        y = int(h*0.28)
        for i, r in enumerate(ranks, start=1):
            line = f"{i}位  Player{r['pid']}  スコア:{r['score']}問  ({'CLEAR' if r['state']=='CLEAR' else 'GAME OVER'})"
            row = f.render(line, True, BLACK); screen.blit(row, row.get_rect(center=(w//2, y))); y += 44
        y += 20
        
        # 評価パネル (評価対象がある & まだ評価していない場合)
        if rating_target_quiz and not rating_done:
            panel_w, panel_h = int(w * 0.8), 160
            panel_rect = pygame.Rect((w - panel_w) // 2, y, panel_w, panel_h)
            pygame.draw.rect(screen, EXPLANATION_BG, panel_rect, border_radius=12)
            pygame.draw.rect(screen, GRAY, panel_rect, 2, border_radius=12)
            
            lbl = pygame.font.SysFont("Meiryo", 24).render("この問題はどうでしたか？", True, BLACK)
            screen.blit(lbl, lbl.get_rect(center=(w//2, panel_rect.top + 25)))
            
            q_text = rating_target_quiz.get("q", "")
            if len(q_text) > 30: q_text = q_text[:30] + "..."
            q_surf = pygame.font.SysFont("Meiryo", 22).render(f"Q. {q_text}", True, GRAY)
            screen.blit(q_surf, q_surf.get_rect(center=(w//2, panel_rect.top + 65)))
            
            # ボタン
            button_good_rect = pygame.Rect(w//2 - 140, panel_rect.bottom - 60, 120, 45)
            button_bad_rect = pygame.Rect(w//2 + 20, panel_rect.bottom - 60, 120, 45)
            pygame.draw.rect(screen, ORANGE, button_good_rect, border_radius=8)
            pygame.draw.rect(screen, NAVY, button_bad_rect, border_radius=8)
            
            t_good = pygame.font.SysFont("Meiryo", 22).render("◯ 良い", True, WHITE)
            t_bad = pygame.font.SysFont("Meiryo", 22).render("× 悪い", True, WHITE)
            screen.blit(t_good, t_good.get_rect(center=button_good_rect.center))
            screen.blit(t_bad, t_bad.get_rect(center=button_bad_rect.center))
            
            y += panel_h + 30
        elif rating_done:
            msg = pygame.font.SysFont("Meiryo", 24).render("評価ありがとうございました！", True, GREEN)
            screen.blit(msg, msg.get_rect(center=(w//2, y + 50)))
            y += 120
        else:
            y += 120
            
        button_w, button_h = 260, 60
        spacing = 40
        center_x = w // 2
        results_retry_rect = pygame.Rect(0, 0, button_w, button_h)
        results_retry_rect.center = (center_x - button_w - spacing, y + 60)
        pygame.draw.rect(screen, GREEN, results_retry_rect, border_radius=12)
        txt_retry = pygame.font.SysFont("Meiryo", 28).render("もう一度遊ぶ", True, WHITE)
        screen.blit(txt_retry, txt_retry.get_rect(center=results_retry_rect.center))
        results_history_button_rect = pygame.Rect(0, 0, button_w, button_h)
        results_history_button_rect.center = (center_x, y + 60)
        pygame.draw.rect(screen, ORANGE, results_history_button_rect, border_radius=12)
        txt_hist = pygame.font.SysFont("Meiryo", 28).render("出題記録", True, WHITE)
        screen.blit(txt_hist, txt_hist.get_rect(center=results_history_button_rect.center))
        results_return_rect = pygame.Rect(0, 0, button_w, button_h)
        results_return_rect.center = (center_x + button_w + spacing, y + 60)
        pygame.draw.rect(screen, BLUE, results_return_rect, border_radius=12)
        txt_return = pygame.font.SysFont("Meiryo", 28).render("タイトルへ", True, WHITE)
        screen.blit(txt_return, txt_return.get_rect(center=results_return_rect.center))

    elif GAME_STATE == "HISTORY":
        draw_history()
    
    
    pygame.display.flip()
    clock.tick(FPS)

# ===================== 終了処理 =====================
stop_event.set()
for t in api_threads:
    if t.is_alive(): t.join(timeout=1.0)
pygame.quit()
sys.exit()
