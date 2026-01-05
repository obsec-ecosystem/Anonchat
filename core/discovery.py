# core/discovery.py

import threading
import time


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

    def start(self):
        self.running = True
        threading.Thread(target=self._broadcast_loop, daemon=True).start()
        threading.Thread(target=self._listen_loop, daemon=True).start()

    def stop(self):
        self.running = False

    def get_peers(self):
        self._cleanup()
        return dict(self.peers)

    # ---------------- internal ----------------

    def _broadcast_loop(self):
        while self.running:
            msg = f"GM {self.identity.anon_id} {self.identity.crypto.public_key_b64}"
            self.transport.send(msg, self.broadcast_ip, self.port)
            time.sleep(self.GM_INTERVAL)

    def _listen_loop(self):
        while self.running:
            msg, ip, _ = self.transport.recv()
            parts = msg.strip().split()

            # Expect exactly: TYPE peer_id pub_key
            if len(parts) != 3:
                continue

            msg_type, peer_id, pub_key = parts

            # Ignore our own messages
            if peer_id == self.identity.anon_id:
                continue

            now = time.time()

            if msg_type == "GM":
                self.peers[peer_id] = (ip, now, pub_key)

                # Reply directly
                ack = f"GM_ACK {self.identity.anon_id} {self.identity.crypto.public_key_b64}"
                self.transport.send(ack, ip, self.port)

            elif msg_type == "GM_ACK":
                self.peers[peer_id] = (ip, now, pub_key)

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
