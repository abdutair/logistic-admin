import json
import sqlite3
from pathlib import Path
from typing import Any

from passlib.context import CryptContext


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "app.db"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                login TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                filename TEXT,
                extracted_data TEXT,
                sent_to_sheets BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        admin = conn.execute("SELECT id FROM users WHERE login = ?", ("admin",)).fetchone()
        if admin is None:
            conn.execute(
                "INSERT INTO users (name, login, password_hash, role) VALUES (?, ?, ?, ?)",
                ("Administrator", "admin", hash_password("admin123"), "admin"),
            )


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def get_user_by_login(login: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE login = ?", (login,)).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def list_users() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, login, role, created_at FROM users ORDER BY created_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def create_user(name: str, login: str, password: str, role: str) -> dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO users (name, login, password_hash, role) VALUES (?, ?, ?, ?)",
            (name, login, hash_password(password), role),
        )
        user_id = cursor.lastrowid
        row = conn.execute(
            "SELECT id, name, login, role, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    return dict(row)


def delete_user(user_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM users WHERE id = ? AND login != 'admin'", (user_id,))
    return cursor.rowcount > 0


def create_log(user_id: int, filename: str, extracted_data: dict[str, Any], sent: bool = False) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO logs (user_id, filename, extracted_data, sent_to_sheets)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, filename, json.dumps(extracted_data, ensure_ascii=False), sent),
        )
        return int(cursor.lastrowid)


def mark_log_sent(user_id: int, filename: str, data: dict[str, Any]) -> None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id FROM logs
            WHERE user_id = ? AND filename = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (user_id, filename),
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE logs SET sent_to_sheets = 1, extracted_data = ? WHERE id = ?",
                (json.dumps(data, ensure_ascii=False), row["id"]),
            )
        else:
            create_log(user_id, filename, data, True)


def list_logs() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT logs.id, users.name AS user_name, logs.filename,
                   logs.sent_to_sheets, logs.created_at
            FROM logs
            LEFT JOIN users ON logs.user_id = users.id
            ORDER BY logs.created_at DESC
            LIMIT 200
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_latest_draft(user_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, filename, extracted_data, created_at
            FROM logs
            WHERE user_id = ? AND sent_to_sheets = 0
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    if row is None:
        return None
    data = dict(row)
    data["extracted_data"] = json.loads(data["extracted_data"])
    return data


def list_clients() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute("SELECT id, name, created_at FROM clients ORDER BY name").fetchall()
    return [dict(row) for row in rows]


def create_client(name: str) -> dict[str, Any]:
    name = name.strip()
    with get_connection() as conn:
        cursor = conn.execute("INSERT INTO clients (name) VALUES (?)", (name,))
        row = conn.execute(
            "SELECT id, name, created_at FROM clients WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    return dict(row)


def delete_client(client_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM clients WHERE id = ?", (client_id,))
    return cursor.rowcount > 0
