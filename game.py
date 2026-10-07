import pygame
import random

TILE = 40
COLS, ROWS = 20, 15
WALL, FLOOR, CHEST, KEY, TRAP = 0, 1, 2, 3, 4
SPEED = 3


def generate_world():
    grid = [[WALL] * COLS for _ in range(ROWS)]
    rooms = []

    for _ in range(8):
        w = random.randint(3, 6)
        h = random.randint(3, 5)
        x = random.randint(1, COLS - w - 1)
        y = random.randint(1, ROWS - h - 1)
        room = pygame.Rect(x, y, w, h)

        overlap = any(
            room.inflate(2, 2).colliderect(r)
            for r in rooms
        )

        if not overlap:
            rooms.append(room)

            for ry in range(y, y + h):
                for rx in range(x, x + w):
                    grid[ry][rx] = FLOOR

    # Connect rooms
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

    # Place chest and key
    if len(rooms) >= 2:
        cr, ck = rooms[-1], rooms[-2]
        grid[cr.centery][cr.centerx] = CHEST
        grid[ck.centery][ck.centerx] = KEY

    # Starting room
    start = rooms[0] if rooms else None

    # Place traps only inside intermediate rooms.
    # Never place them in the starting, key, or chest rooms.
    trap_cells = []

    if len(rooms) > 3:
        for room in rooms[1:-2]:
            for r in range(room.y, room.bottom):
                for c in range(room.x, room.right):
                    if grid[r][c] == FLOOR:
                        trap_cells.append((r, c))

    random.shuffle(trap_cells)

    for r, c in trap_cells[:5]:
        grid[r][c] = TRAP

    return grid, start


COLORS = {
    WALL: (60, 50, 70),
    FLOOR: (200, 190, 170),
    CHEST: (200, 160, 30),
    KEY: (220, 220, 60),
    TRAP: (170, 50, 50),
}


class Player:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, 28, 28)
        self.color = (60, 120, 220)
        self.has_key = False

    def move(self, keys, grid, rows, cols):
        dx = dy = 0

        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            dx = -SPEED
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            dx = SPEED
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            dy = -SPEED
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            dy = SPEED

        self._try_move(dx, 0, grid, rows, cols)
        self._try_move(0, dy, grid, rows, cols)

    def _try_move(self, dx, dy, grid, rows, cols):
        new = self.rect.move(dx, dy)

        for px, py in [
            (new.left, new.top),
            (new.right - 1, new.top),
            (new.left, new.bottom - 1),
            (new.right - 1, new.bottom - 1),
        ]:
            c, r = px // TILE, py // TILE

            if (
                not (0 <= r < rows and 0 <= c < cols)
                or grid[r][c] == WALL
            ):
                return

        self.rect = new

    def draw(self, screen):
        pygame.draw.ellipse(screen, self.color, self.rect)

        if self.has_key:
            pygame.draw.circle(
                screen,
                (220, 220, 60),
                (self.rect.right - 6, self.rect.top + 6),
                5,
            )


class Guard:
    def __init__(self, x, y, left_x, right_x):
        self.rect = pygame.Rect(x, y, 28, 28)
        self.left_x = left_x
        self.right_x = right_x
        self.direction = 1
        self.speed = 2

    def update(self):
        self.rect.x += self.speed * self.direction

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


WIDTH = COLS * TILE
HEIGHT = ROWS * TILE + 50
FPS = 60


class GameEngine:
    def __init__(self):
        pygame.init()

        self.screen = pygame.display.set_mode(
            (WIDTH, HEIGHT)
        )

        pygame.display.set_caption("Treasure Hunt")

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

        if start:
            sx = start.x * TILE + 6
            sy = start.y * TILE + 6
        else:
            sx = TILE + 6
            sy = TILE + 6

        # Store the starting position for traps and guard collisions.
        self.start_x = sx
        self.start_y = sy

        self.player = Player(sx, sy)

        # Find the chest.
        chest_position = None

        for r in range(ROWS):
            for c in range(COLS):
                if self.grid[r][c] == CHEST:
                    chest_position = (r, c)
                    break

            if chest_position is not None:
                break

        # Create a guard near the chest.
        if chest_position is not None:
            chest_r, chest_c = chest_position

            patrol_cells = []

            for c in range(COLS):
                if self.grid[chest_r][c] in (FLOOR, CHEST):
                    patrol_cells.append(c)

            # Do not place the guard directly on the chest.
            patrol_cells = [
                c for c in patrol_cells
                if c != chest_c
            ]

            if len(patrol_cells) >= 2:
                left_c = max(min(patrol_cells), chest_c - 2)
                right_c = min(max(patrol_cells), chest_c + 2)

                if left_c >= right_c:
                    left_c = max(0, chest_c - 1)
                    right_c = min(COLS - 1, chest_c + 1)

                left_x = left_c * TILE + 6
                right_x = right_c * TILE + TILE - 6
                guard_x = left_x
                guard_y = chest_r * TILE + 6

                self.guard = Guard(
                    guard_x,
                    guard_y,
                    left_x,
                    right_x,
                )
            else:
                guard_x = max(0, chest_c - 1) * TILE + 6
                guard_y = chest_r * TILE + 6

                self.guard = Guard(
                    guard_x,
                    guard_y,
                    guard_x,
                    guard_x + TILE,
                )

        else:
            self.guard = Guard(
                TILE + 6,
                TILE + 6,
                TILE + 6,
                TILE * 3,
            )

        self.won = False
        self.status = "Find the KEY, then the CHEST!"

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

    def update(self):
        if self.won:
            return

        # Update guard.
        self.guard.update()

        # Move player.
        keys = pygame.key.get_pressed()

        self.player.move(
            keys,
            self.grid,
            ROWS,
            COLS,
        )

        # Guard collision.
        if self.player.rect.colliderect(self.guard.rect):
            self.player.rect.topleft = (
                self.start_x,
                self.start_y,
            )

            self.status = "Guard caught you! Back to the start!"

        pr = self.player.rect.centery // TILE
        pc = self.player.rect.centerx // TILE

        if 0 <= pr < ROWS and 0 <= pc < COLS:
            cell = self.grid[pr][pc]

            # Trap.
            if cell == TRAP:
                self.player.rect.topleft = (
                    self.start_x,
                    self.start_y,
                )

                self.status = "Trap! Back to the start!"

            # Key.
            elif cell == KEY:
                self.player.has_key = True
                self.grid[pr][pc] = FLOOR
                self.status = "Got the key! Find the CHEST!"

            # Chest.
            elif cell == CHEST and self.player.has_key:
                self.won = True
                self.status = "Treasure found!"

    def draw_minimap(self):
        mini_tile = 7
        map_width = COLS * mini_tile
        map_height = ROWS * mini_tile
        margin = 12

        x0 = WIDTH - map_width - margin
        y0 = margin

        panel = pygame.Rect(
            x0 - 4,
            y0 - 4,
            map_width + 8,
            map_height + 8,
        )

        pygame.draw.rect(
            self.screen,
            (15, 15, 25),
            panel,
        )

        for r in range(ROWS):
            for c in range(COLS):
                cell = self.grid[r][c]

                if cell == WALL:
                    color = (45, 40, 55)
                else:
                    color = (205, 195, 175)

                rect = pygame.Rect(
                    x0 + c * mini_tile,
                    y0 + r * mini_tile,
                    mini_tile,
                    mini_tile,
                )

                pygame.draw.rect(
                    self.screen,
                    color,
                    rect,
                )

        # Player's current position.
        pr = self.player.rect.centery // TILE
        pc = self.player.rect.centerx // TILE

        if 0 <= pr < ROWS and 0 <= pc < COLS:
            player_rect = pygame.Rect(
                x0 + pc * mini_tile,
                y0 + pr * mini_tile,
                mini_tile,
                mini_tile,
            )

            pygame.draw.rect(
                self.screen,
                (60, 120, 220),
                player_rect,
            )

    def draw_inventory(self):
        # Empty inventory slot at the start.
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

        # Draw key icon after key collection.
        if self.player.has_key:
            pygame.draw.circle(
                self.screen,
                (255, 230, 50),
                (slot.centerx - 5, slot.centery - 5),
                6,
            )

            pygame.draw.line(
                self.screen,
                (255, 230, 50),
                (slot.centerx, slot.centery),
                (slot.centerx + 11, slot.centery + 11),
                4,
            )

            pygame.draw.line(
                self.screen,
                (255, 230, 50),
                (slot.centerx + 7, slot.centery + 7),
                (slot.centerx + 11, slot.centery + 3),
                3,
            )

    def draw(self):
        self.screen.fill((30, 25, 40))

        # Draw dungeon.
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

                if cell == KEY:
                    pygame.draw.circle(
                        self.screen,
                        (255, 240, 60),
                        (
                            c * TILE + TILE // 2,
                            r * TILE + TILE // 2,
                        ),
                        10,
                    )

                elif cell == CHEST:
                    pygame.draw.rect(
                        self.screen,
                        (180, 120, 20),
                        rect.inflate(-12, -12),
                        border_radius=4,
                    )

        # Draw guard and player.
        self.guard.draw(self.screen)
        self.player.draw(self.screen)

        # Draw mini-map.
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

        st = self.font.render(
            self.status + "  |  R=Restart",
            True,
            (200, 200, 200),
        )

        self.screen.blit(
            st,
            (8, ROWS * TILE + 13),
        )

        # Inventory.
        self.draw_inventory()

        # Victory screen.
        if self.won:
            ov = pygame.Surface(
                (WIDTH, ROWS * TILE),
                pygame.SRCALPHA,
            )

            ov.fill((0, 0, 0, 140))

            self.screen.blit(
                ov,
                (0, 0),
            )

            msg = self.big_font.render(
                "TREASURE FOUND!",
                True,
                (220, 180, 30),
            )

            sub = self.font.render(
                "Press R to Play Again",
                True,
                (180, 180, 180),
            )

            self.screen.blit(
                msg,
                (
                    WIDTH // 2 - msg.get_width() // 2,
                    ROWS * TILE // 2 - 30,
                ),
            )

            self.screen.blit(
                sub,
                (
                    WIDTH // 2 - sub.get_width() // 2,
                    ROWS * TILE // 2 + 20,
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
    engine = GameEngine()
    engine.run()
