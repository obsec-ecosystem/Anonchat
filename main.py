# main.py

from core.identity import Identity
from core.network import choose_interface_ip
from core.transport import Transport
from core.discovery import Discovery

from app.chat import Chat
from app.cli import (
    print_banner,
    handle_command,
)
from ui.server import run_ui_server

PORT = 54545
BROADCAST_IP = "255.255.255.255"


def main():
    # --- Identity ---
    identity = Identity()

    # --- Interface selection ---
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

    # --- Chat ---
    def on_message(sender_id: str, message: str):
        print(f"\n[{sender_id}] {message}")
        print("> ", end="", flush=True)

    chat = Chat(
        transport=transport,
        discovery=discovery,
        identity=identity,
        port=PORT,
    )

    # --- UI server (non-blocking) ---
    ui = run_ui_server(
        chat=chat,
        discovery=discovery,
        identity=identity,
        upstream_on_message=on_message,  # keep CLI printing
    )

    chat.start(ui.on_message)

    # --- CLI ---
    print_banner(identity)

    try:
        while True:
            line = input("> ").strip()
            if not line:
                continue

            should_continue = handle_command(
                line=line,
                discovery=discovery,
                chat=chat,
            )

            if not should_continue:
                break

    except KeyboardInterrupt:
        pass
    finally:
        print("\nExiting...")
        chat.stop()
        discovery.stop()
        transport.close()


if __name__ == "__main__":
    main()
