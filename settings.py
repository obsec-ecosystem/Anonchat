# settings.py

import os


class Settings:
    """
    Centralized runtime settings.
    Override via environment variables.
    """

    def __init__(
        self,
        nickname: str | None = None,
        interface_ip: str | None = None,
        port: int = 54545,
        broadcast_ip: str = "255.255.255.255",
        ui_host: str = "127.0.0.1",
        ui_port: int = 5000,
    ):
        self.nickname = nickname
        self.interface_ip = interface_ip
        self.port = port
        self.broadcast_ip = broadcast_ip
        self.ui_host = ui_host
        self.ui_port = ui_port

    @classmethod
    def from_env(cls):
        nickname = os.getenv("ANONCHAT_NICKNAME")
        interface_ip = os.getenv("ANONCHAT_INTERFACE_IP")
        port = int(os.getenv("ANONCHAT_PORT", "54545"))
        broadcast_ip = os.getenv("ANONCHAT_BROADCAST_IP", "255.255.255.255")
        ui_host = os.getenv("ANONCHAT_UI_HOST", "127.0.0.1")
        ui_port = int(os.getenv("ANONCHAT_UI_PORT", "5000"))

        return cls(
            nickname=nickname,
            interface_ip=interface_ip,
            port=port,
            broadcast_ip=broadcast_ip,
            ui_host=ui_host,
            ui_port=ui_port,
        )
