# app/cli.py

def print_help():
    print(
        "\nCommands:\n"
        "  /peers                 List discovered peers\n"
        "  /send <id> <message>   Send message to a specific peer\n"
        "  /sendall <message>     Send message to all peers\n"
        "  /help                  Show this help\n"
        "  /quit                  Exit\n"
    )


def show_peers(discovery):
    peers = discovery.get_peers()
    if not peers:
        print("No peers discovered.")
        return

    print("\nPeers:")
    for peer_id, (ip, _) in peers.items():
        print(f"  {peer_id:<15} {ip}")
    print()


def send_all(discovery, transport, identity, port, message: str):
    peers = discovery.get_peers()
    if not peers:
        print("No peers to send to.")
        return

    for peer_id, (ip, _) in peers.items():
        payload = f"{identity.anon_id}: {message}"
        transport.send(payload, ip, port)

    print(f"Sent to {len(peers)} peer(s).")


def send_one(discovery, transport, identity, port, line: str):
    parts = line.split(maxsplit=2)
    if len(parts) < 3:
        print("Usage: /send <peer_id> <message>")
        return

    _, peer_id, message = parts
    peers = discovery.get_peers()

    if peer_id not in peers:
        print(f"Unknown peer: {peer_id}")
        return

    ip, _ = peers[peer_id]
    payload = f"{identity.anon_id}: {message}"
    transport.send(payload, ip, port)

    print(f"Sent to {peer_id}.")
