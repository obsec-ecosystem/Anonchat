import secrets

from flask import jsonify, render_template, request, send_from_directory
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

from anonchat.core.network import list_ipv4_interfaces
from anonchat.core.room_chat import ROOM_MSG_PREFIX
from anonchat.ui.constants import MAX_UPLOAD_BYTES, MAX_UPLOAD_MB, SHARE_DIR, UPLOAD_DIR


def configure_routes(app, ui):
    @app.errorhandler(RequestEntityTooLarge)
    def handle_large_upload(_err):
        return jsonify({"error": f"File too large (max {MAX_UPLOAD_MB} MB)"}), 413

    @app.get("/")
    def index():
        return render_template(
            "index.html",
            my_id=ui.identity.anon_id,
            display_name=ui.identity.display_name(),
        )

    @app.get("/api/state")
    def api_state():
        try:
            after_id = int(request.args.get("after", "0"))
        except ValueError:
            after_id = 0

        room = (request.args.get("room") or "all").strip()

        messages = ui.messages.serialize_messages(
            ui.messages.messages_since(after_id, room)
        )

        peers = ui.serialize_peers()
        peer_ids = {peer["id"] for peer in peers}
        new_peers, room_events = ui.rooms.consume_room_events(peer_ids)

        rooms = ui.rooms.serialize_rooms()
        if new_peers:
            for room_item in ui.rooms.get_owned_discoverable_rooms():
                ui.rooms.announce_room(room_item, new_peers)

        return jsonify(
            {
                "me": {
                    "id": ui.identity.anon_id,
                    "name": ui.identity.display_name(),
                    "nickname": ui.identity.nickname or "",
                },
                "rooms": rooms,
                "peers": peers,
                "messages": messages,
                "room_events": room_events,
                "interface": {
                    "current": ui.current_ip,
                },
            }
        )

    @app.post("/api/send")
    def api_send():
        if not ui.chat:
            return jsonify({"error": "Chat not ready"}), 503

        payload = request.get_json(silent=True) or {}
        room = (payload.get("room") or "all").strip()
        text = (payload.get("text") or "").strip()

        if not text:
            return jsonify({"error": "Message is empty"}), 400

        try:
            if room == "all":
                sent = ui.chat.send_to_all(text)
                ui.messages.store("out", "all", "all", text)
                return jsonify({"ok": True, "sent": sent})

            room_obj = ui.rooms.get_room(room)

            if room_obj:
                if not room_obj.joined:
                    return jsonify({"error": "Join the room before sending"}), 403
                members = set(room_obj.members)
                if not members and room_obj.owner_id:
                    members.add(room_obj.owner_id)
                payload = f"{ROOM_MSG_PREFIX}{room_obj.id}::{text}"
                sent = 0
                for peer_id in members:
                    if peer_id == ui.identity.anon_id:
                        continue
                    ui.chat.send_to_peer(peer_id, payload)
                    sent += 1
                ui.messages.store("out", room_obj.id, room_obj.id, text)
                return jsonify({"ok": True, "sent": sent})

            ui.chat.send_to_peer(room, text)
            ui.messages.store("out", room, room, text)
            return jsonify({"ok": True, "sent": 1})
        except ValueError:
            return jsonify({"error": f"Unknown peer: {room}"}), 400

    @app.post("/api/nickname")
    def api_nickname():
        payload = request.get_json(silent=True) or {}
        nickname = (payload.get("nickname") or "").strip()

        if len(nickname) > 32:
            return jsonify({"error": "Nickname too long (max 32)"}), 400

        ui.identity.nickname = nickname or None
        return jsonify(
            {
                "ok": True,
                "name": ui.identity.display_name(),
                "nickname": ui.identity.nickname or "",
            }
        )

    @app.get("/api/interfaces")
    def api_interfaces():
        return jsonify(
            {
                "interfaces": [
                    {"name": name, "ip": ip}
                    for name, ip in list_ipv4_interfaces()
                ]
            }
        )

    @app.post("/api/interface")
    def api_set_interface():
        payload = request.get_json(silent=True) or {}
        ip = (payload.get("ip") or "").strip()

        if not ip:
            return jsonify({"error": "Missing ip"}), 400

        if not ui.on_set_interface:
            return jsonify({"error": "Interface switching not supported"}), 501

        ok = ui.on_set_interface(ip)
        if ok:
            ui.current_ip = ip
            return jsonify({"ok": True, "ip": ip})

        return jsonify({"error": "Failed to switch interface"}), 500

    @app.post("/api/rooms")
    def api_create_room():
        payload = request.get_json(silent=True) or {}
        name = str(payload.get("name") or "").strip()
        password = str(payload.get("password") or "")
        discoverable = bool(payload.get("discoverable", True))
        try:
            max_members = int(payload.get("max_members") or 0)
        except (TypeError, ValueError):
            max_members = 0

        if not name:
            return jsonify({"error": "Room name required"}), 400
        if len(name) > 40:
            return jsonify({"error": "Room name too long (max 40)"}), 400

        if max_members <= 0:
            max_members = 12
        max_members = max(2, min(max_members, 200))

        if password and len(password) < 4:
            return jsonify({"error": "Password too short (min 4)"}), 400

        room = ui.rooms.create_room(name, password, discoverable, max_members)
        if not room:
            return jsonify({"error": "Room creation failed"}), 500

        return jsonify({"ok": True, "room": ui.rooms.serialize_room(room)})

    @app.post("/api/rooms/join")
    def api_join_room():
        payload = request.get_json(silent=True) or {}
        room_id = str(payload.get("room_id") or "").strip()
        password = str(payload.get("password") or "")

        if not room_id:
            return jsonify({"error": "Missing room id"}), 400

        status, response = ui.rooms.join_room(room_id, password)
        return jsonify(response), status

    @app.post("/api/rooms/leave")
    def api_leave_room():
        payload = request.get_json(silent=True) or {}
        room_id = str(payload.get("room_id") or "").strip()

        if not room_id:
            return jsonify({"error": "Missing room id"}), 400

        status, response = ui.rooms.leave_room(room_id)
        return jsonify(response), status

    @app.post("/api/rooms/kick")
    def api_kick_room_member():
        payload = request.get_json(silent=True) or {}
        room_id = str(payload.get("room_id") or "").strip()
        member_id = str(payload.get("member_id") or "").strip()

        if not room_id:
            return jsonify({"error": "Missing room id"}), 400
        if not member_id:
            return jsonify({"error": "Missing member id"}), 400

        status, response = ui.rooms.kick_member(room_id, member_id)
        return jsonify(response), status

    @app.post("/api/upload")
    def api_upload():
        if "file" not in request.files:
            return jsonify({"error": "Missing file"}), 400

        file = request.files["file"]
        if not file.filename:
            return jsonify({"error": "Missing filename"}), 400

        safe_name = secure_filename(file.filename)
        if not safe_name:
            return jsonify({"error": "Invalid filename"}), 400

        if request.content_length and request.content_length > MAX_UPLOAD_BYTES:
            return jsonify({"error": f"File too large (max {MAX_UPLOAD_MB} MB)"}), 413

        room_id = str(request.form.get("room") or "all").strip() or "all"
        safe_room = secure_filename(room_id) or "all"
        safe_room = safe_room[:64]
        token = secrets.token_hex(8)
        target_name = f"{token}_{safe_name}"
        room_dir = SHARE_DIR / safe_room
        room_dir.mkdir(parents=True, exist_ok=True)
        target_path = room_dir / target_name
        file.save(target_path)

        host = request.host.split(":")[0]
        port = request.host.split(":")[1] if ":" in request.host else "80"
        scheme = request.scheme or "http"
        ip = ui.current_ip or host
        if ip.startswith("127.") or ip == "localhost":
            for _, candidate in list_ipv4_interfaces():
                if not candidate.startswith("127."):
                    ip = candidate
                    break
        url = f"{scheme}://{ip}:{port}/share/{safe_room}/{target_name}"

        return jsonify(
            {
                "ok": True,
                "name": safe_name,
                "size": target_path.stat().st_size,
                "mime": file.mimetype or "application/octet-stream",
                "url": url,
            }
        )

    @app.get("/share/<path:filename>")
    def share_serve(filename: str):
        return send_from_directory(SHARE_DIR, filename, as_attachment=False)

    @app.get("/uploads/<path:filename>")
    def upload_serve(filename: str):
        return send_from_directory(UPLOAD_DIR, filename, as_attachment=False)
