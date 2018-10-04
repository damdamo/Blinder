#! /usr/bin/env python3

from random import randint
import asyncio
import requests
import discord

from urllib.parse import urlparse
from os.path import splitext, basename

# Ratio between two strings
from difflib import SequenceMatcher
import re
import time
from math import floor

ERROR_RATIO = 0.85
NB_MIN_PLAYERS = 1
NB_MAX_PLAYERS = 8
WAIT_TIME_LETTER = 10
WAITING_DISPLAY = 5
WAIT_TIME_SKIP = 30
WAIT_TIME_CANCEL = 30

async def blind_test_game(client, message, roles_allowed, score_max=3):

    server = message.server
    game_channel = message.channel
    content = message.content

    if len(content.split()) > 1:
        try:
            score_temp = int((content.split())[1])
            if score_temp < 8:
                score_max = score_temp
        except ValueError:
            await client.send_message(game_channel, 'Valeur rentrée incorrect')
        finally:
            await client.send_message(game_channel, 'La partie se jouera en {} points'.format(score_max))


    ###################################################################
    # Create List of players
    ###################################################################

    player_list = await create_player_list(client, game_channel, message.author)

    if len(player_list) < NB_MIN_PLAYERS:
        return await client.send_message(game_channel, 'La partie est annulé le nombre de joueur est insuffisant')
    else:
        await client.send_message(game_channel, 'La partie va pouvoir commencer ! En attente du joueur hôte !')

    embed_player = discord.Embed(title="Liste des joueurs", color=0x00ff00)

    index_dic_players = {}
    
    for i, player in enumerate(player_list):
        index_dic_players[player] = i
        value = 'Score: {}'.format(player_list[player])
        embed_player.add_field(name=player, value=value, inline=False)

    msg_embed_score = await client.send_message(message.channel, embed=embed_player)


    ###################################################################
    """Create Private channel"""
    ###################################################################


    # We define permissions for everybody
    # We create a secret channel where only bot and person who calls
    # command can access
    try:
        perm_everyone = discord.PermissionOverwrite(read_messages=False)
        perm_mine = discord.PermissionOverwrite(read_messages=True)
        perm_author = discord.PermissionOverwrite(read_messages=True)
        bt_channel = await client.create_channel(serv, 'Blind-Test', (serv.default_role, perm_everyone), (serv.me, perm_mine), (message.author, perm_author))


        ###################################################################
        """Start the game in a private channel | Bot ask player to give
        image with all informations"""
        ###################################################################

        # Just notification to be warned
        notif = '''Hey {} ! Prêt pour ton blind-test ? C'est ici que ça se passe !
        Tu as juste à suivre les instructions qui suivent !
        '''.format(message.author.mention)
        await client.send_message(bt_channel, notif)

        ###################################################################
        """Loop for all points"""
        ###################################################################

        best_score = 0
        cancel = False

        while best_score < score_max and not cancel:

            list_info = await player_choose_image(client, message.author, bt_channel, game_channel)

            # If the player want to change an information he can or just write "yes" to
            # send the embed with image and informations
            await player_correction_image(client, message.author, list_info, bt_channel)

            ###################################################################
            """Players have to find the right answer !"""
            ###################################################################

            # We hide the answer but we give the number of letters
            # We hide only letters and not ponctuations or space

            current_winner, cancel = await find_answer(client, game_channel, list_info, player_list)

            ###################################################################
            """Modify and Display the current score"""
            ###################################################################

            if current_winner and not cancel:
                await client.purge_from(bt_channel)
                #await client.purge_from(game_channel, check=is_bot)

                msg_current_winner = 'Le joueur {} a remporté le point'.format(current_winner)
                await client.send_message(game_channel, msg_current_winner)

                best_score = find_best_score(player_list)
                value = 'Score: {}'.format(player_list[current_winner])
                # We remove the old embed score and replace with the new one
                await client.delete_message(msg_embed_score)
                embed_player.set_field_at(index_dic_players[current_winner], name=current_winner, value=value, inline=False)
                msg_embed_score = await client.send_message(game_channel, embed=embed_player)

        ###################################################################
        """Remove the blind test channel"""
        ###################################################################

        if cancel:
            text_cancel = 'La partie a été annulée suite à un vote !'
            await client.send_message(game_channel, text_cancel)
        else:
            best_player = get_best_player(player_list)
            msg_winning = 'La partie est terminée ! Bravo au joueur {} qui la remporte !'.format(best_player)
            await client.send_message(game_channel, msg_winning)

    except:
        await client.send_message(game_channel, 'Erreur lors du déroulement de la partie. Celle-ci est annulée !')
        raise Exception()
    finally:
        await client.delete_channel(bt_channel)


async def create_player_list(client, game_channel, author):
    """Create player list"""
    player_list = {}
    msg_game = '''Pour rejoindre la partie écrivez: join '''
    await client.send_message(game_channel, msg_game)
    msg = ''
    while msg or len(player_list) > NB_MAX_PLAYERS:
        msg = await client.wait_for_message(channel=game_channel, timeout=10)
        if msg:
            if client.user != msg.author and msg.author != author and msg.author not in player_list and (msg.content).lower() == 'join':
                #message.author != msg.author and
                player_list[msg.author] = 0
                msg_new_player = 'Le joueur {} a rejoint la partie'.format(msg.author)
                await client.send_message(game_channel, msg_new_player)
    return player_list


async def player_choose_image(client, author, bt_channel, game_channel):
    """Function to create the embed with image"""
    list_info = {}
    while len(list_info) < 3:
        if len(list_info) == 0:
            info = '''1) Donne l'url de ton image (Attention il ne faut que l'image)'''
            await client.send_message(bt_channel, info)
            msg = await client.wait_for_message(author=author, channel=bt_channel)

            image = msg.content
            valid, info_image = check_image(image)

            if valid:
                list_info['url'] = msg.content
                await client.send_message(bt_channel, info_image)

            else:
                await client.send_message(bt_channel, info_image)

        if len(list_info) == 1:
            info = '''2) Tu peux maintenant donner un indice sur ton image (ex: Titre du manga) ! Attention tu es limité par la taille (140 caractères)'''
            await client.send_message(bt_channel, info)
            msg = await client.wait_for_message(author=author, channel=bt_channel)
            clue = msg.content

            valid, info_clue = check_clue(clue)
            if valid:
                list_info['clue'] = clue
                await client.send_message(bt_channel, info_clue)
            else:
                await client.send_message(bt_channel, info_clue)

        if len(list_info) == 2:
            info = '''3) Il te reste à rentrer la réponse que les joueurs devront trouver (ex: Naruto) ! Attention à l'orthographe !'''
            await client.send_message(bt_channel, info)
            msg = await client.wait_for_message(author=author, channel=bt_channel)
            answer = msg.content

            valid, info_answer = check_answer(answer)

            if valid:
                list_info['answer'] = answer.lower()
                await client.send_message(bt_channel, info_answer)
            else:
                await client.send_message(bt_channel, info_answer)
    return list_info

async def create_embed_bt(list_info):
    """Create an embed for the blind test with all informations
    reveal is an int which represents the number of letter that we want to reveal"""

    embed_bt = discord.Embed(title="Blind Test", description="Trouvez la bonne réponse !", color=0x00ff00)
    embed_bt.add_field(name="Indice", value=list_info['clue'], inline=False)
    embed_bt.add_field(name="Réponse", value=list_info['answer'], inline=False)
    embed_bt.set_image(url=list_info['url'])

    return embed_bt

async def player_correction_image(client, author, list_info, bt_channel):
    """Allow to the player to change informations"""

    end = False
    msg_correction = ''' Voici l'aperçu final que les joueurs verront. Tu as plusieurs possibilités:
    - Tape 'yes' si tout est correct (Le tout est envoyé dans le salon de jeu)
    - Tape 'image' pour modifier l'image
    - Tape 'clue' pour modifier l'indice
    - Tape 'answer' pour modifier la réponse
    Une fois que tout est fini écrit 'yes'
    '''

    embed_image = await create_embed_bt(list_info)
    await client.send_message(bt_channel, embed=embed_image)
    await client.send_message(bt_channel, msg_correction)
    msg_cmd = '''Commandes possibles: 'yes', 'image', 'clue', 'answer' '''
    msg_next_cmd = '''Entrez votre prochaine commande: 'yes', 'image', 'clue', 'answer' '''

    while not end:
        msg = await client.wait_for_message(author=author, channel=bt_channel)
        rep = msg.content

        if rep.lower().startswith('yes'):
            end = True
        else:
            if rep.lower().startswith('image'):
                info = '''Donne la nouvelle url de ton image (Attention il ne faut que l'image)'''
                await client.send_message(bt_channel, info)
                msg_image = await client.wait_for_message(author=author, channel=bt_channel)

                url_image = msg_image.content
                valid, info_image = check_image(url_image)

                if valid:
                    list_info['url'] = url_image
                    await client.send_message(bt_channel, info_image)

                else:
                    info_image = '{} La précédente image a été conservée'.format(info_image)
                    await client.send_message(bt_channel, info_image)

            elif rep.lower().startswith('clue'):
                info = '''Donne un nouvel indice ! Attention tu es limité par la taille (140 caractères)'''
                await client.send_message(bt_channel, info)
                msg_clue = await client.wait_for_message(author=author, channel=bt_channel)
                clue = msg_clue.content

                valid, info_clue = check_clue(clue)
                if valid:
                    list_info['clue'] = clue
                    await client.send_message(bt_channel, info_clue)
                else:
                    info_clue = '{} Le précédent indice a été conservé'.format(info_clue)
                    await client.send_message(bt_channel, info_clue)

            elif rep.lower().startswith('answer'):
                info = '''Donne une nouvelle réponse ! Attention à l'orthographe !'''
                await client.send_message(bt_channel, info)
                msg_answer = await client.wait_for_message(author=author, channel=bt_channel)
                answer = msg_answer.content

                valid, info_answer = check_answer(answer)

                if valid:
                    list_info['answer'] = answer.lower()
                    await client.send_message(bt_channel, info_answer)
                else:
                    info_answer = '{} La précédente réponse a été conservé'.format(info_answer)
                    await client.send_message(bt_channel, info_answer)

            else:
                await client.send_message(bt_channel, msg_cmd)

            new_embed = await create_embed_bt(list_info)
            await client.send_message(bt_channel ,embed=new_embed)
            await client.send_message(bt_channel, msg_next_cmd)


async def find_answer(client, game_channel, list_info, player_list):
    """Function where players have to find the right answer"""

    # We send an embed of the blindtest where we hide answer
    answer = list_info['answer']
    answer_hidden = hidden_answer(answer)
    list_info['answer'] = format_hidden_answer(answer_hidden)

    msg_start_game = '''Image affichée dans {} sec'''.format(WAITING_DISPLAY)
    msg_sleeping = await client.send_message(game_channel, msg_start_game)
    await asyncio.sleep(WAITING_DISPLAY)
    await client.delete_message(msg_sleeping)

    embed_bt = await create_embed_bt(list_info)
    bot_msg = await client.send_message(game_channel, embed=embed_bt)

    # Parameter to skip or cancel the game
    cancel = False
    skip_image = False
    # Need to allow just once time to skip or cancel in this function
    cancel_nb = 0
    skip_nb = 0

    current_winner = ''
    find_answer = ''
    end = False
    find = False

    t0 = time.time()

    while not end and not cancel and not skip_image:
        t1 = time.time()

        msg = await client.wait_for_message(timeout=WAIT_TIME_LETTER, channel=game_channel)

        if msg is None and answer_hidden != answer:
            answer_hidden = discover_letter(answer_hidden, answer)
            list_info['answer'] = format_hidden_answer(answer_hidden)
            embed_image = await create_embed_bt(list_info)
            await client.delete_message(bot_msg)
            bot_msg = await client.send_message(game_channel, embed=embed_image)
            t0 = time.time()

        else:
            if msg.author in player_list:
                if t1-t0 > WAIT_TIME_LETTER and answer_hidden != answer:
                    answer_hidden = discover_letter(answer_hidden, answer)
                    list_info['answer'] = format_hidden_answer(answer_hidden)
                    embed_image = await create_embed_bt(list_info)
                    # We remove the last message (last embed)
                    await client.delete_message(bot_msg)
                    bot_msg = await client.send_message(game_channel, embed=embed_image)
                    t0 = time.time()

            if msg.author in player_list:
                find_answer = (msg.content).lower()
                ratio = ratio_string(answer, find_answer)

                if msg.content == 'cancel' and cancel_nb == 0:
                    cancel = await cancel_game(client, player_list, game_channel)
                    cancel_nb = cancel_nb + 1

                elif msg.content == 'skip' and skip_nb == 0:
                    skip_image = await skip_question(client, player_list, game_channel)
                    skip_nb = skip_nb + 1
                    if skip_image:
                        current_winner = None

                elif ratio>=ERROR_RATIO and not find:
                    #info = 'Le joueur {} a donné la bonne réponse: {}'.format(msg.author, msg.content)
                    player_list[msg.author] = player_list[msg.author] + 1
                    current_winner = msg.author
                    end = True
                    find = True
                else:
                    info = 'Le joueur {} a donné une mauvaise réponse: {}'.format(msg.author, msg.content)
                    await client.send_message(game_channel, info)

    return current_winner, cancel

"""def is_bot(m):
    return m.author == client.user"""

async def skip_question(client, player_list, game_channel):
    """Function to start a vote and ask if people wants to skip the question"""
    min_to_skip = floor(len(player_list)/2) + 1
    skip_text = '''Un vote pour passer l'image a été lancé. Entrez 'y' pour accepter ou 'n' pour refuser. Il faut au moins {} 'y' pour skip.'''.format(min_to_skip)
    bot_msg = await client.send_message(game_channel, skip_text)

    nb_yes = nb_no = 0
    list_who_votes = []

    # Timer to cancel
    t0 = time.time()
    t1 = time.time()

    while (nb_no + nb_yes) < len(player_list) and nb_yes <= min_to_skip and t1-t0 < WAIT_TIME_SKIP:
        msg = await client.wait_for_message(timeout=10, channel=game_channel)
        if msg:
            if msg.author in player_list:
                ans = (msg.content).lower()
                if ans == 'y' or ans == 'yes' and msg.author not in list_who_votes:
                    list_who_votes.append(msg.author)
                    nb_yes = nb_yes + 1
                    text_yes = '''{}/{} votes yes'''.format(nb_yes, min_to_skip)
                    await client.send_message(game_channel, text_yes)
                elif ans == 'n' or ans == 'no' and msg.author not in list_who_votes:
                    list_who_votes.append(msg.author)
                    nb_no = nb_no + 1
        t1 = time.time()

    if nb_yes >= min_to_skip:
        text_skip = '''L'image a bien été passée !'''
        await client.send_message(game_channel, text_skip)
        return True
    else:
        text_skip = '''Pas assez de vote yes pour passer l'image'''
        await client.send_message(game_channel, text_skip)
        return False


async def cancel_game(client, player_list, game_channel):
    """Function to start a vote and ask if people wants to cancel the game"""
    min_to_cancel = floor(len(player_list)/2) + 1
    cancel_text = '''Un vote pour l'annulation de la partie a été lancé. Entrez 'y' pour accepter ou 'n' pour refuser. Il faut au moins {} 'y' pour annuler la partie.'''.format(min_to_cancel)
    bot_msg = await client.send_message(game_channel, cancel_text)

    nb_yes = 0
    nb_no = 0
    list_who_votes = []

    # Timer to cancel
    t0 = time.time()
    t1 = time.time()

    while (nb_no + nb_yes) < len(player_list) and nb_yes <= min_to_cancel and t1-t0 < WAIT_TIME_CANCEL:
        msg = await client.wait_for_message(timeout=10, channel=game_channel)
        if msg:
            if msg.author in player_list:
                ans = (msg.content).lower()
                if ans == 'y' or ans == 'yes' and msg.author not in list_who_votes:
                    list_who_votes.append(msg.author)
                    nb_yes = nb_yes + 1
                    text_yes = '''{}/{} votes yes'''.format(nb_yes, min_to_cancel)
                    await client.send_message(game_channel, text_yes)
                elif ans == 'n' or ans == 'no' and msg.author not in list_who_votes:
                    list_who_votes.append(msg.author)
                    nb_no = nb_no + 1
        t1 = time.time()

    if nb_yes >= min_to_cancel:
        return True
    else:
        text_cancel = '''La partie continue !'''
        await client.send_message(game_channel, text_cancel)
        return False

def format_hidden_answer(answer):
    """We need format answer to display it into embed"""
    new_hidden_answer = ' '.join(answer)
    new_hidden_answer = new_hidden_answer.replace('_', '\_')
    return new_hidden_answer


def hidden_answer(answer):
    """Return the answer where we replace alphabetic letters by underscore"""
    answer_hidden = re.sub('\w', '_', answer)
    return answer_hidden

def discover_letter(answer_hidden, answer):
    """Return the hidden string with a new letter discover"""

    end = False
    new_hidden_answer = ''

    while not end:
        nb_alea = randint(0, len(answer)-1)
        if answer_hidden[nb_alea] == '_':
            # We replace hidden letter by the good one
            new_hidden_answer = '{}{}{}'.format(answer_hidden[:nb_alea], answer[nb_alea], answer_hidden[nb_alea+1:])
            end = True

    return new_hidden_answer


def find_best_score(dic):
    best_score = 0
    for el in dic:
        if dic[el] > best_score:
            best_score = dic[el]
    return best_score


def get_best_player(dic):
    score_max = 0
    best_player = 'nobody'
    for player in dic:
        if dic[player] > score_max:
            best_player = player
            score_max = dic[player]
    return best_player


def check_image(url):
    """Check if url is an image"""
    disassembled = urlparse(url)
    file_name, file_ext = splitext(basename(disassembled.path))

    if url_exist(url):
        return True, '''Url valide ! Vérifie bien l'aperçu !'''
    else:
        return False, 'Ton url est invalide !'

def check_clue(clue):
    """Check if the clue has the good format"""


    if len(clue) > 140:
        return False, 'Indice trop long'
    elif url_exist(clue):
        return False, 'Les liens sont interdits'
    else:
        return True, 'Indice de la bonne forme !'

def check_answer(answer):
    """Check if the answer has the good format"""

    if len(answer) > 140:
        return False, 'Réponse trop longue'
    elif url_exist(answer):
        return False, 'Les liens sont interdits'
    else:
        return True, 'Réponse de la bonne forme !'

def url_exist(text):
    """Find if an url exist inside a string"""
    url = re.findall('''http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]
    |[!*\(\), ]|(?:%[0-9a-fA-F][0-9a-fA-F]))+''', text)

    if len(url) == 0:
        return False
    else:
        return True

def ratio_string(right_word, guess_word):
    """Give the ratio between the right word and the guess word"""

    if len(right_word) > len(guess_word):
        smaller = guess_word
    else:
        smaller = right_word

    ratio = 0
    for i in range(len(smaller)):
        if right_word[i] == guess_word[i]:
            ratio = ratio + 1

    diff = abs(len(right_word) - len(guess_word))
    ratio = (ratio - diff) / len(right_word)

    return ratio
