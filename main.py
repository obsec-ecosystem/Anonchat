# main.py

import threading

from core.identity import Identity
from core.transport import Transport

PORT = 54545
BROADCAST_IP = "255.255.255.255"


def listen_loop(transport: Transport):
    print("[*] Listening for incoming messages...")
    while True:
        msg, ip, port = transport.recv()
        print(f"\n[from {ip}:{port}] {msg}")
        print("> ", end="", flush=True)


def main():
    identity = Identity()
    transport = Transport(port=PORT)

    print(f"AnonChat started as: {identity.display_name()}")
    print("Type a message and press Enter to broadcast it on the LAN.")
    print("Ctrl+C to quit.\n")

    # Start listener thread
    t = threading.Thread(target=listen_loop, args=(transport,), daemon=True)
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
