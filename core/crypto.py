# core/crypto.py

import os
import base64

from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305


def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _b64d(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode((s + pad).encode())


class CryptoBox:
    """
    Single-responsibility crypto container.

    - Ephemeral per session
    - One shared key per peer
    - Authenticated encryption
    """

    def __init__(self):
        # Generate ephemeral keypair
        self._priv = x25519.X25519PrivateKey.generate()
        self.public_key_b64 = _b64e(
            self._priv.public_key().public_bytes_raw()
        )

        # peer_id -> shared_key
        self._shared_keys = {}

    # ---- handshake ----

    def register_peer(self, peer_id: str, peer_pub_b64: str):
        """
        Derive and store shared key for a peer.
        """
        if peer_id in self._shared_keys:
            return

        peer_pub = x25519.X25519PublicKey.from_public_bytes(
            _b64d(peer_pub_b64)
        )

        shared = self._priv.exchange(peer_pub)

        key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b"anonchat",
        ).derive(shared)

        self._shared_keys[peer_id] = key

    # ---- messaging ----

    def encrypt(self, peer_id: str, plaintext: str) -> str:
        """
        Encrypt message for peer.
        Returns nonce.ciphertext (base64)
        """
        key = self._shared_keys.get(peer_id)
        if not key:
            raise ValueError("Unknown peer key")

        nonce = os.urandom(12)
        aead = ChaCha20Poly1305(key)
        ct = aead.encrypt(nonce, plaintext.encode(), None)

        return f"{_b64e(nonce)}.{_b64e(ct)}"

    def decrypt(self, peer_id: str, blob: str) -> str:
        """
        Decrypt message from peer.
        """
        key = self._shared_keys.get(peer_id)
        if not key:
            raise ValueError("Unknown peer key")

        nonce_b64, ct_b64 = blob.split(".", 1)
        nonce = _b64d(nonce_b64)
        ct = _b64d(ct_b64)

        aead = ChaCha20Poly1305(key)
        pt = aead.decrypt(nonce, ct, None)
        return pt.decode()
