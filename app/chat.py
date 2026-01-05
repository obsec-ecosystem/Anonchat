# app/chat.py

import os

DEBUG = os.getenv("ANONCHAT_DEBUG") == "1"


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
        self.on_message = None

    def start(self, on_message):
        """
        Start listening for incoming messages.

        on_message(sender_id: str, message: str)
        """
        self.on_message = on_message
        self.running = True
        self.discovery.set_enc_handler(self._handle_enc)

    def stop(self):
        self.running = False
        self.discovery.set_enc_handler(None)

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

    def _handle_enc(self, sender_id: str, ciphertext: str, ip: str):
        if not self.running:
            return

        # Ignore our own messages
        if sender_id == self.identity.anon_id:
            return

        peers = self.discovery.get_peers()
        if sender_id not in peers:
            if DEBUG:
                print(f"[chat] drop ENC from {sender_id} ({ip}): unknown peer")
            return

        _, _, sender_pub_key = peers[sender_id]

        # Register peer key if needed
        self.identity.crypto.register_peer(sender_id, sender_pub_key)

        try:
            plaintext = self.identity.crypto.decrypt(sender_id, ciphertext)
        except Exception:
            # Decryption failed (tampered / wrong key)
            if DEBUG:
                print(f"[chat] drop ENC from {sender_id} ({ip}): decrypt failed")
            return

        if self.on_message:
            self.on_message(sender_id, plaintext)
