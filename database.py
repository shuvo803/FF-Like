from pymongo import ASCENDING, DESCENDING, MongoClient

from config import envv

_client = None
_db = None
_initialized = False


def db():
    """Lazily create (and cache) the MongoDB database handle.

    The client (and its connection pool) is created once per worker
    process and reused for every request — creating a new MongoClient
    per request is a common, easy-to-miss source of slow responses.
    """
    global _client, _db
    if _db is not None:
        return _db
    uri = envv("MONGODB_URI")
    if not uri:
        raise RuntimeError("MONGODB_URI is missing")
    _client = MongoClient(
        uri,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
        maxPoolSize=20,
        retryWrites=True,
    )
    _db = _client[envv("MONGODB_DATABASE", "freefire_like")]
    return _db


def init_db() -> None:
    """Create indexes/defaults once per process, not on every request.

    create_index() is idempotent but still a round-trip to MongoDB;
    calling it on every webhook update (as before) added needless
    latency to every single message. A process-local flag makes this
    a one-time cost after cold start.
    """
    global _initialized
    if _initialized:
        return

    d = db()
    d.users.create_index([("telegram_id", ASCENDING)], unique=True)
    d.users.create_index([("last_activity", DESCENDING)])
    d.requests.create_index([("uid", ASCENDING), ("created_at", DESCENDING)])
    d.requests.create_index([("telegram_id", ASCENDING), ("created_at", DESCENDING)])
    d.settings.create_index([("key", ASCENDING)], unique=True)

    defaults = {"maintenance": False, "cooldown_seconds": 60, "broadcast_lock": False}
    for key, value in defaults.items():
        d.settings.update_one(
            {"key": key},
            {"$setOnInsert": {"key": key, "value": value}},
            upsert=True,
        )

    _initialized = True


def get_setting(key: str, default=None):
    x = db().settings.find_one({"key": key})
    if x is None:
        return default
    return x.get("value", default)


def set_setting(key: str, value) -> None:
    db().settings.update_one({"key": key}, {"$set": {"key": key, "value": value}}, upsert=True)
