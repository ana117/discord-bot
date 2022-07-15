import asyncio
import random

import discord
import os

from discord import FFmpegPCMAudio
from discord.utils import get
from dotenv import load_dotenv
from discord.ext import commands

from utils import DEFAULT_VOLUME, download_music, check_user_authorization, \
    get_guild_music_setting, get_guild_music_queue, create_embed

INTENTS = discord.Intents.all()
FFMPEG_OPTS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}

bot = commands.Bot(command_prefix='n!', intents=INTENTS)


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------\n')


@bot.command(aliases=['p'])
async def play(ctx, *args):
    query = " ".join(args)
    voice = await join(ctx)

    if voice is None:
        msg = await ctx.send(f'{ctx.author.mention} is not in a voice channel!')
        return

    music_data = download_music(query)
    title = music_data['title']
    youtube_url = music_data['webpage_url']
    audio_url = music_data['url']
    thumbnail = music_data['thumbnail']

    current_queue = get_guild_music_queue(ctx.guild)
    current_queue.append({
        'title': title,
        'youtube_url': youtube_url,
        'audio_url': audio_url,
        'thumbnail': thumbnail
    })

    if not voice.is_playing():
        voice.play(
            discord.PCMVolumeTransformer(FFmpegPCMAudio(audio_url, **FFMPEG_OPTS), volume=DEFAULT_VOLUME),
            after=lambda e: asyncio.run(play_next(ctx, voice))
        )
        voice.pause()
        await asyncio.sleep(1)
        voice.resume()

        embed_title = 'Now playing'
        embed_thumbnail = thumbnail
    else:
        embed_title = 'Added to queue'
        embed_thumbnail = discord.Embed.Empty

    embed_desc = f'[{title}]({youtube_url})'
    msg = await ctx.send(embed=create_embed(ctx.guild, embed_title, embed_desc, embed_thumbnail))


async def play_next(ctx, voice):
    current_queue = get_guild_music_queue(ctx.guild)
    if len(current_queue) == 0:
        asyncio.run_coroutine_threadsafe(disconnect_by_inactivity(ctx, voice), ctx.bot.loop)
        return

    current_settings = get_guild_music_setting(ctx.guild)
    last_played = current_queue.pop(0)

    if current_settings.get('shuffle', False):
        random.shuffle(current_queue)

    if current_settings.get('loop', False):
        current_queue.append(last_played)

    if len(current_queue) == 0:
        asyncio.run_coroutine_threadsafe(disconnect_by_inactivity(ctx, voice), ctx.bot.loop)
    else:
        music = current_queue[0]
        embed_title = 'Now playing'
        embed_desc = f'[{music["title"]}]({music["youtube_url"]})'
        embed_thumbnail = music['thumbnail']

        voice.play(
            discord.PCMVolumeTransformer(FFmpegPCMAudio(music['audio_url'], **FFMPEG_OPTS), volume=DEFAULT_VOLUME),
            after=lambda e: asyncio.run(play_next(ctx, voice))
        )

        msg = await ctx.send(embed=create_embed(ctx.guild, embed_title, embed_desc, embed_thumbnail)),


@bot.command(aliases=['q'])
async def queue(ctx):
    current_queue = get_guild_music_queue(ctx.guild)
    embed_desc = ''

    if len(current_queue) == 0:
        embed_title = f'Empty Queue'
    else:
        embed_desc = f'Now playing: [{current_queue[0]["title"]}]({current_queue[0]["youtube_url"]})\n\n'
        for i in range(len(current_queue)):
            embed_desc += f'{i + 1}. [{current_queue[i]["title"]}]({current_queue[i]["youtube_url"]})\n'

        embed_title = f'Queue ({len(current_queue)} song{"s" if len(current_queue) > 1 else ""})'

    msg = await ctx.send(embed=create_embed(ctx.guild, embed_title, embed_desc)),


@bot.command()
async def clear(ctx):
    auth_error = check_user_authorization(ctx, 'clear')
    if auth_error is not None:
        msg = await ctx.send(auth_error),

    else:
        get_guild_music_queue(ctx.guild).clear()
        vc = get(bot.voice_clients, guild=ctx.guild)
        vc.stop()

        embed_title = 'Queue Cleared'
        msg = await ctx.send(embed=create_embed(ctx.guild, embed_title)),


@bot.command()
async def skip(ctx):
    auth_error = check_user_authorization(ctx, 'skip')
    if auth_error is not None:
        msg = await ctx.send(auth_error),

    else:
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
    auth_error = check_user_authorization(ctx, 'leave')
    if auth_error is not None:
        msg = await ctx.send(auth_error),

    else:
        await clear(ctx)
        vc = get(bot.voice_clients, guild=ctx.guild)
        await vc.disconnect()


@bot.command(aliases=['loop', 'shuffle'])
async def toggle_music_setting(ctx):
    changed_setting = ctx.invoked_with

    auth_error = check_user_authorization(ctx, changed_setting)
    if auth_error is not None:
        msg = await ctx.send(auth_error),

    else:
        current_setting = get_guild_music_setting(ctx.guild)

        new_setting_value = False if current_setting[changed_setting] else True
        new_setting_status = 'on' if new_setting_value else 'off'
        current_setting[changed_setting] = new_setting_value

        embed_title = f'{changed_setting.capitalize()} is turned {new_setting_status}!'
        msg = await ctx.send(embed=create_embed(ctx.guild, embed_title)),


async def disconnect_by_inactivity(ctx, voice):
    await asyncio.sleep(60)
    if not voice.is_playing():
        embed_title = 'Disconnecting'
        embed_desc = 'No more songs in queue'

        asyncio.run_coroutine_threadsafe(voice.disconnect(), ctx.bot.loop)
        msg = await ctx.send(embed=create_embed(ctx.guild, embed_title, embed_desc)),


def main():
    print(discord.__version__)
    load_dotenv()
    token = os.getenv('TOKEN')
    bot.run(token)


if __name__ == '__main__':
    main()
