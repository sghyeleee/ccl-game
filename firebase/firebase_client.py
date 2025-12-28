import firebase_admin
from firebase_admin import credentials, firestore

_db = None

def get_db():
    global _db

    if _db is None:
        cred = credentials.Certificate("firebase_key.json")
        firebase_admin.initialize_app(cred)
        _db = firestore.client()

    return _db
