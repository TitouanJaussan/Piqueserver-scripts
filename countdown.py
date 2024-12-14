from piqueserver import *
from piqueserver.commands import command
from twisted.internet.task import LoopingCall

"""
Countdown script by Gato :D
Use: /countdown <duration (in secs) or hh:mm:ss or mm:ss, etc...| 'stop'> <'private' | 'public'> default: [DEFAULT_MODE] <on end message> default: [DEFAULT_END_MESSAGE]'
Example: /countdown 60 private
         /countdown 30 public
         /countdown 1:20 <-> /countdown 80
         /countdown 1:40:00
         /countdown stop
         /check_countdown
"""

DEFAULT_MODE = "private"
COUNTDOWN_STEPS = [600, 300, 150, 60, 30, 20, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1]
DEFAULT_END_MESSAGE = "Time Over !"

@command("check_countdown")
def check_countdown(connection, *args):
    if not connection.currently_active:
        connection.send_chat(f"There is no countdown for now")
        return

    connection.send_chat(f"There is {connection.secs_to_text(connection.current_time)} left")

@command("countdown")
def countdown(connection, *args):
    if len(args) == 0:
        connection.send_chat("/countdown <time in secs>. Will start a countdown for how long you want it to.\nExample: /countdown 10 or /countdown 1:30. Time is in secs")
        return

    if args[0].lower() == "stop":
        if not connection.currently_active:
            connection.send_chat("Can't stop a non-active countdown !")
            return

        connection.send_chat("Stopping countdown ...")
        connection.on_countdow_end()
        return
    
    if connection.currently_active:
        connection.send_chat("A countdown is already running. If you would like to stop it use /countdown stop")
        return
    
    components = args[0].split(":")

    if len(components) > 3:
        connection.send_chat("Invalid time format. Valid format is hh:mm:ss or mm:ss (hh = hour, mm = minute, ss = seconds)")
        return
    
    _time = []

    for component in components:
        try:
            _time.append(int(component))
        except ValueError:
            connection.send_chat(f"Malformed time format: {component}")
            return
    
    if len(_time) == 0:
        connection.send_chat("Malformed time format")
        return

    _time.reverse()

    tot_time = 0
    tot_time += _time[0]
    tot_time += (_time[1] * 60 if len(_time) >= 2 else 0)
    tot_time += (_time[2] * 3600 if len(_time) >= 3 else 0)
    
    if len(args) <= 1:
        public = DEFAULT_MODE.lower() == "public"
    else:
        public = args[1].lower() == "public"
    
    if public:
        if not connection.admin:
            connection.send_chat("You can't create a public countdown, you need to be admin !")
            return

    connection.public = public
    connection.current_time = tot_time
    connection.currently_active = True
    connection.start_countdown()


def apply_script(protocol, connection, config):
    class CountdownConnection(connection):
        call = None
        current_time = 0
        currently_active = False
        public = True

        def secs_to_text(self, secs: int) -> str:
            hours = secs // 3600
            minutes = secs // 60 % 60
            secs = secs % 60
            text = ""

            # Sorry abt the mess down here but it works, so ¯\_(o_o)_/¯
            if hours > 0: text += f"{hours} hour{'s' if hours > 1 else ''} "
            if minutes > 0: text += f"{minutes} min{'s' if minutes > 1 else ''} "
            if secs > 0: text += f"{secs} sec{'s' if secs > 1 else ''} "

            return text

        def tick(self) -> None:
            self.current_time -= 1

            if self.current_time <= 0:
                self.on_countdow_end()
            
            elif self.current_time in COUNTDOWN_STEPS:
                self.send_msg(f"{self.secs_to_text(self.current_time)} left")
        
        def send_msg(self, msg: str):
            if self.public:
                self.protocol.broadcast_chat(msg)
            else:
                self.send_chat(msg)

        def on_countdow_end(self) -> None:
            self.send_msg(DEFAULT_END_MESSAGE)
            self.call.stop()

            self.currently_active = False

        def start_countdown(self) -> None:
            self.send_msg(f"Started a {'public' if self.public else 'private'} countdown of {self.secs_to_text(self.current_time)}")
            self.call = LoopingCall(self.tick)

            self.call.start(1.0)


    return protocol, CountdownConnection
