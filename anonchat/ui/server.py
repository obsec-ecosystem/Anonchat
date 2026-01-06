from __future__ import annotations

import threading
from typing import Callable, Optional

from flask import Flask

from anonchat.core.room_chat import ROOM_CTL_PREFIX, ROOM_MSG_PREFIX, RoomManager
from anonchat.ui.constants import MAX_UPLOAD_BYTES, SHARE_DIR, STATIC_DIR, TEMPLATES_DIR, UPLOAD_DIR
from anonchat.ui.message_store import MessageStore
from anonchat.ui.routes import configure_routes


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

        self._lock = threading.Lock()
        self.messages = MessageStore(self._lock)
        self.rooms = RoomManager(
            lock=self._lock,
            identity=self.identity,
            chat=self.chat,
            store_message=self.messages.store,
        )

        SHARE_DIR.mkdir(parents=True, exist_ok=True)
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

        self.app = Flask(
            __name__,
            template_folder=str(TEMPLATES_DIR),
            static_folder=str(STATIC_DIR),
        )
        self.app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
        configure_routes(self.app, self)

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
            self.rooms.update_chat(chat)
        return self

    def set_current_ip(self, ip: str):
        self.current_ip = ip
        return self

    # ---------------- discovery ----------------

    def serialize_peers(self):
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

    # ---------------- inbound hook ----------------

    def on_message(self, sender_id: str, message: str):
        """
        Hook passed into chat.start().
        Receives decrypted inbound messages.
        """
        if message.startswith(ROOM_CTL_PREFIX):
            self.rooms.handle_room_control(sender_id, message[len(ROOM_CTL_PREFIX):])
            return

        if message.startswith(ROOM_MSG_PREFIX):
            result = self.rooms.handle_room_message(sender_id, message)
            if result and self.upstream_on_message:
                room_id, text = result
                self.upstream_on_message(sender_id, f"[room {room_id}] {text}")
            return

        self.messages.store("in", sender_id, sender_id, message)

        if self.upstream_on_message:
            self.upstream_on_message(sender_id, message)


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
