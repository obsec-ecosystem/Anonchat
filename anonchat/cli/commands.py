# anonchat/cli/commands.py

def print_banner(identity):
    print(f"AnonChat started as: {identity.display_name()}")
    print("Security: encrypted (ephemeral session keys)")
    print("Type /help to see available commands.\n")


def print_menu(identity, ui_url, current_ip):
    print("\n=== AnonChat ===")
    print(f"User: {identity.display_name()}")
    print(f"Interface: {current_ip}")
    print(f"UI: {ui_url}")
    print("Commands: /menu /help /logs /peers /send /sendall /quit\n")


def print_help():
    print(
        "\nCommands:\n"
        "  /peers                 List discovered peers\n"
        "  /send <id> <message>   Send message to a specific peer\n"
        "  /sendall <message>     Send message to all peers\n"
        "  /logs                  Show recent logs\n"
        "  /menu                  Show the main menu\n"
        "  /help                  Show this help\n"
        "  /quit                  Exit\n"
    )


def handle_command(line, discovery, chat, logs=None, show_menu=None):
    """
    Handle a single CLI command.
    Returns False if the app should exit.
    """
    if line in ("/quit", "/exit"):
        return False

    if line == "/menu":
        if show_menu:
            show_menu()
        else:
            print_help()
        return True

    if line == "/help":
        print_help()
        return True

    if line == "/logs":
        if not logs:
            print("No logs yet.")
            return True
        print("\nRecent logs:")
        for entry in logs:
            print(f"  {entry}")
        print()
        return True

    if line == "/peers":
        peers = discovery.get_peers()
        if not peers:
            print("No peers discovered.")
        else:
            print("\nPeers:")
            for peer_id, (ip, _, _, _) in peers.items():
                print(f"  {peer_id:<15} {ip}")
            print()
        return True

    if line.startswith("/sendall "):
        msg = line[len("/sendall "):]
        sent = chat.send_to_all(msg)
        print(f"Sent to {sent} peer(s).")
        return True

    if line.startswith("/send "):
        parts = line.split(maxsplit=2)
        if len(parts) < 3:
            print("Usage: /send <peer_id> <message>")
            return True

        _, peer_id, msg = parts
        try:
            chat.send_to_peer(peer_id, msg)
            print(f"Sent to {peer_id}.")
        except ValueError:
            print(f"Unknown peer: {peer_id}")
        return True

    print("Unknown command. Type /help.")
    return True
