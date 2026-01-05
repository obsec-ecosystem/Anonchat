# app/chat.py

import threading


class Chat:
    """
    Encrypted chat engine (v1).

    Message format:
      ENC <sender_id> <ciphertext>

    Responsibilities:
    - Encrypt messages before sending
    - Decrypt messages on receive
    - Use discovery for peer lookup

    Non-responsibilities:
    - No key exchange logic
    - No CLI
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

        ip, _, peer_pub_key = peers[peer_id]

        # Register peer key (no-op if already known)
        self.identity.crypto.register_peer(peer_id, peer_pub_key)

        ciphertext = self.identity.crypto.encrypt(peer_id, message)

        payload = f"ENC {self.identity.anon_id} {ciphertext}"
        self.transport.send(payload, ip, self.port)

    def send_to_all(self, message: str) -> int:
        peers = self.discovery.get_peers()
        count = 0

        for peer_id in peers.keys():
            self.send_to_peer(peer_id, message)
            count += 1

        return count

    # ---------------- internal ----------------

    def _listen_loop(self, on_message):
        while self.running:
            msg, _, _ = self.transport.recv()
            parts = msg.strip().split(maxsplit=2)

            # Expect: ENC sender_id ciphertext
            if len(parts) != 3:
                continue

            msg_type, sender_id, ciphertext = parts

            if msg_type != "ENC":
                continue

            # Ignore our own messages
            if sender_id == self.identity.anon_id:
                continue

            peers = self.discovery.get_peers()
            if sender_id not in peers:
                continue

            _, _, sender_pub_key = peers[sender_id]

            # Register peer key if needed
            self.identity.crypto.register_peer(sender_id, sender_pub_key)

            try:
                plaintext = self.identity.crypto.decrypt(sender_id, ciphertext)
            except Exception:
                # Decryption failed (tampered / wrong key)
                continue

            on_message(sender_id, plaintext)
