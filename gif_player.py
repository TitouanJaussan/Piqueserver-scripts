from piqueserver.commands import command
from pyspades.contained import BlockAction, SetColor
from pyspades.common import make_color
from twisted.internet.task import LoopingCall
from pyspades.constants import BUILD_BLOCK, DESTROY_BLOCK
from math import sqrt
from PIL import Image
import os

# Gif player by Gato
# To play a gif make a gifs directory in the parent directory of scripts
# Drop a .gif inside of the gifs directory and then do /gif <gif_name.gif> <gif tag> <playback speed> <scale reduction (2 means twice as small as original gif)> <axis ("x" or "y" or "z")>


GIF_SIZE_REDUCTION = 20
DEFAULT_PLAYBACK_SPEED = 0.1  # Render the next frame every 0.1 secs. Can be changed to any value
DEFAULT_AXIS = "x"
DEACTIVATION_RADIUS = 15  # Gifs won't update if there is no player closer than 15 blocks

@command("gif")
def gif(connection, file_name: str = "pedro.gif", gif_tag: str = "gif0", playback_speed: str = str(DEFAULT_PLAYBACK_SPEED), scale: str = str(GIF_SIZE_REDUCTION), axis: str = DEFAULT_AXIS) -> None:
    connection.load_gif("gifs/" + file_name, gif_tag, float(playback_speed), int(scale), axis.lower())

@command("dgif")
def delete_gif(connection, gif_tag: str = "gif0") -> None:
    connection.remove_gif(gif_tag)

@command("gif_pause")
def pause_gif(connection, gif_tag: str):
    connection.pause_gif(gif_tag)

class Gif:
    def __init__(self, file_path: str, connection, playback_speed: float = DEFAULT_PLAYBACK_SPEED, scale: int = GIF_SIZE_REDUCTION, axis: str = DEFAULT_AXIS) -> None:
        self.file_path = file_path
        self.width = 0
        self.height = 0
        self.connection = connection
        self.scale = scale
        self.axis = axis
        self.paused = False

        self.frames = []
        self.tot_frames = 0
        self.ticks = 0

        self.x, self.y, self.z = self.connection.get_location()
        self.load_gif_data()

        self.center_x, self.center_y, self.center_z = self.get_center()

        self.screen_buffer = [[(255, 0, 0) for y in range(self.height)] for x in range(self.width)]

        self.loop = LoopingCall(self.update)
        self.loop.start(playback_speed)

    def load_gif_data(self) -> None:
        base_path = os.path.dirname(os.path.abspath(__file__))
        os.chdir(base_path)
        os.chdir("..")

        gif = Image.open(self.file_path)
        current_frame_idx = 0

        while True:
            try:
                gif.seek(current_frame_idx)
                frame = gif.convert("RGB")

                pixels = frame.load()

                self.width, self.height = frame.size

                current_frame = [[(0, 0, 0) for y in range(self.height)] for x in range(self.width)]

                for x in range(0, self.width, self.scale):
                    for y in range(0, self.height, self.scale):
                        pixel = pixels[x, y]

                        current_frame[int(x / self.scale)][int(y / self.scale)] = (pixel[0], pixel[1], pixel[2])
                
                self.frames.append(current_frame)

                current_frame_idx += 1

            except EOFError:
                self.width = int(self.width / self.scale)
                self.height = int(self.height / self.scale)

                self.tot_frames = current_frame_idx
                self.connection.send_chat(f"Tot frames: {self.tot_frames}")
                break
        
        gif.close()
    
    def get_dist(self, x, y, z) -> float:
        return sqrt(
            (x - self.center_x)**2 +
            (y - self.center_y)**2 +
            (z - self.center_z)**2
        )
    
    def check_for_nearby_players(self) -> None:
        self.paused = True
        for player in self.connection.protocol.players.values():
            if not player.world_object: return None

            dist = self.get_dist(*player.world_object.position.get())

            if dist < DEACTIVATION_RADIUS:
                self.paused = False
                return None

    def update(self) -> None:
        self.ticks += 1
        self.check_for_nearby_players()

        if not self.paused:
            self.render_frame()
    
    def pixel_needs_to_update(self, pixel_x: int, pixel_y: int, target_color: tuple[int, int, int]) -> None:
        pixel = self.screen_buffer[pixel_x][pixel_y]
        color_diff = abs(pixel[0] - target_color[0])
        color_diff += abs(pixel[1] - target_color[1])
        color_diff += abs(pixel[2] - target_color[2])
        color_diff /= 3

        return color_diff > 50
    
    def screen_to_world(self, screen_x: int, screen_y: int) -> tuple[int, int, int]:
        if self.axis == "x":
            return (
                screen_x + self.x,
                self.y,
                self.z - self.height + screen_y
            )
        elif self.axis == "y":
            return (
                self.x,
                screen_x + self.y,
                self.z - self.height + screen_y
            )
        elif self.axis == "z":
            return (
                screen_y + self.x,
                screen_x + self.y,
                self.z
            )
    
    def get_center(self) -> tuple[float, float, float]:
        center_pos = ()

        if self.axis == "x":
            center_pos = (
                self.x + self.width / 2,
                self.y,
                self.z + self.height / 2
            )
        elif self.axis == "y":
            center_pos = (
                self.x,
                self.y + self.width / 2,
                self.z + self.height / 2
            )
        elif self.axis == "z":
            center_pos = (
                self.x + self.width / 2,
                self.y + self.height / 2,
                self.z
            )
        
        return center_pos
    
    def change_pixel(self, screen_x: int, screen_y: int, pixel_color: tuple[int, int, int]) -> None:
        pixel_x, pixel_y, pixel_z = self.screen_to_world(screen_x, screen_y)

        if self.pixel_needs_to_update(screen_x, screen_y, pixel_color):
            self.connection.set_block(pixel_x, pixel_y, pixel_z, pixel_color)
            self.screen_buffer[screen_x][screen_y] = pixel_color
    
    def render_frame(self) -> None:
        frame = self.frames[self.ticks % self.tot_frames]

        for x in range(self.width):
            for y in range(self.height):
                if (x + y)%2 == self.ticks % 2:
                    continue

                self.change_pixel(x, y, frame[x][self.height - y - 1])

    def clear_pixels(self) -> None:
        for x in range(self.width):
            for y in range(self.height):
                pixel_pos = self.screen_to_world(x, y)
                self.connection.del_block(*pixel_pos)

    def kill(self) -> None:
        self.clear_pixels()
        self.loop.stop()


def apply_script(protocol, connection, config):
    class GifConnection(connection):
        all_gifs: dict[str, Gif] = {}
    
        def load_gif(self, file_name: str, gif_tag: str, playback_speed: float, scale: int, axis: str) -> None:
            if self.all_gifs.get(gif_tag) != None:
                self.send_chat("This gif already exists. Delete it with /dgif to create a new one with the same gif tag")
                return None

            if not axis in ("x", "y", "z"):
                self.send_chat("Invalid axis for gif. Must be 'x', 'y' or 'z'")
                return None

            self.all_gifs[gif_tag] = Gif(file_name, self, playback_speed, scale, axis)
            self.send_chat("Loaded gif !")
        
        def remove_gif(self, gif_tag: str) -> None:
            if self.all_gifs.get(gif_tag) == None:
                self.send_chat(f"No gif found with the following tag: '{gif_tag}'")
                return None
            
            _gif = self.all_gifs[gif_tag]
            _gif.kill()
            del self.all_gifs[gif_tag]
            
            self.send_chat(f"Succesfully removed gif")
        
        def pause_gif(self, gif_tag: str) -> None:
            _gif = self.all_gifs.get(gif_tag)

            if _gif == None:
                self.send_chat(f"No gif found with the following tag: {gif_tag}")
                return None
            
            _gif.paused = not _gif.paused
        
        def set_block(self, block_x: int, block_y: int, block_z: int, color: tuple[int, int, int]) -> None:
            set_color = SetColor()
            set_color.value = make_color(*color)
            set_color.player_id = 32

            self.protocol.broadcast_contained(set_color)


            block_action = BlockAction()
            block_action.x = block_x
            block_action.y = block_y
            block_action.z = block_z
            block_action.value = BUILD_BLOCK
            block_action.player_id = 32

            self.protocol.broadcast_contained(block_action)
        
        def del_block(self, block_x: int, block_y: int, block_z: int) -> None:
            block_action = BlockAction()
            block_action.x = block_x
            block_action.y = block_y
            block_action.z = block_z
            block_action.value = DESTROY_BLOCK
            block_action.player_id = 32

            self.protocol.broadcast_contained(block_action)

    return protocol, GifConnection