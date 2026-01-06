# main.py

from core.identity import Identity
from core.network import default_interface_ip
from core.transport import Transport
from core.discovery import Discovery

from app.chat import Chat
from app.cli import (
    print_banner,
    handle_command,
)
from settings import Settings
from ui.server import run_ui_server


def main():
    settings = Settings.from_env()

    # --- Identity ---
    identity = Identity(nickname=settings.nickname)

    # --- Interface selection (auto or configured) ---
    bind_ip = settings.interface_ip or default_interface_ip()
    print(f"\n[*] Using interface IP: {bind_ip}\n")

    # Shared state so UI can trigger interface switch
    state = {
        "transport": None,
        "discovery": None,
        "chat": None,
        "current_ip": bind_ip,
        "ui": None,
    }

    def build_stack(ip: str):
        transport = Transport(
            port=settings.port,
            bind_ip=ip,
            broadcast=True,
        )
        discovery = Discovery(
            transport=transport,
            identity=identity,
            broadcast_ip=settings.broadcast_ip,
            port=settings.port,
        )
        chat = Chat(
            transport=transport,
            discovery=discovery,
            identity=identity,
            port=settings.port,
        )
        return transport, discovery, chat

    def on_message(sender_id: str, message: str):
        print(f"\n[{sender_id}] {message}")
        print("> ", end="", flush=True)

    def switch_interface(new_ip: str) -> bool:
        """
        Stop current stack, rebind transport, and restart discovery/chat.
        """
        if new_ip == state["current_ip"]:
            return True
        print(f"\n[*] Switching interface to {new_ip}")

        # Stop existing stack
        if state["chat"]:
            state["chat"].stop()
        if state["discovery"]:
            state["discovery"].stop()
        if state["transport"]:
            state["transport"].close()

        # Rebuild
        state["current_ip"] = new_ip
        transport, discovery, chat = build_stack(new_ip)
        discovery.start()
        state["transport"] = transport
        state["discovery"] = discovery
        state["chat"] = chat

        # Re-wire UI hooks
        if state["ui"]:
            state["ui"].attach(chat, discovery)
            state["ui"].set_current_ip(new_ip)
            chat.start(state["ui"].on_message)
        return True

    # Initial stack
    transport, discovery, chat = build_stack(bind_ip)
    discovery.start()
    state["transport"] = transport
    state["discovery"] = discovery
    state["chat"] = chat

    # --- UI server (non-blocking) ---
    ui = run_ui_server(
        chat=chat,
        discovery=discovery,
        identity=identity,
        upstream_on_message=on_message,  # keep CLI printing
        host=settings.ui_host,
        port=settings.ui_port,
        on_set_interface=switch_interface,
    )
    ui.set_current_ip(bind_ip)
    state["ui"] = ui

    chat.start(ui.on_message)

    # --- CLI ---
    print_banner(identity)
    ui_host_label = settings.ui_host
    if ui_host_label == "0.0.0.0":
        ui_host_label = bind_ip
    print(f"UI running at http://{ui_host_label}:{settings.ui_port}\n")

    try:
        while True:
            line = input("> ").strip()
            if not line:
                continue

            should_continue = handle_command(
                line=line,
                discovery=state["discovery"],
                chat=state["chat"],
            )

            if not should_continue:
                break

    except KeyboardInterrupt:
        pass
    finally:
        print("\nExiting...")
        if state["chat"]:
            state["chat"].stop()
        if state["discovery"]:
            state["discovery"].stop()
        if state["transport"]:
            state["transport"].close()


if __name__ == "__main__":
    main()
