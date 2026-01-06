# core/transport.py

import socket


class Transport:
    """
    Minimal UDP transport layer.

    Responsibilities:
    - Bind a UDP socket to a specific local interface
    - Send UTF-8 messages
    - Receive UTF-8 messages

    Non-responsibilities:
    - No peer management
    - No discovery logic
    - No protocol parsing
    - No threading
    """

    def __init__(self, port: int, bind_ip: str, broadcast: bool = True):
        self.port = port
        self.bind_ip = bind_ip

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Allow rebinding (useful during restarts)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Enable broadcast if needed
        if broadcast:
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        # Bind ONLY to the selected interface
        self.sock.bind((self.bind_ip, self.port))

    def send(self, message: str, target_ip: str, target_port: int):
        """
        Send a message to a specific IP:port.
        """
        data = message.encode("utf-8")
        self.sock.sendto(data, (target_ip, target_port))

    def recv(self, bufsize: int = 4096):
        """
        Blocking receive.

        Returns:
            message (str), sender_ip (str), sender_port (int)
        """
        data, (ip, port) = self.sock.recvfrom(bufsize)
        message = data.decode("utf-8", errors="ignore")
        return message, ip, port

    def close(self):
        """
        Close the UDP socket.
        """
        self.sock.close()
