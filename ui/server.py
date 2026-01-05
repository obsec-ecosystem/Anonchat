# ui/server.py

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

from flask import Flask, jsonify, render_template, request

BASE_DIR = Path(__file__).resolve().parent.parent


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
    - No discovery logic
    """

    def __init__(self, chat, discovery, identity, upstream_on_message=None):
        self.chat = chat
        self.discovery = discovery
        self.identity = identity
        self.upstream_on_message = upstream_on_message

        self._messages: List[Message] = []
        self._last_id = 0
        self._lock = threading.Lock()

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
            },
            daemon=True,
        )
        thread.start()
        return thread

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
        Hook passed to chat.start().
        Receives decrypted incoming messages.
        """
        # Incoming messages are always peer-specific rooms
        self._store_message("in", sender_id, sender_id, message)

        if self.upstream_on_message:
            self.upstream_on_message(sender_id, message)

    # ---------------- serialization ----------------

    def _serialize_message(self, msg: Message) -> Dict:
        return {
            "id": msg.id,
            "direction": msg.direction,
            "peer_id": msg.peer_id,
            "text": msg.text,
            "ts": msg.ts,
        }

    def _serialize_peers(self) -> List[Dict]:
        peers = self.discovery.get_peers()
        out = []
        for peer_id, (ip, last_seen, _) in peers.items():
            out.append(
                {
                    "id": peer_id,
                    "ip": ip,
                    "last_seen": last_seen,
                }
            )
        return out

    # ---------------- routes ----------------

    def _configure_routes(self):
        app = self.app

        @app.route("/")
        def index():
            return render_template("index.html")

        @app.get("/api/state")
        def api_state():
            after = request.args.get("after", "0")
            room = request.args.get("room", "all")

            try:
                after_id = int(after)
            except ValueError:
                after_id = 0

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
            rooms = ["all"] + [p["id"] for p in peers]

            return jsonify(
                {
                    "me": {
                        "id": self.identity.anon_id,
                        "name": self.identity.display_name(),
                    },
                    "rooms": rooms,
                    "peers": peers,
                    "messages": messages,
                }
            )

        @app.post("/api/send")
        def api_send():
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


def run_ui_server(
    chat,
    discovery,
    identity,
    upstream_on_message: Optional[Callable] = None,
    host: str = "127.0.0.1",
    port: int = 5000,
) -> UIServer:
    """
    Convenience helper.
    """
    ui = UIServer(
        chat=chat,
        discovery=discovery,
        identity=identity,
        upstream_on_message=upstream_on_message,
    )
    ui.run(host=host, port=port)
    return ui
