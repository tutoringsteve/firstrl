__author__ = "Steven Sarasin <tutoringsteve@gmail.com>"

import libtcodpy as libtcod
import math
import textwrap

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
    global tile_map, objects

    objects = [player]

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


libtcod.console_set_custom_font('arial10x10.png', libtcod.FONT_TYPE_GRAYSCALE | libtcod.FONT_LAYOUT_TCOD)
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


def message(msg, color=libtcod.white, console=msg_con):
    msg_width = libtcod.console_get_width(console)
    msg_lines = textwrap.wrap(msg, msg_width)

    for line in msg_lines:
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
    def __init__(self, x, y, char, name, color, blocks=False, fighter=None, AI=None, item=None):
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


def place_objects(room):
    # choose random number of monsters
    num_monsters = libtcod.random_get_int(0, 0, MAX_ROOM_MONSTERS)

    for i in xrange(num_monsters):
        # choose random spot for this monster within the given room
        x = libtcod.random_get_int(0, room.x1 + 1, room.x2 - 1)
        y = libtcod.random_get_int(0, room.y1 + 1, room.y2 - 1)

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

    place_items(room)


class Item:
    def __init__(self, use_function=None):
        self.use_function = use_function

    def use(self):
        # just call the "use_function" if it is defined
        if self.use_function is None:
            message('The ' + self.owner.name + ' cannot be used.', color=libtcod.orange)
        else:
            if self.use_function() != 'cancelled':
                inventory.remove(self.owner)  # destroy after use, unless it was cancelled for some reason

    # an item that can be picked up and used.
    def pick_up(self):
        # add to the player's inventory and remove from the map
        if len(inventory) >= 26:
            message('Your inventory is full, cannot pick up ' + self.owner.name + '.', color=libtcod.orange)
        else:
            inventory.append(self.owner)
            objects.remove(self.owner)
            message('You picked up a ' + self.owner.name + '!', color=libtcod.cyan)

    def drop(self):
        # remove from player's inventory and add to floor underneath the player.
        (self.owner.x, self.owner.y) = (player.x, player.y)
        inventory.remove(self.owner)
        objects.append(self.owner)
        #self.owner.send_to_back()
        message('You dropped a ' + self.owner.name + ' on the floor beneath you.', color=libtcod.cyan)



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


def place_items(room):
    # choose random number of items
    num_items = libtcod.random_get_int(0, 0, MAX_ROOM_ITEMS)

    for i in xrange(num_items):
        # choose random spot for this monster within the given room
        x = libtcod.random_get_int(0, room.x1 + 1, room.x2 - 1)
        y = libtcod.random_get_int(0, room.y1 + 1, room.y2 - 1)
        if not is_blocked(x, y):
            dice = libtcod.random_get_int(0, 0, 100)
            if dice < 10:
                # healing potion
                item_component = Item(use_function=cast_heal)
                item = Object(x, y, '!', 'healing potion', libtcod.violet, item=item_component)
                objects.append(item)
                # make sure items are drawn underneath the player and monsters
                item.send_to_back()
            elif dice < 10 + 10:
                # scroll of lightning
                item_component = Item(use_function=cast_lightning)
                item = Object(x, y, '?', 'scroll of lightning bolt', libtcod.light_yellow, item=item_component)
                objects.append(item)
                # make sure items are drawn underneath the player and monsters
                item.send_to_back()
            elif dice < 10 + 10 + 70:
                # scroll of fireball
                item_component = Item(use_function=cast_fireball)
                item = Object(x, y, '?', 'scroll of fireball', libtcod.dark_orange, item=item_component)
                objects.append(item)
                item.send_to_back()
            else:
                # create a scroll of confusion
                item_component = Item(use_function=cast_confuse)
                item = Object(x, y, '?', 'scroll of confusion', libtcod.darker_red, item=item_component)
                objects.append(item)
                # make sure items are drawn underneath the player and monsters
                item.send_to_back()


def new_game():
    global player, inventory, messages, game_state, player_action

    # create the player Object
    fighter_component = Fighter(hp=30, defense=2, power=5, death_function=player_death)
    player = Object(25, 23, '@', 'The Player <You>', libtcod.white, blocks=True, fighter=fighter_component)

    # generate map without (yet) drawing it to screen
    make_map()
    initialize_fov()

    game_state = 'playing'
    inventory = []

    # welcome message
    messages = []
    message('Welcome back to <game>, player ' + player.name + '! Prepare to die!')


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


def handle_keys():
    global key

    if key.vk == libtcod.KEY_ENTER and key.lalt:
        # Alt + Enter: toggle full screen
        libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
    elif key.vk == libtcod.KEY_ESCAPE:
        return 'exit'

    if game_state == 'playing':
        # movement keys
        if key.vk == libtcod.KEY_UP:
            player_move_or_attack(0, -1)
        elif key.vk == libtcod.KEY_DOWN:
            player_move_or_attack(0, 1)
        elif key.vk == libtcod.KEY_LEFT:
            player_move_or_attack(-1, 0)
        elif key.vk == libtcod.KEY_RIGHT:
            player_move_or_attack(1, 0)
        else:
            # test for other keys
            key_char = chr(key.c)

            if key_char == 'g':
                # pick up an item
                for object in reversed(objects):
                    if (player.x, player.y) == (object.x, object.y) and object.item:
                        object.item.pick_up()
                        break

            if key_char == 'i':
                # show the inventory; if an item is selected, use it
                chosen_item = inventory_menu('Press the key next to an item to use it, or any other to cancel.\n')
                if chosen_item is not None:
                    chosen_item.use()

            if key_char == 'd':
                # show the inventory; if an item is selected it, drop it onto the floor (removing it from the inventory)
                chosen_item = inventory_menu('Press the key next to an item to drop it, or any other to cancel.\n')
                if chosen_item is not None:
                    chosen_item.drop()

            return 'didnt-take-turn'


def draw_all():
    draw_map_panel()
    draw_messages_panel()
    draw_stat_panel()

    # blit the contents of console 'con' to the root console (numeral) '0'
    libtcod.console_blit(stat_con, 0, 0, STAT_PANEL_WIDTH, STAT_PANEL_HEIGHT, 0, 0, 0)
    libtcod.console_blit(con, 0, 0, MAP_WIDTH, MAP_HEIGHT, 0, STAT_PANEL_WIDTH, 0)
    libtcod.console_blit(msg_con, 0, 0, MSG_PANEL_WIDTH, MSG_PANEL_HEIGHT, 0, 0, MAP_HEIGHT)


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
        if visible and object is not player:
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
    libtcod.console_print(stat_con, 1, 6, "Mouse %ctarget%c:" % (libtcod.COLCTRL_2, libtcod.COLCTRL_STOP))
    libtcod.console_print_rect(stat_con, 1, 7, STAT_PANEL_WIDTH - 2, 0,
                               ("%c" + get_names_under_mouse() + "%c") % (libtcod.COLCTRL_2, libtcod.COLCTRL_STOP))


def menu(header, options, width):
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
    y = header_height
    letter_index = ord('a')
    for option_text in options:
        text = '(' + chr(letter_index) + ')' + option_text
        libtcod.console_print_ex(window, 0, y, libtcod.BKGND_NONE, libtcod.LEFT, text)
        y += 1
        letter_index += 1

    # blit contents of "window" to the root console, right-aligning the "window"
    x = STAT_PANEL_WIDTH + SCREEN_WIDTH - width
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
        options = [item.name for item in inventory]

    index = menu(header, options, INVENTORY_WIDTH)

    # if an item was chosen, return it
    if index is None or len(inventory) == 0:
        return None
    else:
        return inventory[index].item


def clear_all():
    # clear all objects in the objects list
    for object in objects:
        object.clear()
    libtcod.console_clear(msg_con)
    libtcod.console_clear(stat_con)


def get_names_under_mouse():
    # return a string with the names of all objects under the mouse
    (x, y) = (mouse.cx - STAT_PANEL_WIDTH, mouse.cy)
    names = [obj.name for obj in objects if
             (obj.x == x and obj.y == y and libtcod.map_is_in_fov(fov_map, obj.x, obj.y))]
    names = set(names)
    names = ', '.join(names)

    return names.capitalize()


def initialize_fov():
    global fov_recompute, fov_map
    fov_recompute = True

    # create fov map based on current tile_map (which must already be generated
    fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
    for y in xrange(MAP_HEIGHT):
        for x in xrange(MAP_WIDTH):
            libtcod.map_set_properties(fov_map, x, y, not tile_map[x][y].block_sight, not tile_map[x][y].blocked)


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
            break

        if game_state == 'playing' and player_action != 'didnt-take-turn':
            for object in objects:
                if object.AI:
                    object.AI.take_turn()


new_game()
play_game()