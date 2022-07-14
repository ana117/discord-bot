import asyncio
import random
from asyncio import sleep, run

import discord
import os

from discord import FFmpegPCMAudio
from discord.utils import get
from dotenv import load_dotenv
from discord.ext import commands
from youtube_dl import YoutubeDL

INTENTS = discord.Intents.all()
FFMPEG_OPTS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}
DEFAULT_VOLUME = 1.0

bot = commands.Bot(command_prefix='n!', intents=INTENTS)
guild_music_queues = {}
guild_music_settings = {}
default_music_setting = {
    'loop': False,
    'shuffle': False,
    'volume': DEFAULT_VOLUME,
}


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------\n')


@bot.command(aliases=['p'])
async def play(ctx, *args):
    query = " ".join(args)

    voice = await join(ctx)
    if voice is None:
        asyncio.run_coroutine_threadsafe(ctx.send(f'{ctx.author.mention} is not in a voice channel!'), bot.loop)
        return

    music_data = await download_music(query)
    title = music_data['title']
    youtube_url = music_data['webpage_url']
    audio_url = music_data['url']
    thumbnail = music_data['thumbnail']

    current_queue = guild_music_queues.get(ctx.guild, [])
    current_queue.append({
        'title': title,
        'youtube_url': youtube_url,
        'audio_url': audio_url,
        'thumbnail': thumbnail
    })
    guild_music_queues[ctx.guild] = current_queue

    if ctx.guild not in guild_music_settings:
        guild_music_settings[ctx.guild] = default_music_setting

    if not voice.is_playing():
        voice.play(
            discord.PCMVolumeTransformer(FFmpegPCMAudio(audio_url, **FFMPEG_OPTS), volume=DEFAULT_VOLUME),
            after=lambda e: run(play_next(ctx, voice))
        )
        voice.pause()
        await sleep(1)
        voice.resume()

        embed_title = 'Now playing'
        embed_thumbnail = thumbnail
    else:
        embed_title = 'Added to queue'
        embed_thumbnail = discord.Embed.Empty

    embed_desc = f'[{title}]({youtube_url})'
    embed = discord.Embed(title=embed_title, description=embed_desc)
    embed.set_footer(text=create_music_setting_footer(ctx))
    embed.set_thumbnail(url=embed_thumbnail)
    asyncio.run_coroutine_threadsafe(ctx.send(embed=embed), bot.loop)


async def play_next(ctx, voice):
    current_queue = guild_music_queues.get(ctx.guild, [])
    if len(current_queue) == 0:
        asyncio.run_coroutine_threadsafe(disconnect_from_vc(ctx, voice), bot.loop)
        return

    current_settings = guild_music_settings.get(ctx.guild, {})
    last_played = current_queue.pop(0)

    if current_settings.get('shuffle', False):
        random.shuffle(current_queue)

    if current_settings.get('loop', False):
        current_queue.append(last_played)

    if len(current_queue) > 0:
        music = current_queue[0]
        embed_title = 'Now playing'
        embed_desc = f'[{music["title"]}]({music["youtube_url"]})'
        embed_thumbnail = music['thumbnail']

        voice.play(
            discord.PCMVolumeTransformer(FFmpegPCMAudio(music['audio_url'], **FFMPEG_OPTS), volume=DEFAULT_VOLUME),
            after=lambda e: run(play_next(ctx, voice))
        )

        embed = discord.Embed(title=embed_title, description=embed_desc)
        embed.set_footer(text=create_music_setting_footer(ctx))
        embed.set_thumbnail(url=embed_thumbnail)
        asyncio.run_coroutine_threadsafe(ctx.send(embed=embed), bot.loop)
    else:
        asyncio.run_coroutine_threadsafe(disconnect_from_vc(ctx, voice), bot.loop)


@bot.command(aliases=['q'])
async def queue(ctx):
    current_queue = guild_music_queues.get(ctx.guild, [])
    embed_desc = ''
    if current_queue:
        embed_desc = f'Now playing: [{current_queue[0]["title"]}]({current_queue[0]["youtube_url"]})\n\n'
        for i in range(len(current_queue)):
            embed_desc += f'{i + 1}. [{current_queue[i]["title"]}]({current_queue[i]["youtube_url"]})\n'

        embed_title = f'Queue ({len(current_queue)} song{"s" if len(current_queue)>1 else ""})'
    else:
        embed_title = f'Empty Queue'

    embed = discord.Embed(title=embed_title, description=embed_desc)
    embed.set_footer(text=create_music_setting_footer(ctx))
    asyncio.run_coroutine_threadsafe(ctx.send(embed=embed), bot.loop)


@bot.command()
async def clear(ctx):
    if await is_user_authorized_vc(ctx, 'stop'):
        guild_music_queues.get(ctx.guild).clear()
        vc = get(bot.voice_clients, guild=ctx.guild)
        vc.stop()

        embed = discord.Embed(title='Queue Cleared')
        embed.set_footer(text=create_music_setting_footer(ctx))
        asyncio.run_coroutine_threadsafe(ctx.send(embed=embed), bot.loop)


@bot.command()
async def skip(ctx):
    if await is_user_authorized_vc(ctx, 'skip'):
        vc = get(bot.voice_clients, guild=ctx.guild)
        vc.stop()


@bot.command()
async def join(ctx):
    # check if user is in a voice channel
    if ctx.author.voice is None:
        return None

    # check if bot is already in a voice channel
    vc = get(bot.voice_clients, guild=ctx.guild)
    if vc:
        return vc

    channel = ctx.author.voice.channel
    return await channel.connect()


@bot.command()
async def leave(ctx):
    if await is_user_authorized_vc(ctx, 'leave'):
        await clear(ctx)
        vc = get(bot.voice_clients, guild=ctx.guild)
        await vc.disconnect()


@bot.command(aliases=['loop', 'shuffle'])
async def change_music_setting(ctx):
    changed_setting = ctx.invoked_with
    if await is_user_authorized_vc(ctx, changed_setting):
        current_setting = guild_music_settings.get(ctx.guild, default_music_setting)

        new_setting_value = False if current_setting[changed_setting] else True
        new_setting_status = 'on' if new_setting_value else 'off'
        current_setting[changed_setting] = new_setting_value

        embed = discord.Embed(
            title=f'{changed_setting.capitalize()} is turned {new_setting_status}!'
        )
        embed.set_footer(text=create_music_setting_footer(ctx))
        asyncio.run_coroutine_threadsafe(ctx.send(embed=embed), bot.loop)


def create_music_setting_footer(ctx):
    current_setting = guild_music_settings.get(ctx.guild, default_music_setting)
    loop_status = 'on' if current_setting.get('loop', False) else 'off'
    shuffle_status = 'on' if current_setting.get('shuffle', False) else 'off'
    return f'loop: {loop_status} | shuffle: {shuffle_status}'


async def disconnect_from_vc(ctx, voice):
    await asyncio.sleep(60)
    if not voice.is_playing():
        embed_title = 'Disconnecting'
        embed_desc = 'No more songs in queue'
        embed = discord.Embed(title=embed_title, description=embed_desc)
        embed.set_footer(text=create_music_setting_footer(ctx))

        asyncio.run_coroutine_threadsafe(voice.disconnect(), bot.loop)
        asyncio.run_coroutine_threadsafe(ctx.send(embed=embed), bot.loop)


async def download_music(query):
    youtube_url = query_to_search_query(query)
    ydl_opts = {'format': 'bestaudio', 'noplaylist': 'True'}
    with YoutubeDL(ydl_opts) as ydl:
        ydl.cache.remove()
        info = ydl.extract_info(f'ytsearch:{youtube_url}', download=False)
    return info['entries'][0]


def query_to_search_query(query):
    # if the query is not a YouTube link, add ytsearch:
    if not query.startswith('https://www.youtube.com'):
        query = f'ytsearch:{query}'
    return query


async def is_user_authorized_vc(ctx, used_command):
    user_vc = ctx.author.voice
    vc = get(bot.voice_clients, guild=ctx.guild)

    # check if user is in a voice channel
    if user_vc is None:
        asyncio.run_coroutine_threadsafe(ctx.send(f'{ctx.author.mention} is not in a voice channel!'), bot.loop)
        return False

    # check if bot is in a voice channel
    if vc is None:
        asyncio.run_coroutine_threadsafe(ctx.send('Bot is not in a voice channel'), bot.loop)
        return False

    # check if bot is in the same voice channel as user
    if vc.channel != user_vc.channel:
        asyncio.run_coroutine_threadsafe(
            ctx.send(f'{ctx.author.mention}, please join {vc.channel.mention} before using !{used_command}'),
            bot.loop
        )
        return False

    return True


def main():
    print(discord.__version__)
    load_dotenv()
    token = os.getenv('TOKEN')
    bot.run(token)


if __name__ == '__main__':
    main()
