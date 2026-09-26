import redis
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()


class RedisClient:
    def __init__(self):
        self.client = None

    def init_app(self, app):
        url = app.config["REDIS_URL"]
        if url.startswith("fakeredis://"):
            import fakeredis

            self.client = fakeredis.FakeRedis(decode_responses=True)
        else:
            self.client = redis.Redis.from_url(url, decode_responses=True, socket_timeout=2)
        app.extensions["redis"] = self


cache = RedisClient()
