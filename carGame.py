from piqueserver.commands import command
from pyspades.contained import SetColor, BlockAction
from pyspades.common import Vertex3, make_color
from pyspades.constants import BUILD_BLOCK, DESTROY_BLOCK
from twisted.internet.task import LoopingCall
from random import randint
from math import floor


@command("create_game")
def create_game(connection):
    if connection.protocol.has_display:
        return "The game is already created!"

    connection.protocol.init_new_game(connection.player_id)
    return "You created the game's board! Use \\del_game to remove it"

@command("del_game")
def delete_game(connection):
    connection.protocol.delete_game()

    return "Deleted the game!"

@command("join")
def start_game(connection):
    if not connection.protocol.has_display:
        return "The game has not been created yet. You need to create the game before joining a game."
    
    if connection.protocol.current_player_id != -1:
        if connection.protocol.current_player_id != connection.player_id:
            return f"The game is already taken by {connection.protocol.players[connection.protocol.current_player_id].name}!"
        else:
            return "You have already joined the game!"

    connection.protocol.join_player(connection.player_id)
    return "You joined the game !\nType \\start to start the game"

@command("leave")
def leave(connection):
    if not connection.protocol.has_display:
        return "The game has not been created yet"
    
    if connection.protocol.current_player_id != connection.player_id:
        return "You have not joined the game yet!"
    
    connection.protocol.leave_player()
    return "You have left the game!"

@command("start")
def start_game(connection):
    if connection.protocol.current_player_id != connection.player_id:
        return "You have not joined the game yet. You need to join the game before starting!"

    connection.protocol.start_game()
    return "Game will start soon. Get ready!"

class Display:
    def __init__(self, protocol, position, width = 10, height = 10):
        self.protocol = protocol
        self.position = position

        self.width = width
        self.height = height

        self.pixels = []
        self.world_blocks = []

    def init(self):
        self._generate_blank_display()
        self._pretty_colors()
        self.full_refresh()

    def delete(self):
        for x in range(self.width):
            for y in range(self.height):
                action = BlockAction()
                action.player_id = 32
                action.x = self.position[0] + x
                action.y = self.position[1]
                action.z = self.position[2] - y
                action.value = DESTROY_BLOCK

                self.protocol.broadcast_contained(action)
        
        self.fill((0, 0, 0))
    
    def _generate_blank_display(self):
        self.pixels = []
        self.world_blocks = []
        for x in range(self.width):
            layer = []
            for y in range(self.height):
                
                layer.append((0, 0, 0))

            self.pixels.append(layer.copy())
            self.world_blocks.append(layer.copy())
    
    def _pretty_colors(self):
        for x in range(self.width):
            for y in range(self.height):
                color = (
                    int((x / self.width) * 255),
                    int((y / self.height) * 255),
                    128
                )

                self.pixels[x][y] = color

    def _refresh_pixel(self, pixel_coords: tuple[int, int]):
        set_color = SetColor()
        set_color.value = make_color(*self.pixels[pixel_coords[0]][pixel_coords[1]])
        set_color.player_id = 32

        self.protocol.broadcast_contained(set_color)

        build_action = BlockAction()
        build_action.x = self.position[0] + pixel_coords[0]
        build_action.y = self.position[1]
        build_action.z = self.position[2] - pixel_coords[1]
        build_action.player_id = 32
        build_action.value = BUILD_BLOCK

        self.protocol.broadcast_contained(build_action)
    
    def refresh(self):
        for x in range(self.width):
            for y in range(self.height):
                if self.pixels[x][y] == self.world_blocks[x][y]:
                    continue

                self._refresh_pixel((x, y))
                self.world_blocks[x][y] = self.pixels[x][y]

    def full_refresh(self):
        for x in range(self.width):
            for y in range(self.height):
                self._refresh_pixel((x, y))
    
    def set_at(self, x_y, color):
        if x_y[0] < 0 or x_y[1] < 0 or x_y[0] >= self.width or x_y[1] >= self.height:
            return None

        self.pixels[x_y[0]][x_y[1]] = color
    
    def fill(self, color):
        for x in range(self.width):
            for y in range(self.height):
                self.set_at((x, y), color)
    
    def rect(self, rect, color):
        for x in range(rect[0], rect[0] + rect[2]):
            for y in range(rect[1], rect[1] + rect[3]):
                self.set_at((x, y), color)

def apply_script(protocol, connection, config):
    class CarGameProtocol(protocol):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

            self.has_display = False
            self.current_player_id = -1
            self.ticks = 0

            self.tick_call = LoopingCall(self.tick)

            self.display = None

        def init_new_game(self, player_id):
            self.position = self.players[player_id].world_object.position.get()
            self.ticks = 0

            self.display = Display(self, (self.position[0], self.position[1], self.position[2] - 2), width=31, height=40)
            self.display.init()
            # self.display.fill((255, 0, 255))

            self.has_display = True

            ## GAME ##
            self.current_lane = randint(0, 3)
            self.current_y = self.display.height // 2
            self.current_speed = 2
            self.dt = 1 / 30

            self.has_started = False
            self.anim_progress = 0

            self.cars = []

            self.moved_left = False
            self.moved_right = False

            self.tick_call.start(1 / 30)

        def delete_game(self):
            if not self.has_display:
                return None

            if self.tick_call.running:
                self.tick_call.stop()
            
            self.display.delete()
            self.has_display = False
            self.leave_player()
        
        def join_player(self, player_id):
            self.current_player_id = player_id

            self.build_block((self.position[0] + self.display.width // 2 + 1, self.position[1] + self.display.height, self.position[2] + 1), (255, 255, 255))
            self.build_block((self.position[0] + self.display.width // 2 - 1, self.position[1] + self.display.height, self.position[2] + 1), (255, 255, 255))
            self.build_block((self.position[0] + self.display.width // 2, self.position[1] + self.display.height + 1, self.position[2] + 1), (255, 255, 255))
            self.build_block((self.position[0] + self.display.width // 2, self.position[1] + self.display.height - 1, self.position[2] + 1), (255, 255, 255))

            self.build_block((self.position[0] + self.display.width // 2 + 1, self.position[1] + self.display.height, self.position[2] + 2), (255, 255, 255))
            self.build_block((self.position[0] + self.display.width // 2 - 1, self.position[1] + self.display.height, self.position[2] + 2), (255, 255, 255))
            self.build_block((self.position[0] + self.display.width // 2, self.position[1] + self.display.height + 1, self.position[2] + 2), (255, 255, 255))
            self.build_block((self.position[0] + self.display.width // 2, self.position[1] + self.display.height - 1, self.position[2] + 2), (255, 255, 255))
            
            self.set_player_position()
        
        def stop_game(self):
            self.has_started = False
            self.cars = []
        
        def leave_player(self):
            self.current_player_id = -1
            self.anim_progress = 0

            self.display._pretty_colors()
            self.stop_game()
        
        def start_game(self):
            self.has_started = True
        
        def set_player_position(self):
            player = self.players.get(self.current_player_id)
            
            player.set_location_safe((
                self.position[0] + self.display.width // 2,
                self.position[1] + self.display.height,
                self.position[2],
            ))

        def handle_player_movement(self):
            player = self.players.get(self.current_player_id)

            if player == None or not self.has_started:
                if player == None: self.current_player_id = -1
                return None
            
            if player.world_object.left:
                if not self.moved_left:
                    self.current_lane = max(self.current_lane - 1, 0)
                    self.moved_left = True
            else:
                self.moved_left = False

            if player.world_object.right:
                if not self.moved_right:
                    self.current_lane = min(self.current_lane + 1, 3)
                    self.moved_right = True
            else:
                self.moved_right = False
            
            if player.world_object.down:
                self.current_y = max(self.current_y - 1, 0)
            
            if player.world_object.up:
                self.current_y = min(self.current_y + 1, self.display.height - 2)
            
            for car in self.cars:
                if car[0] != self.current_lane:
                    continue

                if car[1] - 2 <= self.current_y and car[1] - 2 > self.current_y - 2:
                    self.leave_player()
        
        def draw_car(self, pos, color):
            car_x = (pos[0] * 7) + 4
            car_y = pos[1] + 1

            # Car body
            self.display.rect((car_x, car_y, 2, 3), color)

            # Tires
            self.display.set_at((car_x - 1, car_y), (0, 0, 0))
            self.display.set_at((car_x + 2, car_y), (0, 0, 0))
            self.display.set_at((car_x - 1, car_y + 2), (0, 0, 0))
            self.display.set_at((car_x + 2, car_y + 2), (0, 0, 0))
        
        def render_screen(self):
            road_clr = 90
            self.display.fill((road_clr, road_clr, road_clr))

            for x in range(5):
                for y in range(self.display.height - 2):
                    pos = (
                        (x * 7) + 1,
                        y + 1
                    )
                    color = road_clr

                    offset = (self.ticks * self.dt * self.current_speed) % 8
                    if ((y + floor(offset)) // 4) % 2 == 0:
                        color = 255

                    self.display.set_at(pos, (color,)*3)
            
            ## PLAYER ##
            self.draw_car((self.current_lane, self.current_y), (245, 19, 23))

            ## CARS ##
            for car in self.cars:
                self.draw_car((car[0], floor(car[1])), (60, 80, 240))
            
            ## ANIMATIONS ##
            if self.anim_progress > (self.display.width + self.display.height):
                return None

            for x in range(self.display.width):
                for y in range(self.display.height):
                    if (x + y) > self.anim_progress:
                        self.display.set_at((x, y), (0, 0, 0))

            if self.current_player_id != -1:
                self.anim_progress += 1

        def handle_cars(self):
            if not self.has_started:
                return None

            if self.ticks % 30 == 0:
                self.cars.append([
                    randint(0, 3),
                    self.display.height - 1
                ])

            dead_cars = []
            
            for car_idx, car in enumerate(self.cars):
                car[1] -= self.current_speed * self.dt

                if car[1] < -3:
                    dead_cars.append(car_idx)
            
            for car_idx in dead_cars:
                del self.cars[car_idx]
        
        def build_block(self, pos, color):
            set_color = SetColor()
            set_color.player_id = 32
            set_color.value = make_color(*color)
            self.broadcast_contained(set_color)

            action = BlockAction()
            action.player_id = 32
            action.value = BUILD_BLOCK
            action.x = pos[0]
            action.y = pos[1]
            action.z = pos[2]

            self.broadcast_contained(action)
        
        def tick(self):
            self.handle_player_movement()
            self.handle_cars()
            if self.current_player_id != -1:
                self.render_screen()

            self.display.refresh()

            self.ticks += 1

    return CarGameProtocol, connection