from pyspades.contained import SetColor, BlockAction
from pyspades.common import Vertex3, make_color
from pyspades.constants import BUILD_BLOCK, DESTROY_BLOCK
from piqueserver.commands import command
from twisted.internet.task import LoopingCall
from random import randint, choice


THE_T = [
    ((1, 0), (0, -1), (1, -1), (2, -1)),
    ((1, 0), (1, -2), (1, -1), (2, -1)),
    ((1, -2), (0, -1), (1, -1), (2, -1)),
    ((1, 0), (0, -1), (1, -1), (1, -2)),
    (153, 0, 255)
]

THE_STICK = [
    ((0, -1), (1, -1), (2, -1), (3, -1)),
    ((2, 0), (2, -1), (2, -2), (2, -3)),
    ((0, -2), (1, -2), (2, -2), (3, -2)),
    ((1, 0), (1, -1), (1, -2), (1, -3)),
    (0, 255, 255)
]

THE_L_LEFT = [
    ((0, 0), (0, -1), (1, -1), (2, -1)),
    ((1, 0), (2, 0), (1, -1), (1, -2)),
    ((0, -1), (1, -1), (2, -1), (2, -2)),
    ((1, 0), (1, -1), (1, -2), (0, -2)),
    (0, 0, 255)
]

THE_L_RIGHT = [
    ((0, -1), (1, -1), (2, -1), (2, 0)),
    ((1, 0), (1, -1), (1, -2), (2, -2)),
    ((0, -2), (0, -1), (1, -1), (2, -1)),
    ((0, 0), (1, 0), (1, -1), (1, -2)),
    (255, 170, 0)
]

THE_SQUARE = [
    ((0, 0), (1, 0), (1, -1), (0, -1)),
    ((0, 0), (1, 0), (1, -1), (0, -1)),
    ((0, 0), (1, 0), (1, -1), (0, -1)),
    ((0, 0), (1, 0), (1, -1), (0, -1)),
    (255, 255, 0)
]

THE_DOG_LEFT = [
    ((0, -1), (1, 0), (1, -1), (2, 0)),
    ((1, 0), (1, -1), (2, -1), (2, -2)),
    ((0, -2), (1, -2), (1, -1), (2, -1)),
    ((0, 0), (0, -1), (1, -1), (1, -2)),
    (0, 255, 0)
]

THE_DOG_RIGHT = [
    ((0, 0), (1, 0), (1, -1), (2, -1)),
    ((1, -2), (1, -1), (2, -1), (2, 0)),
    ((0, -1), (1, -1), (1, -2), (2, -2)),
    ((0, -2), (0, -1), (1, -1), (1, 0)),
    (255, 0, 0)
]

ALL_TETROS = [
    THE_T, THE_STICK, THE_L_LEFT, THE_L_RIGHT, THE_SQUARE, THE_DOG_LEFT, THE_DOG_RIGHT
]

SCORE_SINGLE = 100
SCORE_DOUBLE = 300
SCORE_TRIPLE = 500
SCORE_TETRIS = 800


class Tetromino:
    def __init__(self,
                rotA_points: list[tuple[int, int]],
                rotB_points: list[tuple[int, int]],
                rotC_points: list[tuple[int, int]],
                rotD_points: list[tuple[int, int]], color: tuple[int, int, int], connection):

                self.rotA_points = rotA_points
                self.rotB_points = rotB_points
                self.rotC_points = rotC_points
                self.rotD_points = rotD_points

                self.current_rot = 0
                self.pos_x = connection.BOARD_W // 2
                self.pos_y = connection.BOARD_H - 1

                self.color = color
    
    def get_offsets(self) -> list[tuple[int, int]]:
        if self.current_rot == 0: return self.rotA_points
        if self.current_rot == 1: return self.rotB_points
        if self.current_rot == 2: return self.rotC_points
        if self.current_rot == 3: return self.rotD_points
    
    def rotate(self, _dir: int) -> None:
        self.current_rot = (self.current_rot + _dir) % 4

@command("left")
def left(connection, *args):
    connection.move_left()

@command("right")
def right(connection, *args):
    connection.move_right()

@command("up")
def up(connection, *args):
    connection.rotate_piece()

@command("down")
def down(connection, *args):
    connection.move_down()

@command("tetris")
def tetris(connection, *args):
    x, y, z = connection.get_location()
    connection.create_tetris(x + 1, y, z)

def apply_script(protocol, connection, config):
    class TetrisConnection(connection):
        start_position = None
        block_placed = False

        SCREEN_W = 10
        SCREEN_H = 24

        BOARD_W = 10
        BOARD_H = 24
        screen_pixels = []
        world_pixels = []
        board = []
        score = 0

        current_piece = None

        def on_spawn(self, pos) -> None:
            self.send_chat("Generated screen pixels")
            self.screen_pixels = [[(0, 0, 0) for y in range(self.SCREEN_H)] for x in range(self.SCREEN_W)]
            self.world_pixels = [[(255, 255, 255) for y in range(self.SCREEN_H)] for x in range(self.SCREEN_W)]
            self.board = [[(0, 0, 0) for y in range(self.BOARD_H)] for x in range(self.BOARD_W)]

            return connection.on_spawn(self, pos)
        
        def create_piece(self, piece: Tetromino) -> None:
            self.current_piece = piece

        def rotate_piece(self) -> None:
            if self.current_piece != None:
                self.current_piece.rotate(1)
                if not self.is_dir_safe(0, 0):
                    self.current_piece.rotate(-1)

        def create_tetris(self, x: int, y: int, z: int) -> None:
            if self.block_placed:
                return None

            self.start_position = Vertex3()
            self.start_position.x = x
            self.start_position.y = y
            self.start_position.z = z

            self.block_placed = True
            self.ticks = 0

            self.create_piece(Tetromino(*choice(ALL_TETROS), self))

            self.loop = LoopingCall(self.refresh_screen)
            FPS = 20
            self.loop.start(1 / FPS)

        def is_out_of_board(self, x: int, y: int) -> bool:
            return (x < 0 or y < 0 or x > self.BOARD_W - 1 or y > self.BOARD_H - 1)

        def is_dir_safe(self, x: int, y: int) -> bool:
            for offset in self.current_piece.get_offsets():
                board_x = self.current_piece.pos_x + offset[0] + x
                board_y = self.current_piece.pos_y + offset[1] + y

                if self.is_out_of_board(board_x, board_y):
                    return False
                
                if self.board[board_x][board_y] != (0, 0, 0):
                    return False

            
            return True
        
        def move_left(self) -> bool:
            if self.is_dir_safe(-1, 0):
                self.current_piece.pos_x -= 1
                return True
            return False
        
        def move_right(self) -> bool:
            if self.is_dir_safe(1, 0):
                self.current_piece.pos_x += 1
                return True
            return False
            
        def move_down(self) -> bool:
            if self.is_dir_safe(0, -1):
                self.current_piece.pos_y -= 1
                return True
            return False
        
        def game_tick(self) -> None:
            self.ticks += 1

            if self.ticks % 10 == 0:
                if not self.move_down():
                    self.lock_current_piece()
                    self.create_piece(Tetromino(*choice(ALL_TETROS), self))
        
        def lock_current_piece(self) -> None:
            for offset in self.current_piece.get_offsets():
                self.board[self.current_piece.pos_x + offset[0]][self.current_piece.pos_y + offset[1]] = self.current_piece.color

                if offset[1] + self.current_piece.pos_y >= (self.BOARD_H - 1):
                    self.end_game()
        
        def end_game(self) -> None:
            self.free_board()
            self.send_chat(f"Game finished. Score: {self.score} !")
            self.score = 0
        
        def free_board(self) -> None:
            for x in range(self.BOARD_W):
                for y in range(self.BOARD_H):
                    self.board[x][y] = (0, 0, 0)
        
        def pixel_in_current_piece(self, pixel_x: int, pixel_y: int) -> bool:
            for offset in self.current_piece.get_offsets():
                if (pixel_x, pixel_y) == (offset[0] + self.current_piece.pos_x, offset[1] + self.current_piece.pos_y):
                    return True
            
            return False
        
        def update_screen(self) -> None:
            for x in range(self.SCREEN_W):
                for y in range(self.SCREEN_H):
                    self.screen_pixels[x][y] = self.board[x][y]

                    # Piece
                    if self.pixel_in_current_piece(x, y):
                        self.screen_pixels[x][y] = self.current_piece.color
        
        def remove_row(self, row: int) -> None:
            for y in range(row, self.BOARD_H):
                for x in range(0, self.BOARD_W):
                    if not self.is_out_of_board(x, y + 1):
                        self.board[x][y] = self.board[x][y + 1]
                    else:
                        self.board[x][y] = (0, 0, 0)
        
        def update_board(self) -> None:
            tot_removed_rows = 0
            for y in range(self.BOARD_H - 1, -1, -1):
                tot_empty = 0
                for x in range(0, self.BOARD_W):
                    if self.board[x][y] == (0, 0, 0):
                        tot_empty += 1

                if tot_empty == 0:
                    self.remove_row(y)
                    tot_removed_rows += 1
            
            if tot_removed_rows == 1: self.score += SCORE_SINGLE
            if tot_removed_rows == 2: self.score += SCORE_DOUBLE
            if tot_removed_rows == 3: self.score += SCORE_TRIPLE
            if tot_removed_rows == 4: self.score += SCORE_TETRIS

        def refresh_screen(self) -> None:
            self.game_tick()
            self.update_board()
            self.update_screen()
            if self.start_position == None:
                return None
            
            for x in range(self.SCREEN_W):
                for y in range(self.SCREEN_H):
                    pixel = self.screen_pixels[x][y]

                    if self.world_pixels[x][y] == self.screen_pixels[x][y]:
                        continue
                    
                    pixel_x = self.start_position.x + x
                    pixel_y = self.start_position.y
                    pixel_z = self.start_position.z - y
                    
                    set_color = SetColor()
                    set_color.value = make_color(*pixel)
                    set_color.player_id = 32

                    self.world_pixels[x][y] = self.screen_pixels[x][y]

                    self.protocol.broadcast_contained(set_color, save=True)

                    build = BlockAction()
                    build.x = pixel_x
                    build.y = pixel_y
                    build.z = pixel_z
                    build.player_id = 32
                    build.value = BUILD_BLOCK

                    self.protocol.broadcast_contained(build, save=True)
            
    return protocol, TetrisConnection