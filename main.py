# main.py

from core.identity import Identity
from core.transport import Transport
from core.network import choose_interface_ip
from core.discovery import Discovery

from app.cli import (
    print_help,
    show_peers,
    send_all,
    send_one,
)

PORT = 54545
BROADCAST_IP = "255.255.255.255"


def main():
    # --- Identity ---
    identity = Identity()

    # --- Network interface selection ---
    bind_ip = choose_interface_ip()
    print(f"\n[*] Using interface IP: {bind_ip}\n")

    # --- Transport ---
    transport = Transport(
        port=PORT,
        bind_ip=bind_ip,
        broadcast=True,
    )

    # --- Discovery ---
    discovery = Discovery(
        transport=transport,
        identity=identity,
        broadcast_ip=BROADCAST_IP,
        port=PORT,
    )
    discovery.start()

    print(f"AnonChat started as: {identity.display_name()}")
    print("Type /help to see available commands.\n")

    try:
        while True:
            line = input("> ").strip()
            if not line:
                continue

            if line in ("/quit", "/exit"):
                break

            if line == "/help":
                print_help()
                continue

            if line == "/peers":
                show_peers(discovery)
                continue

            if line.startswith("/sendall "):
                msg = line[len("/sendall "):]
                send_all(discovery, transport, identity, PORT, msg)
                continue

            if line.startswith("/send "):
                send_one(discovery, transport, identity, PORT, line)
                continue

            print("Unknown command. Type /help.")

    except KeyboardInterrupt:
        pass
    finally:
        print("\nExiting...")
        discovery.stop()
        transport.close()


if __name__ == "__main__":
    main()
