import pygame
import random
from collections import deque

TILE = 40
COLS, ROWS = 20, 15
WALL, FLOOR, CHEST, KEY, TRAP = 0, 1, 2, 3, 4
SPEED = 3
WIDTH = COLS * TILE
HEIGHT = ROWS * TILE + 50
FPS = 60

COLORS = {
    WALL: (60, 50, 70),
    FLOOR: (200, 190, 170),
    CHEST: (200, 160, 30),
    KEY: (220, 220, 60),
    TRAP: (170, 50, 50),
}


def find_safe_path(grid, start_pos, target_pos):
    """Find one wall-free tile path between two (column, row) positions."""
    if start_pos is None or target_pos is None:
        return set()

    start = (start_pos[1], start_pos[0])
    target = (target_pos[1], target_pos[0])

    queue = deque([start])
    previous = {start: None}

    while queue:
        r, c = queue.popleft()

        if (r, c) == target:
            path = set()
            current = (r, c)

            while current is not None:
                path.add(current)
                current = previous[current]

            return path

        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc

            if not (0 <= nr < ROWS and 0 <= nc < COLS):
                continue

            if grid[nr][nc] == WALL:
                continue

            if (nr, nc) in previous:
                continue

            previous[(nr, nc)] = (r, c)
            queue.append((nr, nc))

    return set()


def build_fallback_world():
    """Build a guaranteed connected five-room dungeon if random generation is insufficient."""
    grid = [[WALL] * COLS for _ in range(ROWS)]

    rooms = [
        pygame.Rect(1, 2, 4, 4),     # Start
        pygame.Rect(6, 2, 4, 4),     # Trap room
        pygame.Rect(11, 2, 4, 4),    # Key
        pygame.Rect(11, 8, 4, 4),    # Trap room
        pygame.Rect(16, 8, 3, 4),    # Chest
    ]

    for room in rooms:
        for r in range(room.y, room.bottom):
            for c in range(room.x, room.right):
                grid[r][c] = FLOOR

    # Connect rooms with one-tile corridors.
    for c in range(rooms[0].centerx, rooms[1].centerx + 1):
        grid[rooms[0].centery][c] = FLOOR

    for c in range(rooms[1].centerx, rooms[2].centerx + 1):
        grid[rooms[1].centery][c] = FLOOR

    for r in range(rooms[2].centery, rooms[3].centery + 1):
        grid[r][rooms[2].centerx] = FLOOR

    for c in range(rooms[3].centerx, rooms[4].centerx + 1):
        grid[rooms[3].centery][c] = FLOOR

    return grid, rooms


def generate_world():
    grid = [[WALL] * COLS for _ in range(ROWS)]
    rooms = []

    # Generate several non-overlapping rooms.
    attempts = 0

    while len(rooms) < 8 and attempts < 200:
        attempts += 1

        w = random.randint(3, 6)
        h = random.randint(3, 5)

        x = random.randint(1, COLS - w - 1)
        y = random.randint(1, ROWS - h - 1)

        room = pygame.Rect(x, y, w, h)

        if any(
            room.inflate(2, 2).colliderect(existing)
            for existing in rooms
        ):
            continue

        rooms.append(room)

        for r in range(room.y, room.bottom):
            for c in range(room.x, room.right):
                grid[r][c] = FLOOR

    # Always have enough rooms for visible traps without making
    # the route impossible.
    if len(rooms) < 5:
        grid, rooms = build_fallback_world()

    # Connect consecutive rooms.
    for i in range(len(rooms) - 1):
        ax, ay = rooms[i].centerx, rooms[i].centery
        bx, by = rooms[i + 1].centerx, rooms[i + 1].centery

        cx = ax

        while cx != bx:
            grid[ay][cx] = FLOOR
            cx += 1 if bx > cx else -1

        cy = ay

        while cy != by:
            grid[cy][bx] = FLOOR
            cy += 1 if by > cy else -1

    start_room = rooms[0]
    key_room = rooms[-2]
    chest_room = rooms[-1]

    start_pos = (
        start_room.centerx,
        start_room.centery,
    )

    key_pos = (
        key_room.centerx,
        key_room.centery,
    )

    chest_pos = (
        chest_room.centerx,
        chest_room.centery,
    )

    # Place key and chest.
    grid[key_pos[1]][key_pos[0]] = KEY
    grid[chest_pos[1]][chest_pos[0]] = CHEST

    # Reserve safe routes for both stages:
    # START -> KEY
    # KEY -> CHEST
    safe_cells = set()

    safe_cells.update(
        find_safe_path(
            grid,
            start_pos,
            key_pos,
        )
    )

    safe_cells.update(
        find_safe_path(
            grid,
            key_pos,
            chest_pos,
        )
    )

    # Never put traps in the start, key, or chest rooms.
    for room in (
        start_room,
        key_room,
        chest_room,
    ):
        for r in range(room.y, room.bottom):
            for c in range(room.x, room.right):
                safe_cells.add((r, c))

    # IMPORTANT:
    # Traps are placed ONLY inside intermediate rooms.
    # This prevents traps from covering the connecting corridors.
    trap_candidates = []

    intermediate_rooms = rooms[1:-2]

    for room in intermediate_rooms:
        for r in range(room.y, room.bottom):
            for c in range(room.x, room.right):

                if grid[r][c] != FLOOR:
                    continue

                if (r, c) in safe_cells:
                    continue

                trap_candidates.append((r, c))

    random.shuffle(trap_candidates)

    # Place up to five traps.
    # Never sacrifice a corridor just to reach five traps.
    for r, c in trap_candidates[:5]:
        grid[r][c] = TRAP

    return grid, start_room


class Player:
    def __init__(self, x, y):
        self.rect = pygame.Rect(
            x,
            y,
            28,
            28,
        )

        self.color = (60, 120, 220)
        self.has_key = False

    def move(self, keys, grid):
        dx = 0
        dy = 0

        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            dx = -SPEED

        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            dx = SPEED

        if keys[pygame.K_UP] or keys[pygame.K_w]:
            dy = -SPEED

        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            dy = SPEED

        self._try_move(
            dx,
            0,
            grid,
        )

        self._try_move(
            0,
            dy,
            grid,
        )

    def _try_move(self, dx, dy, grid):
        new_rect = self.rect.move(
            dx,
            dy,
        )

        corners = (
            (
                new_rect.left,
                new_rect.top,
            ),
            (
                new_rect.right - 1,
                new_rect.top,
            ),
            (
                new_rect.left,
                new_rect.bottom - 1,
            ),
            (
                new_rect.right - 1,
                new_rect.bottom - 1,
            ),
        )

        for px, py in corners:
            c = px // TILE
            r = py // TILE

            if not (
                0 <= r < ROWS
                and 0 <= c < COLS
            ):
                return

            if grid[r][c] == WALL:
                return

        self.rect = new_rect

    def draw(self, screen):
        pygame.draw.ellipse(
            screen,
            self.color,
            self.rect,
        )


class Guard:
    def __init__(
        self,
        x,
        y,
        left_x,
        right_x,
    ):
        self.rect = pygame.Rect(
            x,
            y,
            28,
            28,
        )

        self.left_x = left_x
        self.right_x = right_x

        self.direction = 1
        self.speed = 2

    def update(self):
        self.rect.x += (
            self.speed * self.direction
        )

        if self.rect.left <= self.left_x:
            self.rect.left = self.left_x
            self.direction = 1

        elif self.rect.right >= self.right_x:
            self.rect.right = self.right_x
            self.direction = -1

    def draw(self, screen):
        pygame.draw.rect(
            screen,
            (200, 60, 60),
            self.rect,
            border_radius=5,
        )


class GameEngine:
    def __init__(self):
        pygame.init()

        self.screen = pygame.display.set_mode(
            (WIDTH, HEIGHT)
        )

        pygame.display.set_caption(
            "Treasure Hunt"
        )

        self.clock = pygame.time.Clock()

        self.font = pygame.font.SysFont(
            "monospace",
            24,
        )

        self.big_font = pygame.font.SysFont(
            "monospace",
            40,
            bold=True,
        )

        self.reset()

    def reset(self):
        self.grid, start = generate_world()

        self.start_x = (
            start.x * TILE + 6
        )

        self.start_y = (
            start.y * TILE + 6
        )

        self.player = Player(
            self.start_x,
            self.start_y,
        )

        self.won = False

        self.status = (
            "Find the KEY, then the CHEST!"
        )

        # Find the chest.
        chest_position = None

        for r in range(ROWS):
            for c in range(COLS):

                if self.grid[r][c] == CHEST:
                    chest_position = (
                        r,
                        c,
                    )
                    break

            if chest_position is not None:
                break

        # Task 2:
        # Patrol guard inside the chest room row.
        if chest_position is not None:
            chest_r, chest_c = chest_position

            room_left = None
            room_right = None

            for c in range(COLS):

                if self.grid[chest_r][c] in (
                    FLOOR,
                    CHEST,
                ):

                    if room_left is None:
                        room_left = c

                    room_right = c

            if (
                room_left is not None
                and room_right is not None
            ):

                left_c = room_left
                right_c = room_right

                if left_c == right_c:
                    left_c = max(
                        0,
                        chest_c - 1,
                    )

                    right_c = min(
                        COLS - 1,
                        chest_c + 1,
                    )

                if left_c != chest_c:
                    start_c = left_c
                else:
                    start_c = min(
                        chest_c + 1,
                        right_c,
                    )

                left_x = (
                    left_c * TILE + 6
                )

                right_x = (
                    right_c * TILE
                    + TILE
                    - 6
                )

                self.guard = Guard(
                    start_c * TILE + 6,
                    chest_r * TILE + 6,
                    left_x,
                    right_x,
                )

            else:
                gx = (
                    max(
                        0,
                        chest_c - 1,
                    )
                    * TILE
                    + 6
                )

                self.guard = Guard(
                    gx,
                    chest_r * TILE + 6,
                    gx,
                    gx + TILE,
                )

        else:
            self.guard = Guard(
                TILE + 6,
                TILE + 6,
                TILE + 6,
                TILE * 3,
            )

    def handle_events(self):
        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                return False

            if (
                event.type == pygame.KEYDOWN
                and event.key == pygame.K_r
            ):
                self.reset()

        return True

    def reset_player(self, message):
        self.player.rect.topleft = (
            self.start_x,
            self.start_y,
        )

        self.status = message

    def update(self):
        if self.won:
            return

        # Task 2: guard patrol.
        self.guard.update()

        keys = pygame.key.get_pressed()

        self.player.move(
            keys,
            self.grid,
        )

        # Task 2: guard collision.
        if self.player.rect.colliderect(
            self.guard.rect
        ):
            self.reset_player(
                "Guard caught you! Back to the start!"
            )
            return

        pr = (
            self.player.rect.centery
            // TILE
        )

        pc = (
            self.player.rect.centerx
            // TILE
        )

        if not (
            0 <= pr < ROWS
            and 0 <= pc < COLS
        ):
            return

        cell = self.grid[pr][pc]

        # Task 1: trap collision.
        if cell == TRAP:
            self.reset_player(
                "Trap! Back to the start!"
            )
            return

        # Task 4: key pickup.
        if cell == KEY:
            self.player.has_key = True

            self.grid[pr][pc] = FLOOR

            self.status = (
                "Got the key! Find the CHEST!"
            )

            return

        # Chest only works after key collection.
        if (
            cell == CHEST
            and self.player.has_key
        ):
            self.won = True

            self.status = (
                "Treasure found!"
            )

    def draw_minimap(self):
        # Task 3:
        # Mini-map in the top-right corner.
        mini_tile = 7

        map_width = (
            COLS * mini_tile
        )

        map_height = (
            ROWS * mini_tile
        )

        margin = 12

        x0 = (
            WIDTH
            - map_width
            - margin
        )

        y0 = margin

        panel = pygame.Rect(
            x0 - 5,
            y0 - 5,
            map_width + 10,
            map_height + 10,
        )

        pygame.draw.rect(
            self.screen,
            (15, 15, 25),
            panel,
        )

        for r in range(ROWS):
            for c in range(COLS):

                cell = self.grid[r][c]

                tile_color = (
                    (45, 40, 55)
                    if cell == WALL
                    else (205, 195, 175)
                )

                rect = pygame.Rect(
                    x0 + c * mini_tile,
                    y0 + r * mini_tile,
                    mini_tile,
                    mini_tile,
                )

                pygame.draw.rect(
                    self.screen,
                    tile_color,
                    rect,
                )

        pr = (
            self.player.rect.centery
            // TILE
        )

        pc = (
            self.player.rect.centerx
            // TILE
        )

        if (
            0 <= pr < ROWS
            and 0 <= pc < COLS
        ):

            rect = pygame.Rect(
                x0 + pc * mini_tile,
                y0 + pr * mini_tile,
                mini_tile,
                mini_tile,
            )

            pygame.draw.rect(
                self.screen,
                (60, 120, 220),
                rect,
            )

    def draw_inventory(self):
        # Task 4:
        # Empty slot until key is collected.
        slot = pygame.Rect(
            WIDTH - 60,
            ROWS * TILE + 5,
            40,
            40,
        )

        pygame.draw.rect(
            self.screen,
            (60, 60, 75),
            slot,
        )

        pygame.draw.rect(
            self.screen,
            (180, 180, 190),
            slot,
            2,
        )

        if not self.player.has_key:
            return

        # Simple key icon.
        key_color = (
            255,
            230,
            50,
        )

        pygame.draw.circle(
            self.screen,
            key_color,
            (
                slot.centerx - 7,
                slot.centery - 7,
            ),
            6,
        )

        pygame.draw.line(
            self.screen,
            key_color,
            (
                slot.centerx - 2,
                slot.centery - 2,
            ),
            (
                slot.centerx + 12,
                slot.centery + 12,
            ),
            4,
        )

        pygame.draw.line(
            self.screen,
            key_color,
            (
                slot.centerx + 7,
                slot.centery + 7,
            ),
            (
                slot.centerx + 12,
                slot.centery + 3,
            ),
            3,
        )

    def draw(self):
        self.screen.fill(
            (30, 25, 40)
        )

        # Dungeon.
        for r in range(ROWS):
            for c in range(COLS):

                cell = self.grid[r][c]

                rect = pygame.Rect(
                    c * TILE,
                    r * TILE,
                    TILE,
                    TILE,
                )

                pygame.draw.rect(
                    self.screen,
                    COLORS[cell],
                    rect,
                )

                # Key.
                if cell == KEY:
                    pygame.draw.circle(
                        self.screen,
                        (255, 240, 60),
                        (
                            c * TILE
                            + TILE // 2,
                            r * TILE
                            + TILE // 2,
                        ),
                        10,
                    )

                # Chest.
                elif cell == CHEST:
                    pygame.draw.rect(
                        self.screen,
                        (180, 120, 20),
                        rect.inflate(
                            -12,
                            -12,
                        ),
                        border_radius=4,
                    )

                # Trap.
                elif cell == TRAP:
                    # Make traps visually obvious.
                    pygame.draw.line(
                        self.screen,
                        (80, 20, 20),
                        (
                            c * TILE + 8,
                            r * TILE + 8,
                        ),
                        (
                            c * TILE
                            + TILE
                            - 8,
                            r * TILE
                            + TILE
                            - 8,
                        ),
                        3,
                    )

                    pygame.draw.line(
                        self.screen,
                        (80, 20, 20),
                        (
                            c * TILE
                            + TILE
                            - 8,
                            r * TILE + 8,
                        ),
                        (
                            c * TILE + 8,
                            r * TILE
                            + TILE
                            - 8,
                        ),
                        3,
                    )

        # Guard.
        self.guard.draw(
            self.screen
        )

        # Player.
        self.player.draw(
            self.screen
        )

        # Task 3: mini-map.
        self.draw_minimap()

        # HUD.
        hud = pygame.Rect(
            0,
            ROWS * TILE,
            WIDTH,
            50,
        )

        pygame.draw.rect(
            self.screen,
            (20, 20, 35),
            hud,
        )

        status_surface = self.font.render(
            self.status
            + "  |  R=Restart",
            True,
            (200, 200, 200),
        )

        self.screen.blit(
            status_surface,
            (
                8,
                ROWS * TILE + 13,
            ),
        )

        # Task 4: inventory.
        self.draw_inventory()

        # Victory screen.
        if self.won:
            overlay = pygame.Surface(
                (
                    WIDTH,
                    ROWS * TILE,
                ),
                pygame.SRCALPHA,
            )

            overlay.fill(
                (0, 0, 0, 140)
            )

            self.screen.blit(
                overlay,
                (0, 0),
            )

            message = self.big_font.render(
                "TREASURE FOUND!",
                True,
                (220, 180, 30),
            )

            sub_message = self.font.render(
                "Press R to Play Again",
                True,
                (180, 180, 180),
            )

            self.screen.blit(
                message,
                (
                    WIDTH // 2
                    - message.get_width() // 2,
                    ROWS * TILE // 2
                    - 30,
                ),
            )

            self.screen.blit(
                sub_message,
                (
                    WIDTH // 2
                    - sub_message.get_width() // 2,
                    ROWS * TILE // 2
                    + 20,
                ),
            )

        pygame.display.flip()

    def run(self):
        running = True

        while running:
            running = self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(FPS)

        pygame.quit()


if __name__ == "__main__":
    GameEngine().run()