"""API connection status checker for the settings screen."""
import os
import socket
import threading
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ApiStatus:
    """Holds the current status of each API endpoint."""
    # Network
    internet_ok: Optional[bool] = None  # None = not checked yet
    internet_msg: str = "未チェック"

    # OpenAI
    openai_key_set: bool = False
    openai_model: str = ""
    openai_status: Optional[bool] = None
    openai_msg: str = "未チェック"

    # Gemini
    gemini_key_set: bool = False
    gemini_model: str = ""
    gemini_status: Optional[bool] = None
    gemini_msg: str = "未チェック"

    # Offline bank
    offline_count: int = 0

    # Check in progress
    checking: bool = False


_status = ApiStatus()
_lock = threading.Lock()


def get_status() -> ApiStatus:
    with _lock:
        # Always refresh key/model info from env
        _status.openai_key_set = bool(os.getenv("OPENAI_API_KEY", "").strip())
        _status.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o")
        _status.gemini_key_set = bool(
            os.getenv("GOOGLE_API_KEY", "").strip() or os.getenv("GEMINI_API_KEY", "").strip()
        )
        _status.gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        return ApiStatus(
            internet_ok=_status.internet_ok,
            internet_msg=_status.internet_msg,
            openai_key_set=_status.openai_key_set,
            openai_model=_status.openai_model,
            openai_status=_status.openai_status,
            openai_msg=_status.openai_msg,
            gemini_key_set=_status.gemini_key_set,
            gemini_model=_status.gemini_model,
            gemini_status=_status.gemini_status,
            gemini_msg=_status.gemini_msg,
            offline_count=_status.offline_count,
            checking=_status.checking,
        )


def set_offline_count(count: int):
    with _lock:
        _status.offline_count = count


def run_connectivity_check():
    """Run all connectivity checks in a background thread."""
    with _lock:
        if _status.checking:
            return
        _status.checking = True

    def _worker():
        try:
            # 1. Internet check
            _check_internet()
            # 2. OpenAI check
            _check_openai()
            # 3. Gemini check
            _check_gemini()
        finally:
            with _lock:
                _status.checking = False

    threading.Thread(target=_worker, daemon=True).start()


def _check_internet():
    with _lock:
        _status.internet_msg = "チェック中..."
        _status.internet_ok = None
    try:
        sock = socket.create_connection(("8.8.8.8", 53), timeout=5)
        sock.close()
        with _lock:
            _status.internet_ok = True
            _status.internet_msg = "接続OK"
    except OSError:
        with _lock:
            _status.internet_ok = False
            _status.internet_msg = "接続失敗"


def _check_openai():
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        with _lock:
            _status.openai_status = False
            _status.openai_msg = "APIキー未設定"
        return
    with _lock:
        _status.openai_msg = "チェック中..."
        _status.openai_status = None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        r = client.chat.completions.create(
            model=os.getenv("OPENAI_FAST_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": "Reply with just OK"}],
            max_tokens=5,
            timeout=10,
        )
        if r.choices:
            with _lock:
                _status.openai_status = True
                _status.openai_msg = "接続OK"
        else:
            with _lock:
                _status.openai_status = False
                _status.openai_msg = "応答なし"
    except Exception as e:
        with _lock:
            _status.openai_status = False
            _status.openai_msg = f"エラー: {type(e).__name__}"


def _check_gemini():
    api_key = os.getenv("GOOGLE_API_KEY", "").strip() or os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        with _lock:
            _status.gemini_status = False
            _status.gemini_msg = "APIキー未設定"
        return
    with _lock:
        _status.gemini_msg = "チェック中..."
        _status.gemini_status = None
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        r = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            contents="Reply with just OK",
            config={"temperature": 0.0, "max_output_tokens": 5, "http_options": {"timeout": 10_000}},
        )
        text = getattr(r, "text", "") or ""
        if text.strip():
            with _lock:
                _status.gemini_status = True
                _status.gemini_msg = "接続OK"
        else:
            with _lock:
                _status.gemini_status = False
                _status.gemini_msg = "応答なし"
    except Exception as e:
        with _lock:
            _status.gemini_status = False
            _status.gemini_msg = f"エラー: {type(e).__name__}"
