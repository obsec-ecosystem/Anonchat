# core/network.py

import socket
import psutil


def list_ipv4_interfaces():
    """
    Returns a list of (interface_name, ipv4_address)
    """
    interfaces = []

    for name, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family == socket.AF_INET:
                interfaces.append((name, addr.address))

    return interfaces


def choose_interface_ip() -> str:
    """
    Ask the user to select which interface/IP to use.
    """
    interfaces = list_ipv4_interfaces()

    if not interfaces:
        raise RuntimeError("No IPv4 interfaces found")

    print("\nAvailable network interfaces:\n")

    for i, (name, ip) in enumerate(interfaces):
        print(f"[{i}] {name:<20} {ip}")

    print()

    while True:
        try:
            choice = int(input("Select interface number: "))
            if 0 <= choice < len(interfaces):
                _, ip = interfaces[choice]
                return ip
        except ValueError:
            pass

        print("Invalid selection, try again.\n")
