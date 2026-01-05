# app/chat.py

import threading


class Chat:
    """
    Simple chat engine (v0).

    Responsibilities:
    - Send messages to peers discovered by Discovery
    - Listen for incoming messages
    - Ignore own messages

    Non-responsibilities:
    - No discovery
    - No CLI
    - No crypto
    """

    def __init__(self, transport, discovery, identity, port: int):
        self.transport = transport
        self.discovery = discovery
        self.identity = identity
        self.port = port
        self.running = False

    def start(self, on_message):
        """
        Start listening for incoming messages.

        on_message(sender_id: str, message: str)
        """
        self.running = True
        threading.Thread(
            target=self._listen_loop,
            args=(on_message,),
            daemon=True
        ).start()

    def stop(self):
        self.running = False

    def send_to_peer(self, peer_id: str, message: str):
        peers = self.discovery.get_peers()
        if peer_id not in peers:
            raise ValueError("Unknown peer")

        ip, _ = peers[peer_id]
        payload = f"MSG {self.identity.anon_id} {message}"
        self.transport.send(payload, ip, self.port)

    def send_to_all(self, message: str) -> int:
        peers = self.discovery.get_peers()
        count = 0

        for peer_id, (ip, _) in peers.items():
            payload = f"MSG {self.identity.anon_id} {message}"
            self.transport.send(payload, ip, self.port)
            count += 1

        return count

    # ---------------- internal ----------------

    def _listen_loop(self, on_message):
        while self.running:
            msg, _, _ = self.transport.recv()
            parts = msg.strip().split(maxsplit=2)

            if len(parts) != 3:
                continue

            msg_type, sender_id, text = parts

            if msg_type != "MSG":
                continue

            if sender_id == self.identity.anon_id:
                continue

            on_message(sender_id, text)
