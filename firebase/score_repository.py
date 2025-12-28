from firebase.firebase_client import get_db
from firebase_admin import firestore

COLLECTION_NAME = "scores"


def save_score(username: str, score: int):
    db = get_db()

    db.collection(COLLECTION_NAME).add({
        "username": username,
        "score": score,
        "created_at": firestore.SERVER_TIMESTAMP
    })


def get_leaderboard(limit: int = 10):
    db = get_db()

    docs = (
        db.collection(COLLECTION_NAME)
        .order_by("score", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )

    leaderboard = []
    for d in docs:
        data = d.to_dict()
        leaderboard.append({
            "username": data["username"],
            "score": data["score"]
        })

    return leaderboard
