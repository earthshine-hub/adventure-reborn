import asyncio
import array
import pygame
import sys

# ── Constants ────────────────────────────────────────────────────────────────
SCREEN_W, SCREEN_H = 480, 360
TILE = 32
HUD_TOP = 36
HUD_BOT = 36
COLS = SCREEN_W // TILE                    # 20
ROWS = (SCREEN_H - HUD_TOP - HUD_BOT) // TILE  # 9  (36 HUD top + 36 inv bottom = 72px)
PLAY_TOP = HUD_TOP                         # y where play area starts
PLAY_H   = ROWS * TILE                     # 288
FPS = 60
PLAYER_SPEED = 3

# Colours
BLACK   = (0, 0, 0)
WHITE   = (255, 255, 255)
GRAY    = (80, 80, 80)
DGRAY   = (40, 40, 40)
RED     = (200, 40, 40)
GREEN   = (50, 180, 50)
DGREEN  = (30, 100, 30)
BLUE    = (60, 100, 200)
LBLUE   = (120, 160, 220)
YELLOW  = (220, 200, 40)
BROWN   = (120, 80, 40)
DBROWN  = (80, 50, 20)
PURPLE  = (130, 50, 180)
ORANGE  = (220, 120, 30)
TEAL    = (30, 160, 140)

# Zone floor / wall colours
ZONE_COLORS = {
    "overworld": {"floor": (60, 120, 50),  "wall": (30, 70, 25),  "name_col": (180, 255, 120)},
    "dungeon":   {"floor": (50, 50, 60),   "wall": (25, 25, 35),  "name_col": (160, 140, 220)},
    "castle":    {"floor": (100, 85, 65),  "wall": (55, 40, 25),  "name_col": (255, 210, 100)},
}

# Door direction vectors
DIR_OFFSET = {"right": (1, 0), "left": (-1, 0), "up": (0, -1), "down": (0, 1)}
OPPOSITE   = {"right": "left", "left": "right", "up": "down", "down": "up"}

# Key colours
KEY_COLORS = {"red": (220, 40, 40), "yellow": (220, 200, 40), "blue": (60, 100, 220)}


# ── Tile types ───────────────────────────────────────────────────────────────
WALL  = 0
FLOOR = 1


# ── Room definition ──────────────────────────────────────────────────────────
class Room:
    def __init__(self, rid, name, zone, connections, locked=None):
        """
        rid         : int
        name        : str
        zone        : "overworld" | "dungeon" | "castle"
        connections : dict  e.g. {"right": 1, "down": 5}
        locked      : dict  e.g. {"right": "red"}  — door in that direction needs key
        """
        self.rid = rid
        self.name = name
        self.zone = zone
        self.connections = connections          # dir -> room_id
        self.locked = locked or {}              # dir -> key_color
        self.tiles = self._build_tiles()

    # ------------------------------------------------------------------
    def _build_tiles(self):
        tiles = [[FLOOR] * COLS for _ in range(ROWS)]
        # Border walls
        for c in range(COLS):
            tiles[0][c] = WALL
            tiles[ROWS - 1][c] = WALL
        for r in range(ROWS):
            tiles[r][0] = WALL
            tiles[r][COLS - 1] = WALL

        # Door openings (3 tiles wide, centred)
        def open_h(row, col_center):
            for dc in (-1, 0, 1):
                tiles[row][col_center + dc] = FLOOR

        def open_v(col, row_center):
            for dr in (-1, 0, 1):
                tiles[row_center + dr][col] = FLOOR

        mid_c = COLS // 2
        mid_r = ROWS // 2
        if "up"    in self.connections: open_h(0,        mid_c)
        if "down"  in self.connections: open_h(ROWS - 1, mid_c)
        if "left"  in self.connections: open_v(0,        mid_r)
        if "right" in self.connections: open_v(COLS - 1, mid_r)

        return tiles

    # ------------------------------------------------------------------
    def draw(self, surface):
        zc = ZONE_COLORS[self.zone]
        floor_col = zc["floor"]
        wall_col  = zc["wall"]
        for r in range(ROWS):
            for c in range(COLS):
                rect = pygame.Rect(c * TILE, PLAY_TOP + r * TILE, TILE, TILE)
                col  = floor_col if self.tiles[r][c] == FLOOR else wall_col
                pygame.draw.rect(surface, col, rect)
                # subtle grid line on floor
                if self.tiles[r][c] == FLOOR:
                    pygame.draw.rect(surface, (col[0]-8, col[1]-8, col[2]-8), rect, 1)

    # ------------------------------------------------------------------
    def is_wall(self, px, py):
        """Pixel coords in screen space → wall collision."""
        c = px // TILE
        r = (py - PLAY_TOP) // TILE
        if r < 0 or r >= ROWS or c < 0 or c >= COLS:
            return True
        return self.tiles[r][c] == WALL

    # ------------------------------------------------------------------
    def draw_locked_doors(self, surface):
        """Draw coloured bars over locked doorways."""
        mid_c = COLS // 2
        mid_r = ROWS // 2
        for direction, key_color in self.locked.items():
            col = KEY_COLORS[key_color]
            if direction == "right":
                x = (COLS - 1) * TILE
                y = PLAY_TOP + (mid_r - 1) * TILE
                pygame.draw.rect(surface, col, (x, y, TILE, TILE * 3))
            elif direction == "left":
                x = 0
                y = PLAY_TOP + (mid_r - 1) * TILE
                pygame.draw.rect(surface, col, (x, y, TILE, TILE * 3))
            elif direction == "up":
                x = (mid_c - 1) * TILE
                y = PLAY_TOP
                pygame.draw.rect(surface, col, (x, y, TILE * 3, TILE))
            elif direction == "down":
                x = (mid_c - 1) * TILE
                y = PLAY_TOP + (ROWS - 1) * TILE
                pygame.draw.rect(surface, col, (x, y, TILE * 3, TILE))


# ── Player ───────────────────────────────────────────────────────────────────
class Player:
    W, H = 20, 26

    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)
        # RPG stats
        self.max_hp = 30
        self.hp     = 30
        self.attack  = 5
        self.defense = 1
        self.xp      = 0
        self.level   = 1
        self.xp_next = 50
        # Inventory
        self.inventory = []   # list of item dicts
        self.weapon    = None
        self.shield    = None
        # Unlocked doors (set of key colours)
        self.keys = set()
        # Animation
        self.facing     = "right"  # "right" | "left" | "up" | "down"
        self.hurt_timer = 0
        self.anim_frame = 0.0      # running cycle counter
        self.moving     = False

    @property
    def rect(self):
        return pygame.Rect(int(self.x) - self.W // 2,
                           int(self.y) - self.H // 2,
                           self.W, self.H)

    def draw(self, surface):
        cx, cy = int(self.x), int(self.y)
        # Body
        pygame.draw.rect(surface, BLUE,
                         (cx - 10, cy - 8, 20, 18))
        # Head
        pygame.draw.ellipse(surface, LBLUE,
                            (cx - 8, cy - 20, 16, 16))

        r = self.facing == "right"
        sign = 1 if r else -1

        # Helmet ridge (top of head)
        pygame.draw.rect(surface, (80, 120, 200), (cx - 6, cy - 21, 12, 3))

        # Visor slit (dark bar across mid-head)
        pygame.draw.rect(surface, (20, 30, 60), (cx - 7, cy - 16, 14, 4))

        # Eyes — two small whites with dark pupils inside the visor slit
        e1x = cx + sign * 2
        e2x = cx + sign * 5
        pygame.draw.circle(surface, WHITE,  (e1x, cy - 14), 2)
        pygame.draw.circle(surface, WHITE,  (e2x, cy - 14), 2)
        pygame.draw.circle(surface, BLACK,  (e1x + sign, cy - 14), 1)
        pygame.draw.circle(surface, BLACK,  (e2x + sign, cy - 14), 1)

        # Nose — small pixel bump
        pygame.draw.rect(surface, (160, 190, 230), (cx + sign * 6, cy - 13, 2, 2))

        # Mouth — thin line, slight smile
        pygame.draw.line(surface, (80, 110, 180),
                         (cx + sign * 2, cy - 10),
                         (cx + sign * 6, cy - 10), 1)
        pygame.draw.line(surface, (80, 110, 180),
                         (cx + sign * 6, cy - 10),
                         (cx + sign * 7, cy - 11), 1)

        # Chin guard (small rectangle below head)
        pygame.draw.rect(surface, (90, 130, 210), (cx - 5, cy - 5, 10, 3))

        # Legs — animated running cycle
        swing = math.sin(self.anim_frame) * 6 if self.moving else 0.0
        leg_col  = BLUE
        boot_col = (30, 50, 130)
        f = self.facing
        if f in ("left", "right"):
            # Moving horizontally: legs swing forward/back along x
            s = int(swing) * (1 if f == "right" else -1)
            lx_top, rx_top = cx - 5, cx + 5
            pygame.draw.line(surface, leg_col,  (lx_top, cy + 10), (lx_top + s,     cy + 18), 4)
            pygame.draw.line(surface, leg_col,  (rx_top, cy + 10), (rx_top - s,     cy + 18), 4)
            pygame.draw.circle(surface, boot_col, (lx_top + s,     cy + 18), 3)
            pygame.draw.circle(surface, boot_col, (rx_top - s,     cy + 18), 3)
        else:
            # Moving up/down: legs swing left/right
            s = int(swing)
            pygame.draw.line(surface, leg_col,  (cx - 5, cy + 10), (cx - 5 + s,  cy + 18), 4)
            pygame.draw.line(surface, leg_col,  (cx + 5, cy + 10), (cx + 5 - s,  cy + 18), 4)
            pygame.draw.circle(surface, boot_col, (cx - 5 + s,  cy + 18), 3)
            pygame.draw.circle(surface, boot_col, (cx + 5 - s,  cy + 18), 3)
        # Arms — swing opposite to legs (only when no weapon obscures them)
        arm_col = BLUE
        arm_swing = -swing * 0.6
        if not self.weapon:
            if f in ("left", "right"):
                s2 = int(arm_swing) * (1 if f == "right" else -1)
                pygame.draw.line(surface, arm_col, (cx - 10, cy - 2), (cx - 13 - s2, cy + 6), 3)
                pygame.draw.line(surface, arm_col, (cx + 10, cy - 2), (cx + 13 + s2, cy + 6), 3)
            else:
                s2 = int(arm_swing)
                pygame.draw.line(surface, arm_col, (cx - 10, cy - 2), (cx - 13 + s2, cy + 6), 3)
                pygame.draw.line(surface, arm_col, (cx + 10, cy - 2), (cx + 13 - s2, cy + 6), 3)
        # Weapon — held out in facing direction like original Adventure
        if self.weapon:
            magic     = "Magic" in self.weapon["name"]
            blade_col = YELLOW if magic else (200, 200, 220)
            hilt_col  = (160, 120, 40) if magic else BROWN
            f = self.facing
            # Anchor at the player's hand (edge of body in facing direction)
            if f == "right":
                bx1, by1 = cx + 10, cy
                bx2, by2 = cx + 38, cy          # blade tip
                gx1, gy1 = cx + 16, cy - 7      # crossguard ends
                gx2, gy2 = cx + 16, cy + 7
                px,  py  = cx + 11, cy           # pommel
            elif f == "left":
                bx1, by1 = cx - 10, cy
                bx2, by2 = cx - 38, cy
                gx1, gy1 = cx - 16, cy - 7
                gx2, gy2 = cx - 16, cy + 7
                px,  py  = cx - 11, cy
            elif f == "up":
                bx1, by1 = cx, cy - 10
                bx2, by2 = cx, cy - 38
                gx1, gy1 = cx - 7, cy - 16
                gx2, gy2 = cx + 7, cy - 16
                px,  py  = cx, cy - 11
            else:  # down
                bx1, by1 = cx, cy + 10
                bx2, by2 = cx, cy + 38
                gx1, gy1 = cx - 7, cy + 16
                gx2, gy2 = cx + 7, cy + 16
                px,  py  = cx, cy + 11
            # Blade
            pygame.draw.line(surface, blade_col, (bx1, by1), (bx2, by2), 3)
            # Tip highlight
            pygame.draw.circle(surface, WHITE, (bx2, by2), 2)
            # Crossguard
            pygame.draw.line(surface, hilt_col, (gx1, gy1), (gx2, gy2), 3)
            # Pommel
            pygame.draw.circle(surface, hilt_col, (px, py), 3)

        # Shield — on the off-hand side (opposite to facing)
        if self.shield:
            f = self.facing
            sc = (60, 100, 180)   # shield face colour
            sb = (30,  50, 120)   # shield border / boss colour
            if f == "right":
                sx, sy = cx - 14, cy - 2
                pts = [(sx, sy - 7), (sx + 9, sy - 7),
                       (sx + 9, sy + 5), (sx + 4, sy + 10), (sx, sy + 5)]
            elif f == "left":
                sx, sy = cx + 14, cy - 2
                pts = [(sx, sy - 7), (sx - 9, sy - 7),
                       (sx - 9, sy + 5), (sx - 4, sy + 10), (sx, sy + 5)]
            elif f == "up":
                sx, sy = cx + 3, cy + 2
                pts = [(sx - 7, sy), (sx + 7, sy),
                       (sx + 7, sy + 9), (sx, sy + 14), (sx - 7, sy + 9)]
            else:  # down
                sx, sy = cx + 3, cy - 8
                pts = [(sx - 7, sy), (sx + 7, sy),
                       (sx + 7, sy - 9), (sx, sy - 14), (sx - 7, sy - 9)]
            pygame.draw.polygon(surface, sc, pts)
            pygame.draw.polygon(surface, sb, pts, 2)
            # Central boss (small circle)
            bx = sum(p[0] for p in pts) // len(pts)
            by = sum(p[1] for p in pts) // len(pts)
            pygame.draw.circle(surface, sb, (bx, by), 2)

    def weapon_rect(self):
        """Hitbox of the held weapon — matches the drawn blade."""
        cx, cy = int(self.x), int(self.y)
        L = 28   # blade length (10 body offset + 28 = tip at 38)
        T = 8    # hit thickness
        if self.facing == "right":  return pygame.Rect(cx + 10,      cy - T//2, L, T)
        if self.facing == "left":   return pygame.Rect(cx - 10 - L,  cy - T//2, L, T)
        if self.facing == "up":     return pygame.Rect(cx - T//2,    cy - 10 - L, T, L)
        return pygame.Rect(cx - T//2, cy + 10, T, L)

    def move(self, dx, dy, room):
        if dx > 0:  self.facing = "right"
        elif dx < 0: self.facing = "left"
        elif dy < 0: self.facing = "up"
        elif dy > 0: self.facing = "down"
        self.moving = (dx != 0 or dy != 0)
        if self.moving:
            self.anim_frame += 0.28
        # Move X then Y for axis-separated collision
        nx = self.x + dx
        if not self._collides(nx, self.y, room):
            self.x = nx
        ny = self.y + dy
        if not self._collides(self.x, ny, room):
            self.y = ny

    def _collides(self, px, py, room):
        hw, hh = self.W // 2, self.H // 2
        corners = [
            (px - hw + 2, py - hh + 2),
            (px + hw - 2, py - hh + 2),
            (px - hw + 2, py + hh - 2),
            (px + hw - 2, py + hh - 2),
        ]
        return any(room.is_wall(int(cx), int(cy)) for cx, cy in corners)

    def gain_xp(self, amount):
        self.xp += amount
        levelled = False
        while self.xp >= self.xp_next:
            self.xp -= self.xp_next
            self.level += 1
            self.xp_next = int(self.xp_next * 1.8)
            self.max_hp += 10
            self.hp      = min(self.hp + 10, self.max_hp)
            self.attack  += 2
            self.defense += 1
            levelled = True
        return levelled

    def take_damage(self, amount):
        dmg = max(1, amount - self.defense)
        self.hp = max(0, self.hp - dmg)
        self.hurt_timer = 20

    @property
    def alive(self):
        return self.hp > 0


# ── Enemies ───────────────────────────────────────────────────────────────────
import math, random

class Enemy:
    def __init__(self, kind, x, y):
        self.kind = kind   # "slime" | "bat" | "skeleton" | "dragon"
        self.x = float(x)
        self.y = float(y)
        self.hurt_timer  = 0
        self.invuln      = 0   # frames of invulnerability after being hit
        cfg = {
            "slime":    dict(hp=10, atk=3,  xp=10,  spd=0.8,  col=(50,200,60),   size=12),
            "bat":      dict(hp=5,  atk=2,  xp=8,   spd=2.2,  col=(150,60,200),  size=8),
            "skeleton": dict(hp=20, atk=6,  xp=20,  spd=1.2,  col=(220,220,200), size=14),
            "dragon":   dict(hp=80, atk=12, xp=100, spd=0.6,  col=(200,40,30),   size=22),
        }[kind]
        self.max_hp  = cfg["hp"]
        self.hp      = cfg["hp"]
        self.atk     = cfg["atk"]
        self.xp      = cfg["xp"]
        self.spd     = cfg["spd"]
        self.col     = cfg["col"]
        self.size    = cfg["size"]
        # AI state
        self.wander_timer  = 0
        self.wander_dx     = 0.0
        self.wander_dy     = 0.0
        self.shoot_timer   = 0

    @property
    def alive(self): return self.hp > 0

    @property
    def rect(self):
        s = self.size
        return pygame.Rect(int(self.x)-s, int(self.y)-s, s*2, s*2)

    def update(self, player, room, projectiles):
        if self.invuln > 0: self.invuln -= 1
        if self.hurt_timer > 0: self.hurt_timer -= 1

        dx_to = player.x - self.x
        dy_to = player.y - self.y
        dist  = math.hypot(dx_to, dy_to) or 1

        if self.kind == "slime":
            self._wander(room)
        elif self.kind == "bat":
            if dist < 200:
                # erratic: add random jitter
                jx = dx_to/dist + random.uniform(-0.6, 0.6)
                jy = dy_to/dist + random.uniform(-0.6, 0.6)
                self._move(jx * self.spd, jy * self.spd, room)
            else:
                self._wander(room)
        elif self.kind == "skeleton":
            if dist < 220:
                self._move(dx_to/dist * self.spd, dy_to/dist * self.spd, room)
            else:
                self._wander(room)
        elif self.kind == "dragon":
            if dist < 300:
                self._move(dx_to/dist * self.spd, dy_to/dist * self.spd, room)
            self.shoot_timer -= 1
            if self.shoot_timer <= 0 and dist < 280:
                self.shoot_timer = 90
                projectiles.append(Projectile(self.x, self.y, dx_to/dist, dy_to/dist))

    def _wander(self, room):
        self.wander_timer -= 1
        if self.wander_timer <= 0:
            self.wander_timer = random.randint(30, 90)
            angle = random.uniform(0, math.tau)
            self.wander_dx = math.cos(angle) * self.spd
            self.wander_dy = math.sin(angle) * self.spd
        self._move(self.wander_dx, self.wander_dy, room)

    def _move(self, dx, dy, room):
        nx = self.x + dx
        if not room.is_wall(int(nx), int(self.y)):
            self.x = nx
        ny = self.y + dy
        if not room.is_wall(int(self.x), int(ny)):
            self.y = ny

    def take_damage(self, amount):
        if self.invuln > 0: return
        self.hp = max(0, self.hp - amount)
        self.hurt_timer = 10
        self.invuln     = 15

    def draw(self, surface):
        cx, cy = int(self.x), int(self.y)
        col = WHITE if self.hurt_timer > 0 else self.col
        s   = self.size

        if self.kind == "slime":
            pygame.draw.ellipse(surface, col, (cx-s, cy-s//2, s*2, int(s*1.4)))
            pygame.draw.circle(surface, (col[0]//2, col[1]//2, col[2]//2),
                               (cx, cy - s//2), s//3)  # eye shine

        elif self.kind == "bat":
            # wings
            pygame.draw.polygon(surface, col,
                [(cx-s*2, cy), (cx-s//2, cy-s), (cx, cy+s//3)])
            pygame.draw.polygon(surface, col,
                [(cx+s*2, cy), (cx+s//2, cy-s), (cx, cy+s//3)])
            pygame.draw.circle(surface, col, (cx, cy), s//2)

        elif self.kind == "skeleton":
            # skull
            pygame.draw.circle(surface, col, (cx, cy-s//2), s//2)
            # eye sockets
            pygame.draw.circle(surface, BLACK, (cx-3, cy-s//2-1), 2)
            pygame.draw.circle(surface, BLACK, (cx+3, cy-s//2-1), 2)
            # spine
            pygame.draw.line(surface, col, (cx, cy), (cx, cy+s), 2)
            # ribs
            for ry in (cy+3, cy+7):
                pygame.draw.line(surface, col, (cx, ry), (cx-6, ry+3), 1)
                pygame.draw.line(surface, col, (cx, ry), (cx+6, ry+3), 1)
            # legs
            pygame.draw.line(surface, col, (cx, cy+s), (cx-5, cy+s+8), 2)
            pygame.draw.line(surface, col, (cx, cy+s), (cx+5, cy+s+8), 2)

        elif self.kind == "dragon":
            # body
            pygame.draw.ellipse(surface, col, (cx-s, cy-s//2, s*2, s))
            # head
            pygame.draw.ellipse(surface, col, (cx+s//2, cy-s//3, s, s//2))
            # eye
            pygame.draw.circle(surface, YELLOW, (cx+s, cy-s//6), 3)
            # wings
            pygame.draw.polygon(surface, (col[0]-30, col[1], col[2]),
                [(cx-s//2, cy-s//4),
                 (cx-s*2,  cy-s),
                 (cx,      cy-s//2)])
            pygame.draw.polygon(surface, (col[0]-30, col[1], col[2]),
                [(cx-s//4, cy-s//4),
                 (cx-s,    cy-s*2),
                 (cx+s//4, cy-s//2)])

        # HP bar above enemy
        bar_w = s * 2
        hp_pct = self.hp / self.max_hp
        pygame.draw.rect(surface, DGRAY, (cx - s, cy - s - 6, bar_w, 3))
        pygame.draw.rect(surface, RED,   (cx - s, cy - s - 6, int(bar_w * hp_pct), 3))


# ── Projectile ────────────────────────────────────────────────────────────────
class Projectile:
    SPEED = 3.5
    RADIUS = 5

    def __init__(self, x, y, dx, dy):
        self.x  = float(x)
        self.y  = float(y)
        self.dx = dx * self.SPEED
        self.dy = dy * self.SPEED
        self.alive = True

    def update(self, room):
        self.x += self.dx
        self.y += self.dy
        if room.is_wall(int(self.x), int(self.y)):
            self.alive = False

    def draw(self, surface):
        pygame.draw.circle(surface, ORANGE, (int(self.x), int(self.y)), self.RADIUS)
        pygame.draw.circle(surface, YELLOW, (int(self.x), int(self.y)), self.RADIUS - 2)

    @property
    def rect(self):
        r = self.RADIUS
        return pygame.Rect(int(self.x)-r, int(self.y)-r, r*2, r*2)


# ── Floor Item ────────────────────────────────────────────────────────────────
class FloorItem:
    def __init__(self, data, x, y):
        self.data  = data   # item dict
        self.x     = x
        self.y     = y
        self.bob   = 0.0    # animation phase

    @property
    def rect(self):
        return pygame.Rect(self.x - 12, self.y - 12, 24, 24)

    def draw(self, surface):
        self.bob += 0.08
        offset = int(math.sin(self.bob) * 3)
        # Glow ring
        pygame.draw.circle(surface, (60, 60, 30), (self.x, self.y + offset), 14, 1)
        _draw_item_icon(surface, self.data, self.x, self.y + offset, 10)
        # Label
        # (skipped for cleanliness — tooltip shown in HUD when nearby)


# ── Inventory Screen ──────────────────────────────────────────────────────────
class InventoryScreen:
    SLOT = 52
    COLS = 4
    PAD  = 12

    def __init__(self, font_s, font_l):
        self.font_s = font_s
        self.font_l = font_l

    def draw(self, surface, player):
        # Dim background
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))

        title = self.font_l.render("INVENTORY  (I:close  L-click:use/equip  R-click or 1-8:drop)", True, WHITE)
        surface.blit(title, (SCREEN_W//2 - title.get_width()//2, 20))

        ox = SCREEN_W//2 - (self.COLS * (self.SLOT + self.PAD))//2
        oy = 60
        for i in range(8):
            col_i = i % self.COLS
            row_i = i // self.COLS
            sx = ox + col_i * (self.SLOT + self.PAD)
            sy = oy + row_i * (self.SLOT + self.PAD)
            occupied = i < len(player.inventory)
            item = player.inventory[i] if occupied else None

            # Slot background
            slot_col = (50, 50, 70)
            if item and (item is player.weapon or item is player.shield):
                slot_col = (60, 80, 40)  # equipped highlight
            pygame.draw.rect(surface, slot_col, (sx, sy, self.SLOT, self.SLOT))
            pygame.draw.rect(surface, GRAY,     (sx, sy, self.SLOT, self.SLOT), 1)

            # Slot number
            num = self.font_s.render(str(i+1), True, GRAY)
            surface.blit(num, (sx + 3, sy + 3))

            if item:
                _draw_item_icon(surface, item, sx + self.SLOT//2, sy + self.SLOT//2, 14)
                name = self.font_s.render(item["name"], True, WHITE)
                surface.blit(name, (sx + self.SLOT//2 - name.get_width()//2, sy + self.SLOT - 14))

        # Stats panel
        stats = [
            f"Level  {player.level}",
            f"HP     {player.hp}/{player.max_hp}",
            f"ATK    {player.attack}",
            f"DEF    {player.defense}",
            f"XP     {player.xp}/{player.xp_next}",
        ]
        sx2 = ox + self.COLS * (self.SLOT + self.PAD) + 20
        for i, line in enumerate(stats):
            t = self.font_s.render(line, True, (180, 220, 180))
            surface.blit(t, (sx2, oy + i * 18))



# ── HUD ──────────────────────────────────────────────────────────────────────
class HUD:
    def __init__(self, font_small, font_large):
        self.font_s = font_small
        self.font_l = font_large
        self.room_name_alpha = 0
        self.room_name_text  = ""
        self.levelup_timer   = 0

    def notify_room(self, name):
        self.room_name_text  = name
        self.room_name_alpha = 255

    def notify_levelup(self):
        self.levelup_timer = 120

    def draw(self, surface, player, room_name):
        # ── Top bar ──────────────────────────────────────────────
        pygame.draw.rect(surface, (15, 15, 15), (0, 0, SCREEN_W, HUD_TOP))

        # HP bar
        bar_w = 120
        hp_pct = player.hp / player.max_hp
        pygame.draw.rect(surface, DGRAY,  (8, 8, bar_w, 14))
        pygame.draw.rect(surface, RED,    (8, 8, int(bar_w * hp_pct), 14))
        pygame.draw.rect(surface, WHITE,  (8, 8, bar_w, 14), 1)
        hp_txt = self.font_s.render(f"HP {player.hp}/{player.max_hp}", True, WHITE)
        surface.blit(hp_txt, (10, 9))

        # XP bar
        xp_pct = player.xp / player.xp_next
        pygame.draw.rect(surface, DGRAY,  (8, 24, bar_w, 6))
        pygame.draw.rect(surface, YELLOW, (8, 24, int(bar_w * xp_pct), 6))

        # Level
        lv_txt = self.font_s.render(f"Lv {player.level}", True, YELLOW)
        surface.blit(lv_txt, (136, 10))

        # Room name (fade in)
        if self.room_name_alpha > 0:
            name_surf = self.font_l.render(self.room_name_text, True,
                                           ZONE_COLORS["overworld"]["name_col"])
            name_surf.set_alpha(min(self.room_name_alpha, 255))
            surface.blit(name_surf, (SCREEN_W // 2 - name_surf.get_width() // 2, 6))
            self.room_name_alpha = max(0, self.room_name_alpha - 2)

        # Level-up flash
        if self.levelup_timer > 0:
            msg = self.font_l.render("LEVEL UP!", True, YELLOW)
            alpha = min(self.levelup_timer * 2, 255)
            msg.set_alpha(alpha)
            surface.blit(msg, (SCREEN_W // 2 - msg.get_width() // 2, PLAY_TOP + 20))
            self.levelup_timer -= 1

        # ── Bottom bar (inventory strip + tip) ───────────────────
        bot_y = PLAY_TOP + PLAY_H
        pygame.draw.rect(surface, (15, 15, 15), (0, bot_y, SCREEN_W, HUD_BOT))
        slot_size = 28
        for i in range(4):
            sx = 8 + i * (slot_size + 4)
            sy = bot_y + 2
            pygame.draw.rect(surface, DGRAY, (sx, sy, slot_size, slot_size))
            pygame.draw.rect(surface, GRAY,  (sx, sy, slot_size, slot_size), 1)
            if i < len(player.inventory):
                item = player.inventory[i]
                _draw_item_icon(surface, item, sx + slot_size // 2, sy + slot_size // 2, 10)
        tip = self.font_s.render("WASD: move   I: inventory to use/equip", True, (110, 110, 130))
        surface.blit(tip, (SCREEN_W // 2 - tip.get_width() // 2, bot_y + (HUD_BOT - tip.get_height()) // 2))



# ── Item icon helper ─────────────────────────────────────────────────────────
def _draw_item_icon(surface, item, cx, cy, size):
    t = item["type"]
    if t == "sword":
        magic = "Magic" in item["name"]
        blade = YELLOW if magic else (180, 180, 200)
        grip  = BROWN  if not magic else (160, 120, 40)
        # Blade — long diagonal line from bottom-left to top-right
        pygame.draw.line(surface, blade,
                         (cx - size + 2, cy + size - 2),
                         (cx + size - 2, cy - size + 2), 3)
        # Tip highlight
        pygame.draw.circle(surface, WHITE, (cx + size - 2, cy - size + 2), 2)
        # Crossguard — perpendicular bar across the mid-point
        gx, gy = cx - size//3, cy + size//3
        pygame.draw.line(surface, grip,
                         (gx - size//3, gy + size//3),
                         (gx + size//3, gy - size//3), 3)
        # Grip — short stub below crossguard
        pygame.draw.line(surface, grip,
                         (gx - 2, gy + 2),
                         (gx - size//3 - 1, gy + size//3 + 1), 3)
        # Pommel — small circle at grip end
        pygame.draw.circle(surface, grip,
                           (gx - size//3 - 1, gy + size//3 + 1), 2)
    elif t == "shield":
        pygame.draw.polygon(surface, BLUE,
                            [(cx, cy - size), (cx + size, cy), (cx, cy + size), (cx - size, cy)])
    elif t == "key":
        pygame.draw.circle(surface, KEY_COLORS[item["color"]], (cx, cy - size // 2), size // 2, 2)
        pygame.draw.line(surface, KEY_COLORS[item["color"]], (cx, cy), (cx, cy + size), 2)
    elif t == "potion":
        pygame.draw.ellipse(surface, RED, (cx - size // 2, cy - size, size, size * 2 - 2))
    elif t == "chalice":
        pygame.draw.polygon(surface, YELLOW,
                            [(cx - size, cy + size), (cx - size // 2, cy - size),
                             (cx + size // 2, cy - size), (cx + size, cy + size)])


# ── Item factories ────────────────────────────────────────────────────────────
def make_sword():        return {"name": "Sword",        "type": "sword",  "atk": 4}
def make_magic_sword():  return {"name": "Magic Sword",  "type": "sword",  "atk": 10}
def make_shield():       return {"name": "Shield",       "type": "shield", "def": 3}
def make_key(color):     return {"name": f"{color.title()} Key", "type": "key", "color": color}
def make_potion():       return {"name": "Health Potion","type": "potion", "hp": 20}
def make_chalice():      return {"name": "Golden Chalice","type": "chalice"}


# ── World builder ────────────────────────────────────────────────────────────
def build_world():
    CX = SCREEN_W // 2
    CY = PLAY_TOP + PLAY_H // 2

    rooms = [
        # Zone 1 — Overworld
        Room(0,  "The Green Fields",    "overworld", {"right": 1, "down": 5}),
        Room(1,  "Old Forest Path",     "overworld", {"left": 0, "right": 2}),
        Room(2,  "Wizard's Clearing",   "overworld", {"left": 1, "right": 3, "down": 7}),
        Room(3,  "Crumbling Outpost",   "overworld", {"left": 2, "right": 4}),
        Room(4,  "Eastern Overlook",    "overworld", {"left": 3}),
        # Zone 2 — Dungeon
        Room(5,  "Dungeon Entrance",    "dungeon",   {"up": 0, "right": 6, "down": 10}),
        Room(6,  "Torch-lit Corridor",  "dungeon",   {"left": 5, "right": 7}),
        Room(7,  "Crossroads Chamber",  "dungeon",   {"left": 6, "up": 2, "right": 8, "down": 12}),
        Room(8,  "Bone-strewn Hall",    "dungeon",   {"left": 7, "right": 9}),
        Room(9,  "Hidden Vault",        "dungeon",   {"left": 8}),
        # Zone 3 — Castle
        Room(10, "Castle Gate",         "castle",    {"up": 5, "right": 11}),
        Room(11, "Guard Barracks",      "castle",    {"left": 10, "right": 12},  locked={"right": "red"}),
        Room(12, "Inner Courtyard",     "castle",    {"left": 11, "up": 7, "right": 13}),
        Room(13, "Armory",              "castle",    {"left": 12, "right": 14},  locked={"right": "yellow"}),
        Room(14, "Throne Room",         "castle",    {"left": 13}),
    ]
    room_map = {r.rid: r for r in rooms}

    # Enemy spawns  { room_id: [(kind, x_offset, y_offset), ...] }
    enemy_spawns = {
        0:  [("slime",    -80,  40), ("slime",    80, -40)],
        1:  [("slime",      0,  60), ("bat",    -60, -60)],
        3:  [("bat",      -60,  40), ("bat",     60,  40)],
        4:  [("slime",    -40,   0), ("bat",     40,   0)],
        5:  [("skeleton", -60,  40)],
        6:  [("skeleton",  60,  20), ("bat",    -60, -40)],
        7:  [("skeleton", -80,  60), ("skeleton", 80, -60)],
        8:  [("skeleton",  40,  30), ("skeleton",-40, -30)],
        9:  [("skeleton",   0,   0)],
        10: [("skeleton", -60,  50), ("bat",     60, -50)],
        11: [("skeleton", -40,  30), ("skeleton", 40,  30)],
        12: [("skeleton",   0,  60), ("bat",    -80, -60)],
        13: [("skeleton", -60,  40), ("skeleton", 60, -40)],
        14: [("dragon",    60,   0)],
    }

    # Item spawns  { room_id: [(item_dict, x_offset, y_offset), ...] }
    item_spawns = {
        1:  [(make_sword(),        0,  -60)],
        3:  [(make_potion(),      60,  -40)],
        6:  [(make_shield(),     -60,  -40), (make_potion(), 60, 40)],
        8:  [(make_key("yellow"), 60,  -40)],
        9:  [(make_key("red"),     0,    0)],
        11: [(make_potion(),      -60,  40)],
        13: [(make_magic_sword(), 60,  -40)],
        14: [(make_chalice(),    -60,   0)],
    }

    # Build per-room enemy and item lists
    room_enemies = {}
    room_items   = {}
    for rid, spawns in enemy_spawns.items():
        room_enemies[rid] = [Enemy(k, CX+ox, CY+oy) for k, ox, oy in spawns]
    for rid, spawns in item_spawns.items():
        room_items[rid]   = [FloorItem(d, CX+ox, CY+oy) for d, ox, oy in spawns]

    room_npcs = {
        2: NPC("Aldric the Wizard", CX, CY - 60, [
            "Greetings, brave soul. The dungeon below is riddled with skeletons and worse.",
            "Seek the Red Key hidden in the vault to the east — it opens the castle's inner gate.",
            "The Yellow Key lies deeper still. Without both, the Throne Room remains sealed.",
            "Good luck. The realm depends on you retrieving the Golden Chalice.",
        ]),
        10: NPC("Ghost of the Knight", CX + 60, CY, [
            "Heed my warning, traveler. I too sought the Chalice... and perished.",
            "The Dragon guards the Throne Room. It breathes fire — do not let it corner you.",
            "A Magic Sword rests in the Armory. It is far mightier than a common blade.",
            "Equip it before you face the Dragon. You will need every advantage.",
        ], col=(160, 200, 255)),
    }

    return room_map, room_enemies, room_items, room_npcs


# ── Transition helper ─────────────────────────────────────────────────────────
def check_room_transition(player, room, rooms, unlocked_keys):
    """
    Returns (new_room_id, spawn_x, spawn_y) or None.
    Checks if player walks through a doorway.
    """
    mid_c = COLS // 2
    mid_r = ROWS // 2

    px, py = int(player.x), int(player.y)
    play_bottom = PLAY_TOP + PLAY_H

    for direction, neighbor_id in room.connections.items():
        # Check if this door is locked
        if direction in room.locked:
            key_needed = room.locked[direction]
            if key_needed not in unlocked_keys:
                continue  # door is locked, skip transition

        # Trigger when player centre enters the border tile
        if direction == "right"  and px >= SCREEN_W - TILE // 2:
            spawn_x = TILE + player.W
            spawn_y = PLAY_TOP + mid_r * TILE
            return neighbor_id, spawn_x, spawn_y

        elif direction == "left" and px <= TILE // 2:
            spawn_x = SCREEN_W - TILE - player.W
            spawn_y = PLAY_TOP + mid_r * TILE
            return neighbor_id, spawn_x, spawn_y

        elif direction == "up"   and py <= PLAY_TOP + TILE // 2:
            spawn_x = mid_c * TILE
            spawn_y = play_bottom - TILE - player.H
            return neighbor_id, spawn_x, spawn_y

        elif direction == "down" and py >= play_bottom - TILE // 2:
            spawn_x = mid_c * TILE
            spawn_y = PLAY_TOP + TILE + player.H
            return neighbor_id, spawn_x, spawn_y

    return None


# ── Music generation (Bach Minuet in G, BWV Anh. 114) ────────────────────────
_FREQS = {
    'C2': 65.41,'D2': 73.42,'E2': 82.41,'F2': 87.31,'G2': 98.00,'A2':110.00,'B2':123.47,
    'C3':130.81,'D3':146.83,'E3':164.81,'F3':174.61,'G3':196.00,
    'Ab3':207.65,'A3':220.00,'Bb3':233.08,'B3':246.94,
    'C4':261.63,'D4':293.66,'Eb4':311.13,'E4':329.63,'F#4':369.99,
    'G4':392.00,'Ab4':415.30,'A4':440.00,'Bb4':466.16,'B4':493.88,
    'C5':523.25,'D5':587.33,'Eb5':622.25,'E5':659.25,'F#5':739.99,
    'G5':783.99,'Ab5':830.61,'A5':880.00,'Bb5':932.33,'B5':987.77,
}

def _note_buf(freq, dur, sr=22050, vol=0.22):
    n   = int(sr * dur)
    rel = max(1, min(int(sr * 0.06), n))
    buf = [0.0] * n
    for i in range(n):
        env  = (n - i) / rel if i > n - rel else 1.0
        t    = i / sr
        buf[i] = vol * env * math.sin(2 * math.pi * freq * t)
    return buf

def _thump_buf(freq, dur, sr=22050, vol=0.55):
    """Short punchy bass thump with exponential decay and mild 2nd harmonic."""
    n = int(sr * dur)
    buf = [0.0] * n
    for i in range(n):
        env = math.exp(-5.0 * i / n)
        t = i / sr
        buf[i] = vol * env * (0.75 * math.sin(2 * math.pi * freq * t)
                              + 0.25 * math.sin(2 * math.pi * freq * 2 * t))
    return buf

def _mix_into(dst, src, pos):
    for i, s in enumerate(src):
        idx = pos + i
        if idx < len(dst):
            dst[idx] += s

async def make_music_async(sr=22050):
    """Generate Bach Minuet in G asynchronously — 24 bars."""
    try:
        beat = 0.50
        MELODY = [
            # bars 1-4 (section A, phrase 1)
            ('G5',1),('A5',1),('B5',1),
            ('G5',2),('G5',1),
            ('C5',1),('D5',1),('C5',1),
            ('B4',3),
            # bars 5-8 (section A, phrase 2)
            ('A4',1),('B4',1),('C5',1),
            ('D5',3),
            ('D5',1),('C5',1),('B4',1),
            ('A4',3),
            # bars 9-12 (section A, phrase 3)
            ('B4',1),('C5',1),('D5',1),
            ('G5',2),('D5',1),
            ('E5',1),('D5',1),('C5',1),
            ('G4',3),
            # bars 13-16 (section B, phrase 1 — D major region)
            ('D5',1),('C5',1),('B4',1),
            ('A4',3),
            ('D5',1),('E5',1),('F#5',1),
            ('G5',3),
            # bars 17-20 (section B, phrase 2 — descending)
            ('E5',1),('D5',1),('C5',1),
            ('B4',3),
            ('C5',1),('B4',1),('A4',1),
            ('G4',3),
            # bars 21-24 (closing — return to G, grand cadence)
            ('G5',1),('F#5',1),('E5',1),
            ('D5',2),('C5',1),
            ('B4',1),('A4',1),('G4',1),
            ('G5',3),
        ]
        BASS = [
            # bars 1-4
            ('G3',1),('B3',1),('D4',1),
            ('G4',2),('D4',1),
            ('C4',1),('E4',1),('G3',1),
            ('G3',3),
            # bars 5-8
            ('F#4',1),('D4',1),('A3',1),
            ('D4',3),
            ('G3',1),('B3',1),('D4',1),
            ('A3',3),
            # bars 9-12
            ('G3',1),('B3',1),('D4',1),
            ('G4',2),('D4',1),
            ('C4',1),('G3',1),('E4',1),
            ('G3',3),
            # bars 13-16
            ('G3',1),('B3',1),('D4',1),
            ('A3',3),
            ('D4',1),('F#4',1),('A3',1),
            ('G4',3),
            # bars 17-20
            ('C4',1),('E4',1),('G3',1),
            ('G3',3),
            ('C4',1),('E4',1),('A3',1),
            ('G3',3),
            # bars 21-24
            ('G4',1),('D4',1),('B3',1),
            ('D4',3),
            ('G3',1),('B3',1),('D4',1),
            ('G3',3),
        ]
        total_samples = int(sum(b for _, b in MELODY) * beat * sr)
        mix = [0.0] * total_samples

        pos = 0
        for idx, (note, beats) in enumerate(MELODY):
            dur = beats * beat
            _mix_into(mix, _note_buf(_FREQS[note], dur, sr, vol=0.28), pos)
            pos += int(dur * sr)
            if idx % 4 == 3:
                await asyncio.sleep(0)

        pos = 0
        for idx, (note, beats) in enumerate(BASS):
            dur = beats * beat
            _mix_into(mix, _note_buf(_FREQS[note], dur, sr, vol=0.14), pos)
            pos += int(dur * sr)
            if idx % 4 == 3:
                await asyncio.sleep(0)

        buf = array.array('h', [max(-32767, min(32767, int(s * 32767))) for s in mix])
        return pygame.mixer.Sound(buffer=buf)
    except Exception as e:
        print("Music gen failed:", e)
        return None


async def make_gameplay_music_async(sr=22050):
    """Generate ominous Space Invaders-style bass thump loop."""
    try:
        # 4 descending bass thumps with rests — slow and menacing
        # (freq_key or None for rest, duration_seconds)
        # Notes lowered + tempo slowed 25% (durations × 1.25)
        PATTERN = [
            ('E2', 0.25), (None, 0.56),
            ('C2', 0.25), (None, 0.56),
            ('D2', 0.25), (None, 0.56),
            ('C2', 0.25), (None, 0.88),
            # second half: sparse double-tap for depth
            ('E2', 0.25), (None, 0.44),
            ('E2', 0.15), (None, 0.44),
            ('C2', 0.25), (None, 0.44),
            ('D2', 0.25), (None, 0.75),
        ]
        total_dur = sum(d for _, d in PATTERN)
        total_samples = int(total_dur * sr)
        mix = [0.0] * total_samples

        pos = 0
        for idx, (freq_key, dur) in enumerate(PATTERN):
            n = int(dur * sr)
            if freq_key is not None:
                _mix_into(mix, _thump_buf(_FREQS[freq_key], dur, sr, vol=0.60), pos)
            pos += n
            if idx % 4 == 3:
                await asyncio.sleep(0)

        buf = array.array('h', [max(-32767, min(32767, int(s * 32767))) for s in mix])
        return pygame.mixer.Sound(buffer=buf)
    except Exception as e:
        print("Gameplay music gen failed:", e)
        return None


async def make_boss_music_async(sr=22050):
    """Scary, fast, frenetic boss battle music — rapid minor/tritone runs."""
    try:
        beat = 0.09  # very fast (~667 BPM per 16th note)
        MELODY = [
            # phrase 1: rapid descending chromatic run
            ('E5',1),('Eb5',1),('D5',1),('C5',1),
            ('B4',1),('Bb4',1),('A4',1),('Ab4',1),
            # phrase 2: tritone oscillation — the "devil's interval"
            ('A4',1),('Eb5',1),('A4',1),('Eb5',1),
            ('A4',1),('Eb5',1),('A4',2),
            # phrase 3: frenzied leap pattern
            ('E5',1),('A4',1),('Bb4',1),('E5',1),
            ('D5',1),('Ab4',1),('A4',1),('E5',1),
            # phrase 4: driving chromatic ascent then crash
            ('A4',1),('Bb4',1),('B4',1),('C5',1),
            ('C5',1),('B4',1),('Bb4',1),('A4',2),
        ]
        BASS = [
            # driving alternating A2/E2 bass thumps at half speed
            ('A2',1),('E2',1),('A2',1),('E2',1),
            ('A2',1),('E2',1),('A2',1),('E2',1),
            ('A2',1),('Bb3',1),('A2',1),('E2',1),
            ('A2',1),('E2',1),('A2',1),('E2',1),
            ('A2',1),('E2',1),('A2',1),('E2',1),
            ('Ab3',1),('E2',1),('A2',1),('E2',1),
            ('A2',1),('E2',1),('A2',1),('Bb3',1),
            ('A2',1),('E2',1),('A2',2),
        ]
        total_mel = sum(b for _, b in MELODY)
        total_bas = sum(b for _, b in BASS)
        total_beats = max(total_mel, total_bas)
        total_samples = int(total_beats * beat * sr)
        mix = [0.0] * total_samples

        pos = 0
        for idx, (note, beats) in enumerate(MELODY):
            dur = beats * beat
            _mix_into(mix, _note_buf(_FREQS[note], dur * 0.85, sr, vol=0.32), pos)
            pos += int(dur * sr)
            if idx % 4 == 3:
                await asyncio.sleep(0)

        pos = 0
        for idx, (note, beats) in enumerate(BASS):
            dur = beats * beat
            _mix_into(mix, _thump_buf(_FREQS[note], dur * 0.70, sr, vol=0.50), pos)
            pos += int(dur * sr)
            if idx % 4 == 3:
                await asyncio.sleep(0)

        buf = array.array('h', [max(-32767, min(32767, int(s * 32767))) for s in mix])
        return pygame.mixer.Sound(buffer=buf)
    except Exception as e:
        print("Boss music gen failed:", e)
        return None


async def make_victory_music_async(sr=22050):
    """Soaring triumphant victory fanfare."""
    try:
        beat = 0.28  # exciting, march-like
        MELODY = [
            # rising fanfare — G major arpeggio to the sky
            ('G4',1),('B4',1),('D5',1),
            ('G5',2),('B5',1),
            # peak and shimmer
            ('A5',1),('B5',1),('A5',1),
            ('G5',3),
            # second phrase — soaring
            ('B5',1),('A5',1),('G5',1),
            ('A5',2),('B5',1),
            ('D5',1),('G5',1),('B5',1),
            ('G5',4),
            # third phrase — triumphant cascade
            ('G5',1),('A5',1),('B5',1),
            ('G5',2),('D5',1),
            ('B4',1),('D5',1),('G5',1),
            # grand final hold
            ('G5',1),('B5',2),
            ('G5',6),
        ]
        BASS = [
            ('G3',3), ('G4',3),
            ('D4',3), ('G4',3),
            ('G3',3), ('D4',3),
            ('G4',6),
            ('G3',3), ('G4',3),
            ('D4',3), ('G4',3),
            ('G3',3),
            ('G3',3),
            ('G4',9),
        ]
        total_samples = int(sum(b for _, b in MELODY) * beat * sr)
        mix = [0.0] * total_samples

        pos = 0
        for idx, (note, beats) in enumerate(MELODY):
            dur = beats * beat
            _mix_into(mix, _note_buf(_FREQS[note], dur, sr, vol=0.35), pos)
            pos += int(dur * sr)
            if idx % 4 == 3:
                await asyncio.sleep(0)

        pos = 0
        for idx, (note, beats) in enumerate(BASS):
            dur = beats * beat
            _mix_into(mix, _note_buf(_FREQS[note], dur, sr, vol=0.18), pos)
            pos += int(dur * sr)
            if idx % 4 == 3:
                await asyncio.sleep(0)

        buf = array.array('h', [max(-32767, min(32767, int(s * 32767))) for s in mix])
        return pygame.mixer.Sound(buffer=buf)
    except Exception as e:
        print("Victory music gen failed:", e)
        return None


# ── Start screen ──────────────────────────────────────────────────────────────
def draw_start_screen(surface, font_xl, font_title, font_s, frame):
    # Sky
    surface.fill((18, 12, 45))

    # Scale factor: all original x positions were designed for 640px width
    sc = SCREEN_W / 640.0

    # Ground sits at 72% of screen height, leaving 28% for title text below
    GND = int(SCREEN_H * 0.72)   # 259 at 360px height

    # Twinkling stars (above ground)
    rng = random.Random(77)
    for _ in range(90):
        sx = rng.randint(0, SCREEN_W)
        sy = rng.randint(0, GND - 20)
        br = rng.randint(140, 255)
        if (frame // 25 + rng.randint(0, 3)) % 4:
            pygame.draw.circle(surface, (br, br, br), (sx, sy), 1)

    # Crescent moon (upper-right, scaled)
    mx = int(SCREEN_W * 0.85)
    pygame.draw.circle(surface, (245, 235, 175), (mx, 45), 28)
    pygame.draw.circle(surface, (18, 12, 45),    (mx + 12, 37), 22)

    # ── Castle silhouette ─────────────────────────────────────────────────────
    C = (16, 10, 30)

    def battlements(x, w, y, bw=12, bh=15, gap=4):
        for bx in range(x, x + w, bw + gap):
            pygame.draw.rect(surface, C, (bx, y - bh, min(bw, x + w - bx), bh))

    def window(x, y, w=8, h=13):
        pygame.draw.rect(surface, (12, 8, 22), (x, y, w, h))
        pygame.draw.rect(surface, (90, 55, 15), (x+1, y+1, w-2, h-2))

    def sx(v): return int(v * sc)   # scale an x value

    # Ground
    pygame.draw.rect(surface, (12, 10, 20), (0, GND, SCREEN_W, SCREEN_H - GND))

    # Moat
    pygame.draw.rect(surface, (18, 28, 80), (SCREEN_W//2 - sx(110), GND, sx(220), 10))

    # Far left small tower
    pygame.draw.rect(surface, C, (sx(88), GND - 58, sx(46), 58))
    battlements(sx(88), sx(46), GND - 58, sx(10), 11, sx(3))
    window(sx(104), GND - 44)

    # Far right small tower
    pygame.draw.rect(surface, C, (sx(506), GND - 58, sx(46), 58))
    battlements(sx(506), sx(46), GND - 58, sx(10), 11, sx(3))
    window(sx(516), GND - 44)

    # Left curtain wall
    pygame.draw.rect(surface, C, (sx(134), GND - 35, sx(86), 35))
    battlements(sx(134), sx(86), GND - 35, sx(11), 11, sx(3))

    # Right curtain wall
    pygame.draw.rect(surface, C, (sx(420), GND - 35, sx(86), 35))
    battlements(sx(420), sx(86), GND - 35, sx(11), 11, sx(3))

    # Left tower
    pygame.draw.rect(surface, C, (sx(164), GND - 84, sx(68), 84))
    battlements(sx(164), sx(68), GND - 84, sx(12), 13, sx(3))
    window(sx(177), GND - 72)
    window(sx(177), GND - 52)

    # Right tower
    pygame.draw.rect(surface, C, (sx(408), GND - 84, sx(68), 84))
    battlements(sx(408), sx(68), GND - 84, sx(12), 13, sx(3))
    window(sx(421), GND - 72)
    window(sx(421), GND - 52)

    # Main keep
    pygame.draw.rect(surface, C, (sx(256), GND - 118, sx(128), 118))
    battlements(sx(256), sx(128), GND - 118, sx(14), 15, sx(4))
    window(sx(278), GND - 102)
    window(sx(306), GND - 102)
    window(sx(278), GND - 78)
    window(sx(306), GND - 78)

    # Gate arch
    gx, gy = SCREEN_W // 2 - sx(26), GND - 58
    pygame.draw.rect(surface, (10, 6, 18), (gx, gy, sx(52), 58))
    pygame.draw.circle(surface, (10, 6, 18), (SCREEN_W // 2, gy + 1), sx(26))
    for bar_x in range(gx + sx(6), gx + sx(52), sx(10)):
        pygame.draw.line(surface, (30, 20, 50), (bar_x, gy), (bar_x, GND), 2)
    pygame.draw.line(surface, (30, 20, 50), (gx, gy + 20), (gx + sx(52), gy + 20), 2)
    pygame.draw.line(surface, (30, 20, 50), (gx, gy + 40), (gx + sx(52), gy + 40), 2)

    # Flag on main keep
    flag_phase = frame * 0.08
    flag_x = SCREEN_W // 2 + 4
    flag_y = GND - 132
    pygame.draw.line(surface, (160, 140, 100), (flag_x, flag_y), (flag_x, flag_y - 24), 2)
    pts = [(flag_x, flag_y - 24),
           (flag_x + int(16 * math.cos(flag_phase)), flag_y - 17 + int(4 * math.sin(flag_phase))),
           (flag_x, flag_y - 8)]
    pygame.draw.polygon(surface, RED, pts)

    # ── Title block (below castle) ────────────────────────────────────────────
    ty = GND + 10

    # Decorative line
    pygame.draw.line(surface, (120, 100, 40), (30, ty - 2), (SCREEN_W - 30, ty - 2), 1)

    # Title
    sh = font_xl.render("ADVENTURE  REBORN", True, (50, 30, 5))
    surface.blit(sh, (SCREEN_W // 2 - sh.get_width() // 2 + 2, ty + 2))
    t1 = font_xl.render("ADVENTURE  REBORN", True, (255, 215, 50))
    surface.blit(t1, (SCREEN_W // 2 - t1.get_width() // 2, ty))

    # Subtitle
    sub = font_title.render("A Quest for the Golden Chalice", True, (190, 165, 110))
    surface.blit(sub, (SCREEN_W // 2 - sub.get_width() // 2, ty + 22))

    # Blinking prompt
    if (frame // 28) % 2 == 0:
        prompt = font_s.render("Press any key to begin", True, (220, 210, 180))
        surface.blit(prompt, (SCREEN_W // 2 - prompt.get_width() // 2, ty + 44))


# ── Sound ─────────────────────────────────────────────────────────────────────
def _make_beep(freq=440, duration=0.12, vol=0.35, sample_rate=22050):
    """Generate a mono 16-bit sine-wave Sound. Returns None on failure."""
    try:
        n   = int(sample_rate * duration)
        buf = array.array('h', [0] * n)
        for i in range(n):
            fade     = 1.0 - i / n
            buf[i]   = int(vol * 32767 * fade * math.sin(2 * math.pi * freq * i / sample_rate))
        return pygame.mixer.Sound(buffer=buf)
    except Exception:
        return None

def _make_chord(freqs, duration=0.18, vol=0.3, sample_rate=22050):
    try:
        n   = int(sample_rate * duration)
        buf = array.array('h', [0] * n)
        for i in range(n):
            fade = 1.0 - i / n
            s    = sum(math.sin(2 * math.pi * f * i / sample_rate) for f in freqs)
            buf[i] = int(vol * 32767 * fade * s / len(freqs))
        return pygame.mixer.Sound(buffer=buf)
    except Exception:
        return None

def init_sounds():
    try:
        pygame.mixer.pre_init(22050, -16, 1, 512)
        pygame.mixer.init()
    except Exception:
        pass
    return {
        "pickup":   _make_beep(880,  0.10),
        "hurt":     _make_beep(220,  0.15, vol=0.5),
        "death":    _make_beep(150,  0.25, vol=0.5),
        "levelup":  _make_chord([523, 659, 784], 0.30),
        "unlock":   _make_chord([440, 554], 0.20),
        "chalice":  _make_chord([523, 659, 784, 1047], 0.50),
    }

def play(sounds, name):
    s = sounds.get(name)
    if s:
        try: s.play()
        except Exception: pass


# ── NPC ───────────────────────────────────────────────────────────────────────
class NPC:
    def __init__(self, name, x, y, lines, col=(220, 180, 80)):
        self.name  = name
        self.x     = x
        self.y     = y
        self.lines = lines
        self.col   = col
        self.bob   = 0.0

    @property
    def rect(self):
        return pygame.Rect(self.x - 14, self.y - 24, 28, 38)

    def draw(self, surface):
        self.bob += 0.05
        cy_off = int(math.sin(self.bob) * 2)
        cx, cy = self.x, self.y + cy_off
        # Robe
        pygame.draw.polygon(surface, self.col,
            [(cx-10, cy+10), (cx-14, cy+24), (cx+14, cy+24), (cx+10, cy+10)])
        # Torso
        pygame.draw.rect(surface, self.col, (cx-8, cy-6, 16, 16))
        # Head
        pygame.draw.circle(surface, (240, 210, 160), (cx, cy-12), 9)
        # Wizard hat
        pygame.draw.polygon(surface, (70, 30, 110),
            [(cx-10, cy-17), (cx, cy-34), (cx+10, cy-17)])
        pygame.draw.rect(surface, (90, 45, 130), (cx-12, cy-19, 24, 4))
        # Eyes
        pygame.draw.circle(surface, BLACK, (cx-3, cy-13), 2)
        pygame.draw.circle(surface, BLACK, (cx+3, cy-13), 2)
        # Star on hat
        pygame.draw.circle(surface, YELLOW, (cx, cy-26), 2)


# ── Dialogue box ──────────────────────────────────────────────────────────────
class DialogueBox:
    H   = 94
    PAD = 12

    def __init__(self, font_s, font_l):
        self.font_s  = font_s
        self.font_l  = font_l
        self.active  = False
        self.npc     = None
        self.page    = 0

    def open(self, npc):
        self.npc    = npc
        self.page   = 0
        self.active = True

    def advance(self):
        if not self.active: return
        self.page += 1
        if self.page >= len(self.npc.lines):
            self.active = False
            self.npc    = None

    def draw(self, surface):
        if not self.active: return
        by = PLAY_TOP + PLAY_H - self.H
        pygame.draw.rect(surface, (10, 10, 35), (0, by, SCREEN_W, self.H))
        pygame.draw.rect(surface, (120, 100, 200), (0, by, SCREEN_W, self.H), 2)

        name_surf = self.font_l.render(self.npc.name, True, (220, 200, 80))
        surface.blit(name_surf, (self.PAD, by + self.PAD))

        # Word-wrap text
        words, rows, cur = self.npc.lines[self.page].split(), [], ""
        for w in words:
            test = (cur + " " + w).strip()
            if len(test) > 70:
                rows.append(cur); cur = w
            else:
                cur = test
        if cur: rows.append(cur)
        for i, row in enumerate(rows[:3]):
            surface.blit(self.font_s.render(row, True, WHITE),
                         (self.PAD, by + 30 + i * 17))

        prompt = self.font_s.render("E / Tap to continue", True, GRAY)
        surface.blit(prompt, (SCREEN_W - prompt.get_width() - self.PAD, by + self.H - 16))


# ── Touch D-pad ───────────────────────────────────────────────────────────────
def _is_portrait():
    """Detect if browser is in portrait orientation via JS global set by index.html."""
    try:
        import platform as _plt
        return bool(getattr(_plt.window, 'PORTRAIT_MODE', False))
    except Exception:
        return False

_TOUCH_DEVICE = None
def _is_touch_device():
    """Return True if device has a touch screen (mobile). Cached after first call."""
    global _TOUCH_DEVICE
    if _TOUCH_DEVICE is None:
        try:
            import platform as _plt
            mtp = getattr(_plt.window.navigator, 'maxTouchPoints', 0)
            _TOUCH_DEVICE = int(mtp) > 0
        except Exception:
            _TOUCH_DEVICE = False
    return _TOUCH_DEVICE


class TouchDpad:
    BTN = 80   # large tap target — fat-finger friendly
    GAP = 24   # gap between buttons — no overlap

    def __init__(self, font_s):
        self.font_s = font_s
        B  = self.BTN
        G  = self.GAP
        cx = 105
        cy = PLAY_TOP + PLAY_H - 110
        self.dir_rects = {
            "up":    pygame.Rect(cx - B//2, cy - B - G, B, B),
            "down":  pygame.Rect(cx - B//2, cy + G,     B, B),
            "left":  pygame.Rect(cx - B - G, cy - B//2, B, B),
            "right": pygame.Rect(cx + G,     cy - B//2, B, B),
        }
        rx = SCREEN_W - 90
        ry = PLAY_TOP + PLAY_H - 110
        self.inv_rect  = pygame.Rect(rx - B//2, ry - B//2, B, B)
        self.talk_rect = pygame.Rect(rx - B//2, ry - B//2 - B - G, B, B)

        self._finger_dirs = {}   # finger_id -> dir name
        self._mouse_dirs  = set()
        self._inv_tapped  = False
        self._talk_tapped = False

    def _finger_to_game(self, fx, fy):
        """Convert normalised finger coords to game-pixel coords.
        In portrait mode the canvas is CSS-rotated -90° so coords need remapping."""
        if _is_portrait():
            # rotate(-90deg): visual (vx,vy) → canvas (1-vy)*W, vx*H
            return int((1.0 - fy) * SCREEN_W), int(fx * SCREEN_H)
        return int(fx * SCREEN_W), int(fy * SCREEN_H)

    def handle_event(self, event):
        self._inv_tapped  = False
        self._talk_tapped = False

        if event.type in (pygame.FINGERDOWN, pygame.FINGERMOTION):
            px, py = self._finger_to_game(event.x, event.y)
            for name, rect in self.dir_rects.items():
                if rect.collidepoint(px, py):
                    self._finger_dirs[event.finger_id] = name
            if self.inv_rect.collidepoint(px, py)  and event.type == pygame.FINGERDOWN:
                self._inv_tapped = True
            if self.talk_rect.collidepoint(px, py) and event.type == pygame.FINGERDOWN:
                self._talk_tapped = True

        elif event.type == pygame.FINGERUP:
            self._finger_dirs.pop(event.finger_id, None)

        elif event.type == pygame.MOUSEBUTTONDOWN:
            for name, rect in self.dir_rects.items():
                if rect.collidepoint(event.pos):
                    self._mouse_dirs.add(name)
            if self.inv_rect.collidepoint(event.pos):  self._inv_tapped  = True
            if self.talk_rect.collidepoint(event.pos): self._talk_tapped = True

        elif event.type == pygame.MOUSEBUTTONUP:
            self._mouse_dirs.clear()

    def reset(self):
        """Clear all active directions — call when leaving non-gameplay states."""
        self._finger_dirs.clear()
        self._mouse_dirs.clear()

    @property
    def dx(self):
        dirs = set(self._finger_dirs.values()) | self._mouse_dirs
        return (PLAYER_SPEED if "right" in dirs else 0) - (PLAYER_SPEED if "left" in dirs else 0)

    @property
    def dy(self):
        dirs = set(self._finger_dirs.values()) | self._mouse_dirs
        return (PLAYER_SPEED if "down" in dirs else 0) - (PLAYER_SPEED if "up" in dirs else 0)

    def draw(self, surface):
        if not _is_touch_device():
            return
        active = set(self._finger_dirs.values()) | self._mouse_dirs
        arrows = {"up": "^", "down": "v", "left": "<", "right": ">"}
        for name, rect in self.dir_rects.items():
            col = (140, 140, 190, 190) if name in active else (60, 60, 90, 150)
            s = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
            s.fill(col)
            surface.blit(s, rect)
            pygame.draw.rect(surface, (160, 160, 210), rect, 1)
            t = self.font_s.render(arrows[name], True, WHITE)
            surface.blit(t, (rect.centerx - t.get_width()//2,
                             rect.centery - t.get_height()//2))

        for rect, label in [(self.inv_rect, "INV"), (self.talk_rect, "TALK")]:
            s = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
            s.fill((60, 60, 90, 150))
            surface.blit(s, rect)
            pygame.draw.rect(surface, (160, 160, 210), rect, 1)
            t = self.font_s.render(label, True, WHITE)
            surface.blit(t, (rect.centerx - t.get_width()//2,
                             rect.centery - t.get_height()//2))


# ── Win / Game Over screens ───────────────────────────────────────────────────
def draw_win_screen(surface, font_l, font_s, frame, flash_timer=0):
    surface.fill((10, 10, 40))
    # Animated star field
    rng = random.Random(42)
    for _ in range(60):
        sx = rng.randint(0, SCREEN_W)
        sy = rng.randint(0, SCREEN_H)
        if (frame // 20 + rng.randint(0,1)) % 2:
            pygame.draw.circle(surface, WHITE, (sx, sy), 1)
    # Chalice icon
    _draw_item_icon(surface, {"type":"chalice","name":"Golden Chalice"},
                    SCREEN_W//2, 120, 24)
    t1 = font_l.render("YOU WIN!", True, YELLOW)
    t2 = font_s.render("You retrieved the Golden Chalice!", True, WHITE)
    t3 = font_s.render("Press R or tap to play again", True, GRAY)
    surface.blit(t1, (SCREEN_W//2 - t1.get_width()//2, 170))
    surface.blit(t2, (SCREEN_W//2 - t2.get_width()//2, 200))
    surface.blit(t3, (SCREEN_W//2 - t3.get_width()//2, 230))
    # Victory flash overlay — gold/white burst that fades out
    if flash_timer > 0:
        alpha = min(220, int(220 * flash_timer / 90))
        # Alternate gold and white for a flickering burst
        col = (255, 240, 100) if (flash_timer // 4) % 2 == 0 else (255, 255, 255)
        flash_surf = pygame.Surface((SCREEN_W, SCREEN_H))
        flash_surf.fill(col)
        flash_surf.set_alpha(alpha)
        surface.blit(flash_surf, (0, 0))

def draw_gameover_screen(surface, font_l, font_s):
    surface.fill((18, 4, 4))
    t1 = font_l.render("GAME OVER", True, RED)
    t2 = font_s.render("You have fallen in battle.", True, (200, 180, 180))
    t3 = font_s.render("Press R or tap to try again", True, GRAY)
    surface.blit(t1, (SCREEN_W//2 - t1.get_width()//2, 170))
    surface.blit(t2, (SCREEN_W//2 - t2.get_width()//2, 200))
    surface.blit(t3, (SCREEN_W//2 - t3.get_width()//2, 230))


# ── Inventory helpers ─────────────────────────────────────────────────────────
def _use_item(player, idx):
    """Use or equip/unequip the item at inventory slot idx."""
    item = player.inventory[idx]
    if item["type"] == "potion":
        player.hp = min(player.max_hp, player.hp + item["hp"])
        player.inventory.pop(idx)
    elif item["type"] == "sword":
        if player.weapon is item:
            player.attack -= item["atk"]
            player.weapon  = None
        else:
            if player.weapon:
                player.attack -= player.weapon["atk"]
            player.weapon  = item
            player.attack += item["atk"]
    elif item["type"] == "shield":
        if player.shield is item:
            player.defense -= item["def"]
            player.shield   = None
        else:
            if player.shield:
                player.defense -= player.shield["def"]
            player.shield   = item
            player.defense += item["def"]


def _drop_item(player, idx, room_id, room_items, drop_x, drop_y):
    """Remove item from inventory and place it on the floor."""
    item = player.inventory[idx]
    # Unequip if equipped
    if item is player.weapon:
        player.attack -= item["atk"]
        player.weapon  = None
    if item is player.shield:
        player.defense -= item["def"]
        player.shield   = None
    player.inventory.pop(idx)
    # Scatter slightly so stacked items are reachable
    offset_x = random.randint(-20, 20)
    offset_y = random.randint(-20, 20)
    room_items.setdefault(room_id, []).append(
        FloorItem(item, int(drop_x) + offset_x, int(drop_y) + offset_y)
    )


def _inv_slot_at(mouse_pos):
    """Return inventory slot index (0-7) under mouse_pos, or None."""
    SLOT = InventoryScreen.SLOT
    PAD  = InventoryScreen.PAD
    COLS = InventoryScreen.COLS
    ox = SCREEN_W // 2 - (COLS * (SLOT + PAD)) // 2
    oy = 60
    mx, my = mouse_pos
    for i in range(8):
        col_i = i % COLS
        row_i = i // COLS
        sx = ox + col_i * (SLOT + PAD)
        sy = oy + row_i * (SLOT + PAD)
        if sx <= mx <= sx + SLOT and sy <= my <= sy + SLOT:
            return i
    return None


# ── Main game ────────────────────────────────────────────────────────────────
async def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Adventure Reborn")
    clock = pygame.time.Clock()

    # pygame.font.Font(None, size) uses the built-in bitmap font — crisp at all sizes
    font_s     = pygame.font.Font(None, 18)
    font_l     = pygame.font.Font(None, 22)
    font_title = pygame.font.Font(None, 24)
    font_xl    = pygame.font.Font(None, 42)
    sounds     = init_sounds()

    def new_game():
        rooms, room_enemies, room_items, room_npcs = build_world()
        player = Player(SCREEN_W // 2, PLAY_TOP + PLAY_H // 2)
        hud    = HUD(font_s, font_l)
        hud.notify_room(rooms[0].name)
        return rooms, room_enemies, room_items, room_npcs, player, hud, 0, []

    rooms, room_enemies, room_items, room_npcs, player, hud, current_room_id, projectiles = new_game()

    inv_screen  = InventoryScreen(font_s, font_l)
    dialogue    = DialogueBox(font_s, font_l)
    dpad        = TouchDpad(font_s)

    # Game state: "start" | "playing" | "inventory" | "dialogue" | "win" | "gameover"
    state = "start"
    frame = 0
    start_input_delay = 0          # frames elapsed on start screen; ignore input for first 60
    music_sound = None          # start screen music
    music_task = None           # asyncio Future for start music generation
    gameplay_music_sound = None # in-game ominous bass loop
    gameplay_music_task = None  # asyncio Future for gameplay music generation
    gameplay_music_started = False
    boss_music_sound = None     # boss room (room 14) music
    boss_music_task = None
    boss_music_started = False
    victory_music_sound = None  # win fanfare
    victory_music_task = None
    victory_music_started = False
    win_flash_timer = 0         # frames remaining for win flash effect

    running = True
    while running:
        clock.tick(FPS)
        frame += 1

        # ── Events ───────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            # Touch / dpad events (always processed)
            dpad.handle_event(event)

            if state == "start":
                if start_input_delay >= 60:
                    interacted = (event.type == pygame.KEYDOWN
                                  or event.type == pygame.MOUSEBUTTONDOWN
                                  or event.type == pygame.FINGERDOWN)
                    if interacted:
                        if music_sound: music_sound.stop()
                        state = "playing"
                        gameplay_music_started = False
                continue

            if state in ("win", "gameover"):
                if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN):
                    rooms, room_enemies, room_items, room_npcs, player, hud, current_room_id, projectiles = new_game()
                    dialogue.active = False
                    if gameplay_music_sound: gameplay_music_sound.stop()
                    if boss_music_sound: boss_music_sound.stop()
                    if victory_music_sound: victory_music_sound.stop()
                    gameplay_music_started = boss_music_started = victory_music_started = False
                    win_flash_timer = 0
                    start_input_delay = 0
                    if music_sound:
                        music_sound.set_volume(0.25)
                        music_sound.play(-1)
                    state = "start"
                continue

            if state == "dialogue":
                if event.type == pygame.KEYDOWN and event.key == pygame.K_e:
                    dialogue.advance()
                    if not dialogue.active: state = "playing"
                if event.type in (pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN):
                    dialogue.advance()
                    if not dialogue.active: state = "playing"
                if dpad._talk_tapped:
                    dialogue.advance()
                    if not dialogue.active: state = "playing"
                continue

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

                if event.key == pygame.K_i:
                    state = "inventory" if state == "playing" else "playing"
                    if state == "playing":
                        dpad.reset()

                if state == "inventory":
                    if pygame.K_1 <= event.key <= pygame.K_8:
                        idx = event.key - pygame.K_1
                        if idx < len(player.inventory):
                            _drop_item(player, idx, current_room_id, room_items,
                                       player.x, player.y)
                elif state == "playing":
                    if pygame.K_1 <= event.key <= pygame.K_8:
                        idx = event.key - pygame.K_1
                        if idx < len(player.inventory):
                            _drop_item(player, idx, current_room_id, room_items,
                                       player.x, player.y)
                    if event.key == pygame.K_e:
                        # Talk to nearby NPC
                        npc = room_npcs.get(current_room_id)
                        if npc and math.hypot(player.x - npc.x, player.y - npc.y) < 50:
                            dialogue.open(npc)
                            state = "dialogue"

            if event.type == pygame.MOUSEBUTTONDOWN:
                if state == "inventory":
                    slot_idx = _inv_slot_at(event.pos)
                    if slot_idx is not None and slot_idx < len(player.inventory):
                        if event.button == 1:
                            _use_item(player, slot_idx)
                        elif event.button == 3:
                            _drop_item(player, slot_idx, current_room_id, room_items,
                                       player.x, player.y)

            # Touch INV button
            if dpad._inv_tapped:
                state = "inventory" if state == "playing" else "playing"
                if state == "playing":
                    dpad.reset()
            # Touch TALK button
            if dpad._talk_tapped and state == "playing":
                npc = room_npcs.get(current_room_id)
                if npc and math.hypot(player.x - npc.x, player.y - npc.y) < 60:
                    dialogue.open(npc)
                    state = "dialogue"

        # ── Non-playing states: just draw ─────────────────────────
        if state == "start":
            start_input_delay += 1
            # Kick off all music generation on first frame
            if music_task is None:
                music_task         = asyncio.ensure_future(make_music_async())
                gameplay_music_task= asyncio.ensure_future(make_gameplay_music_async())
                boss_music_task    = asyncio.ensure_future(make_boss_music_async())
                victory_music_task = asyncio.ensure_future(make_victory_music_async())
            # Auto-play music as soon as it's generated
            if music_task.done() and music_sound is None:
                music_sound = music_task.result()
                if music_sound:
                    music_sound.set_volume(0.25)
                    music_sound.play(-1)
            # Pre-load other music results as they finish
            if gameplay_music_task is not None and gameplay_music_task.done() and gameplay_music_sound is None:
                gameplay_music_sound = gameplay_music_task.result()
            if boss_music_task is not None and boss_music_task.done() and boss_music_sound is None:
                boss_music_sound = boss_music_task.result()
            if victory_music_task is not None and victory_music_task.done() and victory_music_sound is None:
                victory_music_sound = victory_music_task.result()
            draw_start_screen(screen, font_xl, font_title, font_s, frame)
            pygame.display.flip()
            await asyncio.sleep(0)
            continue

        if state == "win":
            draw_win_screen(screen, font_l, font_s, frame, win_flash_timer)
            dpad.draw(screen)
            pygame.display.flip()
            await asyncio.sleep(0)
            continue

        if state == "gameover":
            draw_gameover_screen(screen, font_l, font_s)
            dpad.draw(screen)
            pygame.display.flip()
            await asyncio.sleep(0)
            continue

        if state == "inventory":
            room = rooms[current_room_id]
            screen.fill(BLACK)
            room.draw(screen)
            inv_screen.draw(screen, player)
            dpad.draw(screen)
            pygame.display.flip()
            await asyncio.sleep(0)
            continue

        # ── Movement (playing + dialogue both allow movement except dialogue freezes) ──
        room = rooms[current_room_id]
        if state == "playing":
            keys_pressed = pygame.key.get_pressed()
            dx = dpad.dx
            dy = dpad.dy
            if keys_pressed[pygame.K_LEFT]  or keys_pressed[pygame.K_a]: dx -= PLAYER_SPEED
            if keys_pressed[pygame.K_RIGHT] or keys_pressed[pygame.K_d]: dx += PLAYER_SPEED
            if keys_pressed[pygame.K_UP]    or keys_pressed[pygame.K_w]: dy -= PLAYER_SPEED
            if keys_pressed[pygame.K_DOWN]  or keys_pressed[pygame.K_s]: dy += PLAYER_SPEED
            if dx and dy:
                dx = int(dx * 0.707)
                dy = int(dy * 0.707)
            player.move(dx, dy, room)

        # ── Enemies & combat ─────────────────────────────────────
        if state == "playing":
            enemies_here = room_enemies.get(current_room_id, [])
            for enemy in enemies_here:
                enemy.update(player, room, projectiles)
                if enemy.rect.colliderect(player.rect):
                    if player.hurt_timer <= 0:
                        player.take_damage(enemy.atk)
                        play(sounds, "hurt")

            if player.hurt_timer > 0:
                player.hurt_timer -= 1

            if player.weapon:
                wr = player.weapon_rect()
                for enemy in enemies_here:
                    prev_hp = enemy.hp
                    if wr.colliderect(enemy.rect):
                        enemy.take_damage(player.attack)
                    if enemy.hp < prev_hp and not enemy.alive:
                        play(sounds, "death")

            dead = [e for e in enemies_here if not e.alive]
            for e in dead:
                if player.gain_xp(e.xp):
                    hud.notify_levelup()
                    play(sounds, "levelup")
            room_enemies[current_room_id] = [e for e in enemies_here if e.alive]

            for proj in projectiles:
                proj.update(room)
                if proj.rect.colliderect(player.rect):
                    player.take_damage(12)
                    play(sounds, "hurt")
                    proj.alive = False
            projectiles = [p for p in projectiles if p.alive]

            # ── Room transition ───────────────────────────────────
            result = check_room_transition(player, room, rooms, player.keys)
            if result:
                new_id, sx, sy = result
                if room.locked and any(
                    k in player.keys for k in room.locked.values()
                ):
                    play(sounds, "unlock")
                projectiles.clear()
                current_room_id = new_id
                player.x, player.y = float(sx), float(sy)
                hud.notify_room(rooms[new_id].name)

            # ── Auto-pickup ───────────────────────────────────────
            items_here = room_items.get(current_room_id, [])
            for fi in items_here[:]:
                if player.rect.colliderect(fi.rect):
                    if fi.data["type"] == "key":
                        player.keys.add(fi.data["color"])
                        if len(player.inventory) < 8:
                            player.inventory.append(fi.data)
                        items_here.remove(fi)
                        play(sounds, "pickup")
                    elif len(player.inventory) < 8:
                        player.inventory.append(fi.data)
                        items_here.remove(fi)
                        play(sounds, "pickup")
                        if fi.data["type"] == "sword" and player.weapon is None:
                            player.weapon  = fi.data
                            player.attack += fi.data["atk"]
                        elif fi.data["type"] == "shield" and player.shield is None:
                            player.shield   = fi.data
                            player.defense += fi.data["def"]
                        if fi.data["type"] == "chalice":
                            play(sounds, "chalice")
                            win_flash_timer = 90
                            state = "win"

            # ── Check death ───────────────────────────────────────
            if not player.alive:
                state = "gameover"

        # ── Music routing ────────────────────────────────────────
        in_boss_room = (state == "playing" and current_room_id == 14)

        # Collect finished tasks
        if gameplay_music_task is not None and gameplay_music_task.done() and gameplay_music_sound is None:
            gameplay_music_sound = gameplay_music_task.result()
        if boss_music_task is not None and boss_music_task.done() and boss_music_sound is None:
            boss_music_sound = boss_music_task.result()
        if victory_music_task is not None and victory_music_task.done() and victory_music_sound is None:
            victory_music_sound = victory_music_task.result()

        if state == "win":
            # Stop all gameplay music; victory fanfare plays once
            if gameplay_music_started and gameplay_music_sound:
                gameplay_music_sound.stop()
                gameplay_music_started = False
            if boss_music_started and boss_music_sound:
                boss_music_sound.stop()
                boss_music_started = False
            if not victory_music_started and victory_music_sound:
                victory_music_sound.set_volume(0.55)
                victory_music_sound.play(0)   # play once, no loop
                victory_music_started = True
            if win_flash_timer > 0:
                win_flash_timer -= 1
        elif in_boss_room:
            # Boss room: stop gameplay music, play boss music
            if gameplay_music_started and gameplay_music_sound:
                gameplay_music_sound.stop()
                gameplay_music_started = False
            if not boss_music_started and boss_music_sound:
                boss_music_sound.set_volume(0.45)
                boss_music_sound.play(-1)
                boss_music_started = True
        elif state == "playing":
            # Normal rooms: stop boss music, play gameplay music
            if boss_music_started and boss_music_sound:
                boss_music_sound.stop()
                boss_music_started = False
            if not gameplay_music_started and gameplay_music_sound:
                gameplay_music_sound.set_volume(0.35)
                gameplay_music_sound.play(-1)
                gameplay_music_started = True
        else:
            # Non-playing states (gameover, inventory, dialogue): silence both
            if gameplay_music_started and gameplay_music_sound:
                gameplay_music_sound.stop()
                gameplay_music_started = False
            if boss_music_started and boss_music_sound:
                boss_music_sound.stop()
                boss_music_started = False

        # ── Draw ─────────────────────────────────────────────────
        screen.fill(BLACK)
        room.draw(screen)
        room.draw_locked_doors(screen)

        for fi in room_items.get(current_room_id, []):
            fi.draw(screen)

        npc = room_npcs.get(current_room_id)
        if npc:
            npc.draw(screen)
            # "TALK" prompt when nearby
            if math.hypot(player.x - npc.x, player.y - npc.y) < 50:
                tip = font_s.render(f"E / TALK: {npc.name}", True, YELLOW)
                screen.blit(tip, (SCREEN_W//2 - tip.get_width()//2, PLAY_TOP + 8))

        for enemy in room_enemies.get(current_room_id, []):
            enemy.draw(screen)

        for proj in projectiles:
            proj.draw(screen)

        player.draw(screen)
        if player.hurt_timer > 0 and player.hurt_timer % 4 < 2:
            flash = pygame.Surface((player.W, player.H), pygame.SRCALPHA)
            flash.fill((255, 0, 0, 100))
            screen.blit(flash, player.rect)

        hud.draw(screen, player, rooms[current_room_id].name)
        dpad.draw(screen)

        if state == "dialogue":
            dialogue.draw(screen)

        pygame.display.flip()
        await asyncio.sleep(0)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    asyncio.run(main())
