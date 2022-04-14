import gc
from os import *
import time
import network
from mqtt import MQTTClient

from machine import Pin, unique_id
from binascii import hexlify

from neopixel import NeoPixel

import ujson as json
import uasyncio as asyncio

print('\n\n')

CONFIG = None
WLAN = None


#########
# Config
#
def do_read_config(filename):
    global CONFIG
    try:
        CONFIG = json.load(open('config.json', 'r'))
    except:
        print('ERROR! Can`t load config!')
        exit(-1)


def do_connect():
    global CONFIG
    global WLAN

    if CONFIG is None or 'wifi' not in CONFIG:
        print('ERROR! No wifi config!')
        exit(-1)

    WLAN = network.WLAN(network.STA_IF)
    WLAN.active(True)

    if WLAN.isconnected():
        WLAN.disconnect()

    WLAN.connect(
        CONFIG['wifi']['essid'],
        CONFIG['wifi']['password']
    )

    # Awaiting network connect...
    while not WLAN.isconnected():
        print('Connecting to {}...'.format(CONFIG['wifi']['essid']))
        time.sleep(2)

    # Print our IP address
    print('IP: [ {} ]'.format(WLAN.ifconfig()[0]))


# ----------------------------------------------------------------------------
# START PROGRAM
# ----------------------------------------------------------------------------

do_read_config('config.json')
do_connect()

device_unique_id = hexlify(unique_id()).decode('ascii').upper()

print("Device type:", CONFIG['type'])
print("Device uid:", device_unique_id)

# ----------------MQTT  variables---------------------
mqtt_config = CONFIG['mqtt']
mqtt_host = mqtt_config['host']
mqtt_port = mqtt_config['port']
mqtt_client_id = 'device::{}/{}'.format(
    CONFIG['type'],
    device_unique_id + device_unique_id,
)

mqtt_topic_prefix = "{}/{}".format(
    CONFIG['type'],
    device_unique_id + device_unique_id,
)

mqtt_status_topic = "{}/{}".format(
    mqtt_topic_prefix,
    mqtt_config['topic']['status']
)
print("status topic:", mqtt_status_topic)

mqtt_api_topic = "{}/{}".format(
    mqtt_topic_prefix,
    mqtt_config['topic']['api']
)
print("api topic:", mqtt_api_topic)

# ---------------- NeoPixel ---------------------
np = []
for pin in CONFIG["gpio"]["branch"]:
    np.append(NeoPixel(Pin(pin, Pin.OUT), 500))

np = [
     NeoPixel(Pin(2, Pin.OUT), 500),
     NeoPixel(Pin(4, Pin.OUT), 500),
     NeoPixel(Pin(14, Pin.OUT), 500),
     NeoPixel(Pin( 2, Pin.OUT), 1000),
     NeoPixel(Pin(14, Pin.OUT), 1000),
#     # NeoPixel(Pin(12, Pin.OUT), 1000),
#     # NeoPixel(Pin( 2, Pin.OUT), 1000),
#     # NeoPixel(Pin(14, Pin.OUT), 1000),
 ]

for branch in range(len(np)):
    for pixel in range(np[branch].n):
        np[branch][pixel] = (0, 0, 0)
    np[branch].write()
    

def low_brightness(r, g, b):
    return (int(r * 0.12), int(g * 0.12), int(b * 0.12))

def get_color_order(order, r, g, b):
    r, g, b = low_brightness(r, g, b)
    if order == 'RBG':
        return (r, b, g)
    else:
        return (r, g, b)


# ---------------- MQTT ---------------------
def on_message_callback(mqtt_api_subscribe_topic, msg):
    print('topic: "{}", msg: "{}"'.format(mqtt_api_subscribe_topic, msg))
    path = mqtt_api_subscribe_topic.decode('ascii').split('/')
    print(path)
    if path[-3] == 'led':
        """
        Branch processing
        """
        if path[-2].lower() == 'all':
            branches = range(len(np))
        else:
            try:
                x = int(path[-2])
                if x == None or abs(x) > len(np):
                    print('Branch out of range!')
                    return
                branches = [x]  # make it iterable
            except:
                print('Branch not numeric!')
                return
        """
        Color processing
        """
        try:
            color = json.loads(msg.decode('ascii'))
        except:
            print('Invalid data!')
            return

    for b in branches:
        """
        Pixel processing
        """
        pixels = []

        # если все, то загораются все
        if path[-1].lower() == 'all':
            pixels = range(np[b].n)
            for p in pixels:
                np[b][i] = get_color_order(CONFIG["gpio"]["color_order"], color['red'], color['green'], color['blue'])
            np[b].write()
            return pixels

        str = path[-1].split(',')
        if len(str) == 2 and str[0][0] == "[" and str[1][-1] == "]":
            first_num_array = int(str[0][1:])
            second_num_array = int(str[1][:-1])
            r = range(first_num_array, second_num_array + 1)
            i = first_num_array
            for i in r:
                np[b][i] = get_color_order(CONFIG["gpio"]["color_order"], color['red'], color['green'], color['blue'])
            np[b].write()
        else:
            try:
                y = int(path[-1])
                if y == None or abs(y) >= np[b].n:
                    print('Pixel out of range!')
                    return
                pixels = [y]  # make it iterable
                for p in pixels:
                    np[b][i] = get_color_order(CONFIG["gpio"]["color_order"], color['red'], color['green'], color['blue'])
                np[b].write()
            except:
                print('Pixel not numeric!')
                return {"pin": 0, "num": 10},
        np[b].write()


# Connect
print('Connecting to "{}:{}", CID: "{}"'.format(
    mqtt_host,
    mqtt_port,
    mqtt_client_id
))

client = MQTTClient(
    mqtt_client_id,
    mqtt_host,
    mqtt_port,
    keepalive=20,
)

client.set_last_will(
    topic=mqtt_config['topic']['status'],
    msg='0', retain=True,
)

client.set_callback(on_message_callback)
client.connect()

print('Connected, publishing status')
client.publish(
    topic=mqtt_config['topic']['status'],
    msg='1', retain=True,
)

print('Subscribing to "{}"'.format(mqtt_api_topic))
client.subscribe(mqtt_api_topic)

counter = 0

while True:
    client.check_msg()
    if counter % 200 == 0:
        print("alive...")
        client.ping()
    counter += 1
    time.sleep(0.05)
