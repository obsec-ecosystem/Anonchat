# core/identity.py

import uuid


class Identity:
    """
    Ephemeral anonymous identity for this session.
    Nickname is cosmetic only.
    """

    def __init__(self, nickname: str | None = None):
        self.anon_id = f"anon-{uuid.uuid4().hex[:8]}"
        self.nickname = nickname

    def display_name(self) -> str:
        if self.nickname:
            return f"{self.anon_id} ({self.nickname})"
        return self.anon_id
