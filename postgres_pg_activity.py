#!/usr/bin/env python
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any


def read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(f"Env file not found: {path}")

    data: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def connect_pg(env: dict[str, str]):
    engine = env.get("DB_ENGINE", "postgresql").lower()
    if engine not in {"postgresql", "postgres", "django.db.backends.postgresql"}:
        raise RuntimeError(f"DB_ENGINE is not PostgreSQL: {engine}")

    kwargs = {
        "dbname": env.get("DB_NAME", "myportfolio"),
        "user": env.get("DB_USER", "postgres"),
        "password": env.get("DB_PASSWORD", ""),
        "host": env.get("DB_HOST", "127.0.0.1"),
        "port": int(env.get("DB_PORT", "5432")),
        "connect_timeout": int(env.get("DB_CONNECT_TIMEOUT", "5")),
    }

    try:
        import psycopg2  # type: ignore

        conn = psycopg2.connect(**kwargs)
        driver = "psycopg2"
    except Exception as first_err:
        try:
            import psycopg  # type: ignore

            conn = psycopg.connect(**kwargs)
            driver = "psycopg"
        except Exception as second_err:
            raise RuntimeError(
                "Failed to import/connect with psycopg2/psycopg"
            ) from Exception(f"first={first_err}; second={second_err}")

    conn.autocommit = True
    return conn, driver


def print_rows(rows: list[tuple[Any, ...]], headers: list[str]) -> None:
    if not rows:
        print("(no rows)")
        return

    widths = [len(h) for h in headers]
    for row in rows:
        for i, col in enumerate(row):
            widths[i] = max(widths[i], len(str(col)))

    def fmt_row(values: tuple[Any, ...] | list[str]) -> str:
        return " | ".join(str(v).ljust(widths[i]) for i, v in enumerate(values))

    print(fmt_row(headers))
    print("-+-".join("-" * w for w in widths))
    for row in rows:
        print(fmt_row(row))


def run_query(cur, sql: str) -> tuple[list[str], list[tuple[Any, ...]]]:
    cur.execute(sql)
    headers = [desc[0] for desc in cur.description] if cur.description else []
    rows = list(cur.fetchall()) if cur.description else []
    return headers, rows


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PostgreSQL freeze diagnostics (pg_stat_activity/blockers/cancel/terminate)"
    )
    parser.add_argument(
        "--action",
        default="snapshot",
        choices=["snapshot", "blockers", "cancel", "terminate"],
        help="Operation to run",
    )
    parser.add_argument("--target-pid", type=int, default=0, help="Target backend PID")
    parser.add_argument(
        "--env-path",
        default="django/.env",
        help="Path to env file containing DB settings",
    )
    args = parser.parse_args()

    env_path = Path(args.env_path)
    env_map = read_env_file(env_path)

    conn, driver = connect_pg(env_map)
    print(f"connected via {driver}")

    with conn.cursor() as cur:
        if args.action == "snapshot":
            sql = """
SELECT
  now() AS observed_at,
  pid,
  usename,
  application_name,
  client_addr,
  state,
  wait_event_type,
  wait_event,
  now() - query_start AS query_age,
  now() - xact_start AS xact_age,
  pg_blocking_pids(pid) AS blocking_pids,
  LEFT(query, 220) AS query
FROM pg_stat_activity
WHERE datname = current_database()
  AND pid <> pg_backend_pid()
ORDER BY query_start NULLS LAST;
"""
            headers, rows = run_query(cur, sql)
            print_rows(rows, headers)

        elif args.action == "blockers":
            sql = """
WITH waiting AS (
  SELECT pid, unnest(pg_blocking_pids(pid)) AS blocker_pid
  FROM pg_stat_activity
  WHERE cardinality(pg_blocking_pids(pid)) > 0
)
SELECT
  w.pid AS waiting_pid,
  wa.usename AS waiting_user,
  now() - wa.query_start AS waiting_for,
  LEFT(wa.query, 160) AS waiting_query,
  w.blocker_pid,
  ba.usename AS blocker_user,
  ba.state AS blocker_state,
  now() - ba.xact_start AS blocker_xact_age,
  LEFT(ba.query, 160) AS blocker_query
FROM waiting w
JOIN pg_stat_activity wa ON wa.pid = w.pid
JOIN pg_stat_activity ba ON ba.pid = w.blocker_pid
ORDER BY waiting_for DESC;
"""
            headers, rows = run_query(cur, sql)
            print_rows(rows, headers)

        elif args.action == "cancel":
            if args.target_pid <= 0:
                raise ValueError("--target-pid is required for cancel")
            sql = f"SELECT pg_cancel_backend({args.target_pid}) AS canceled;"
            headers, rows = run_query(cur, sql)
            print_rows(rows, headers)

        elif args.action == "terminate":
            if args.target_pid <= 0:
                raise ValueError("--target-pid is required for terminate")
            sql = f"SELECT pg_terminate_backend({args.target_pid}) AS terminated;"
            headers, rows = run_query(cur, sql)
            print_rows(rows, headers)

    conn.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
