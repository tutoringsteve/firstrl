from functools import partial

__author__ = "Steven Sarasin <tutoringsteve@gmail.com>"

import libtcodpy as libtcod
import math
import textwrap
import shelve

# size of the map
MAP_WIDTH = 80
MAP_HEIGHT = 45

STAT_PANEL_WIDTH = 20
STAT_PANEL_HEIGHT = MAP_HEIGHT

MSG_PANEL_HEIGHT = 10
MSG_PANEL_WIDTH = MAP_WIDTH + STAT_PANEL_WIDTH

# window size
SCREEN_WIDTH = STAT_PANEL_WIDTH + MAP_WIDTH
SCREEN_HEIGHT = MAP_HEIGHT + MSG_PANEL_HEIGHT

INVENTORY_WIDTH = 50

ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 26

MAX_ROOM_MONSTERS = 3
MAX_ROOM_ITEMS = 2

MAX_UPSTAIRS = 3
MIN_UPSTAIRS = 3
MAX_DOWNSTAIRS = 1
MIN_DOWNSTAIRS = 1

FOV_ALGO = 0
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10

HEAL_AMOUNT = 4

LIGHTNING_RANGE = 5
LIGHTNING_DAMAGE = 20

CONFUSE_NUM_TURNS = 10
CONFUSE_RANGE = 8

FIREBALL_RADIUS = 3
FIREBALL_DAMAGE = 12

PHASE_DOOR_DISTANCE = 3

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


def change_depth(depth_to_change_by):
    global current_depth

    if depth_to_change_by + current_depth < 0:
        current_depth = 0
    else:
        current_depth += depth_to_change_by

    libtcod.console_clear(con)
    make_map()
    initialize_fov()
    libtcod.console_flush()


def make_map():
    global tile_map, objects
    global num_downstairs, num_upstairs

    objects = [player]

    rooms = []
    num_rooms = 0
    num_downstairs = 0
    num_upstairs = 0

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

    place_stairs(rooms)


def midpoint(x1, y1, x2, y2):
    return (x1 + x2) / 2, (y1 + y2) / 2


def plus_or_minus_one():
    zero_or_one = libtcod.random_get_int(0, 0, 1)
    return (-1) ** zero_or_one


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


def target_tile(max_range=None):
    # return the position of a tile left-clicked in player's FOV (optionally with a further restricted range),
    # or (None, None) the user cancels targeting.
    global key, mouse
    while True:
        # Stop showing inventory and continues to render screen while targeting
        libtcod.console_flush()
        clear_all()
        libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS | libtcod.EVENT_MOUSE, key, mouse)
        draw_all()

        (x, y) = (mouse.cx - STAT_PANEL_WIDTH, mouse.cy)

        if mouse.lbutton_pressed and libtcod.map_is_in_fov(fov_map, x, y) and \
                (max_range is None or player.distance_to_tile(x, y) <= max_range):
            return (x, y)

        if mouse.rbutton_pressed or key.vk == libtcod.KEY_ESCAPE:
            message('Targeting cancelled by player.', color=libtcod.orange)
            return (None, None)


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


libtcod.console_set_custom_font('fonts/arial10x10.png', libtcod.FONT_TYPE_GRAYSCALE | libtcod.FONT_LAYOUT_TCOD)
libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'python/libtcod tutorial', False)
con = libtcod.console_new(MAP_WIDTH, MAP_HEIGHT)
stat_con = libtcod.console_new(STAT_PANEL_WIDTH, STAT_PANEL_HEIGHT)
msg_con = libtcod.console_new(MSG_PANEL_WIDTH, MSG_PANEL_HEIGHT)
# will have no effect on turn-based games
libtcod.sys_set_fps(LIMIT_FPS)


def render_bar(console, x, y, total_width, name, value, maximum, bar_color, back_color):
    # render a bar for health or some other stat that can be decreased from max to 0
    bar_width = int(float(value) / maximum * total_width)

    # render the background first
    libtcod.console_set_default_background(console, back_color)
    libtcod.console_rect(console, x, y, total_width, 1, False, libtcod.BKGND_SET)

    # now render the bar on top
    libtcod.console_set_default_background(console, bar_color)
    if bar_width > 0:
        libtcod.console_rect(console, x, y, bar_width, 1, False, libtcod.BKGND_SET)
    # centered text with values over bar
    libtcod.console_set_default_foreground(console, libtcod.white)
    libtcod.console_print_ex(console, x + total_width / 2, y, libtcod.BKGND_NONE, libtcod.CENTER,
                             '%s: %s/%s' % (name, value, maximum))
    libtcod.console_set_default_background(console, libtcod.black)


def possibly_plural_msg(quantity, name):
    if quantity == 1:
        return 'a ' + name
    else:
        return str(quantity) + ' ' + name + 's'


def message(msg, color=libtcod.white, console=msg_con):
    msg_width = libtcod.console_get_width(console)
    msg_lines = textwrap.wrap(msg, msg_width)

    for line in reversed(msg_lines):
        messages.append((line, color))


def closest_monster(max_range):
    # find closest enemy, up to a maximum range, and in the player's FOV
    closest_enemy = None
    closest_dist = max_range + 1

    for object in objects:
        if object.fighter and not object == player and libtcod.map_is_in_fov(fov_map, object.x, object.y):
            # calculate distance between this object and the player
            dist = player.distance_to_object(object)
            if dist < closest_dist:
                closest_enemy = object
                closest_dist = dist
    return closest_enemy


def player_death(player):
    global game_state
    message('You have been killed!', color=libtcod.lighter_red)
    game_state = 'dead'

    # change player look to corpse on death
    player.char = '%'
    player.color = libtcod.dark_red


def monster_death(monster):
    global messages
    # transform monster into corpse! It no longer has AI and no longer blocks
    message(monster.name.capitalize() + ' has been killed!', color=libtcod.green)
    monster.char = '%'
    monster.always_visible = True
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
            death_function = self.death_function
            if death_function is not None:
                death_function(self.owner)

    def heal(self, amount):
        # heal by the given amount, without going over the maximum
        self.hp += amount
        if self.hp > self.max_hp:
            self.hp = self.max_hp

    def attack(self, target):
        global messages
        # a simple formula for attack damage
        damage = self.power - target.fighter.defense

        if damage > 0:
            # make the target take some damage
            message(self.owner.name.capitalize() + ' attacks ' + target.name + ' for ' + str(damage) + ' hit points.',
                    color=libtcod.orange)
            target.fighter.take_damage(damage)
        else:
            message(self.owner.name.capitalize() + ' attacks ' + target.name + ' for no damage!',
                    color=libtcod.darker_yellow)


class BasicMonster:
    # AI for a basic monster:
    def take_turn(self):
        # a basic monster takes its turn. If you can see it, it will chase
        monster = self.owner
        if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):

            # move towards player if far away
            # close enough, attack! (if the player is still alive.)
            if monster.distance_to_object(player) >= 2:
                monster.move_towards(player.x, player.y)
            elif player.fighter.hp > 0:
                monster.fighter.attack(player)


class ConfusedMonster:
    # AI for a temporarily confused monster (reverts to previous AI after a while).
    def __init__(self, old_AI, num_turns=CONFUSE_NUM_TURNS):
        self.old_AI = old_AI
        self.num_turns = num_turns

    def take_turn(self):
        if self.num_turns > 0:
            # move in a random direction
            self.owner.move(libtcod.random_get_int(0, -1, 1), libtcod.random_get_int(0, -1, 1))
            self.num_turns -= 1
        else:
            self.owner.AI = self.old_AI
            message('The ' + self.owner.name + ' is no longer confused.', libtcod.darker_yellow)


class Object:
    # this is a generic object: the player, a monster, an item, the stairs...
    # it's always represented by a character on screen.
    def __init__(self, x, y, char, name, color, blocks=False, always_visible=False, fighter=None, AI=None, item=None):
        self.x = x
        self.y = y
        self.char = char
        self.name = name
        self.color = color
        self.blocks = blocks
        self.always_visible = always_visible

        self.fighter = fighter
        if self.fighter:
            self.fighter.owner = self

        self.AI = AI
        if self.AI:
            self.AI.owner = self

        self.item = item
        if self.item:
            self.item.owner = self

    def move(self, dx, dy):
        if (in_map(self.x + dx, self.y + dy)) and (not is_blocked(self.x + dx, self.y + dy)):
            # move by the given amount
            self.x += dx
            self.y += dy

    def distance_to_object(self, other):
        # return the distance to another Object
        dx = other.x - self.x
        dy = other.y - self.y
        return math.sqrt(dx ** 2 + dy ** 2)

    def distance_to_tile(self, x, y):
        dx = x - self.x
        dy = y - self.y
        return math.sqrt(dx ** 2 + dy ** 2)

    def move_towards(self, target_x, target_y):
        # vector from current location to desired location
        dx = target_x - self.x
        dy = target_y - self.y
        distance = math.sqrt(dx ** 2 + dy ** 2)

        # normalize vector
        dx = int(round(dx / distance))
        dy = int(round(dy / distance))
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
        objects.remove(self)
        objects.insert(0, self)


def save_game():
    # open a new empty shelve (possibly overwriting an old one)
    file = shelve.open('savegame', 'n')
    file['tile_map'] = tile_map
    file['objects'] = objects
    file['player_index'] = objects.index(player)
    file['current_depth'] = current_depth
    file['inventory'] = inventory
    file['messages'] = messages
    file['game_state'] = game_state
    file.close()


def load_game():
    # open the previously saved shelve and load the game data
    global tile_map, objects, player, inventory, messages, game_state, current_depth

    file = shelve.open('savegame', 'r')
    current_depth = file['current_depth']
    tile_map = file['tile_map']
    objects = file['objects']
    player = objects[file['player_index']]
    inventory = file['inventory']
    messages = file['messages']
    game_state = file['game_state']
    file.close()

    initialize_fov()

# monster_spawn_stats = { 'monster-name': {depth: chance-of-spawning-at-depth,   #0 < chance-of-spawning-at-depth <= 100
# depth2: chance-of-spawning-at-depth2, ... }
monster_spawn_stats = {
    'orc': {0: 100, 1: 100, 2: 100, 3: 100, 4: 100, 5: 100, 6: 95, 7: 90, 8: 85, 9: 80, 10: 75, 11: 70,
            12: 65, 13: 60, 14: 55, 15: 50},
    'troll': {5: 30, 6: 40, 7: 50, 8: 60, 9: 80, 10: 100, 11: 95, 12: 90, 13: 85, 14: 80, 15: 75,
              16: 70, 17: 65, 18: 60, 19: 55, 20: 50}}

item_spawn_stats = {
    'healing potion': {0: 100, 1: 100, 2: 100, 3: 100, 4: 100, 5: 100, 6: 95, 7: 90, 8: 85, 9: 80, 10: 75, 11: 70,
                       12: 65, 13: 60, 14: 55, 15: 50, 16: 70, 17: 65, 18: 60, 19: 55, 20: 50},
    'scroll of lightning bolt': {0: 100, 1: 100, 2: 100, 3: 100, 4: 100, 5: 100, 6: 95, 7: 90, 8: 85, 9: 80,
                                 10: 75, 11: 70, 12: 65, 13: 60, 14: 55, 15: 50, 16: 70, 17: 65, 18: 60, 19: 55,
                                 20: 50},
    'scroll of fireball': {0: 100, 1: 100, 2: 100, 3: 100, 4: 100, 5: 100, 6: 95, 7: 90, 8: 85, 9: 80, 10: 75,
                           11: 70, 12: 65, 13: 60, 14: 55, 15: 50, 16: 70, 17: 65, 18: 60, 19: 55, 20: 50},
    'scroll of confusion': {0: 100, 1: 100, 2: 100, 3: 100, 4: 100, 5: 100, 6: 95, 7: 90, 8: 85, 9: 80, 10: 75,
                            11: 70, 12: 65, 13: 60, 14: 55, 15: 50, 16: 70, 17: 65, 18: 60, 19: 55, 20: 50},
    'scroll of magic mapping': {0: 100, 1: 100, 2: 100, 3: 100, 4: 100, 5: 100},
    'scroll of phase door': {0: 100, 1: 100, 2: 100, 3: 100, 4: 100, 5: 100}}


def depth_chances(depth, game_objects):
    # pull out all the objects with non-zero probabilities of spawning at depth and put them in a dictionary
    # together with their probability of appearing at depth
    object_chances = {game_object: game_objects[game_object][depth] for game_object in game_objects if
                      depth in game_objects[game_object]}
    # scale the probabilities so that their relative size is the same and their weighted sum is close to 100
    weight = sum(object_chances.values())
    for game_object in object_chances:
        object_chances[game_object] = round((float(object_chances[game_object]) / weight) * 100)

    return object_chances


def random_choice(depth, game_objects):
    objects_chances_dict = depth_chances(depth, game_objects)
    choices = objects_chances_dict.keys()
    chances = objects_chances_dict.values()
    print 'Objects_chances_dict =', objects_chances_dict
    if len(choices) == 0 or len(chances) == 0:
        raise RuntimeError('object_chances_dict had an empty value or keys set ')

    if len(choices) != len(chances):
        raise RuntimeError('random choice needs a dictionary with a 1-to-1 key: value relationship')

    running_total_chance = 0

    dice_roll = libtcod.random_get_int(0, 0, 100)
    print 'Dice_roll =', dice_roll
    for index, chance in enumerate(chances):
        running_total_chance += chance
        if dice_roll <= running_total_chance:
            print 'choices[index] =', choices[index], 'index =', index
            return choices[index]


def place_objects(room):
    # choose random number of monsters
    num_monsters = libtcod.random_get_int(0, 0, MAX_ROOM_MONSTERS)

    for i in xrange(num_monsters):
        # choose random spot for this monster within the given room
        x = libtcod.random_get_int(0, room.x1 + 1, room.x2 - 1)
        y = libtcod.random_get_int(0, room.y1 + 1, room.y2 - 1)

        if not is_blocked(x, y):
            monster_name = random_choice(current_depth, monster_spawn_stats)
            if monster_name == 'orc':
                fighter_component = Fighter(hp=10, defense=0, power=3, death_function=monster_death)
                ai_component = BasicMonster()
                monster = Object(x, y, 'o', 'Pathetic Orc', libtcod.desaturated_green, blocks=True,
                                 fighter=fighter_component, AI=ai_component)
            elif monster_name == 'troll':
                fighter_component = Fighter(hp=16, defense=1, power=4, death_function=monster_death)
                ai_component = BasicMonster()
                monster = Object(x, y, 'T', 'Troll Runt', libtcod.darker_green, blocks=True, fighter=fighter_component,
                                 AI=ai_component)
            objects.append(monster)

    place_items(room)


def place_items(room):
    # choose random number of items
    num_items = libtcod.random_get_int(0, 0, MAX_ROOM_ITEMS)

    for i in xrange(num_items):
        # choose random spot for this monster within the given room
        x = libtcod.random_get_int(0, room.x1 + 1, room.x2 - 1)
        y = libtcod.random_get_int(0, room.y1 + 1, room.y2 - 1)
        if not is_blocked(x, y):
            item_name = random_choice(current_depth, item_spawn_stats)
            item_component = Item(items[item_name]['use_function'])
            item = Object(x, y, items[item_name]['char'], item_name, always_visible=True,
                          color=items[item_name]['color'], item=item_component)

            objects.append(item)
            # make sure items are drawn underneath the player and monsters
            item.send_to_back()


class Item:
    def __init__(self, use_function=None, quantity=1):
        self.use_function = use_function
        self.quantity = quantity

    def use(self):
        # just call the "use_function" if it is defined
        if self.use_function is None:
            message('The ' + self.owner.name + ' cannot be used.', color=libtcod.orange)
        else:
            if self.use_function() != 'cancelled':
                if self.quantity == 1:
                    inventory.remove(self.owner)  # destroy after use, unless it was cancelled for some reason
                else:
                    self.quantity -= 1

    # an item that can be picked up and used.
    def pick_up(self):
        # add to the player's inventory and remove from the map
        for itm in inventory:
            if itm.name == self.owner.name:
                itm.item.quantity += self.quantity
                objects.remove(self.owner)
                message('You picked up ' + possibly_plural_msg(self.quantity, self.owner.name) + '!',
                        color=libtcod.cyan)
                return
        if len(inventory) >= 26:
            message('Your inventory is full, cannot pick up ' + self.owner.name + '.', color=libtcod.orange)
        else:
            inventory.append(self.owner)
            objects.remove(self.owner)
            message('You picked up ' + possibly_plural_msg(self.quantity, self.owner.name) + '!',
                    color=libtcod.cyan)

    def drop(self):
        # remove from player's inventory and add to floor underneath the player.
        self.owner.x, self.owner.y = player.x, player.y

        same_item_on_tile_already = False

        for object in objects:
            if object.item and self.owner.distance_to_object(object) == 0 and self.owner.name == object.name:
                object.item.quantity += self.quantity
                same_item_on_tile_already = True
        if not same_item_on_tile_already:
            objects.append(self.owner)

        # self.owner.send_to_back()
        message('You dropped a ' + self.owner.name + ' on the floor beneath you.', color=libtcod.cyan)
        inventory.remove(self.owner)


def cast_heal():
    # heal the player
    if player.fighter.hp == player.fighter.max_hp:
        message('You are already at full health.', color=libtcod.orange)
        return 'cancelled'

    message('Your wounds start to feel better!', color=libtcod.light_green)
    player.fighter.heal(HEAL_AMOUNT)


def cast_lightning():
    monster = closest_monster(LIGHTNING_RANGE)
    if monster is None:
        message('No enemy is close enough to strike.')
        return 'cancelled'

    message('A lightning bolt strikes the ' + monster.name + ' with a loud thunder! The damage is ' + str(
        LIGHTNING_DAMAGE) + ' hit points.', color=libtcod.lightest_red)
    monster.fighter.take_damage(LIGHTNING_DAMAGE)


def cast_confuse():
    # find closest enemy in-range and confuse it
    monster = closest_monster(CONFUSE_RANGE)
    if monster is None:
        message('No enemy is close enough to confuse.', color=libtcod.orange)
        return 'cancelled'
    # replace the monster's AI with a "confused" one; after some turns the original AI will be restored
    old_AI = monster.AI
    monster.AI = ConfusedMonster(old_AI)
    monster.AI.owner = monster
    message('The eyes of the ' + monster.name + ' look vacant, confused even. The monster begins to stumble around.')


def cast_fireball():
    # ask the player for a target tile to throw a fireball at
    message('Left-click a target tile for the fireball. Escape or right-click to cancel targeting.', color=libtcod.cyan)

    (x, y) = target_tile()
    if x is None:
        return 'cancelled'

    message('The fireball explodes, burning everything within a ' + str(FIREBALL_RADIUS) + ' tile radius!')

    for obj in objects:
        if obj.distance_to_tile(x, y) < FIREBALL_RADIUS and obj.fighter:
            message('The ' + obj.name + ' gets burned for ' + str(FIREBALL_DAMAGE) + ' hit points.',
                    color=libtcod.lightest_red)
            obj.fighter.take_damage(FIREBALL_DAMAGE)


def cast_magic_map():
    global fov_recompute
    # magic mapping marks the map as revealed, as if you had been to all the squares before.
    message("Your mind's eye opens wide, and the surroundings feel somehow familiar to you.", color=libtcod.white)
    libtcod.map_compute_fov(fov_map, player.x, player.y, 9999, FOV_LIGHT_WALLS, FOV_ALGO)
    for y in xrange(MAP_HEIGHT):
        for x in xrange(MAP_WIDTH):
            if libtcod.map_is_walkable(fov_map, x, y):
                # flagging adjacent tiles so that the walls are also visible
                tile_map[x - 1][y - 1].explored = True
                tile_map[x - 1][y].explored = True
                tile_map[x - 1][y + 1].explored = True
                tile_map[x][y - 1].explored = True
                tile_map[x][y].explored = True
                tile_map[x][y + 1].explored = True
                tile_map[x + 1][y - 1].explored = True
                tile_map[x + 1][y].explored = True
                tile_map[x + 1][y + 1].explored = True
    fov_recompute = True
    draw_map_panel()
    libtcod.console_flush()


def cast_phase_door():
    message("The air in front of you crackles with magic energy and begins to warble like heat waves. You step into the"
            " disturbance as though it were an open door and find yourself several metres from where you were. Looking "
            "back you see no sign of the disturbance.", libtcod.light_orange)

    searching_for_destination = True
    while searching_for_destination:
        # choose dx, dy so that their sum is PHASE_DOOR_DISTANCE
        dx = libtcod.random_get_int(0, 0, PHASE_DOOR_DISTANCE)
        dy = PHASE_DOOR_DISTANCE - dx
        # apply random + / - to dx , dy after determining their magnitude
        dx *= plus_or_minus_one()
        dy *= plus_or_minus_one()
        if not is_blocked(player.x + dx, player.y + dy):
            player_move_or_attack(dx, dy)
            searching_for_destination = False


items = {
    'healing potion': {'name': 'healing potion', 'char': '!', 'color': libtcod.violet, 'use_function': cast_heal},
    'scroll of lightning bolt': {'name': 'scroll of lightning bolt', 'char': '?', 'color': libtcod.light_yellow,
                                 'use_function': cast_lightning},
    'scroll of fireball': {'name': 'scroll of fireball', 'char': '?', 'color': libtcod.dark_orange,
                           'use_function': cast_fireball},
    'scroll of confusion': {'name': 'scroll of confusion', 'char': '?', 'color': libtcod.darker_red,
                            'use_function': cast_confuse},
    'scroll of magic mapping': {'name': 'scroll of magic mapping', 'char': '?', 'color': libtcod.lightest_green,
                                'use_function': cast_magic_map},
    'scroll of phase door': {'name': 'scroll of phase door', 'char': '?', 'color': libtcod.lightest_azure,
                             'use_function': cast_phase_door}}


def place_stairs(rooms):
    num_upstairs = 0
    num_downstairs = 0
    downstairs = libtcod.random_get_int(0, MIN_DOWNSTAIRS, MAX_DOWNSTAIRS)
    upstairs = libtcod.random_get_int(0, MIN_UPSTAIRS, MAX_UPSTAIRS)
    while num_downstairs < downstairs or num_upstairs < upstairs:
        random_index = libtcod.random_get_int(0, 0, len(rooms) - 1)
        room = rooms[random_index]
        x = libtcod.random_get_int(0, room.x1 + 1, room.x2 - 1)
        y = libtcod.random_get_int(0, room.y1 + 1, room.y2 - 1)
        if (not is_blocked(x, y)) and (libtcod.console_get_char(con, x, y) not in ('<', '>')):
            dice = libtcod.random_get_int(0, 0, 100)
            if dice < 50 and num_upstairs < upstairs:
                stair = Object(x, y, '<', 'stairs', always_visible=True, color=libtcod.white)
                objects.append(stair)
                stair.send_to_back()
                num_upstairs += 1
            elif num_downstairs < downstairs:
                stair = Object(x, y, '>', 'stairs', always_visible=True, color=libtcod.white)
                objects.append(stair)
                stair.send_to_back()
                num_downstairs += 1


def new_game():
    global player, inventory, messages, game_state, player_action, current_depth

    # create the player Object
    fighter_component = Fighter(hp=30, defense=2, power=5, death_function=player_death)
    player = Object(25, 23, '@', 'The Player <You>', always_visible=True, color=libtcod.white, blocks=True,
                    fighter=fighter_component)

    current_depth = 0

    # generate map without (yet) drawing it to screen
    make_map()
    return_stairs = Object(player.x, player.y, '<', 'stairs', always_visible=True, color=libtcod.white)
    objects.append(return_stairs)
    return_stairs.send_to_back()
    initialize_fov()

    game_state = 'playing'
    inventory = []

    # welcome message
    messages = []
    message('Welcome back to <game>, player ' + player.name + '! Prepare to die!')


#############
# KEYBOARD EVENT HANDLING
#############


def player_move_or_attack(dx, dy):
    global fov_recompute

    # the coordinates the player is attempting to move to/attack
    x = player.x + dx
    y = player.y + dy

    # find an attackable object at (x, y)
    target = None
    for object in objects:
        if (object.x, object.y) == (x, y) and object.fighter:
            target = object
            break

    # attack if target found, move otherwise
    if target is not None and target.blocks:
        if target.fighter:
            player.fighter.attack(target)
    else:
        player.move(dx, dy)
        fov_recompute = True


player_move_or_attack_up = partial(player_move_or_attack, 0, -1)
player_move_or_attack_down = partial(player_move_or_attack, 0, 1)
player_move_or_attack_left = partial(player_move_or_attack, -1, 0)
player_move_or_attack_right = partial(player_move_or_attack, 1, 0)
player_wait_one_turn = partial(player_move_or_attack, 0, 0)


def pickup_item():
    for object in reversed(objects):
        if (player.x, player.y) == (object.x, object.y) and object.item:
            object.item.pick_up()
            break


def drop_from_inventory():
    # show the inventory; if an item is selected it, drop it onto the floor (removing it from the inventory)
    chosen_item = inventory_menu('Press the key next to an item to drop it, or any other to cancel.\n')
    if chosen_item is not None:
        chosen_item.drop()


def view_inventory():
    # show the inventory; if an item is selected, use it
    chosen_item = inventory_menu('Press the key next to an item to use it, or any other to cancel.\n')
    if chosen_item is not None:
        chosen_item.use()


def use_stairs_up():
    # go upstairs
    for object in objects:
        if (player.x, player.y) == (object.x, object.y) and object.name == 'stairs' and object.char == '<':
            change_depth(1)
            break
    return_stairs = Object(player.x, player.y, '>', 'stairs', always_visible=True, color=libtcod.white)
    objects.append(return_stairs)
    return_stairs.send_to_back()


def use_stairs_down():
    # go downstairs
    for object in objects:
        if (player.x, player.y) == (object.x, object.y) and object.name == 'stairs' and object.char == '>':
            change_depth(-1)
            break
    return_stairs = Object(player.x, player.y, '<', 'stairs', always_visible=True, color=libtcod.white)
    objects.append(return_stairs)
    return_stairs.send_to_back()


def handle_keys():
    global key

    if key.vk == libtcod.KEY_ENTER and key.lalt:
        # Alt + Enter: toggle full screen
        libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
    elif key.vk == libtcod.KEY_ESCAPE:
        return 'exit'

    playing_controls = {libtcod.KEY_UP: player_move_or_attack_up,
                        libtcod.KEY_DOWN: player_move_or_attack_down,
                        libtcod.KEY_LEFT: player_move_or_attack_left,
                        libtcod.KEY_RIGHT: player_move_or_attack_right,
                        libtcod.KEY_KP2: player_move_or_attack_down,
                        libtcod.KEY_KP4: player_move_or_attack_left,
                        libtcod.KEY_KP5: player_wait_one_turn,
                        libtcod.KEY_KP6: player_move_or_attack_right,
                        libtcod.KEY_KP8: player_move_or_attack_up,
                        ord('d'): drop_from_inventory,
                        ord('g'): pickup_item,
                        ord('i'): view_inventory,
                        ord('<'): use_stairs_up,
                        ord('>'): use_stairs_down}

    keyboard_controls_by_context = {'playing': playing_controls}

    if game_state in keyboard_controls_by_context:
        controls = keyboard_controls_by_context[game_state]

        if key.vk in controls:
            controls[key.vk]()
        else:
            if key.c in controls:
                controls[key.c]()
            return 'didnt-take-turn'


###########
# END OF KEYBOARD HANDLING
###########

def draw_all():
    draw_map_panel()
    draw_messages_panel()
    draw_stat_panel()

    # blit the contents of console 'con' to the root console (numeral) '0'
    libtcod.console_blit(stat_con, 0, 0, STAT_PANEL_WIDTH, STAT_PANEL_HEIGHT, 0, 0, 0)
    libtcod.console_blit(con, 0, 0, MAP_WIDTH, MAP_HEIGHT, 0, STAT_PANEL_WIDTH, 0)
    libtcod.console_blit(msg_con, 0, 0, MSG_PANEL_WIDTH, MSG_PANEL_HEIGHT, 0, 0, MAP_HEIGHT)

    draw_target_tile_highlighter()


def draw_map_panel():
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
        if (visible or (object.always_visible and tile_map[object.x][object.y].explored)) \
                and object is not player:
            object.draw()
    player.draw()


def draw_messages_panel():
    # draw the boundary of the panel with a gold line
    old_foreground_color = libtcod.console_get_default_foreground(msg_con)
    libtcod.console_set_default_foreground(msg_con, libtcod.gold)
    libtcod.console_hline(msg_con, 0, 0, MSG_PANEL_WIDTH)
    libtcod.console_set_default_foreground(msg_con, old_foreground_color)

    # print the last many messages to the message console that will fit in the console.
    for i, msg_and_color in enumerate(reversed(messages)):
        if (i + 1) > MSG_PANEL_HEIGHT:
            break
        else:
            msg, color = msg_and_color
            libtcod.console_set_default_foreground(msg_con, color)
            libtcod.console_print(msg_con, 1, (i + 1), msg)
            libtcod.console_set_default_foreground(msg_con, old_foreground_color)


def draw_stat_panel():
    # draw the boundary of the panel with a gold line
    old_foreground_color = libtcod.console_get_default_foreground(stat_con)
    libtcod.console_set_default_foreground(stat_con, libtcod.gold)
    libtcod.console_vline(stat_con, STAT_PANEL_WIDTH - 1, 0, STAT_PANEL_HEIGHT)
    libtcod.console_set_default_foreground(stat_con, old_foreground_color)

    # A string with a red over black word, using predefined color control codes
    libtcod.console_set_color_control(libtcod.COLCTRL_1, libtcod.red, libtcod.black)
    libtcod.console_set_color_control(libtcod.COLCTRL_2, libtcod.green, libtcod.black)
    libtcod.console_print(stat_con, 1, 1,
                          "Position: %c(%s, %s)%c" % (libtcod.COLCTRL_1, player.x, player.y, libtcod.COLCTRL_STOP))
    libtcod.console_print(stat_con, 1, 2, "Defense: %s" % player.fighter.defense)
    libtcod.console_print(stat_con, 1, 3, "Power: %s" % player.fighter.power)
    render_bar(stat_con, 1, 4, STAT_PANEL_WIDTH - 2, 'HP', player.fighter.hp, player.fighter.max_hp,
               libtcod.darker_green, libtcod.dark_red)
    libtcod.console_print(stat_con, 1, 5, "Mouse: %c(%s, %s)%c" % (
        libtcod.COLCTRL_1, mouse.cx - STAT_PANEL_WIDTH, mouse.cy, libtcod.COLCTRL_STOP))
    libtcod.console_print(stat_con, 1, 7, "Current depth: " + str(current_depth))
    libtcod.console_print(stat_con, 1, 10, "Mouse %ctarget%c:" % (libtcod.COLCTRL_2, libtcod.COLCTRL_STOP))
    libtcod.console_print_rect(stat_con, 1, 11, STAT_PANEL_WIDTH - 2, 0,
                               ("%c" + get_names_under_mouse() + "%c") % (libtcod.COLCTRL_2, libtcod.COLCTRL_STOP))


def draw_target_tile_highlighter():
    if (mouse.cx - STAT_PANEL_WIDTH >= 0) and (mouse.cy < MAP_HEIGHT):
        target = libtcod.console_new(1, 1)
        libtcod.console_fill_background(target, (220,), (220,), (220,))
        libtcod.console_blit(target, 0, 0, 1, 1, 0, mouse.cx, mouse.cy, .10, .50)


def menu(header, options, width, x=-1, y=-1):
    global key
    if len(options) > 26:
        raise ValueError('Cannot have a menu with more than 26 options (a to z).')

    # calculate total height for the header (after auto-wrap) and one line per option
    header_height = libtcod.console_get_height_rect(con, 0, 0, width, MAP_HEIGHT, header)
    height = len(options) + header_height

    # make a separate console to draw the menu to
    window = libtcod.console_new(width, height)

    # print header with auto-wrap
    libtcod.console_set_default_foreground(window, libtcod.white)
    libtcod.console_print_rect_ex(window, 0, 0, width, height, libtcod.BKGND_NONE, libtcod.LEFT, header)

    # print all the options
    # y = header_height
    letter_index = ord('a')
    for option_text in options:
        text = '(' + chr(letter_index) + ')' + option_text
        libtcod.console_print_ex(window, 0, header_height, libtcod.BKGND_NONE, libtcod.LEFT, text)
        header_height += 1
        letter_index += 1

    # blit contents of "window" to the root console, right-aligning the "window"
    if x == -1:
        x = STAT_PANEL_WIDTH + SCREEN_WIDTH - width
    if y == -1:
        y = 0
    libtcod.console_blit(window, 0, 0, width, height, 0, x, y, 1.0, 0.7)

    libtcod.console_flush()
    key = libtcod.console_wait_for_keypress(True)

    print chr(key.c)
    index = key.c - ord('a')
    if (index >= 0) and (index < len(options)):
        return index
    else:
        return None


def inventory_menu(header):
    if len(inventory) == 0:
        options = ['Inventory is empty.']
    else:
        options = [((str(item.item.quantity) + ' x ' + item.name) if item.item.quantity > 1 else item.name) for item in
                   inventory]

    index = menu(header, options, INVENTORY_WIDTH)

    # if an item was chosen, return it
    if index is None or len(inventory) == 0:
        return None
    else:
        return inventory[index].item


def debug_menu(header):
    pass


def clear_all():
    # clear all objects in the objects list
    for object in objects:
        object.clear()
    libtcod.console_clear(msg_con)
    libtcod.console_clear(stat_con)


def clear_all_consoles():
    libtcod.console_clear(msg_con)
    libtcod.console_clear(stat_con)
    libtcod.console_clear(con)
    libtcod.console_clear(0)


def mouse_can_see(obj):
    (x, y) = (mouse.cx - STAT_PANEL_WIDTH, mouse.cy)
    return (obj.always_visible and tile_map[x][y].explored) or libtcod.map_is_in_fov(fov_map, obj.x, obj.y)


def quantity_and_name_if_item_and_more_than_one_else_name(obj):
    return (str(obj.item.quantity) + ' x ' + obj.name.capitalize()) if (obj.item and obj.item.quantity > 1) \
        else obj.name.capitalize()


def get_names_under_mouse():
    # return a string with the names of all objects under the mouse
    (x, y) = (mouse.cx - STAT_PANEL_WIDTH, mouse.cy)
    names = [quantity_and_name_if_item_and_more_than_one_else_name(obj) for obj in objects if (obj.x, obj.y) == (x, y)
             and mouse_can_see(obj)]
    names = ', '.join(names)
    return names


def initialize_fov():
    global fov_recompute, fov_map
    fov_recompute = True

    # create fov map based on current tile_map (which must already be generated
    fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
    for y in xrange(MAP_HEIGHT):
        for x in xrange(MAP_WIDTH):
            libtcod.map_set_properties(fov_map, x, y, not tile_map[x][y].block_sight, not tile_map[x][y].blocked)

    libtcod.console_clear(con)


################################
# INITIALIZATION AND GAME LOOP #
################################


def play_game():
    global key, mouse, player_action

    player_action = None

    mouse = libtcod.Mouse()
    key = libtcod.Key()

    while not libtcod.console_is_window_closed():

        libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS | libtcod.EVENT_MOUSE, key, mouse)

        draw_all()
        libtcod.console_flush()
        clear_all()

        # handle keys and exit game if needed
        player_action = handle_keys()
        if player_action == 'exit':
            save_game()
            break

        if game_state == 'playing' and player_action != 'didnt-take-turn':
            for object in objects:
                if object.AI:
                    object.AI.take_turn()


def main_menu():
    # will work with no image but the background on the menu will be plain black.
    img = libtcod.image_load('images\menu_background.png')

    while not libtcod.console_is_window_closed():
        clear_all_consoles()
        libtcod.image_blit_2x(img, 0, 0, 0)

        choice = menu('', ['Play a new game', 'Continue last game', 'Quit'], width=24, x=4, y=2)
        if key.vk == libtcod.KEY_ENTER and (key.lalt or key.ralt):
            # Alt + Enter: toggle full screen
            libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())

        if choice == 0:
            new_game()
            play_game()
        elif choice == 1:
            try:
                load_game()
            except:
                menu('\n No saved game to load. \n', [], width=24, x=((STAT_PANEL_WIDTH + SCREEN_WIDTH - 24) / 2), y=2)
                continue
            play_game()
        elif choice == 2:
            break


main_menu()
