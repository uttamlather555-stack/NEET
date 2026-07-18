import time
import os
from functools import lru_cache
from supabase import create_client

TABLE = "app_state"
ROW_ID = 1

DEFAULT_ADMIN_PASSWORD = "212020"  # change this after first login if possible

@lru_cache(maxsize=None)
def _get_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("Supabase credentials missing. Please set SUPABASE_URL and SUPABASE_KEY environment variables.")
    return create_client(url, key)

def _default_db():
    return {
        "quiz_state": {
            "active": False,
            "question_data": None,
            "answers": {},
            "answer_times": {},
            "revealed": False,
            "timer_seconds": 0,
            "question_start_time": 0,
            "auto_mode": False,
            "subject": None,
            "topic": None,
            "difficulty": "Medium",
            "pyq_style": False,
            "total_questions": 0,
            "current_index": 0,
            "question_source": "ai",
            "bank_order": [],
        },
        "full_tests": {},
        "current_session_scores": {},
        "users": {
            "admin": {
                "password": DEFAULT_ADMIN_PASSWORD,
                "role": "admin",
                "lifetime_score": 0,
                "last_seen": time.time(),
                "blocked": False,
                "avatar_color": "#6366f1",
            }
        },
        "scores": {},
    }

def upgrade_db(data: dict) -> dict:
    """Ensure older saved states gain new fields without losing data."""
    defaults = _default_db()

    for key, value in defaults.items():
        if key not in data:
            data[key] = value

    # nested quiz_state
    for k, v in defaults["quiz_state"].items():
        data["quiz_state"].setdefault(k, v)

    # per-user upgrades
    for uname, uinfo in data.get("users", {}).items():
        uinfo.setdefault("lifetime_score", data.get("scores", {}).get(uname, 0))
        uinfo.setdefault("last_seen", time.time())
        uinfo.setdefault("blocked", False)
        uinfo.setdefault("avatar_color", "#6366f1")

    for test in data.get("full_tests", {}).values():
        test.setdefault("test_type", "test")
        for sub in test.get("submissions", {}).values():
            if "best" in sub:
                continue 
            if sub.get("submitted_at") is not None and sub.get("score") is not None:
                sub["best"] = {
                    "answers": dict(sub.get("answers", {})),
                    "score": sub["score"],
                    "correct_count": sub.get("correct_count", 0),
                    "wrong_count": sub.get("wrong_count", 0),
                    "unattempted_count": sub.get("unattempted_count", 0),
                    "started_at": sub.get("started_at", 0),
                    "submitted_at": sub["submitted_at"],
                }
            else:
                sub["best"] = None
            sub.setdefault("attempt_count", 1 if sub.get("best") else 0)

    return data

class DatabaseUnavailableError(Exception):
    pass

def load_db() -> dict:
    client = _get_client()
    try:
        result = client.table(TABLE).select("data").eq("id", ROW_ID).execute()
    except Exception as e:
        raise DatabaseUnavailableError(str(e))

    if result.data:
        return upgrade_db(result.data[0]["data"])

    fresh = upgrade_db(_default_db())
    save_db(fresh)
    return fresh

def save_db(data: dict, max_attempts: int = 3):
    client = _get_client()
    last_error = None
    for attempt in range(max_attempts):
        try:
            client.table(TABLE).update({"data": data, "updated_at": "now()"}).eq("id", ROW_ID).execute()
            return
        except Exception as e:
            last_error = e
            if attempt < max_attempts - 1:
                time.sleep(0.4 * (attempt + 1))
    raise DatabaseUnavailableError(str(last_error))

def register_user(username: str, user_data: dict) -> str:
    client = _get_client()
    try:
        result = client.rpc(
            "register_user", {"p_username": username, "p_user_data": user_data}
        ).execute()
        return result.data if isinstance(result.data, str) else "ok"
    except Exception:
        return "error"

def touch_user_last_seen(username: str):
    client = _get_client()
    try:
        client.rpc("touch_last_seen", {"p_username": username}).execute()
    except Exception:
        pass
