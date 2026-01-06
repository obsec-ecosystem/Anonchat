import threading
import time
from typing import Dict, List, Optional

from front.models import Message


class MessageStore:
    def __init__(self, lock: Optional[threading.Lock] = None):
        self._lock = lock or threading.Lock()
        self._messages: List[Message] = []
        self._last_id = 0

    def _next_id(self) -> int:
        self._last_id += 1
        return self._last_id

    def store(self, direction: str, room: str, peer_id: str, text: str) -> Message:
        with self._lock:
            msg = Message(
                id=self._next_id(),
                direction=direction,
                room=room,
                peer_id=peer_id,
                text=text,
                ts=time.time(),
            )
            self._messages.append(msg)
            return msg

    def messages_since(self, after_id: int, room: str) -> List[Message]:
        with self._lock:
            if room == "all":
                return [m for m in self._messages if m.id > after_id]
            return [m for m in self._messages if m.id > after_id and m.room == room]

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
