from dataclasses import dataclass


@dataclass
class Message:
    id: int
    direction: str      # "in" | "out"
    room: str           # "all" | peer_id | room_id
    peer_id: str
    text: str
    ts: float
