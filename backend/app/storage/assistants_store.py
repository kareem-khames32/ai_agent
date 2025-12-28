"""
Assistants Storage Module
CRUD operations for voice AI assistants using SQLite
"""
import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List

from .sqlite_db import db


class AssistantsStore:
    """Store for managing voice AI assistants"""

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new assistant

        Args:
            data: Assistant configuration dict

        Returns:
            Created assistant with ID
        """
        assistant_id = data.get("id") or str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        # Serialize JSON fields
        voice_settings = json.dumps(data.get("voice_settings", {}))
        transcriber_settings = json.dumps(data.get("transcriber_settings", {}))
        stop_speaking_plan = json.dumps(data.get("stop_speaking_plan", {}))
        tools = json.dumps(data.get("tools", []))
        metadata = json.dumps(data.get("metadata", {}))

        db.execute("""
            INSERT INTO assistants (
                id, name, mode, model_provider, model_name, system_prompt,
                first_message, first_message_mode, temperature, max_tokens,
                voice_provider, voice_id, voice_settings,
                transcriber_provider, transcriber_language, transcriber_settings,
                stop_speaking_plan, tools, metadata, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            assistant_id,
            data.get("name", "Untitled Assistant"),
            data.get("mode", "pipeline"),
            data.get("model_provider", "openai"),
            data.get("model_name", "gpt-4o-mini"),
            data.get("system_prompt", ""),
            data.get("first_message", ""),
            data.get("first_message_mode", "assistant-speaks-first"),
            data.get("temperature", 0.7),
            data.get("max_tokens", 200),
            data.get("voice_provider", "openai"),
            data.get("voice_id", "alloy"),
            voice_settings,
            data.get("transcriber_provider", "deepgram"),
            data.get("transcriber_language", "ar"),
            transcriber_settings,
            stop_speaking_plan,
            tools,
            metadata,
            now,
            now,
        ))

        return self.get(assistant_id)

    def get(self, assistant_id: str) -> Optional[Dict[str, Any]]:
        """
        Get an assistant by ID

        Args:
            assistant_id: Assistant UUID

        Returns:
            Assistant dict or None if not found
        """
        row = db.fetch_one(
            "SELECT * FROM assistants WHERE id = ?",
            (assistant_id,)
        )

        if not row:
            return None

        return self._parse_row(row)

    def list(self, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """
        List all assistants with pagination

        Args:
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            Dict with assistants list and pagination info
        """
        # Get total count
        count_result = db.fetch_one("SELECT COUNT(*) as count FROM assistants")
        total = count_result["count"] if count_result else 0

        # Get assistants
        rows = db.fetch_all(
            "SELECT * FROM assistants ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        )

        assistants = [self._parse_row(row) for row in rows]

        return {
            "assistants": assistants,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def update(self, assistant_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Update an assistant

        Args:
            assistant_id: Assistant UUID
            data: Fields to update

        Returns:
            Updated assistant or None if not found
        """
        # Check if exists
        existing = self.get(assistant_id)
        if not existing:
            return None

        # Build update query
        updates = []
        params = []

        simple_fields = [
            "name", "mode", "model_provider", "model_name", "system_prompt",
            "first_message", "first_message_mode", "temperature", "max_tokens",
            "voice_provider", "voice_id", "transcriber_provider", "transcriber_language"
        ]

        json_fields = [
            "voice_settings", "transcriber_settings", "stop_speaking_plan",
            "tools", "metadata"
        ]

        for field in simple_fields:
            if field in data:
                updates.append(f"{field} = ?")
                params.append(data[field])

        for field in json_fields:
            if field in data:
                updates.append(f"{field} = ?")
                params.append(json.dumps(data[field]))

        if not updates:
            return existing

        # Add updated_at
        updates.append("updated_at = ?")
        params.append(datetime.utcnow().isoformat())

        # Add assistant_id
        params.append(assistant_id)

        query = f"UPDATE assistants SET {', '.join(updates)} WHERE id = ?"
        db.execute(query, tuple(params))

        return self.get(assistant_id)

    def delete(self, assistant_id: str) -> bool:
        """
        Delete an assistant

        Args:
            assistant_id: Assistant UUID

        Returns:
            True if deleted, False if not found
        """
        existing = self.get(assistant_id)
        if not existing:
            return False

        db.execute("DELETE FROM assistants WHERE id = ?", (assistant_id,))
        return True

    def _parse_row(self, row: Dict) -> Dict[str, Any]:
        """Parse database row to assistant dict"""
        return {
            "id": row["id"],
            "name": row["name"],
            "mode": row["mode"],
            "model_provider": row["model_provider"],
            "model_name": row["model_name"],
            "system_prompt": row["system_prompt"],
            "first_message": row["first_message"],
            "first_message_mode": row["first_message_mode"],
            "temperature": row["temperature"],
            "max_tokens": row["max_tokens"],
            "voice_provider": row["voice_provider"],
            "voice_id": row["voice_id"],
            "voice_settings": json.loads(row["voice_settings"] or "{}"),
            "transcriber_provider": row["transcriber_provider"],
            "transcriber_language": row["transcriber_language"],
            "transcriber_settings": json.loads(row["transcriber_settings"] or "{}"),
            "stop_speaking_plan": json.loads(row["stop_speaking_plan"] or "{}"),
            "tools": json.loads(row["tools"] or "[]"),
            "metadata": json.loads(row["metadata"] or "{}"),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }


# Global instance
assistants_store = AssistantsStore()
