from piqueserver import *
from piqueserver.commands import command
import json
import os


@command("role")
def role(connection, role: str):
    save_role(connection.name, role)

def get_json() -> dict:
    try:
        file = open("roles.json", "r")
        out = json.load(file)

        print(out)
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

def save_role(user_name: str, role: str) -> None:
    data = get_json()
    data[user_name] = role

    with open("roles.json", "w") as file:
        json.dump(data, file, indent=4)

def apply_script(protocol, connection, config):
    class RoleConnection(connection):
        def on_login(self, name: str):
            role: str = load_role(name)

            if role == None:
                self.send_chat(f"You don't have a role yet !\nGet one with /role <your role>.\nExample: /role 'the Master of Bamboo' -> {name} the Master of bamboo connected !")
                self.protocol.broadcast_chat(f"{name}, roleless connected !")
            else:
                self.protocol.broadcast_chat(f"{name}, {role} connected !")

            return connection.on_login(self, name)

    return protocol, RoleConnection