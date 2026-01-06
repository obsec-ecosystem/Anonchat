from collections import deque
import logging
import time

from anonchat.cli.commands import handle_command, print_menu
from anonchat.config.settings import Settings
from anonchat.core.discovery import Discovery
from anonchat.core.identity import Identity
from anonchat.core.network import default_interface_ip
from anonchat.core.transport import Transport
from anonchat.messaging.chat import Chat
from anonchat.ui.server import run_ui_server


def main():
    settings = Settings.from_env()
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    log_buffer = deque(maxlen=200)

    def record_log(message: str):
        stamp = time.strftime("%H:%M:%S")
        log_buffer.append(f"{stamp} {message}")

    # --- Identity ---
    identity = Identity(nickname=settings.nickname)

    # --- Interface selection (auto or configured) ---
    bind_ip = settings.interface_ip or default_interface_ip()
    record_log(f"Using interface IP: {bind_ip}")

    # Shared state so UI can trigger interface switch
    state = {
        "transport": None,
        "discovery": None,
        "chat": None,
        "current_ip": bind_ip,
        "ui": None,
    }

    def current_ui_url():
        host_label = settings.ui_host
        if host_label == "0.0.0.0":
            host_label = state["current_ip"]
        return f"http://{host_label}:{settings.ui_port}"

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

    def stop_stack():
        if state["chat"]:
            state["chat"].stop()
        if state["discovery"]:
            state["discovery"].stop()
        if state["transport"]:
            state["transport"].close()

    def on_message(sender_id: str, message: str):
        record_log(f"[{sender_id}] {message}")

    def switch_interface(new_ip: str) -> bool:
        """
        Stop current stack, rebind transport, and restart discovery/chat.
        """
        if new_ip == state["current_ip"]:
            return True
        record_log(f"Switching interface to {new_ip}")

        # Stop existing stack
        stop_stack()

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
        record_log(f"Interface switched to {new_ip}")
        record_log(f"UI running at {current_ui_url()}")
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
        upstream_on_message=on_message,
        host=settings.ui_host,
        port=settings.ui_port,
        on_set_interface=switch_interface,
    )
    ui.set_current_ip(bind_ip)
    state["ui"] = ui

    chat.start(ui.on_message)

    # --- CLI ---
    record_log(f"UI running at {current_ui_url()}")

    def show_menu():
        print_menu(identity, current_ui_url(), state["current_ip"])

    show_menu()

    try:
        while True:
            line = input("> ").strip()
            if not line:
                continue

            should_continue = handle_command(
                line=line,
                discovery=state["discovery"],
                chat=state["chat"],
                logs=log_buffer,
                show_menu=show_menu,
            )

            if not should_continue:
                break

    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        print("\nExiting...")
        stop_stack()
