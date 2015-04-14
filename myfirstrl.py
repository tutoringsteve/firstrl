__author__ = "Steven Sarasin <tutoringsteve@gmail.com"

import libtcodpy as libtcod

# window size
SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50

# size of the map
MAP_WIDTH = 80
MAP_HEIGHT = 45

ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 26

FOV_ALGO = 0
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10
fov_recompute = False

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
            new_x, new_y = new_room.center()
            print chr(65 + num_rooms), "x1, x2, y1, y2, c1, c2", new_room.x1, new_room.x2, new_room.y1, new_room.y2, new_x, new_y

            # optional: print "room number" to see how the map drawing works
            room_no = Object(new_x, new_y, chr(65 + num_rooms), libtcod.white)
            objects.insert(0, room_no)
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
                print "this happened at num_rooms", num_rooms
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
con = libtcod.console_new(SCREEN_WIDTH, SCREEN_HEIGHT)

# will have no effect on turn-based games
libtcod.sys_set_fps(LIMIT_FPS)


class Object:
    # this is a generic object: the player, a monster, an item, the stairs...
    # it's always represented by a character on screen.
    def __init__(self, x, y, char, color):
        self.x = x
        self.y = y
        self.char = char
        self.color = color

    def move(self, dx, dy):
        if (in_map(self.x + dx, self.y + dy)) and (not tile_map[self.x + dx][self.y + dy].blocked):
            # move by the given amount
            self.x += dx
            self.y += dy

    def draw(self):
        # set the color and then
        libtcod.console_set_default_foreground(con, self.color)
        libtcod.console_put_char(con, self.x, self.y, self.char, libtcod.BKGND_NONE)

    def clear(self):
        # erase the character that represents this object
        libtcod.console_put_char(con, self.x, self.y, ' ', libtcod.BKGND_NONE)


player = Object(25, 23, '@', libtcod.white)
npc = Object(SCREEN_WIDTH / 2 - 5, SCREEN_HEIGHT / 2, '@', libtcod.yellow)
objects = [npc, player]


def handle_keys():
    global fov_recompute

    key = libtcod.console_check_for_keypress(True)
    if key.vk == libtcod.KEY_ENTER and key.lalt:
        # Alt + Enter: toggle fullscreen
        libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
    elif key.vk == libtcod.KEY_ESCAPE:
        return True

    # movement keys
    if libtcod.console_is_key_pressed(libtcod.KEY_UP):
        player.move(0, -1)
        fov_recompute = True
    elif libtcod.console_is_key_pressed(libtcod.KEY_DOWN):
        player.move(0, 1)
        fov_recompute = True
    elif libtcod.console_is_key_pressed(libtcod.KEY_LEFT):
        player.move(-1, 0)
        fov_recompute = True
    elif libtcod.console_is_key_pressed(libtcod.KEY_RIGHT):
        player.move(1, 0)
        fov_recompute = True


def draw_all():
    global fov_recompute

    if fov_recompute:
        #recompute FOV if needed (the player moved or something)
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
        object.draw()

    # blit the contents of console 'con' to the root console (numeral) '0'
    libtcod.console_blit(con, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, 0, 0)


def clear_all():
    # clear all objects in the objects list
    for object in objects:
        object.clear()


make_map()

fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
for y in xrange(MAP_HEIGHT):
    for x in xrange(MAP_WIDTH):
        libtcod.map_set_properties(fov_map, x, y, not tile_map[x][y].block_sight, not tile_map[x][y].blocked)


def blocked_gen():
    for y in xrange(MAP_HEIGHT):
        for x in xrange(MAP_WIDTH):
            yield (not tile_map[x][y].blocked)


def explored_gen():
    for y in xrange(MAP_HEIGHT):
        for x in xrange(MAP_WIDTH):
            yield (tile_map[x][y].explored)


total_walkable = sum(blocked_gen())
total_explored = sum(explored_gen())
while not libtcod.console_is_window_closed():
    libtcod.console_set_default_foreground(0, libtcod.white)

    draw_all()

    libtcod.console_flush()

    clear_all()
    # A string with a red over black word, using predefined color control codes
    libtcod.console_set_color_control(libtcod.COLCTRL_1,libtcod.red,libtcod.black)
    libtcod.console_print(0,1,1,"String with a %cred%c word."%(libtcod.COLCTRL_1,libtcod.COLCTRL_STOP))
    # A string with a red word (over default background color), using generic color control codes
    libtcod.console_print(0,1,2,"String with a %c%c%c%cred%c word."%(libtcod.COLCTRL_FORE_RGB,255,1,1,libtcod.COLCTRL_STOP))
    # A string with a red over black word, using generic color control codes
    libtcod.console_print(0,1,3,"String with a %c%c%c%c%c%c%c%cred%c word." % (libtcod.COLCTRL_FORE_RGB,255,1,1,libtcod.COLCTRL_BACK_RGB,1,1,1,libtcod.COLCTRL_STOP))
    # handle keys and exit game if needed
    exit = handle_keys()
    if exit:
        break