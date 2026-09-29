from flask import session
from flask_login import current_user
from flask_socketio import join_room, leave_room, send

def register_socket_events(socketio, rooms):
    @socketio.on("message")
    def handle_message(data):
        room = session.get("room")
        if not current_user.is_authenticated or room not in rooms:
            return

        content = {
            "name": current_user.username,
            "message": data.get("data", ""),
        }
        send(message=content, to=room)
        rooms[room]["messages"].append(content)
        print(f"{current_user.username} said: {content['message']}")

    @socketio.on("connect")
    def handle_connect(auth):
        room = session.get("room")
        if not current_user.is_authenticated or room not in rooms:
            return False

        join_room(room=room)
        name = current_user.username
        send(message={"name": name, "message": "has entered the room"}, to=room)
        rooms[room]["members"] += 1
        print(f"{name} joined room {room}")

    @socketio.on("disconnect")
    def handle_disconnect():
        room = session.get("room")
        if not room:
            return

        name = (
            current_user.username
            if current_user.is_authenticated
            else "A user"
        )
        leave_room(room=room)

        if room in rooms:
            rooms[room]["members"] -= 1
            if rooms[room]["members"] <= 0:
                del rooms[room]

        send(message={"name": name, "message": "has left the room"}, to=room)
        print(f"{name} left room {room}")
