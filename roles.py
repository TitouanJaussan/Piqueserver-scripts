from piqueserver import *
from piqueserver.commands import command
import json
import os

@command("change_role", admin_only=True)
def change_role(connection, user: str, _role: str):
    save_role(connection, user, _role)

@command("role")
def role(connection, *args):
    save_role(connection, connection.name, " ".join(args))

def get_json() -> dict:
    try:
        file = open("roles.json", "r")
        out = json.load(file)

        file.close()
        return out

    except:
        f = open("roles.json", "w")
        f.write("{}")
        f.close()
        return {}

def load_role(user_name: str) -> str:
    data = get_json()
    return data.get(user_name)

def save_role(connection, user_name: str, role: str) -> None:
    data = get_json()
    data[user_name] = role

    connection.send_chat(f"Role succesfully updated to {role}!")

    with open("roles.json", "w") as file:
        json.dump(data, file, indent=4)

def apply_script(protocol, connection, config):
    class RoleConnection(connection):
        def on_login(self, name: str):
            role: str = load_role(name)

            if role == None:
                self.send_chat(f"You don't have a role yet!")
            else:
                self.protocol.broadcast_chat(f"{name}, {role} connected!")

            return connection.on_login(self, name)

    return protocol, RoleConnection
