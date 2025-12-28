"""
SQLite Database Manager
Simple SQLite setup for local storage
"""
import sqlite3
import json
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid

# Database file location
DATA_DIR = Path(__file__).parent.parent.parent / "data"
DB_FILE = DATA_DIR / "voiceai.db"


def ensure_data_dir():
    """Ensure data directory exists"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    """Get SQLite connection with row factory"""
    ensure_data_dir()
    conn = sqlite3.connect(str(DB_FILE), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


class SQLiteDB:
    """Simple SQLite database manager"""

    def __init__(self):
        self._init_tables()

    def _init_tables(self):
        """Initialize all database tables"""
        conn = get_connection()
        cursor = conn.cursor()

        # Assistants table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS assistants (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                mode TEXT DEFAULT 'pipeline',
                model_provider TEXT DEFAULT 'openai',
                model_name TEXT DEFAULT 'gpt-4o-mini',
                system_prompt TEXT,
                first_message TEXT,
                first_message_mode TEXT DEFAULT 'assistant-speaks-first',
                temperature REAL DEFAULT 0.7,
                max_tokens INTEGER DEFAULT 200,
                voice_provider TEXT DEFAULT 'openai',
                voice_id TEXT DEFAULT 'alloy',
                voice_settings TEXT DEFAULT '{}',
                transcriber_provider TEXT DEFAULT 'deepgram',
                transcriber_language TEXT DEFAULT 'ar',
                transcriber_settings TEXT DEFAULT '{}',
                stop_speaking_plan TEXT DEFAULT '{}',
                tools TEXT DEFAULT '[]',
                metadata TEXT DEFAULT '{}',
                created_at TEXT,
                updated_at TEXT
            )
        """)

        # Credentials table (encrypted API keys)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS credentials (
                id TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                credential_type TEXT NOT NULL,
                api_key TEXT,
                region TEXT,
                extra TEXT DEFAULT '{}',
                created_at TEXT,
                updated_at TEXT
            )
        """)

        # Call logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS call_logs (
                id TEXT PRIMARY KEY,
                assistant_id TEXT,
                phone_number TEXT,
                direction TEXT DEFAULT 'inbound',
                status TEXT DEFAULT 'completed',
                duration_sec REAL DEFAULT 0,
                cost_stt REAL DEFAULT 0,
                cost_llm REAL DEFAULT 0,
                cost_tts REAL DEFAULT 0,
                cost_total REAL DEFAULT 0,
                transcript TEXT DEFAULT '[]',
                recording_path TEXT,
                metrics TEXT DEFAULT '{}',
                started_at TEXT,
                ended_at TEXT,
                created_at TEXT
            )
        """)

        # Webhooks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS webhooks (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                events TEXT DEFAULT '[]',
                secret TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT,
                updated_at TEXT
            )
        """)

        # Users table (simple auth)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT,
                updated_at TEXT
            )
        """)

        # API Keys table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                key_hash TEXT NOT NULL,
                prefix TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                last_used_at TEXT,
                created_at TEXT
            )
        """)

        conn.commit()
        conn.close()

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a query"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor

    def fetch_one(self, query: str, params: tuple = ()) -> Optional[Dict]:
        """Fetch one row as dict"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        row = cursor.fetchone()
        conn.close()
        if row:
            return dict(row)
        return None

    def fetch_all(self, query: str, params: tuple = ()) -> List[Dict]:
        """Fetch all rows as list of dicts"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]


# Global instance
db = SQLiteDB()
