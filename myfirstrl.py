__author__ = "Steven Sarasin <tutoringsteve@gmail.com"

import libtcodpy as libtcod
import math

# size of the map
MAP_WIDTH = 80
MAP_HEIGHT = 45

STAT_PANEL_WIDTH = 20
STAT_PANEL_HEIGHT = MAP_HEIGHT

# window size
SCREEN_WIDTH = STAT_PANEL_WIDTH + MAP_WIDTH
SCREEN_HEIGHT = MAP_HEIGHT

ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 26

MAX_ROOM_MONSTERS = 3

FOV_ALGO = 0
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10

fov_recompute = True

LIMIT_FPS = 20

color_dark_wall = libtcod.Color(r=0, g=0, b=100)
color_lit_wall = libtcod.Color(r=130, g=110, b=50)
color_dark_ground = libtcod.Color(r=50, g=50, b=150)
color_lit_ground = libtcod.Color(r=200, g=180, b=50)


class Tile:
    # a tile of the map and its properties
    def __init__(self, blocked, block_sight=None):
        self.blocked = blocked
        self.explored = False

        # by default, if a tile is blocked, it also blocks sight
        if block_sight is None:
            block_sight = blocked
        self.block_sight = block_sight


def make_map():
    global tile_map
    rooms = []
    num_rooms = 0

    # fill map with "unblocked" tiles
    tile_map = [[Tile(blocked=True) for y in xrange(MAP_HEIGHT)] for x in xrange(MAP_WIDTH)]

    for r in xrange(MAX_ROOMS):
        # random width and height
        w = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        h = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        x = libtcod.random_get_int(0, 0, MAP_WIDTH - w - 1)
        y = libtcod.random_get_int(0, 0, MAP_HEIGHT - h - 1)

        new_room = Rect(x, y, w, h)

        failed = False
        if in_map(x, y) and in_map(x + w, y + h):
            for other_room in rooms:
                if new_room.intersects(other_room):
                    failed = True
                    break
        else:
            failed = True
            r -= 1

        if not failed:
            create_room(new_room)
            # add some contents to this room, such as monsters
            place_objects(new_room)

            new_x, new_y = new_room.center()

            # optional: print "room number" to see how the map drawing works
            # room_no = Object(new_x, new_y, chr(65 + num_rooms), chr(65 + num_rooms), libtcod.white)
            # objects.insert(0, room_no)
            if num_rooms == 0:
                # place character center of first room
                player.x, player.y = new_room.center()
            else:
                # from second room and beyond connect via tunnel
                prev_x, prev_y = rooms[-1].center()

                # coin toss (random int either 0 or 1)
                if libtcod.random_get_int(0, 0, 1) == 1:
                    create_h_tunnel(prev_x, new_x, prev_y)
                    create_v_tunnel(new_x, prev_y, new_y)
                else:
                    create_v_tunnel(prev_x, prev_y, new_y)
                    create_h_tunnel(prev_x, new_x, new_y)
            rooms.append(new_room)
            num_rooms += 1


def midpoint(x1, y1, x2, y2):
    return (x1 + x2) / 2, (y1 + y2) / 2


class Rect:
    # a rectangle on the map. used to characterize a room.
    def __init__(self, x, y, w, h):
        self.x1, self.y1 = x, y
        self.x2, self.y2 = x + w, y + h

    def center(self):
        return midpoint(self.x1, self.y1, self.x2, self.y2)

    def intersects(self, other):
        return (self.x1 <= other.x2 and self.x2 >= other.x1 and
                self.y1 <= other.y2 and self.y2 >= other.y1)


def in_map(x, y):
    return (x in xrange(MAP_WIDTH)) and (y in xrange(MAP_HEIGHT))


def is_blocked(x, y):
    if tile_map[x][y].blocked:
        return True

    for object in objects:
        if object.blocks and ((object.x, object.y) == (x, y)):
            return True

    return False


def create_h_tunnel(x1, x2, y):
    x1, x2 = min(x1, x2), max(x1, x2)
    for x in xrange(x1, x2 + 1):
        if in_map(x, y):
            tile_map[x][y].blocked = False
            tile_map[x][y].block_sight = False


def create_v_tunnel(x, y1, y2):
    y1, y2 = min(y1, y2), max(y1, y2)
    for y in xrange(y1, y2 + 1):
        if in_map(x, y):
            tile_map[x][y].blocked = False
            tile_map[x][y].block_sight = False


def create_room(room):
    # go through the tiles in the rectangle and make them passable
    for x in xrange(room.x1 + 1, room.x2):
        for y in xrange(room.y1 + 1, room.y2):
            if in_map(x, y):
                tile_map[x][y].blocked = False
                tile_map[x][y].block_sight = False


libtcod.console_set_custom_font('arial10x10.png', libtcod.FONT_TYPE_GRAYSCALE | libtcod.FONT_LAYOUT_TCOD)
libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'python/libtcod tutorial', False)
con = libtcod.console_new(MAP_WIDTH, MAP_HEIGHT)
stat_con = libtcod.console_new(STAT_PANEL_WIDTH, STAT_PANEL_HEIGHT)

# will have no effect on turn-based games
libtcod.sys_set_fps(LIMIT_FPS)


def player_death(player):
    global game_state
    print 'You have been killed!'
    game_state = 'dead'

    # change player look to corpse on death
    player.char = '%'
    player.color = libtcod.dark_red


def monster_death(monster):
    # transform monster into corpse! It no longer has AI and no longer blocks
    print monster.name.capitalize(), 'has been killed!'
    monster.char = '%'
    monster.color = libtcod.dark_red
    monster.blocks = False
    monster.fighter = None
    monster.AI = None
    monster.name = 'remains of ' + monster.name
    monster.send_to_back()


class Fighter:
    # combat-related properties and methods (monster, player, NPC)
    def __init__(self, hp, defense, power, death_function=None):
        self.max_hp = hp
        self.hp = hp
        self.defense = defense
        self.power = power
        self.death_function = death_function

    def take_damage(self, damage):
        # apply damage if possible
        if damage > 0:
            self.hp -= damage

        # check for death and call death function if there is one
        if self.hp <= 0:
            function = self.death_function
            if function is not None:
                function(self.owner)

    def attack(self, target):
        # a simple formula for attack damage
        damage = self.power - target.fighter.defense

        if damage > 0:
            # make the target take some damage
            print self.owner.name.capitalize(), 'attacks', target.name, 'for', str(damage), 'hit points.'
            target.fighter.take_damage(damage)
        else:
            print self.owner.name.capitalize(), 'attacks', target.name, 'for no damage!'


class BasicMonster:
    # AI for a basic monster:
    def take_turn(self):
        # a basic monster takes its turn. If you can see it, it will chase
        monster = self.owner
        if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):

            # move towards player if far away
            # close enough, attack! (if the player is still alive.)
            if monster.distance_to(player) >= 2:
                monster.move_towards(player.x, player.y)
            elif player.fighter.hp > 0:
                monster.fighter.attack(player)


class Object:
    # this is a generic object: the player, a monster, an item, the stairs...
    # it's always represented by a character on screen.
    def __init__(self, x, y, char, name, color, blocks=False, fighter=None, AI=None):
        self.x = x
        self.y = y
        self.char = char
        self.name = name
        self.color = color
        self.blocks = blocks

        self.fighter = fighter
        if self.fighter:
            self.fighter.owner = self

        self.AI = AI
        if self.AI:
            self.AI.owner = self

    def move(self, dx, dy):
        if (in_map(self.x + dx, self.y + dy)) and (not is_blocked(self.x + dx, self.y + dy)):
            # move by the given amount
            self.x += dx
            self.y += dy

    def distance_to(self, other):
        # return the distance to another Object
        dx = other.x - self.x
        dy = other.y - self.y
        return math.sqrt(dx**2 + dy**2)

    def move_towards(self, target_x, target_y):
        # vector from current location to desired location
        dx = target_x - self.x
        dy = target_y - self.y
        distance = math.sqrt(dx**2 + dy**2)

        # normalize vector
        dx = int(round(dx/distance))
        dy = int(round(dy/distance))
        self.move(dx, dy)

    def draw(self):
        # set the color and then
        libtcod.console_set_default_foreground(con, self.color)
        libtcod.console_put_char(con, self.x, self.y, self.char, libtcod.BKGND_NONE)

    def clear(self):
        # erase the character that represents this object
        libtcod.console_put_char(con, self.x, self.y, ' ', libtcod.BKGND_NONE)

    def send_to_back(self):
        # make this object drawn first, so others will be drawn instead if occupying same
        # tile
        global objects
        objects.remove(self)
        objects.insert(0, self)

def place_objects(room):
    # choose random number of monsters
    num_monsters = libtcod.random_get_int(0, 0, MAX_ROOM_MONSTERS)

    for i in xrange(num_monsters):
        # choose random spot for this monster within the given room
        x = libtcod.random_get_int(0, room.x1, room.x2)
        y = libtcod.random_get_int(0, room.y1, room.y2)

        if not is_blocked(x, y):
            if libtcod.random_get_int(0, 0, 100) < 80:
                # create an orc (80% chance)
                fighter_component = Fighter(hp=10, defense=0, power=3, death_function=monster_death)
                ai_component = BasicMonster()

                monster = Object(x, y, 'o', 'Pathetic Orc', libtcod.desaturated_green, blocks=True,
                                 fighter=fighter_component, AI=ai_component)
            else:
                # create a Troll (20% chance)
                fighter_component = Fighter(hp=16, defense=1, power=4, death_function=monster_death)
                ai_component = BasicMonster()

                monster = Object(x, y, 'T', 'Troll Runt', libtcod.darker_green, blocks=True, fighter=fighter_component,
                                 AI=ai_component)

            objects.append(monster)


fighter_component = Fighter(hp=30, defense=2, power=5, death_function=player_death)
player = Object(25, 23, '@', 'The Player <You>', libtcod.white, blocks=True, fighter=fighter_component)
objects = [player]


def player_move_or_attack(dx, dy):
    global fov_recompute

    # the coordinates the player is attempting to move to/attack
    x = player.x + dx
    y = player.y + dy

    # find an attackable object at (x, y)
    target = None
    for object in objects:
        if (object.x, object.y) == (x, y):
            target = object
            break

    # attack if target found, move otherwise
    if target is not None and target.blocks:
        if target.fighter:
            player.fighter.attack(target)
    else:
        player.move(dx, dy)
        fov_recompute = True


def handle_keys():
    global fov_recompute

    key = libtcod.console_check_for_keypress(True)
    if key.vk == libtcod.KEY_ENTER and key.lalt:
        # Alt + Enter: toggle fullscreen
        libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
    elif key.vk == libtcod.KEY_ESCAPE:
        return 'exit'

    if game_state == 'playing':
        # movement keys
        if libtcod.console_is_key_pressed(libtcod.KEY_UP):
            player_move_or_attack(0, -1)
        elif libtcod.console_is_key_pressed(libtcod.KEY_DOWN):
            player_move_or_attack(0, 1)
        elif libtcod.console_is_key_pressed(libtcod.KEY_LEFT):
            player_move_or_attack(-1, 0)
        elif libtcod.console_is_key_pressed(libtcod.KEY_RIGHT):
            player_move_or_attack(1, 0)
        else:
            return 'didnt-take-turn'


def draw_all():
    global fov_recompute

    if fov_recompute:
        # recompute FOV if needed (the player moved or something)
        fov_recompute = False
        libtcod.map_compute_fov(fov_map, player.x, player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)

        for y in xrange(MAP_HEIGHT):
            for x in xrange(MAP_WIDTH):
                visible = libtcod.map_is_in_fov(fov_map, x, y)
                wall = tile_map[x][y].block_sight
                if not visible:
                    if tile_map[x][y].explored:
                        if wall:
                            libtcod.console_set_char_background(con, x, y, color_dark_wall, libtcod.BKGND_SET)
                        else:
                            libtcod.console_set_char_background(con, x, y, color_dark_ground, libtcod.BKGND_SET)
                else:
                    if wall:
                        libtcod.console_set_char_background(con, x, y, color_lit_wall, libtcod.BKGND_SET)
                    else:
                        libtcod.console_set_char_background(con, x, y, color_lit_ground, libtcod.BKGND_SET)
                    tile_map[x][y].explored = True

    for object in objects:
        visible = libtcod.map_is_in_fov(fov_map, object.x, object.y)
        if visible:
            object.draw()

    # blit the contents of console 'con' to the root console (numeral) '0'
    libtcod.console_blit(stat_con, 0, 0, STAT_PANEL_WIDTH, STAT_PANEL_HEIGHT, 0, 0, 0)
    libtcod.console_blit(con, 0, 0, MAP_WIDTH, MAP_HEIGHT, 0, STAT_PANEL_WIDTH, 0)


def clear_all():
    # clear all objects in the objects list
    for object in objects:
        object.clear()

    libtcod.console_clear(stat_con)


make_map()

fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
for y in xrange(MAP_HEIGHT):
    for x in xrange(MAP_WIDTH):
        libtcod.map_set_properties(fov_map, x, y, not tile_map[x][y].block_sight, not tile_map[x][y].blocked)

################################
# INITIALIZATION AND GAME LOOP #
################################

game_state = 'playing'
player_action = None

while not libtcod.console_is_window_closed():
    libtcod.console_set_default_foreground(0, libtcod.white)

    # A string with a red over black word, using predefined color control codes
    libtcod.console_set_color_control(libtcod.COLCTRL_1, libtcod.red, libtcod.black)
    libtcod.console_print(stat_con, 1, 1,
                          "Position: %c(%s, %s)%c" % (libtcod.COLCTRL_1, player.x, player.y, libtcod.COLCTRL_STOP))
    libtcod.console_print(stat_con, 1, 2, "HP: %s/%s" % (player.fighter.hp, player.fighter.max_hp))
    libtcod.console_print(stat_con, 1, 3, "Defense: %s" % player.fighter.defense)
    libtcod.console_print(stat_con, 1, 4, "Power: %s" % player.fighter.power)
    draw_all()

    libtcod.console_flush()

    clear_all()
    # handle keys and exit game if needed
    player_action = handle_keys()
    if player_action == 'exit':
        break

    if game_state == 'playing' and player_action != 'didnt-take-turn':
        for object in objects:
            if object.AI:
                object.AI.take_turn()