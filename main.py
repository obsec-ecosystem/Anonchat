# main.py

import threading

from core.identity import Identity
from core.transport import Transport
from core.network import choose_interface_ip

PORT = 54545
BROADCAST_IP = "255.255.255.255"


def listen_loop(transport: Transport, identity: Identity):
    print("[*] Listening for incoming messages...")
    while True:
        msg, ip, port = transport.recv()

        # Ignore our own messages
        if msg.startswith(identity.anon_id):
            continue

        print(f"\n[from {ip}:{port}] {msg}")
        print("> ", end="", flush=True)


def main():
    identity = Identity()

    bind_ip = choose_interface_ip()
    print(f"\n[*] Using interface IP: {bind_ip}\n")

    transport = Transport(port=PORT, bind_ip=bind_ip)

    print(f"AnonChat started as: {identity.display_name()}")
    print("Type a message and press Enter to broadcast it.")
    print("Ctrl+C to quit.\n")

    t = threading.Thread(
        target=listen_loop,
        args=(transport, identity),
        daemon=True
    )
    t.start()

    try:
        while True:
            msg = input("> ").strip()
            if not msg:
                continue

            payload = f"{identity.anon_id}: {msg}"
            transport.send(payload, BROADCAST_IP, PORT)

    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        transport.close()


if __name__ == "__main__":
    main()
