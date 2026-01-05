# core/discovery.py

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

            if msg_type == "GM":
                pub_key = payload
                self.peers[peer_id] = (ip, now, pub_key)

                # Reply directly
                ack = f"GM_ACK {self.identity.anon_id} {self.identity.crypto.public_key_b64}"
                self.transport.send(ack, ip, self.port)

            elif msg_type == "GM_ACK":
                pub_key = payload
                self.peers[peer_id] = (ip, now, pub_key)
            else:
                if DEBUG:
                    print(f"[discovery] drop unknown type: {msg_type}")
                continue

            self._cleanup()

    def _cleanup(self):
        now = time.time()
        expired = [
            peer_id
            for peer_id, (_, last_seen, _) in self.peers.items()
            if now - last_seen > self.PEER_TIMEOUT
        ]
        for peer_id in expired:
            del self.peers[peer_id]
