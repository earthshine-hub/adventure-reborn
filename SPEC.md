# Adventure Reborn — Game Specification

## Overview

A top-down pixel art action-RPG inspired by the Atari 2600 game *Adventure*. The player explores a small interconnected world, collects items, fights enemies, and ultimately retrieves the **Golden Chalice** from a guarded castle.

**Engine:** Python 3 + Pygame
**Window:** 640×480, 60fps
**Controls:** WASD/arrows to move, E to interact, I for inventory, Space/Z to attack
**Art:** All graphics drawn with `pygame.draw` primitives — no external assets required

---

## World

15 rooms across 3 zones connected by directional doorways.

```
Zone 1 — Overworld (rooms 0–4)   Zone 2 — Dungeon (rooms 5–9)   Zone 3 — Castle (rooms 10–14)
  [0]—[1]—[2]—[3]—[4]               [5]—[6]—[7]—[8]—[9]              [10]—[11]═[12]—[13]═[14]
   |           |                      |       |                           |        |
  (to 5)     (to 7)                 (to 0) (to 2,12)                  (to 5)  (to 7)
```

`═` = locked door. Room 11 requires the Red Key; Room 13 requires the Yellow Key.

Room 14 (the throne room) contains the Dragon boss and the Golden Chalice.

---

## Entities

### Player
- Stats: HP, maxHP, Attack, Defense, XP, Level
- Levels up at XP thresholds (50, 150, 300, …), increasing stats
- Inventory: up to 8 items; one weapon and one shield can be equipped

### Enemies

| Name     | Color  | Speed | HP  | Attack | XP  | Behavior                          |
|----------|--------|-------|-----|--------|-----|-----------------------------------|
| Slime    | Green  | Slow  | 10  | 3      | 10  | Random wander                     |
| Bat      | Purple | Fast  | 5   | 2      | 8   | Erratic chase when player nearby  |
| Skeleton | White  | Med   | 20  | 6      | 20  | Patrols, aggros on sight          |
| Dragon   | Red    | Slow  | 80  | 12     | 100 | Fires projectiles; boss of room 14|

### Items

| Item          | Effect                              | Found in       |
|---------------|-------------------------------------|----------------|
| Sword         | Equippable; +4 Attack               | Room 1         |
| Magic Sword   | Equippable; +10 Attack              | Room 13        |
| Shield        | Equippable; +3 Defense              | Room 6         |
| Red Key       | Opens locked door to room 12        | Room 9         |
| Yellow Key    | Opens locked door to room 14        | Room 8         |
| Health Potion | Restores 20 HP when used            | Rooms 3, 6, 11 |
| Golden Chalice| Win condition                       | Room 14        |

### NPCs
- **Aldric the Wizard** (Room 2): Hints about the dungeon and keys
- **Ghost of the Knight** (Room 10): Warns about the Dragon; hints at the Magic Sword

---

## UI / HUD

- **Top-left:** HP bar (red), XP bar (yellow), Level label
- **Top-center:** Current room name
- **Bottom strip:** First 4 inventory slots shown at all times
- **Inventory screen (I key):** Full-screen overlay, all 8 slots, use/equip with number keys or click
- **Dialogue box:** Appears at screen bottom when talking to an NPC; advance with E

---

## Win / Lose

- **Win:** Picking up the Golden Chalice triggers a victory screen
- **Lose:** HP hits 0 → Game Over screen with Restart option

---

## Milestones

### Milestone 1 — Core Engine
*Goal: A playable world you can walk through.*

- [ ] Pygame window, game loop, 60fps clock
- [ ] Room class: tile grid (wall/floor/door), rendering with zone-appropriate colors
- [ ] Room transitions (walk through a doorway → load adjacent room)
- [ ] Player class: movement, wall collision, pixel-art sprite
- [ ] HUD: HP bar, room name
- [ ] All 15 rooms defined with correct connections and locked-door flags

**Deliverable:** Player can walk through all 15 rooms; locked doors block passage.

---

### Milestone 2 — Combat & Items
*Goal: The game loop is complete — fight, loot, level up.*

- [ ] Enemy base class + 4 enemy types with sprites and behavior (wander/patrol/chase/projectile)
- [ ] Combat: player attack swing (hitbox + animation flash), enemy melee damage, death + XP reward
- [ ] Dragon projectile system
- [ ] Item class: floor items with pickup (E key)
- [ ] Inventory screen (I key): display, equip weapons/shield, use potions
- [ ] All items placed in correct rooms; keys unlock correct doors
- [ ] Player leveling (XP thresholds → stat increases + level-up flash)
- [ ] Enemy spawns placed in correct rooms per design

**Deliverable:** Full combat loop; player can clear rooms, collect items, open locked doors.

---

### Milestone 3 — Story, Polish & Win/Lose
*Goal: A complete, releasable game.*

- [ ] NPC dialogue system: dialogue box, multi-line text, advance with E
- [ ] Aldric and Ghost of the Knight with their dialogue lines
- [ ] Win screen: triggered by picking up the Golden Chalice
- [ ] Game Over screen with Restart (reload room 0, reset player)
- [ ] Sound effects via `pygame.mixer`: footstep, sword swing, enemy death, item pickup, door unlock
- [ ] Room name transitions (fade-in text on room enter)
- [ ] Inventory bottom-strip always visible
- [ ] Final playtesting pass: balance enemy stats, XP curve, item placement

**Deliverable:** Complete, playable game from start to win/lose screen.
