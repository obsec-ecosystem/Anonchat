# core/discovery.py

import threading
import time


class Discovery:
    """
    Simple Zeroconf-style peer discovery.

    Protocol:
      GM <peer_id>
      GM_ACK <peer_id>

    Keeps an in-memory table:
      peer_id -> (ip, last_seen)
    """

    GM_INTERVAL = 3        # seconds
    PEER_TIMEOUT = 10      # seconds

    def __init__(self, transport, identity, broadcast_ip: str, port: int):
        self.transport = transport
        self.identity = identity
        self.broadcast_ip = broadcast_ip
        self.port = port

        self.peers = {}  # peer_id -> (ip, last_seen)
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
            msg = f"GM {self.identity.anon_id}"
            self.transport.send(msg, self.broadcast_ip, self.port)
            time.sleep(self.GM_INTERVAL)

    def _listen_loop(self):
        while self.running:
            msg, ip, _ = self.transport.recv()
            parts = msg.strip().split()

            if len(parts) != 2:
                continue

            msg_type, peer_id = parts

            # Ignore our own messages
            if peer_id == self.identity.anon_id:
                continue

            now = time.time()

            if msg_type == "GM":
                self.peers[peer_id] = (ip, now)

                # Reply directly
                ack = f"GM_ACK {self.identity.anon_id}"
                self.transport.send(ack, ip, self.port)

            elif msg_type == "GM_ACK":
                self.peers[peer_id] = (ip, now)

            self._cleanup()

    def _cleanup(self):
        now = time.time()
        expired = [
            peer_id
            for peer_id, (_, last_seen) in self.peers.items()
            if now - last_seen > self.PEER_TIMEOUT
        ]
        for peer_id in expired:
            del self.peers[peer_id]
