import discord

from discord.utils import get
from youtube_dl import YoutubeDL
from scraper import find_song_data

DEFAULT_VOLUME = 1.0
guild_music_queues = {}
guild_music_settings = {}
default_music_setting = {
    'loop': False,
    'shuffle': False,
    'volume': DEFAULT_VOLUME,
}


def download_music(query):
    youtube_url = extract_query(query)
    ydl_opts = {'format': 'bestaudio', 'quiet': True}

    with YoutubeDL(ydl_opts) as ydl:
        ydl.cache.remove()
        info = ydl.extract_info(f'{youtube_url}', download=False)
    return info['entries']


def extract_query(query):
    # if the query is not a YouTube link, add ytsearch:
    if not query.startswith('https://www.youtube.com'):
        query = f'ytsearch:{query}'
    return query


def create_music_settings_status(guild):
    current_setting = get_guild_music_setting(guild)
    loop_status = 'on' if current_setting.get('loop', False) else 'off'
    shuffle_status = 'on' if current_setting.get('shuffle', False) else 'off'
    return f'loop: {loop_status} | shuffle: {shuffle_status}'


def create_embed(guild, title, description=discord.Embed.Empty, thumbnail=discord.Embed.Empty, url=discord.Embed.Empty):
    embed = discord.Embed(title=title, description=description, url=url)
    embed.set_footer(text=create_music_settings_status(guild))
    embed.set_thumbnail(url=thumbnail)
    return embed


def check_user_authorization(ctx, used_command):
    user_vc = ctx.author.voice
    vc = get(ctx.bot.voice_clients, guild=ctx.guild)

    # check if user is in a voice channel
    if user_vc is None:
        return f'{ctx.author.mention} is not in a voice channel!'

    # check if bot is in a voice channel
    if vc is None:
        return 'Bot is not in a voice channel!'

    # check if bot is in the same voice channel as user
    if vc.channel != user_vc.channel:
        return f'{ctx.author.mention}, please join {vc.channel.mention} before using `{ctx.prefix}{used_command}`.'

    return None


def get_guild_music_setting(guild):
    if guild not in guild_music_settings:
        guild_music_settings[guild] = default_music_setting
    return guild_music_settings.get(guild)


def get_guild_music_queue(guild):
    if guild not in guild_music_queues:
        guild_music_queues[guild] = []
    return guild_music_queues.get(guild)


async def send_message(ctx, text=None, embed=discord.Embed.Empty, reactions=None):
    if reactions is None:
        reactions = []

    channel = ctx.channel
    bot = ctx.me

    last_message = channel.last_message
    embeds = last_message.embeds

    # if the sender is this bot and have embeds, delete it
    if last_message.author == bot and len(embeds) > 0:
        await last_message.delete()

    if embed == discord.Embed.Empty:
        msg = await ctx.send(text)
    else:
        msg = await ctx.send(text, embed=embed)
    for reaction in reactions:
        await add_reaction(msg, reaction)
    return msg


async def add_reaction(message, reaction):
    await message.add_reaction(reaction)


async def get_song_data(query):
    title = clean_lyric_query(query)
    return find_song_data(title)


def clean_lyric(lyric):
    lyric = lyric.split('\n', 1)[1]     # remove song title in the first line
    if lyric.endswith('Embed'):         # remove embed
        lyric = lyric[:-5]
    while lyric[-1].isnumeric():        # remove 'pyong' count
        lyric = lyric[:-1]

    return lyric


def clean_lyric_query(query):
    excluded = {'M/V', 'MV'}
    for word in excluded:
        query = query.replace(word, '')
    return query


def update_help_command_info(commands):
    for command in commands:
        if command.name == 'help':
            command.brief = 'Show help'
            command.usage = '`n!help`  or   `n!help <command>`'
            command.description = 'Show list of commands with a short description or ' \
                                  'a detailed description of a specific command.'
            break
