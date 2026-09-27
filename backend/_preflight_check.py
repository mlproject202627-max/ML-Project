"""Preflight check: is Postgres reachable and is the schema seeded?"""
from sqlalchemy import create_engine, text

URL = "postgresql://sentinel:sentinel_secret@localhost:5432/sentinel_db"

try:
    engine = create_engine(URL, pool_pre_ping=True)
    with engine.connect() as conn:
        tables = [
            r[0]
            for r in conn.execute(
                text(
                    "select tablename from pg_tables "
                    "where schemaname='public' order by 1"
                )
            )
        ]
    print("DB: connected")
    print("tables:", ", ".join(tables) if tables else "(none)")
    if "users" in tables:
        with engine.connect() as conn:
            n = conn.execute(text("select count(*) from users")).scalar()
            print("users:", n)
except Exception as exc:
    print("DB: FAILED ->", type(exc).__name__, str(exc)[:300])
