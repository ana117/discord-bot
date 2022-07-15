import discord
from discord.utils import get
from youtube_dl import YoutubeDL

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
    ydl_opts = {'format': 'bestaudio', 'noplaylist': 'True'}

    with YoutubeDL(ydl_opts) as ydl:
        ydl.cache.remove()
        info = ydl.extract_info(f'ytsearch:{youtube_url}', download=False)
    return info['entries'][0]


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


def create_embed(guild, title, description=discord.Embed.Empty, thumbnail=discord.Embed.Empty):
    embed = discord.Embed(title=title, description=description)
    embed.set_footer(text=create_music_settings_status(guild))
    embed.set_thumbnail(url=thumbnail)
    return embed


def check_user_authorization(ctx, used_command):
    user_vc = ctx.author.voice
    vc = get(ctx.bot.voice_clients, guild=ctx.guild)

    error = None
    # check if user is in a voice channel
    if user_vc is None:
        error = f'{ctx.author.mention} is not in a voice channel!'

    # check if bot is in a voice channel
    if vc is None:
        error = 'Bot is not in a voice channel'

    # check if bot is in the same voice channel as user
    if vc.channel != user_vc.channel:
        error = f'{ctx.author.mention}, please join {vc.channel.mention} before using !{used_command}'

    return error


def get_guild_music_setting(guild):
    if guild not in guild_music_settings:
        guild_music_settings[guild] = default_music_setting
    return guild_music_settings.get(guild)


def get_guild_music_queue(guild):
    if guild not in guild_music_queues:
        guild_music_queues[guild] = []
    return guild_music_queues.get(guild)
