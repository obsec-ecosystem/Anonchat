# core/discovery.py

import base64
import os
import threading
import time

DEBUG = os.getenv("ANONCHAT_DEBUG") == "1"


class Discovery:
    """
    Simple Zeroconf-style peer discovery.

    Protocol:
      GM <peer_id> <pub_key>
      GM_ACK <peer_id> <pub_key>
      NICK <peer_id> <nickname_b64>

    Keeps an in-memory table:
      peer_id -> (ip, last_seen, pub_key)
    """

    GM_INTERVAL = 3        # seconds
    PEER_TIMEOUT = 10      # seconds

    def __init__(self, transport, identity, broadcast_ip: str, port: int):
        self.transport = transport
        self.identity = identity
        self.broadcast_ip = broadcast_ip
        self.port = port

        # peer_id -> (ip, last_seen, pub_key)
        self.peers = {}
        self.running = False
        self.enc_handler = None

    def start(self):
        self.running = True
        threading.Thread(target=self._broadcast_loop, daemon=True).start()
        threading.Thread(target=self._listen_loop, daemon=True).start()

    def stop(self):
        self.running = False

    def get_peers(self):
        self._cleanup()
        return dict(self.peers)

    def set_enc_handler(self, handler):
        self.enc_handler = handler

    # ---------------- internal ----------------

    def _broadcast_loop(self):
        while self.running:
            msg = f"GM {self.identity.anon_id} {self.identity.crypto.public_key_b64}"
            try:
                self.transport.send(msg, self.broadcast_ip, self.port)
                nickname = self.identity.nickname or ""
                if nickname:
                    nick_b64 = base64.urlsafe_b64encode(nickname.encode("utf-8")).decode("ascii")
                    nick_msg = f"NICK {self.identity.anon_id} {nick_b64}"
                    self.transport.send(nick_msg, self.broadcast_ip, self.port)
            except OSError:
                if not self.running:
                    break
            time.sleep(self.GM_INTERVAL)

    def _listen_loop(self):
        while self.running:
            try:
                msg, ip, _ = self.transport.recv()
            except OSError:
                if not self.running:
                    break
                continue
            if DEBUG:
                print(f"[discovery] recv {ip}: {msg}")

            parts = msg.strip().split(maxsplit=2)

            # Expect exactly: TYPE peer_id pub_key
            if len(parts) != 3:
                if DEBUG:
                    print(f"[discovery] drop malformed: {msg!r}")
                continue

            msg_type, peer_id, payload = parts

            if msg_type == "ENC":
                if self.enc_handler:
                    self.enc_handler(peer_id, payload, ip)
                elif DEBUG:
                    print("[discovery] ENC handler not set; dropped")
                self._cleanup()
                continue

            # Ignore our own messages
            if peer_id == self.identity.anon_id:
                continue

            now = time.time()

            if msg_type in ("GM", "GM_ACK"):
                pub_key, nick = self._parse_payload(payload)
                if peer_id in self.peers:
                    _, _, _, existing_nick = self.peers[peer_id]
                else:
                    existing_nick = None
                self.peers[peer_id] = (ip, now, pub_key, nick or existing_nick)

                if msg_type == "GM":
                    ack = f"GM_ACK {self.identity.anon_id} {self.identity.crypto.public_key_b64}"
                    self.transport.send(ack, ip, self.port)
            elif msg_type == "NICK":
                if peer_id in self.peers:
                    ip, _, pub_key, _ = self.peers[peer_id]
                    nick = self._parse_nick(payload)
                    self.peers[peer_id] = (ip, now, pub_key, nick)
            else:
                if DEBUG:
                    print(f"[discovery] drop unknown type: {msg_type}")
                continue

            self._cleanup()

    def _cleanup(self):
        now = time.time()
        expired = [
            peer_id
            for peer_id, (_, last_seen, _, _) in self.peers.items()
            if now - last_seen > self.PEER_TIMEOUT
        ]
        for peer_id in expired:
            del self.peers[peer_id]

    def _parse_payload(self, payload: str):
        if "|" not in payload:
            return payload, None
        pub_key, nick_b64 = payload.split("|", 1)
        if not nick_b64:
            return pub_key, None
        try:
            nick = base64.urlsafe_b64decode(nick_b64.encode("ascii")).decode("utf-8")
        except Exception:
            nick = None
        return pub_key, nick

    def _parse_nick(self, payload: str):
        try:
            return base64.urlsafe_b64decode(payload.encode("ascii")).decode("utf-8")
        except Exception:
            return None
