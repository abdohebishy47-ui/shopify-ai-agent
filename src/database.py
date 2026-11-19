import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

DB_DIR = Path(__file__).resolve().parent.parent / "data"
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "app.db"

def get_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                name TEXT NOT NULL,
                role TEXT DEFAULT 'staff',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Activity Logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT NOT NULL,
                product_id TEXT,
                product_title TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

        # Check if default admin exists
        cursor.execute("SELECT COUNT(*) as count FROM users")
        if cursor.fetchone()["count"] == 0:
            cursor.execute("""
                INSERT INTO users (username, password, name, role)
                VALUES (?, ?, ?, ?)
            """, ("admin", "elhoda@2026", "المدير العام", "admin"))
            conn.commit()

def authenticate_user(username: str, password: str) -> Optional[dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username.strip(), password.strip()))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

def get_user_by_username(username: str) -> Optional[dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, name, role, created_at FROM users WHERE username = ?", (username.strip(),))
        row = cursor.fetchone()
        return dict(row) if row else None

def list_users() -> list[dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, name, role, created_at FROM users ORDER BY id ASC")
        return [dict(r) for r in cursor.fetchall()]

def create_user(username: str, password: str, name: str, role: str = "staff") -> bool:
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (username, password, name, role)
                VALUES (?, ?, ?, ?)
            """, (username.strip(), password.strip(), name.strip(), role.strip()))
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        return False

def delete_user(user_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        # Prevent deleting the last admin
        cursor.execute("SELECT role FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            return False
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        return True

def log_activity(username: str, action: str, details: str, product_id: Optional[str] = None, product_title: Optional[str] = None):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO activity_logs (username, action, details, product_id, product_title, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (username, action, details, product_id, product_title, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()

def get_activity_logs(limit: int = 100, username_filter: Optional[str] = None) -> list[dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        if username_filter and username_filter.strip() and username_filter != "all":
            cursor.execute("""
                SELECT * FROM activity_logs WHERE username = ? ORDER BY id DESC LIMIT ?
            """, (username_filter.strip(), limit))
        else:
            cursor.execute("""
                SELECT * FROM activity_logs ORDER BY id DESC LIMIT ?
            """, (limit,))
        return [dict(r) for r in cursor.fetchall()]

# Initialize database on load
init_db()
