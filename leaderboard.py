from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

# Supabase 프로젝트 정보
PROJECT_ID = "gzlylnktkrktfbsckvce"
DEFAULT_SUPABASE_URL = f"https://{PROJECT_ID}.supabase.co"
TABLE = "leaderboard_entries"


def _get_supabase_url() -> str:
    return os.getenv("SUPABASE_URL", DEFAULT_SUPABASE_URL).rstrip("/")


def _get_anon_key() -> str:
    # Supabase 콘솔에서 "Publishable key"로 노출되는 값을 클라이언트에서 사용한다.
    # (절대 secret key를 클라이언트에 넣지 말 것)
    return (
        os.getenv("SUPABASE_ANON_KEY", "").strip()
        or os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()
        or os.getenv("SUPABASE_KEY", "").strip()
    )


def _headers() -> dict[str, str]:
    key = _get_anon_key()
    if not key:
        raise RuntimeError("SUPABASE_ANON_KEY 환경변수가 설정되어 있지 않습니다.")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _request(method: str, path: str, *, query: str = "", body: Optional[dict] = None) -> bytes:
    url = f"{_get_supabase_url()}{path}"
    if query:
        url = f"{url}?{query}"
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Supabase HTTPError {e.code}: {detail}") from e
    except Exception as e:
        raise RuntimeError(f"Supabase 요청 실패: {e}") from e


def sanitize_nickname(raw: str, *, max_len: int = 12) -> str:
    s = raw.strip()
    s = s.replace("\n", " ").replace("\r", " ")
    if len(s) > max_len:
        s = s[:max_len]
    return s


@dataclass
class LeaderboardEntry:
    nickname: str
    score: int


def submit_score(game: str, nickname: str, score: int) -> None:
    nickname = sanitize_nickname(nickname)
    if not nickname:
        raise ValueError("닉네임이 비어있습니다.")
    payload = {"game": game, "nickname": nickname, "score": int(score)}
    _request("POST", f"/rest/v1/{TABLE}", body=payload)


def fetch_top(game: str, limit: int = 10) -> List[LeaderboardEntry]:
    query = urllib.parse.urlencode(
        {
            "select": "nickname,score,created_at",
            "game": f"eq.{game}",
            "order": "score.desc,created_at.asc",
            "limit": str(limit),
        }
    )
    raw = _request("GET", f"/rest/v1/{TABLE}", query=query)
    items = json.loads(raw.decode("utf-8") or "[]")
    out: List[LeaderboardEntry] = []
    for item in items:
        out.append(LeaderboardEntry(nickname=str(item.get("nickname", "")), score=int(item.get("score", 0))))
    return out


def submit_and_fetch_async(
    game: str,
    nickname: str,
    score: int,
    *,
    top_n: int = 5,
    callback: Callable[[Optional[str], Optional[List[LeaderboardEntry]]], None],
) -> None:
    """백그라운드 스레드에서 저장+랭킹조회 후 callback(err, entries)."""

    def _worker() -> None:
        try:
            submit_score(game, nickname, score)
            entries = fetch_top(game, limit=top_n)
            callback(None, entries)
        except Exception as e:
            callback(str(e), None)

    threading.Thread(target=_worker, daemon=True).start()


