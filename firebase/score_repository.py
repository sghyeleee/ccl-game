from firebase.firebase_client import get_db
from firebase_admin import firestore


def save_high_score(nickname: str, game_name: str, score: int) -> bool:
    """닉네임 기준 최고 점수일 경우에만 갱신한다.
    
    DB 구조:
    - 컬렉션: game_name (게임별로 컬렉션 분리)
    - 문서 ID: nickname
    - 필드: nickname, score, updated_at
    
    Returns:
        True if the score was updated (new high score), False otherwise.
    """
    db = get_db()
    # 게임별로 컬렉션 분리, 문서 ID는 닉네임
    doc_ref = db.collection(game_name).document(nickname)
    doc = doc_ref.get()

    if doc.exists:
        existing = doc.to_dict()
        if existing.get("score", 0) >= score:
            # 기존 점수가 더 높으면 갱신하지 않음
            return False

    doc_ref.set({
        "nickname": nickname,
        "score": score,
        "updated_at": firestore.SERVER_TIMESTAMP
    })
    return True


def get_high_score(nickname: str, game_name: str) -> int:
    """닉네임 기준 최고 점수를 조회한다."""
    db = get_db()
    doc = db.collection(game_name).document(nickname).get()

    if doc.exists:
        return doc.to_dict().get("score", 0)
    return 0


def get_leaderboard(game_name: str, limit: int = 10):
    """게임별 리더보드를 조회한다."""
    db = get_db()

    docs = (
        db.collection(game_name)
        .order_by("score", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )

    leaderboard = []
    for d in docs:
        data = d.to_dict()
        leaderboard.append({
            "nickname": data.get("nickname", d.id),
            "score": data.get("score", 0)
        })

    return leaderboard
