from __future__ import annotations

import hashlib
import json
import secrets
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set

from flask import Flask, jsonify, render_template, request, send_from_directory
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

from core.network import list_ipv4_interfaces

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
MAX_UPLOAD_MB = 10
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
ROOM_CTL_PREFIX = "ROOMCTL::"
ROOM_MSG_PREFIX = "ROOMMSG::"


@dataclass
class Message:
    id: int
    direction: str      # "in" | "out"
    room: str           # "all" | peer_id | room_id
    peer_id: str
    text: str
    ts: float


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


class UIServer:
    """
    Thin Flask UI layer.
    - No transport
    - No crypto
    - No discovery ownership
    """

    def __init__(
        self,
        chat,
        discovery,
        identity,
        upstream_on_message: Optional[Callable] = None,
        on_set_interface: Optional[Callable[[str], bool]] = None,
    ):
        self.chat = chat
        self.discovery = discovery
        self.identity = identity
        self.upstream_on_message = upstream_on_message
        self.on_set_interface = on_set_interface

        self.current_ip: Optional[str] = None

        self._messages: List[Message] = []
        self._last_id = 0
        self._lock = threading.Lock()
        self._rooms: Dict[str, Room] = {}
        self._room_events: List[Dict] = []
        self._known_peers: Set[str] = set()

        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

        self.app = Flask(
            __name__,
            template_folder=str(BASE_DIR / "templates"),
            static_folder=str(BASE_DIR / "static"),
        )
        self.app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
        self._configure_routes()

    # ---------------- lifecycle ----------------

    def run(self, host: str = "127.0.0.1", port: int = 5000):
        thread = threading.Thread(
            target=self.app.run,
            kwargs={
                "host": host,
                "port": port,
                "debug": False,
                "use_reloader": False,
                "threaded": True,
            },
            daemon=True,
        )
        thread.start()
        return thread

    def attach(self, chat, discovery):
        """
        Swap chat/discovery references (used after interface switch).
        """
        with self._lock:
            self.chat = chat
            self.discovery = discovery
        return self

    def set_current_ip(self, ip: str):
        self.current_ip = ip
        return self

    # ---------------- message bookkeeping ----------------

    def _next_id(self) -> int:
        self._last_id += 1
        return self._last_id

    def _store_message(self, direction: str, room: str, peer_id: str, text: str):
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
        return {
            "id": room.id,
            "name": room.name,
            "owner_id": room.owner_id,
            "created_at": room.created_at,
            "max_members": room.max_members,
            "locked": room.locked,
            "discoverable": room.discoverable,
            "member_count": len(room.members),
            "joined": room.joined,
            "pending": room.pending,
            "is_owner": room.owner_id == self.identity.anon_id,
        }

    def _serialize_rooms(self) -> List[Dict]:
        with self._lock:
            rooms = list(self._rooms.values())
        rooms.sort(key=lambda r: r.created_at)
        return [self._serialize_room(room) for room in rooms]

    def _push_room_event(self, event: Dict):
        with self._lock:
            self._room_events.append(event)
            if len(self._room_events) > 50:
                self._room_events = self._room_events[-50:]

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

    def _announce_room(self, room: Room, peer_ids: Optional[Set[str]] = None):
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

    def _handle_room_control(self, sender_id: str, raw_payload: str):
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
                        room.discoverable = bool(room_data.get("discoverable", room.discoverable))
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

    def _handle_room_message(self, sender_id: str, message: str):
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

    def on_message(self, sender_id: str, message: str):
        """
        Hook passed into chat.start().
        Receives decrypted inbound messages.
        """
        if message.startswith(ROOM_CTL_PREFIX):
            self._handle_room_control(sender_id, message[len(ROOM_CTL_PREFIX):])
            return

        if message.startswith(ROOM_MSG_PREFIX):
            result = self._handle_room_message(sender_id, message)
            if result and self.upstream_on_message:
                room_id, text = result
                self.upstream_on_message(sender_id, f"[room {room_id}] {text}")
            return

        self._store_message("in", sender_id, sender_id, message)

        if self.upstream_on_message:
            self.upstream_on_message(sender_id, message)

    # ---------------- serialization ----------------

    def _serialize_message(self, msg: Message) -> Dict:
        return {
            "id": msg.id,
            "direction": msg.direction,
            "room": msg.room,
            "peer_id": msg.peer_id,
            "text": msg.text,
            "ts": msg.ts,
            "iso": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(msg.ts)),
        }

    def _serialize_peers(self) -> List[Dict]:
        if not self.discovery:
            return []

        peers = self.discovery.get_peers()
        return [
            {
                "id": peer_id,
                "ip": ip,
                "last_seen": last_seen,
                "nickname": nickname or "",
            }
            for peer_id, (ip, last_seen, _, nickname) in peers.items()
        ]

    # ---------------- routes ----------------

    def _configure_routes(self):
        app = self.app

        @app.errorhandler(RequestEntityTooLarge)
        def handle_large_upload(_err):
            return jsonify({"error": f"File too large (max {MAX_UPLOAD_MB} MB)"}), 413

        @app.get("/")
        def index():
            return render_template(
                "index.html",
                my_id=self.identity.anon_id,
                display_name=self.identity.display_name(),
            )

        @app.get("/api/state")
        def api_state():
            try:
                after_id = int(request.args.get("after", "0"))
            except ValueError:
                after_id = 0

            room = (request.args.get("room") or "all").strip()

            with self._lock:
                if room == "all":
                    msgs = [m for m in self._messages if m.id > after_id]
                else:
                    msgs = [
                        m for m in self._messages
                        if m.id > after_id and m.room == room
                    ]

                messages = [self._serialize_message(m) for m in msgs]

            peers = self._serialize_peers()
            peer_ids = {peer["id"] for peer in peers}
            with self._lock:
                new_peers = peer_ids - self._known_peers
                if new_peers:
                    self._known_peers |= new_peers
                room_events = list(self._room_events)
                self._room_events.clear()

            rooms = self._serialize_rooms()
            if new_peers:
                with self._lock:
                    announce_rooms = [
                        room
                        for room in self._rooms.values()
                        if room.owner_id == self.identity.anon_id and room.discoverable
                    ]
                for room_item in announce_rooms:
                    self._announce_room(room_item, new_peers)

            return jsonify(
                {
                    "me": {
                        "id": self.identity.anon_id,
                        "name": self.identity.display_name(),
                        "nickname": self.identity.nickname or "",
                    },
                    "rooms": rooms,
                    "peers": peers,
                    "messages": messages,
                    "room_events": room_events,
                    "interface": {
                        "current": self.current_ip,
                    },
                }
            )

        @app.post("/api/send")
        def api_send():
            if not self.chat:
                return jsonify({"error": "Chat not ready"}), 503

            payload = request.get_json(silent=True) or {}
            room = (payload.get("room") or "all").strip()
            text = (payload.get("text") or "").strip()

            if not text:
                return jsonify({"error": "Message is empty"}), 400

            try:
                if room == "all":
                    sent = self.chat.send_to_all(text)
                    self._store_message("out", "all", "all", text)
                    return jsonify({"ok": True, "sent": sent})

                with self._lock:
                    room_obj = self._rooms.get(room)

                if room_obj:
                    if not room_obj.joined:
                        return jsonify({"error": "Join the room before sending"}), 403
                    members = set(room_obj.members)
                    if not members and room_obj.owner_id:
                        members.add(room_obj.owner_id)
                    payload = f"{ROOM_MSG_PREFIX}{room_obj.id}::{text}"
                    sent = 0
                    for peer_id in members:
                        if peer_id == self.identity.anon_id:
                            continue
                        self.chat.send_to_peer(peer_id, payload)
                        sent += 1
                    self._store_message("out", room_obj.id, room_obj.id, text)
                    return jsonify({"ok": True, "sent": sent})

                self.chat.send_to_peer(room, text)
                self._store_message("out", room, room, text)
                return jsonify({"ok": True, "sent": 1})
            except ValueError:
                return jsonify({"error": f"Unknown peer: {room}"}), 400

        @app.post("/api/nickname")
        def api_nickname():
            payload = request.get_json(silent=True) or {}
            nickname = (payload.get("nickname") or "").strip()

            if len(nickname) > 32:
                return jsonify({"error": "Nickname too long (max 32)"}), 400

            self.identity.nickname = nickname or None
            return jsonify(
                {
                    "ok": True,
                    "name": self.identity.display_name(),
                    "nickname": self.identity.nickname or "",
                }
            )

        @app.get("/api/interfaces")
        def api_interfaces():
            return jsonify(
                {
                    "interfaces": [
                        {"name": name, "ip": ip}
                        for name, ip in list_ipv4_interfaces()
                    ]
                }
            )

        @app.post("/api/interface")
        def api_set_interface():
            payload = request.get_json(silent=True) or {}
            ip = (payload.get("ip") or "").strip()

            if not ip:
                return jsonify({"error": "Missing ip"}), 400

            if not self.on_set_interface:
                return jsonify({"error": "Interface switching not supported"}), 501

            ok = self.on_set_interface(ip)
            if ok:
                self.current_ip = ip
                return jsonify({"ok": True, "ip": ip})

            return jsonify({"error": "Failed to switch interface"}), 500

        @app.post("/api/rooms")
        def api_create_room():
            payload = request.get_json(silent=True) or {}
            name = str(payload.get("name") or "").strip()
            password = str(payload.get("password") or "")
            discoverable = bool(payload.get("discoverable", True))
            try:
                max_members = int(payload.get("max_members") or 0)
            except (TypeError, ValueError):
                max_members = 0

            if not name:
                return jsonify({"error": "Room name required"}), 400
            if len(name) > 40:
                return jsonify({"error": "Room name too long (max 40)"}), 400

            if max_members <= 0:
                max_members = 12
            max_members = max(2, min(max_members, 200))

            locked = bool(password)
            salt = None
            password_hash = None
            if locked:
                if len(password) < 4:
                    return jsonify({"error": "Password too short (min 4)"}), 400
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
                    return jsonify({"error": "Room creation failed"}), 500

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

            self._announce_room(room)
            return jsonify({"ok": True, "room": self._serialize_room(room)})

        @app.post("/api/rooms/join")
        def api_join_room():
            payload = request.get_json(silent=True) or {}
            room_id = str(payload.get("room_id") or "").strip()
            password = str(payload.get("password") or "")

            if not room_id:
                return jsonify({"error": "Missing room id"}), 400

            with self._lock:
                room = self._rooms.get(room_id)
                if not room:
                    return jsonify({"error": "Room not found"}), 404
                if room.owner_id == self.identity.anon_id:
                    room.joined = True
                    room.pending = False
                    return jsonify({"ok": True, "room": self._serialize_room(room)})
                if room.joined:
                    return jsonify({"ok": True, "room": self._serialize_room(room)})
                room.pending = True

            try:
                self._send_room_ctl(
                    room.owner_id,
                    {"type": "room_join", "room_id": room_id, "password": password},
                )
            except ValueError:
                with self._lock:
                    room = self._rooms.get(room_id)
                    if room:
                        room.pending = False
                return jsonify({"error": "Room owner offline"}), 400

            return jsonify({"ok": True})

        @app.post("/api/rooms/leave")
        def api_leave_room():
            payload = request.get_json(silent=True) or {}
            room_id = str(payload.get("room_id") or "").strip()

            if not room_id:
                return jsonify({"error": "Missing room id"}), 400

            with self._lock:
                room = self._rooms.get(room_id)
                if not room:
                    return jsonify({"error": "Room not found"}), 404
                if room.owner_id == self.identity.anon_id:
                    return jsonify({"error": "Owner cannot leave the room"}), 400
                room.joined = False
                room.pending = False
                room.members.discard(self.identity.anon_id)

            try:
                self._send_room_ctl(
                    room.owner_id,
                    {"type": "room_leave", "room_id": room_id},
                )
            except ValueError:
                pass

            return jsonify({"ok": True})

        @app.post("/api/upload")
        def api_upload():
            if "file" not in request.files:
                return jsonify({"error": "Missing file"}), 400

            file = request.files["file"]
            if not file.filename:
                return jsonify({"error": "Missing filename"}), 400

            safe_name = secure_filename(file.filename)
            if not safe_name:
                return jsonify({"error": "Invalid filename"}), 400

            if request.content_length and request.content_length > MAX_UPLOAD_BYTES:
                return jsonify({"error": f"File too large (max {MAX_UPLOAD_MB} MB)"}), 413

            timestamp = int(time.time())
            target_name = f"{timestamp}_{safe_name}"
            target_path = UPLOAD_DIR / target_name
            file.save(target_path)

            host = request.host.split(":")[0]
            port = request.host.split(":")[1] if ":" in request.host else "80"
            scheme = request.scheme or "http"
            ip = self.current_ip or host
            if ip.startswith("127.") or ip == "localhost":
                for _, candidate in list_ipv4_interfaces():
                    if not candidate.startswith("127."):
                        ip = candidate
                        break
            url = f"{scheme}://{ip}:{port}/uploads/{target_name}"

            return jsonify(
                {
                    "ok": True,
                    "name": safe_name,
                    "size": target_path.stat().st_size,
                    "mime": file.mimetype or "application/octet-stream",
                    "url": url,
                }
            )

        @app.get("/uploads/<path:filename>")
        def upload_serve(filename: str):
            return send_from_directory(UPLOAD_DIR, filename, as_attachment=False)


def run_ui_server(
    chat,
    discovery,
    identity,
    upstream_on_message: Optional[Callable] = None,
    host: str = "127.0.0.1",
    port: int = 5000,
    on_set_interface: Optional[Callable[[str], bool]] = None,
) -> UIServer:
    """
    Convenience helper.
    """
    ui = UIServer(
        chat=chat,
        discovery=discovery,
        identity=identity,
        upstream_on_message=upstream_on_message,
        on_set_interface=on_set_interface,
    )
    ui.run(host=host, port=port)
    return ui
