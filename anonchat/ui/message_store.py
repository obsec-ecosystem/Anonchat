import sqlite3
import threading
import time
from typing import Dict, List, Optional

from anonchat.ui.constants import DATA_DIR
from anonchat.ui.models import Message


class MessageStore:
    def __init__(self, lock: Optional[threading.Lock] = None):
        self._lock = lock or threading.Lock()
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(DATA_DIR / "messages.db"),
            check_same_thread=False,
        )
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                direction TEXT NOT NULL,
                room TEXT NOT NULL,
                peer_id TEXT NOT NULL,
                text TEXT NOT NULL,
                ts REAL NOT NULL
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_room_id ON messages (room, id)"
        )
        self._conn.commit()

    def store(self, direction: str, room: str, peer_id: str, text: str) -> Message:
        with self._lock:
            ts = time.time()
            cursor = self._conn.execute(
                "INSERT INTO messages (direction, room, peer_id, text, ts) VALUES (?, ?, ?, ?, ?)",
                (direction, room, peer_id, text, ts),
            )
            self._conn.commit()
            return Message(
                id=int(cursor.lastrowid),
                direction=direction,
                room=room,
                peer_id=peer_id,
                text=text,
                ts=ts,
            )

    def messages_since(self, after_id: int, room: str) -> List[Message]:
        with self._lock:
            if room == "all":
                rows = self._conn.execute(
                    "SELECT id, direction, room, peer_id, text, ts FROM messages WHERE id > ? ORDER BY id ASC",
                    (after_id,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT id, direction, room, peer_id, text, ts FROM messages WHERE id > ? AND room = ? ORDER BY id ASC",
                    (after_id, room),
                ).fetchall()
            return [
                Message(
                    id=row[0],
                    direction=row[1],
                    room=row[2],
                    peer_id=row[3],
                    text=row[4],
                    ts=row[5],
                )
                for row in rows
            ]

    def serialize_message(self, msg: Message) -> Dict:
        return {
            "id": msg.id,
            "direction": msg.direction,
            "room": msg.room,
            "peer_id": msg.peer_id,
            "text": msg.text,
            "ts": msg.ts,
            "iso": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(msg.ts)),
        }

    def serialize_messages(self, messages: List[Message]) -> List[Dict]:
        return [self.serialize_message(msg) for msg in messages]
