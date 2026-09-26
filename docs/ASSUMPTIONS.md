# Assumptions

Decisions made where the build prompt left room for interpretation.

1. **Product name.** The prototype is called "TaniGuard" ("tani" = farming in Malay). Rename freely.
2. **Migrations.** Alembic is used through Flask-Migrate (`flask db upgrade`), which is a thin wrapper over Alembic.
3. **Local development without Docker.** If `DATABASE_URL` is unset the backend falls back to SQLite in `data/dev.db`; tests use in-memory SQLite and `fakeredis`. Production and Docker Compose use MySQL 8 and Redis 7.
4. **Frontend serving.** In Docker Compose the React build is served by nginx on port 8080, which proxies `/api` to the backend.
