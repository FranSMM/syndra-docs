## Playbook 9: Database Migrations & Schema Management

* **Never blindly trust --autogenerate:** Alembic is excellent for standard relational tables but is completely blind to complex constraints and specialized Postgres indexes (like GIN on JSONB).

* **Migration Atomic Rule:** 1 Migration = 1 Purpose. Keep structural table creations strictly separated from performance tuning (index injections) to maintain a clean, readable, and easily reversible rollback history.

* **Execution:** Apply migrations using `docker compose exec backend alembic upgrade head`.

* **Testing Down-Revisions:** Always ensure your `downgrade()` function accurately reverses the `upgrade()` logic. An untested downgrade is a corrupted database waiting to happen.
