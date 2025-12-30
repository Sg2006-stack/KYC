# database.py
from pymongo import MongoClient, errors
from datetime import datetime
import logging

DB_URL = "mongodb://localhost:27017"

try:
    client = MongoClient(DB_URL, serverSelectionTimeoutMS=2000)
    client.admin.command('ping')  # test connection
    # avoid non-ascii characters that can raise on some Windows consoles
    print("Connected to MongoDB")
    db = client["kyc_system"]
    users = db["users"]

except errors.ServerSelectionTimeoutError:
    print("MongoDB not running - using in-memory fallback DB")

    class InsertOneResult:
        def __init__(self, inserted_id):
            self.inserted_id = inserted_id

    class LocalFallbackDB:
        def __init__(self):
            self.storage = []

        def insert_one(self, data):
            data = dict(data)
            data["_local_saved_at"] = datetime.utcnow()
            self.storage.append(data)
            return InsertOneResult(len(self.storage) - 1)

        def find(self, *args, **kwargs):
            return list(self.storage)

        def find_one(self, query, projection=None):
            # simple matching for equality on top-level keys
            for doc in self.storage:
                ok = True
                for k, v in query.items():
                    if doc.get(k) != v:
                        ok = False
                        break
                if ok:
                    # apply basic projection support (exclude keys set to 0)
                    if projection:
                        res = dict(doc)
                        for pk, val in projection.items():
                            if val == 0 and pk in res:
                                res.pop(pk, None)
                        return res
                    return dict(doc)
            return None

    users = LocalFallbackDB()
