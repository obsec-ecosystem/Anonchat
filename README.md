# Anonchat

LAN-first messenger with rooms, peer discovery, and a lightweight web UI.

## Features
- LAN discovery and encrypted peer chat.
- Rooms with join/leave, owner controls, and member list.
- Web UI + CLI running side by side.
- Local message history stored on disk.
- File sharing stored per-room with randomized filenames.

## Requirements
- Python 3.10+
- Dependencies: `flask`, `psutil`, `cryptography`

## Quick start
```bash
python main.py
```
Open the UI at the URL printed in the console (default `http://<ip>:5000`).

## Configuration
Set environment variables to override defaults:
- `ANONCHAT_NICKNAME`
- `ANONCHAT_INTERFACE_IP`
- `ANONCHAT_PORT`
- `ANONCHAT_BROADCAST_IP`
- `ANONCHAT_UI_HOST`
- `ANONCHAT_UI_PORT`

## Data and storage
- Messages: `database/messages.db`
- Shared files: `share/<room>/<random>_<filename>`
- Legacy uploads: `uploads/`

## Project layout
- `anonchat/core`: networking, crypto, discovery, rooms
- `anonchat/messaging`: chat transport logic
- `anonchat/ui`: Flask UI + templates/static assets
- `anonchat/cli`: CLI commands and menu
- `anonchat/config`: runtime settings

## Build Windows exe
```powershell
pip install -r requirements.txt -r requirements-build.txt
.\scripts\build_windows.ps1
```
The exe will be in `dist/anonchat.exe`.
