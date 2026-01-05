from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

from flask import Flask, jsonify, render_template, request, send_from_directory
from werkzeug.utils import secure_filename

from core.network import list_ipv4_interfaces

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"


@dataclass
class Message:
    id: int
    direction: str      # "in" | "out"
    room: str           # "all" | peer_id
    peer_id: str
    text: str
    ts: float


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

        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

        self.app = Flask(
            __name__,
            template_folder=str(BASE_DIR / "templates"),
            static_folder=str(BASE_DIR / "static"),
        )
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

    def on_message(self, sender_id: str, message: str):
        """
        Hook passed into chat.start().
        Receives decrypted inbound messages.
        """
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
            rooms = ["all"]

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
                else:
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
