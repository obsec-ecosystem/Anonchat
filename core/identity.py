# core/identity.py

import uuid

from core.crypto import CryptoBox


class Identity:
    """
    Ephemeral anonymous identity for this session.

    - anon_id: short, random session identifier
    - nickname: cosmetic only
    - crypto: per-session CryptoBox (encryption handled elsewhere)
    """

    def __init__(self, nickname: str | None = None):
        self.anon_id = f"anon-{uuid.uuid4().hex[:8]}"
        self.nickname = nickname

        # Per-session crypto context (ephemeral keys)
        self.crypto = CryptoBox()

    def display_name(self) -> str:
        if self.nickname:
            return f"{self.anon_id} ({self.nickname})"
        return self.anon_id
