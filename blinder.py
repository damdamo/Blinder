#! /usr/bin/env python3

import io
import random
import asyncio
import requests
from discord import Game
import discord

import python_script.bt_game as bt

BOT_PREFIX = ("?", "$")
TOKEN = 'NDY2OTA3MTU3NzYyNDA4NDU4.Dii54A.Mb0BLra6YC6ni_xwlKyvtAdHQiI'

# client = Bot(command_prefix=BOT_PREFIX)
client = discord.Client()


# List roles allowed for functions
ROLES_PERSOS = ["l'ombre du slender"]
ROLES_READ_GIF = ['organisation xiii', 'héros légendaire', 'gardien de la porte millénaire', 'champion'] + ROLES_PERSOS
ROLES_ADD_GIF = ['organisation xiii', 'héros légendaire'] + ROLES_PERSOS
ROLES_DEL_GIF = ['organisation xiii', 'héros légendaire'] + ROLES_PERSOS
ROLES_CLEAR_BOT_MESSAGES = ['organisation xiii', 'héros légendaire', 'gardien de la porte millénaire'] + ROLES_PERSOS
ROLES_PURGE = ['organisation xiii']
HIGHEST_ROLE = 'organisation xiii'

ERROR_RATIO = 0.85
NB_MIN_PLAYERS = 1
NB_MAX_PLAYERS = 8
WAIT_TIME_LETTER = 10
WAITING_DISPLAY = 5

@client.event
async def on_message(message):
    # We get user highest role
    user_role = (str(message.author.top_role)).lower()

    # HELP
    if message.content.startswith('?help'):
        help_message = ''

        how_to_play = '''Pour lancer une partie de blindtest il vous suffit de taper la commande:
        ?bt_image
        Vous pouvez ajouter le score a atteindre pour gagner comme ceci:
        ex: ?bt_image 5 (3 est le score par défaut si vous ne mettez rien)'''

        await client.send_message(message.channel,how_to_play)

    # BLIND TEST GAME
    if message.content.startswith('?bt_image'):
        await bt.blind_test_game(client, message, HIGHEST_ROLE)


@client.event
async def on_ready():
    await client.change_presence(game=Game(name="?help"))
    print("Logged in as " + client.user.name)


async def list_servers():
    await client.wait_until_ready()
    while not client.is_closed:
        print("Current servers:")
        for server in client.servers:
            print(server.name)
        await asyncio.sleep(600)

# Music test
"""elif message.content.startswith('?musico'):
    for server in client.servers:
        for channel in server.channels:
            pass
    if not opus.is_loaded():
        opus.load_opus()
    voice = await client.join_voice_channel(message.author.voice_channel)
    player = voice.create_ffmpeg_player('dk.mp3')
    player.start()"""

# client.loop.create_task(list_servers())
client.run(TOKEN)
