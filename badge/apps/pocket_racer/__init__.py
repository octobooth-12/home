"""Race another badge and dash traffic into their lane."""

import errno
import math
import os
import random
import sys

from badgeware import State


APP_DIR = "/system/apps/pocket_racer"
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

screen.font = font.nope

GRASS = color.rgb(39, 114, 68)
GRASS_DARK = color.rgb(30, 94, 55)
ROAD = color.rgb(55, 60, 67)
ROAD_EDGE = color.rgb(228, 230, 218)
LANE_MARK = color.rgb(239, 211, 102)
WHITE = color.rgb(245, 247, 240)
DIM = color.rgb(185, 193, 194)
PLAYER = color.rgb(72, 196, 255)
PLAYER_GLASS = color.rgb(181, 237, 255)
WHEEL = color.rgb(20, 24, 29)
TRAFFIC = (
    color.rgb(255, 91, 83),
    color.rgb(255, 173, 66),
    color.rgb(205, 124, 255),
    color.rgb(244, 239, 224),
)
POWER_COLORS = (
    color.rgb(72, 196, 255),
    color.rgb(255, 173, 66),
    color.rgb(111, 240, 151),
)
POWER_LABELS = ("B", "+", "S")
POWER_TYPES = ("boost", "life", "shield")

TITLE = "POCKET RACER"
LANE_COUNT = 3
ROAD_WIDTH = 108
CAR_WIDTH = 14
CAR_HEIGHT = 22
PLAYER_Y = 91
MAX_FRAME_SECONDS = 0.05
NETWORK_PORT = 39421
NETWORK_RETRY_SECONDS = 0.6
DASH_SECONDS = 0.22
DASH_COOLDOWN = 1.4
DASH_RANGE = 38
POWERUP_INTERVAL = 5.5
BOOST_SECONDS = 5.0
MAX_LIVES = 3
WOULD_BLOCK = (errno.EAGAIN,)

high_score = {"highscore": 0}
State.load("pocket_racer", high_score)

TITLE_SCREEN = 0
CONNECTING = 1
WAITING = 2
PLAYING = 3
GAME_OVER = 4
NETWORK_ERROR = 5
state = TITLE_SCREEN
score = 0
opponent_score = 0
elapsed = 0.0
spawn_elapsed = 0.0
road_offset = 0.0
player_lane = 1
player_x = 0.0
traffic = []
powerups = []
powerup_elapsed = 0.0
boost_time = 0.0
lives = MAX_LIVES
shield = 0
hit_grace = 0.0
dash_time = 0.0
dash_cooldown = 0.0
network_role = None
network_socket = None
socket_api = None
wifi_api = None
peer_address = None
peer_ready = False
network_message = ""
network_error = ""
last_network_send = 0
last_peer_seen = 0
result_message = ""


def road_geometry():
    road_width = min(ROAD_WIDTH, screen.width - 24)
    left = (screen.width - road_width) // 2
    lane_width = road_width / LANE_COUNT
    return left, road_width, lane_width


def lane_center(lane):
    left, _, lane_width = road_geometry()
    return left + lane_width * (lane + 0.5)


def draw_car(cx, cy, body, player=False):
    x = int(cx - CAR_WIDTH / 2)
    y = int(cy - CAR_HEIGHT / 2)

    screen.pen = WHEEL
    screen.rectangle(x - 2, y + 4, 3, 5)
    screen.rectangle(x + CAR_WIDTH - 1, y + 4, 3, 5)
    screen.rectangle(x - 2, y + CAR_HEIGHT - 9, 3, 5)
    screen.rectangle(x + CAR_WIDTH - 1, y + CAR_HEIGHT - 9, 3, 5)

    screen.pen = body
    screen.shape(shape.rounded_rectangle(x, y, CAR_WIDTH, CAR_HEIGHT, 3))

    screen.pen = PLAYER_GLASS if player else color.rgb(86, 101, 112)
    screen.rectangle(x + 3, y + 5, CAR_WIDTH - 6, 5)
    screen.rectangle(x + 3, y + 13, CAR_WIDTH - 6, 4)

    screen.pen = LANE_MARK if player else color.rgb(255, 225, 146)
    screen.rectangle(x + 2, y + 1, 3, 2)
    screen.rectangle(x + CAR_WIDTH - 5, y + 1, 3, 2)


def draw_powerup(lane, y, kind):
    x = lane_center(lane)
    power_index = POWER_TYPES.index(kind)
    screen.pen = POWER_COLORS[power_index]
    screen.shape(shape.circle(x, y, 7))
    label = POWER_LABELS[power_index]
    label_width, _ = screen.measure_text(label)
    screen.pen = ROAD
    screen.text(label, x - label_width / 2, y - 4)


def draw_road(dt):
    global road_offset

    road_offset = (road_offset + dt * 58) % 28
    screen.pen = GRASS
    screen.rectangle(0, 0, screen.width, screen.height)

    for y in range(-20, screen.height, 28):
        stripe_y = int((y + road_offset) % (screen.height + 28)) - 14
        screen.pen = GRASS_DARK
        screen.rectangle(5, stripe_y, 3, 9)
        screen.rectangle(screen.width - 8, stripe_y + 12, 3, 9)

    left, road_width, lane_width = road_geometry()
    screen.pen = ROAD_EDGE
    screen.rectangle(left - 3, 0, 3, screen.height)
    screen.rectangle(left + road_width, 0, 3, screen.height)
    screen.pen = ROAD
    screen.rectangle(left, 0, road_width, screen.height)

    screen.pen = LANE_MARK
    dash_offset = int(road_offset)
    for divider in range(1, LANE_COUNT):
        x = int(left + lane_width * divider)
        for y in range(-28, screen.height + 28, 28):
            screen.rectangle(x - 1, y + dash_offset, 2, 14)


def draw_hud():
    screen.pen = color.rgb(13, 17, 23, 205)
    screen.rectangle(0, 0, screen.width, 29)
    screen.pen = WHITE
    screen.text("YOU %03d" % score, 4, 3)
    opponent_text = "R:%03d" % opponent_score
    text_width, _ = screen.measure_text(opponent_text)
    screen.text(opponent_text, screen.width - text_width - 4, 3)

    dash_label = "DASH" if dash_cooldown <= 0 else "WAIT"
    text_width, _ = screen.measure_text(dash_label)
    screen.pen = LANE_MARK if dash_cooldown <= 0 else DIM
    screen.text(dash_label, (screen.width - text_width) // 2, 3)

    boost_label = "B:%d" % int(math.ceil(boost_time))
    inventory = "%s L:%d S:%d  SEL:DASH" % (boost_label, lives, shield)
    screen.pen = WHITE
    screen.text(inventory, 4, 17)


def draw_centered(text, y, pen=WHITE):
    text_width, _ = screen.measure_text(text)
    screen.pen = pen
    screen.text(text, (screen.width - text_width) // 2, y)


def close_network():
    global network_socket, peer_address, peer_ready

    if network_socket is not None:
        network_socket.close()
        network_socket = None
    peer_address = None
    peer_ready = False


def start_connection(role):
    global state, network_role, network_error, network_message
    global last_network_send, last_peer_seen

    close_network()
    network_role = role
    network_error = ""
    network_message = "Connecting to Wi-Fi..."
    last_network_send = 0
    last_peer_seen = badge.ticks
    state = CONNECTING


def open_network_socket():
    global network_socket, socket_api, state, network_message, network_error

    try:
        import socket as socket_module

        socket_api = socket_module
        connection = socket_api.socket(socket_api.AF_INET, socket_api.SOCK_DGRAM)
        connection.setsockopt(socket_api.SOL_SOCKET, socket_api.SO_REUSEADDR, 1)
        connection.setblocking(False)
        connection.setsockopt(socket_api.SOL_SOCKET, socket_api.SO_BROADCAST, 1)
        connection.bind(("0.0.0.0", NETWORK_PORT))
        network_socket = connection
    except ImportError:
        network_error = "Wi-Fi sockets are only available on the badge."
        state = NETWORK_ERROR
        return
    except OSError as error:
        network_error = "Could not open Wi-Fi game link: %s" % error
        state = NETWORK_ERROR
        return

    state = WAITING
    network_message = (
        "Waiting for a JOIN player..."
        if network_role == "host"
        else "Searching for a host..."
    )


def send_packet(packet, address=None):
    if network_socket is None:
        return
    destination = address or peer_address
    if destination is None:
        return
    try:
        network_socket.sendto(packet, destination)
    except OSError as error:
        if error.args and error.args[0] in WOULD_BLOCK:
            return
        network_error = "Wi-Fi link send failed: %s" % error
        fail_network(network_error)


def fail_network(message):
    global state, network_error

    close_network()
    network_error = message
    state = NETWORK_ERROR


def start_game():
    global state, score, opponent_score, elapsed, spawn_elapsed
    global player_lane, player_x, traffic, powerups, powerup_elapsed
    global boost_time, lives, shield, hit_grace, dash_time, dash_cooldown
    global result_message

    state = PLAYING
    score = 0
    opponent_score = 0
    elapsed = 0.0
    spawn_elapsed = 0.0
    player_lane = 1
    player_x = lane_center(player_lane)
    traffic = []
    powerups = []
    powerup_elapsed = 0.0
    boost_time = 0.0
    lives = MAX_LIVES
    shield = 0
    hit_grace = 0.0
    dash_time = 0.0
    dash_cooldown = 0.0
    result_message = ""


def begin_game_over(message):
    global state, result_message

    state = GAME_OVER
    result_message = message
    if score > high_score["highscore"]:
        high_score["highscore"] = score
        State.save("pocket_racer", high_score)


def service_network():
    global state, peer_address, network_message, last_network_send
    global last_peer_seen, opponent_score, peer_ready, wifi_api

    now = badge.ticks
    if state == CONNECTING:
        try:
            if wifi_api is None:
                import wifi as wifi_module

                wifi_api = wifi_module
        except ImportError:
            fail_network("Wi-Fi is only available on a physical badge.")
            return
        code, message = wifi_api.status()
        if code == wifi_api.NOT_CONFIGURED:
            network_message = "Set up Wi-Fi in Settings first."
        elif wifi_api.is_connected() or wifi_api.connect():
            open_network_socket()
        else:
            network_message = "Connecting to Wi-Fi..."
            if code < 0:
                network_message = message
        return

    if state not in (WAITING, PLAYING, GAME_OVER) or network_socket is None:
        return

    if state == WAITING and now - last_network_send >= NETWORK_RETRY_SECONDS * 1000:
        if network_role == "host":
            send_packet(b"PR1|HOST", ("255.255.255.255", NETWORK_PORT))
        elif peer_address is not None:
            send_packet(b"PR1|JOIN")
        else:
            send_packet(b"PR1|DISCOVER", ("255.255.255.255", NETWORK_PORT))
        last_network_send = now

    if state == PLAYING and peer_address is not None and now - last_network_send >= 250:
        if network_role == "host" and not peer_ready:
            send_packet(b"PR1|START")
        else:
            send_packet(("PR1|STATE|%d" % score).encode())
        last_network_send = now

    for _ in range(6):
        try:
            packet, address = network_socket.recvfrom(64)
        except OSError as error:
            if error.args and error.args[0] in WOULD_BLOCK:
                break
            fail_network("Wi-Fi link receive failed: %s" % error)
            return

        if packet == b"PR1|HOST":
            if state == WAITING and network_role == "join":
                peer_address = (address[0], NETWORK_PORT)
                network_message = "Host found; joining..."
        elif packet in (b"PR1|JOIN", b"PR1|DISCOVER"):
            if state == WAITING and network_role == "host":
                peer_address = address
                start_game()
                send_packet(b"PR1|START")
                last_peer_seen = now
        elif packet == b"PR1|START":
            if state == WAITING and network_role == "join":
                peer_address = (address[0], NETWORK_PORT)
                start_game()
                last_peer_seen = now
        elif peer_address and address[0] == peer_address[0]:
            last_peer_seen = now
            parts = packet.split(b"|")
            if len(parts) == 3 and parts[0] == b"PR1" and parts[1] == b"STATE":
                try:
                    opponent_score = int(parts[2])
                    peer_ready = True
                except ValueError:
                    pass
            elif len(parts) == 3 and parts[0] == b"PR1" and parts[1] == b"ATTACK":
                try:
                    lane = int(parts[2])
                except ValueError:
                    continue
                if 0 <= lane < LANE_COUNT and state == PLAYING:
                    traffic.append([lane, -CAR_HEIGHT, random.randint(0, len(TRAFFIC) - 1)])
            elif packet.startswith(b"PR1|OUT|"):
                begin_game_over("YOU WIN!")

    if state == PLAYING and now - last_peer_seen > 7000:
        begin_game_over("RIVAL DISCONNECTED")


def dash():
    global dash_time, dash_cooldown

    if dash_cooldown > 0:
        return
    dash_time = DASH_SECONDS
    dash_cooldown = DASH_COOLDOWN

    for index, car in enumerate(traffic):
        if car[0] == player_lane and -DASH_RANGE <= car[1] - PLAYER_Y <= 4:
            traffic.pop(index)
            send_packet(("PR1|ATTACK|%d" % player_lane).encode())
            return


def collect_powerup(kind):
    global boost_time, lives, shield

    if kind == "boost":
        boost_time = BOOST_SECONDS
    elif kind == "life":
        lives = min(MAX_LIVES, lives + 1)
    elif kind == "shield":
        shield = 1


def take_hit():
    global lives, shield, hit_grace

    if hit_grace > 0:
        return False
    if shield:
        shield = 0
        hit_grace = 0.8
        return False
    if lives > 1:
        lives -= 1
        hit_grace = 1.2
        return False
    return True


def update_game(dt):
    global elapsed, spawn_elapsed, player_lane, player_x, score
    global dash_time, dash_cooldown, powerup_elapsed
    global boost_time, hit_grace

    elapsed += dt
    dash_time = max(0.0, dash_time - dt)
    dash_cooldown = max(0.0, dash_cooldown - dt)
    boost_time = max(0.0, boost_time - dt)
    hit_grace = max(0.0, hit_grace - dt)

    if badge.pressed(BUTTON_LEFT):
        player_lane = max(0, player_lane - 1)
    elif badge.pressed(BUTTON_RIGHT):
        player_lane = min(LANE_COUNT - 1, player_lane + 1)
    if badge.pressed(BUTTON_SELECT):
        dash()

    target_x = lane_center(player_lane)
    player_x += (target_x - player_x) * min(1.0, dt * 14)

    spawn_elapsed += dt
    spawn_interval = max(0.58, 1.18 - elapsed * 0.012)
    if spawn_elapsed >= spawn_interval:
        spawn_elapsed -= spawn_interval
        traffic.append([random.randint(0, LANE_COUNT - 1), -CAR_HEIGHT,
                        random.randint(0, len(TRAFFIC) - 1)])

    powerup_elapsed += dt
    if powerup_elapsed >= POWERUP_INTERVAL:
        powerup_elapsed -= POWERUP_INTERVAL
        powerups.append([
            random.randint(0, LANE_COUNT - 1),
            -CAR_HEIGHT,
            POWER_TYPES[random.randint(0, len(POWER_TYPES) - 1)],
        ])

    speed = min(92.0, 42.0 + elapsed * 2.4)
    if boost_time > 0:
        speed *= 1.65
    remaining = []
    for car in traffic:
        car[1] += speed * dt
        if abs(car[1] - PLAYER_Y) < CAR_HEIGHT - 2:
            if dash_time <= 0 and abs(lane_center(car[0]) - player_x) < CAR_WIDTH - 2:
                if take_hit():
                    send_packet(("PR1|OUT|%d" % score).encode())
                    begin_game_over("CRASH!")
                    return
        if car[1] > screen.height + CAR_HEIGHT:
            score += 1
        else:
            remaining.append(car)
    traffic[:] = remaining

    remaining_powerups = []
    for pickup in powerups:
        pickup[1] += speed * dt
        if (pickup[0] == player_lane and
                abs(pickup[1] - PLAYER_Y) < 12):
            collect_powerup(pickup[2])
        elif pickup[1] <= screen.height + 8:
            remaining_powerups.append(pickup)
    powerups[:] = remaining_powerups


def update():
    global state, network_role

    dt = min(MAX_FRAME_SECONDS, max(0, badge.ticks_delta) / 1000)
    service_network()
    draw_road(dt if state != GAME_OVER else 0)

    if state == TITLE_SCREEN:
        draw_car(lane_center(1), PLAYER_Y, PLAYER, True)
        draw_centered(TITLE, 19)
        draw_centered("SELECT: SOLO RACE", 40, WHITE)
        draw_centered("LEFT: HOST WI-FI RACE", 60, DIM)
        draw_centered("RIGHT: JOIN WI-FI RACE", 78, DIM)
        draw_centered("DASH: SELECT", 101, LANE_MARK)
        if badge.pressed(BUTTON_SELECT):
            close_network()
            network_role = None
            start_game()
        elif badge.pressed(BUTTON_LEFT):
            start_connection("host")
        elif badge.pressed(BUTTON_RIGHT):
            start_connection("join")
        return

    if state == CONNECTING:
        draw_centered("WI-FI SETUP", 26)
        draw_centered(network_message, 51, DIM)
        draw_centered("Configure Wi-Fi in Settings.", 75, WHITE)
        draw_centered("BACK TO RETURN", 101, LANE_MARK)
        if badge.pressed(BUTTON_BACK):
            close_network()
            state = TITLE_SCREEN
        return

    if state == WAITING:
        heading = "HOSTING RACE" if network_role == "host" else "JOINING RACE"
        draw_centered(heading, 26)
        draw_centered(network_message, 53, DIM)
        draw_centered("Same Wi-Fi network required.", 76, WHITE)
        draw_centered("BACK TO CANCEL", 101, LANE_MARK)
        if badge.pressed(BUTTON_BACK):
            close_network()
            state = TITLE_SCREEN
        return

    if state == NETWORK_ERROR:
        draw_centered("NETWORK ERROR", 26)
        draw_centered(network_error[:24], 50, DIM)
        draw_centered("Check Wi-Fi and try again.", 73, WHITE)
        draw_centered("SELECT TO RETURN", 101, LANE_MARK)
        if badge.pressed(BUTTON_SELECT):
            close_network()
            state = TITLE_SCREEN
        return

    if state == PLAYING:
        update_game(dt)
        for car in traffic:
            draw_car(lane_center(car[0]), car[1], TRAFFIC[car[2]])
        for pickup in powerups:
            draw_powerup(pickup[0], pickup[1], pickup[2])
        player_y = PLAYER_Y - 9 if dash_time > 0 else PLAYER_Y
        player_color = PLAYER if hit_grace <= 0 or int(badge.ticks / 80) % 2 else WHITE
        draw_car(player_x, player_y, player_color, True)
        draw_hud()
        return

    for car in traffic:
        draw_car(lane_center(car[0]), car[1], TRAFFIC[car[2]])
    draw_car(player_x, PLAYER_Y, PLAYER, True)
    draw_hud()
    screen.pen = color.rgb(13, 17, 23, 190)
    screen.rectangle(0, 31, screen.width, 56)
    draw_centered(result_message, 39)
    draw_centered("YOU %03d   RIVAL %03d" % (score, opponent_score), 58, DIM)
    draw_centered("BACK TO RETURN TO MENU", 77, LANE_MARK)
    if badge.pressed(BUTTON_BACK):
        close_network()
        state = TITLE_SCREEN


run(update)
