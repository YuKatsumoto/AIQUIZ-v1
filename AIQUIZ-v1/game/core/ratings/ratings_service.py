import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


def _entry_key(item: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(item.get("q", "")).strip(),
        str(item.get("subject", "")).strip(),
        str(item.get("grade", "")).strip(),
    )


def _normalize(data: Any) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {"good": [], "bad": []}
    if not isinstance(data, dict):
        return out
    for bucket in ("good", "bad"):
        values = data.get(bucket, [])
        if not isinstance(values, list):
            continue
        seen = set()
        normalized_bucket: list[dict[str, Any]] = []
        for item in values:
            if not isinstance(item, dict):
                continue
            q = str(item.get("q", "")).strip()
            if not q:
                continue
            entry = {
                "q": q,
                "subject": str(item.get("subject", "")).strip(),
                "grade": str(item.get("grade", "")).strip(),
                "difficulty": str(item.get("difficulty", "")).strip(),
                "ts": int(item.get("ts", int(time.time()))),
            }
            key = _entry_key(entry)
            if key in seen:
                continue
            seen.add(key)
            normalized_bucket.append(entry)
        out[bucket] = normalized_bucket
    return out


def _merge(base_data: dict[str, Any], extra_data: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    base = _normalize(base_data)
    extra = _normalize(extra_data)
    merged = {"good": list(base["good"]), "bad": list(base["bad"])}
    existing = {"good": {_entry_key(x) for x in merged["good"]}, "bad": {_entry_key(x) for x in merged["bad"]}}
    for bucket in ("good", "bad"):
        for item in extra[bucket]:
            key = _entry_key(item)
            if key in existing[bucket]:
                continue
            merged[bucket].append(item)
            existing[bucket].add(key)
    return merged


class RatingsService:
    def __init__(self, local_path: str):
        self.local_path = Path(local_path)
        self.firebase_db_url = os.getenv("FIREBASE_DB_URL", "").strip().rstrip("/")
        self.firebase_auth_token = os.getenv("FIREBASE_AUTH_TOKEN", "").strip()
        self.firebase_ratings_path = os.getenv("FIREBASE_RATINGS_PATH", "quiz_ratings/shared").strip().strip("/")
        self.ratings = {"good": [], "bad": []}

    def _firebase_url(self) -> str:
        if not self.firebase_db_url:
            return ""
        path = self.firebase_ratings_path or "quiz_ratings/shared"
        url = f"{self.firebase_db_url}/{path}.json"
        if self.firebase_auth_token:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}auth={urllib.parse.quote(self.firebase_auth_token)}"
        return url

    def _firebase_load(self) -> dict[str, Any]:
        url = self._firebase_url()
        if not url:
            return {"good": [], "bad": []}
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                raw = resp.read().decode("utf-8")
            return _normalize(json.loads(raw) if raw else {})
        except Exception:
            return {"good": [], "bad": []}

    def _firebase_save(self, data: dict[str, Any]) -> None:
        url = self._firebase_url()
        if not url:
            return
        try:
            payload = json.dumps(_normalize(data), ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="PUT")
            with urllib.request.urlopen(req, timeout=7):
                pass
        except Exception:
            return

    def load(self) -> dict[str, Any]:
        local_data: dict[str, Any] = {"good": [], "bad": []}
        if self.local_path.exists():
            try:
                local_data = json.loads(self.local_path.read_text(encoding="utf-8"))
            except Exception:
                local_data = {"good": [], "bad": []}
        merged = _normalize(local_data)
        remote_data = self._firebase_load()
        merged = _merge(merged, remote_data)
        self.ratings = merged
        self.save_local()
        return self.ratings

    def save_local(self) -> None:
        self.local_path.parent.mkdir(parents=True, exist_ok=True)
        self.local_path.write_text(json.dumps(_normalize(self.ratings), ensure_ascii=False, indent=2), encoding="utf-8")

    def sync_to_remote(self) -> None:
        remote_data = self._firebase_load()
        self.ratings = _merge(remote_data, self.ratings)
        self.save_local()
        self._firebase_save(self.ratings)

    def sync_from_remote(self) -> None:
        remote_data = self._firebase_load()
        self.ratings = _merge(self.ratings, remote_data)
        self.save_local()

    def mark_good(self, quiz: dict[str, Any], subject: str, grade: int, difficulty: str = "") -> None:
        entry = {
            "q": str(quiz.get("q", "")).strip(),
            "subject": str(subject).strip(),
            "grade": str(grade).strip(),
            "difficulty": str(difficulty).strip(),
            "ts": int(time.time()),
        }
        if not entry["q"]:
            return
        key = _entry_key(entry)
        if key in {_entry_key(x) for x in self.ratings["good"]}:
            return
        self.ratings["good"].append(entry)
        self.save_local()
        self.sync_to_remote()

    def mark_bad(self, quiz: dict[str, Any], subject: str, grade: int, difficulty: str = "") -> None:
        entry = {
            "q": str(quiz.get("q", "")).strip(),
            "subject": str(subject).strip(),
            "grade": str(grade).strip(),
            "difficulty": str(difficulty).strip(),
            "ts": int(time.time()),
        }
        if not entry["q"]:
            return
        key = _entry_key(entry)
        if key in {_entry_key(x) for x in self.ratings["bad"]}:
            return
        self.ratings["bad"].append(entry)
        if len(self.ratings["bad"]) > 120:
            self.ratings["bad"] = self.ratings["bad"][-120:]
        self.save_local()
        self.sync_to_remote()
