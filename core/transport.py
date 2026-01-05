# core/transport.py

import socket


class Transport:
    """
    Dumb UDP transport layer.
    Responsible only for sending and receiving bytes.
    """

    def __init__(self, port: int, broadcast: bool = True):
        self.port = port

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        if broadcast:
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        # Listen on all interfaces
        self.sock.bind(("", port))

    def send(self, data: str, ip: str, port: int):
        """
        Send a UTF-8 message to a specific IP:port.
        """
        self.sock.sendto(data.encode("utf-8"), (ip, port))

    def recv(self, bufsize: int = 4096):
        """
        Blocking receive.
        Returns (message:str, sender_ip:str, sender_port:int)
        """
        data, (ip, port) = self.sock.recvfrom(bufsize)
        return data.decode("utf-8", errors="ignore"), ip, port

    def close(self):
        self.sock.close()
