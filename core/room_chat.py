import hashlib
import json
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple

ROOM_CTL_PREFIX = "ROOMCTL::"
ROOM_MSG_PREFIX = "ROOMMSG::"


@dataclass
class Room:
    id: str
    name: str
    owner_id: str
    created_at: float
    max_members: int
    locked: bool
    discoverable: bool
    password_hash: Optional[str] = None
    password_salt: Optional[str] = None
    members: Set[str] = field(default_factory=set)
    joined: bool = False
    pending: bool = False


class RoomManager:
    def __init__(
        self,
        lock: Optional[threading.Lock],
        identity,
        chat,
        store_message: Callable[[str, str, str, str], None],
    ):
        self._lock = lock or threading.Lock()
        self.identity = identity
        self.chat = chat
        self._store_message = store_message

        self._rooms: Dict[str, Room] = {}
        self._room_events: List[Dict] = []
        self._known_peers: Set[str] = set()

    def update_chat(self, chat):
        self.chat = chat

    def get_room(self, room_id: str) -> Optional[Room]:
        with self._lock:
            return self._rooms.get(room_id)

    def _hash_password(self, password: str, salt: str) -> str:
        return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()

    def _room_public_payload(self, room: Room) -> Dict:
        return {
            "id": room.id,
            "name": room.name,
            "owner_id": room.owner_id,
            "created_at": room.created_at,
            "max_members": room.max_members,
            "locked": room.locked,
            "discoverable": room.discoverable,
        }

    def _serialize_room(self, room: Room) -> Dict:
        members = []
        if room.joined or room.owner_id == self.identity.anon_id:
            members = sorted(room.members)
        return {
            "id": room.id,
            "name": room.name,
            "owner_id": room.owner_id,
            "created_at": room.created_at,
            "max_members": room.max_members,
            "locked": room.locked,
            "discoverable": room.discoverable,
            "member_count": len(room.members),
            "members": members,
            "joined": room.joined,
            "pending": room.pending,
            "is_owner": room.owner_id == self.identity.anon_id,
        }

    def serialize_rooms(self) -> List[Dict]:
        with self._lock:
            rooms = list(self._rooms.values())
        rooms.sort(key=lambda r: r.created_at)
        return [self._serialize_room(room) for room in rooms]

    def serialize_room(self, room: Room) -> Dict:
        return self._serialize_room(room)

    def _push_room_event(self, event: Dict):
        with self._lock:
            self._room_events.append(event)
            if len(self._room_events) > 50:
                self._room_events = self._room_events[-50:]

    def consume_room_events(self, peer_ids: Set[str]) -> Tuple[Set[str], List[Dict]]:
        with self._lock:
            new_peers = peer_ids - self._known_peers
            if new_peers:
                self._known_peers |= new_peers
            room_events = list(self._room_events)
            self._room_events.clear()
        return set(new_peers), room_events

    def get_owned_discoverable_rooms(self) -> List[Room]:
        with self._lock:
            return [
                room
                for room in self._rooms.values()
                if room.owner_id == self.identity.anon_id and room.discoverable
            ]

    def _send_room_ctl(self, peer_id: str, payload: Dict):
        if not self.chat:
            return
        message = f"{ROOM_CTL_PREFIX}{json.dumps(payload, separators=(',', ':'))}"
        self.chat.send_to_peer(peer_id, message)

    def _broadcast_room_ctl(self, peer_ids: Set[str], payload: Dict):
        if not self.chat:
            return
        for peer_id in peer_ids:
            if peer_id == self.identity.anon_id:
                continue
            try:
                self._send_room_ctl(peer_id, payload)
            except ValueError:
                continue

    def announce_room(self, room: Room, peer_ids: Optional[Set[str]] = None):
        if not room.discoverable or not self.chat:
            return
        payload = {"type": "room_announce", "room": self._room_public_payload(room)}
        message = f"{ROOM_CTL_PREFIX}{json.dumps(payload, separators=(',', ':'))}"
        if peer_ids is None:
            self.chat.send_to_all(message)
            return
        for peer_id in peer_ids:
            if peer_id == self.identity.anon_id:
                continue
            try:
                self.chat.send_to_peer(peer_id, message)
            except ValueError:
                continue

    def handle_room_control(self, sender_id: str, raw_payload: str):
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            return
        if not isinstance(payload, dict):
            return

        kind = payload.get("type")
        if kind == "room_announce":
            room_data = payload.get("room") or {}
            room_id = str(room_data.get("id") or "").strip()
            if not room_id:
                return
            owner_id = str(room_data.get("owner_id") or sender_id)
            if owner_id != sender_id:
                owner_id = sender_id
            name = str(room_data.get("name") or f"Room {room_id[:6]}").strip()
            locked = bool(room_data.get("locked"))
            max_members = int(room_data.get("max_members") or 0)
            discoverable = bool(room_data.get("discoverable", True))
            created_at = float(room_data.get("created_at") or time.time())

            with self._lock:
                room = self._rooms.get(room_id)
                is_new = room is None
                if room is None:
                    room = Room(
                        id=room_id,
                        name=name,
                        owner_id=owner_id,
                        created_at=created_at,
                        max_members=max_members,
                        locked=locked,
                        discoverable=discoverable,
                        members={owner_id},
                        joined=False,
                    )
                    self._rooms[room_id] = room
                else:
                    room.name = name
                    room.owner_id = owner_id
                    room.locked = locked
                    room.max_members = max_members
                    room.discoverable = discoverable
                    room.created_at = created_at
                    if not room.members:
                        room.members.add(owner_id)

            if is_new:
                self._push_room_event(
                    {"type": "room_discovered", "room_id": room_id, "name": name}
                )
            return

        if kind == "room_join":
            room_id = str(payload.get("room_id") or "").strip()
            password = str(payload.get("password") or "")
            if not room_id:
                return
            with self._lock:
                room = self._rooms.get(room_id)
                if not room or room.owner_id != self.identity.anon_id:
                    return
                max_members = room.max_members
                if max_members > 0 and len(room.members) >= max_members:
                    ok = False
                    reason = "Room is full"
                elif room.locked:
                    if not room.password_hash or not room.password_salt:
                        ok = False
                        reason = "Room is locked"
                    else:
                        hashed = self._hash_password(password, room.password_salt)
                        if hashed != room.password_hash:
                            ok = False
                            reason = "Invalid password"
                        else:
                            ok = True
                            reason = ""
                else:
                    ok = True
                    reason = ""

                if ok:
                    room.members.add(sender_id)
                    members = sorted(room.members)
                    room_payload = self._room_public_payload(room)
                else:
                    members = []
                    room_payload = None

            if ok:
                ack = {
                    "type": "room_join_ack",
                    "room_id": room_id,
                    "ok": True,
                    "members": members,
                    "room": room_payload,
                }
                self._send_room_ctl(sender_id, ack)
                self._broadcast_room_ctl(
                    set(members),
                    {"type": "room_members", "room_id": room_id, "members": members},
                )
            else:
                ack = {
                    "type": "room_join_ack",
                    "room_id": room_id,
                    "ok": False,
                    "reason": reason,
                }
                self._send_room_ctl(sender_id, ack)
            return

        if kind == "room_join_ack":
            room_id = str(payload.get("room_id") or "").strip()
            ok = bool(payload.get("ok"))
            reason = str(payload.get("reason") or "")
            room_data = payload.get("room") or {}
            members = payload.get("members") or []
            if not room_id:
                return

            with self._lock:
                room = self._rooms.get(room_id)
                if room is None and room_data:
                    room = Room(
                        id=room_id,
                        name=str(room_data.get("name") or f"Room {room_id[:6]}").strip(),
                        owner_id=str(room_data.get("owner_id") or sender_id),
                        created_at=float(room_data.get("created_at") or time.time()),
                        max_members=int(room_data.get("max_members") or 0),
                        locked=bool(room_data.get("locked")),
                        discoverable=bool(room_data.get("discoverable", False)),
                        members=set(),
                    )
                    self._rooms[room_id] = room

                if not room:
                    return

                if ok:
                    room.joined = True
                    room.pending = False
                    room.members = set(members)
                    if self.identity.anon_id not in room.members:
                        room.members.add(self.identity.anon_id)
                    if room_data:
                        room.name = str(room_data.get("name") or room.name).strip()
                        room.owner_id = str(room_data.get("owner_id") or room.owner_id)
                        room.created_at = float(room_data.get("created_at") or room.created_at)
                        room.max_members = int(room_data.get("max_members") or room.max_members)
                        room.locked = bool(room_data.get("locked"))
                        room.discoverable = bool(
                            room_data.get("discoverable", room.discoverable)
                        )
                else:
                    room.pending = False

            if ok:
                self._push_room_event(
                    {"type": "room_joined", "room_id": room_id, "name": room.name}
                )
            else:
                self._push_room_event(
                    {
                        "type": "room_join_denied",
                        "room_id": room_id,
                        "name": room.name if room else "",
                        "reason": reason or "Join denied",
                    }
                )
            return

        if kind == "room_members":
            room_id = str(payload.get("room_id") or "").strip()
            members = payload.get("members") or []
            if not room_id:
                return
            with self._lock:
                room = self._rooms.get(room_id)
                if not room:
                    return
                room.members = set(members)
                room.joined = self.identity.anon_id in room.members
                room.pending = False
            return

        if kind == "room_leave":
            room_id = str(payload.get("room_id") or "").strip()
            if not room_id:
                return
            with self._lock:
                room = self._rooms.get(room_id)
                if not room or room.owner_id != self.identity.anon_id:
                    return
                if sender_id in room.members:
                    room.members.discard(sender_id)
                members = sorted(room.members)
            self._broadcast_room_ctl(
                set(members),
                {"type": "room_members", "room_id": room_id, "members": members},
            )
            return

        if kind == "room_kick":
            room_id = str(payload.get("room_id") or "").strip()
            reason = str(payload.get("reason") or "")
            if not room_id:
                return
            with self._lock:
                room = self._rooms.get(room_id)
                if not room:
                    return
                room.joined = False
                room.pending = False
                room.members.discard(self.identity.anon_id)
            self._push_room_event(
                {
                    "type": "room_kicked",
                    "room_id": room_id,
                    "name": room.name if room else "",
                    "reason": reason or "Removed from room",
                }
            )
            return

    def handle_room_message(self, sender_id: str, message: str):
        parts = message.split("::", 2)
        if len(parts) != 3:
            return None
        _, room_id, text = parts
        room_id = room_id.strip()
        if not room_id:
            return None

        with self._lock:
            room = self._rooms.get(room_id)
            if not room:
                room = Room(
                    id=room_id,
                    name=f"Room {room_id[:6]}",
                    owner_id=sender_id,
                    created_at=time.time(),
                    max_members=0,
                    locked=False,
                    discoverable=False,
                    members={sender_id},
                    joined=True,
                )
                self._rooms[room_id] = room
            room.joined = True
            room.pending = False
            room.members.add(self.identity.anon_id)
            room.members.add(sender_id)

        self._store_message("in", room_id, sender_id, text)
        return room_id, text

    def create_room(
        self,
        name: str,
        password: str,
        discoverable: bool,
        max_members: int,
    ) -> Optional[Room]:
        locked = bool(password)
        salt = None
        password_hash = None
        if locked:
            salt = secrets.token_hex(8)
            password_hash = self._hash_password(password, salt)

        room_id = ""
        with self._lock:
            for _ in range(8):
                candidate = f"room_{secrets.token_hex(4)}"
                if candidate not in self._rooms:
                    room_id = candidate
                    break
            if not room_id:
                return None

            room = Room(
                id=room_id,
                name=name,
                owner_id=self.identity.anon_id,
                created_at=time.time(),
                max_members=max_members,
                locked=locked,
                discoverable=discoverable,
                password_hash=password_hash,
                password_salt=salt,
                members={self.identity.anon_id},
                joined=True,
            )
            self._rooms[room_id] = room

        self.announce_room(room)
        return room

    def join_room(self, room_id: str, password: str) -> Tuple[int, Dict]:
        with self._lock:
            room = self._rooms.get(room_id)
            if not room:
                return 404, {"error": "Room not found"}
            if room.owner_id == self.identity.anon_id:
                room.joined = True
                room.pending = False
                return 200, {"ok": True, "room": self._serialize_room(room)}
            if room.joined:
                return 200, {"ok": True, "room": self._serialize_room(room)}
            room.pending = True
            owner_id = room.owner_id

        try:
            self._send_room_ctl(
                owner_id,
                {"type": "room_join", "room_id": room_id, "password": password},
            )
        except ValueError:
            with self._lock:
                room = self._rooms.get(room_id)
                if room:
                    room.pending = False
            return 400, {"error": "Room owner offline"}

        return 200, {"ok": True}

    def leave_room(self, room_id: str) -> Tuple[int, Dict]:
        with self._lock:
            room = self._rooms.get(room_id)
            if not room:
                return 404, {"error": "Room not found"}
            if room.owner_id == self.identity.anon_id:
                return 400, {"error": "Owner cannot leave the room"}
            room.joined = False
            room.pending = False
            room.members.discard(self.identity.anon_id)
            owner_id = room.owner_id

        try:
            self._send_room_ctl(
                owner_id,
                {"type": "room_leave", "room_id": room_id},
            )
        except ValueError:
            pass

        return 200, {"ok": True}

    def kick_member(self, room_id: str, member_id: str) -> Tuple[int, Dict]:
        if not member_id:
            return 400, {"error": "Missing member id"}
        with self._lock:
            room = self._rooms.get(room_id)
            if not room:
                return 404, {"error": "Room not found"}
            if room.owner_id != self.identity.anon_id:
                return 403, {"error": "Only the owner can kick members"}
            if member_id == self.identity.anon_id:
                return 400, {"error": "Owner cannot kick self"}
            if member_id not in room.members:
                return 404, {"error": "Member not found"}
            room.members.discard(member_id)
            members = sorted(room.members)

        self._broadcast_room_ctl(
            set(members),
            {"type": "room_members", "room_id": room_id, "members": members},
        )
        try:
            self._send_room_ctl(member_id, {"type": "room_kick", "room_id": room_id})
        except ValueError:
            pass

        return 200, {"ok": True}
