"""점수 저장소.

Firebase REST API를 사용하여 게임 점수를 저장하고 조회합니다.
"""

from __future__ import annotations

from typing import Dict, List

from firebase.firebase_client import get_document, set_document, query_collection


def save_high_score(nickname: str, game_name: str, score: int) -> bool:
    """닉네임 기준 최고 점수일 경우에만 갱신한다.
    
    DB 구조:
    - 컬렉션: game_name (게임별로 컬렉션 분리)
    - 문서 ID: nickname
    - 필드: nickname, score
    
    Returns:
        True if the score was updated (new high score), False otherwise.
    """
    try:
        # 기존 점수 조회
        existing = get_document(game_name, nickname)
        
        if existing:
            existing_score = existing.get("score", 0)
            if existing_score >= score:
                # 기존 점수가 더 높으면 갱신하지 않음
                return False
        
        # 새 점수 저장
        success = set_document(game_name, nickname, {
            "nickname": nickname,
            "score": score,
        })
        
        return success
    except Exception as e:
        print(f"[DEBUG] 점수 저장 실패: {e}")
        return False


def get_high_score(nickname: str, game_name: str) -> int:
    """닉네임 기준 최고 점수를 조회한다."""
    try:
        doc = get_document(game_name, nickname)
        if doc:
            return doc.get("score", 0)
        return 0
    except Exception as e:
        print(f"[DEBUG] 점수 조회 실패: {e}")
        return 0


def get_leaderboard(game_name: str, limit: int = 10) -> List[Dict[str, any]]:
    """게임별 리더보드를 조회한다."""
    try:
        docs = query_collection(
            collection=game_name,
            order_by="score",
            descending=True,
            limit=limit
        )
        
        leaderboard = []
        for doc in docs:
            leaderboard.append({
                "nickname": doc.get("nickname", "???"),
                "score": doc.get("score", 0)
            })
        
        return leaderboard
    except Exception as e:
        print(f"[DEBUG] 리더보드 조회 실패: {e}")
        return []
