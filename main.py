import asyncio
import random

import discord
import os

from discord import FFmpegPCMAudio
from discord.utils import get
from dotenv import load_dotenv
from discord.ext import commands

from utils import DEFAULT_VOLUME, download_music, check_user_authorization, \
    get_guild_music_setting, get_guild_music_queue, create_embed, send_message, get_lyric, clean_lyric, \
    update_help_command_info

INTENTS = discord.Intents.all()
FFMPEG_OPTS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}


class CustomHelp(commands.MinimalHelpCommand):
    def add_bot_commands_formatting(self, commands, heading):
        output = ['```']
        for command in commands:
            spaces = 25 - len(command.name)
            blank_space = ' '
            if spaces < 0:
                spaces = 0
            spaces_str = blank_space * spaces
            output.append(f'{command.name}{spaces_str}{command.brief}')
        output.append('```')
        self.paginator.add_line('\n'.join(output))

    def add_command_formatting(self, command):
        self.paginator.add_line(f'**{self.clean_prefix}{command.qualified_name}**\n')
        self.paginator.add_line(f'{command.description}\n')
        self.paginator.add_line(f'**Usage:** {command.usage}')

        if command.aliases:
            self.add_aliases_formatting(command.aliases)

    def add_aliases_formatting(self, aliases):
        output = f'**{self.aliases_heading}** '
        formatted_aliases = []
        for alias in aliases:
            formatted_aliases.append(f'n!{alias}')
        output += ', '.join(formatted_aliases)
        self.paginator.add_line(output)

    async def send_pages(self):
        destination = self.get_destination()
        embed = discord.Embed(description='')
        for page in self.paginator.pages:
            embed.description += page
        await destination.send(embed=embed)


bot = commands.Bot(command_prefix='n!', intents=INTENTS, help_command=CustomHelp())


@bot.event
async def on_ready():
    activity = discord.Activity(name='over you', type=discord.ActivityType.watching)
    await bot.change_presence(activity=activity)

    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------\n')


@bot.command(aliases=['p'],
             brief='Play an audio from YouTube',
             usage='`n!play <query>` |  query can be a video title or a YouTube URL.',
             description='Play an audio from YouTube. '
                         'If the bot is playing something, than this command will add the new audio to the queue.')
async def play(ctx, *args):
    query = " ".join(args)
    voice = await join(ctx)

    if voice is None:
        await send_message(ctx, text=f'{ctx.author.mention} is not in a voice channel!')
        return

    music_datas = download_music(query)
    current_queue = get_guild_music_queue(ctx.guild)
    for music_data in music_datas:
        current_queue.append({
            'title': music_data['title'],
            'youtube_url': music_data['webpage_url'],
            'audio_url': music_data['url'],
            'thumbnail': music_data['thumbnail']
        })

    title = music_datas[0]['title']
    youtube_url = music_datas[0]['webpage_url']
    audio_url = music_datas[0]['url']
    thumbnail = music_datas[0]['thumbnail']

    reactions = []
    if not voice.is_playing():
        voice.play(
            discord.PCMVolumeTransformer(FFmpegPCMAudio(audio_url, **FFMPEG_OPTS), volume=DEFAULT_VOLUME),
            after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx, voice), ctx.bot.loop)
        )

        embed_title = 'Now playing'
        embed_thumbnail = thumbnail
        reactions.append('📜')
    else:
        embed_title = 'Added to queue'
        embed_thumbnail = discord.Embed.Empty

    embed_desc = f'[{title}]({youtube_url})'
    await send_message(
        ctx,
        embed=create_embed(ctx.guild, embed_title, embed_desc, embed_thumbnail),
        reactions=reactions
    )


async def play_next(ctx, voice):
    current_queue = get_guild_music_queue(ctx.guild)
    if len(current_queue) == 0:
        await disconnect_by_inactivity(ctx, voice)
        return

    current_settings = get_guild_music_setting(ctx.guild)
    last_played = current_queue.pop(0)

    if current_settings.get('shuffle', False):
        random.shuffle(current_queue)

    if current_settings.get('loop', False):
        current_queue.append(last_played)

    if len(current_queue) == 0:
        await disconnect_by_inactivity(ctx, voice)
    else:
        music = current_queue[0]
        embed_title = 'Now playing'
        embed_desc = f'[{music["title"]}]({music["youtube_url"]})'
        embed_thumbnail = music['thumbnail']
        reactions = ['📜']

        voice.play(
            discord.PCMVolumeTransformer(FFmpegPCMAudio(music['audio_url'], **FFMPEG_OPTS), volume=DEFAULT_VOLUME),
            after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx, voice), ctx.bot.loop)
        )

        await send_message(
            ctx,
            embed=create_embed(ctx.guild, embed_title, embed_desc, embed_thumbnail),
            reactions=reactions
        )


@bot.command(aliases=['q'],
             brief='Show current queue',
             usage='`n!queue`',
             description='Show current queue (with number of songs left and currently playing song).')
async def queue(ctx):
    current_queue = get_guild_music_queue(ctx.guild)
    embed_desc = ''

    embed_title = f'Empty Queue'
    if len(current_queue) != 0:
        embed_desc = f'**Now playing:**  [{current_queue[0]["title"]}]({current_queue[0]["youtube_url"]})\n\n'

        if len(current_queue) > 1:
            embed_title = f'Queue ({len(current_queue) - 1} song{"s" if len(current_queue) - 1 > 1 else ""})'

            for i in range(1, len(current_queue)):
                embed_desc += f'{i}.  [{current_queue[i]["title"]}]({current_queue[i]["youtube_url"]})\n'

    await send_message(ctx, embed=create_embed(ctx.guild, embed_title, embed_desc))


@bot.command(brief='Clear queue',
             usage='`n!clear`',
             description='Clear queue and stop currently playing song.')
async def clear(ctx):
    auth_error = check_user_authorization(ctx, 'clear')
    if auth_error is not None:
        await send_message(ctx, text=auth_error)

    else:
        get_guild_music_queue(ctx.guild).clear()
        vc = get(bot.voice_clients, guild=ctx.guild)
        vc.stop()

        embed_title = 'Queue Cleared'
        await send_message(ctx, embed=create_embed(ctx.guild, embed_title))


@bot.command(brief='Skip current song',
             usage='`n!skip`',
             description='Skip currently playing song.')
async def skip(ctx):
    auth_error = check_user_authorization(ctx, 'skip')
    if auth_error is not None:
        await send_message(ctx, text=auth_error)
    else:
        vc = get(bot.voice_clients, guild=ctx.guild)
        vc.stop()


@bot.command(brief='Join voice channel',
             usage='`n!join`',
             description="Join command's author voice channel.")
async def join(ctx):
    # check if user is in a voice channel
    if ctx.author.voice is None:
        return None

    # check if bot is already in a voice channel
    vc = get(bot.voice_clients, guild=ctx.guild)
    if vc:
        return vc

    channel = ctx.author.voice.channel
    voice = await channel.connect()
    await ctx.guild.change_voice_state(channel=voice.channel, self_deaf=True)
    return voice


@bot.command(brief='Leave voice channel',
             usage='`n!leave`',
             description='Leave currently connected voice channel. '
                         'Can be only used by user on the same voice channel')
async def leave(ctx):
    auth_error = check_user_authorization(ctx, 'leave')
    if auth_error is not None:
        await send_message(ctx, text=auth_error)
    else:
        await clear(ctx)
        vc = get(bot.voice_clients, guild=ctx.guild)
        await vc.disconnect()


@bot.command(brief='Toggle loop queue',
             usage='`n!loop`',
             description='Turn loop on if currently off and vice versa.')
async def loop(ctx):
    await toggle_music_setting(ctx, 'loop')


@bot.command(brief='Toggle shuffle queue',
             usage='`n!shuffle`',
             description='Turn shuffle on if currently off and vice versa.')
async def shuffle(ctx):
    await toggle_music_setting(ctx, 'shuffle')


async def toggle_music_setting(ctx, setting):
    auth_error = check_user_authorization(ctx, setting)
    if auth_error is not None:
        await send_message(ctx, text=auth_error)
    else:
        current_setting = get_guild_music_setting(ctx.guild)

        new_setting_value = False if current_setting[setting] else True
        new_setting_status = 'on' if new_setting_value else 'off'
        current_setting[setting] = new_setting_value

        embed_title = f'{setting.capitalize()} is turned {new_setting_status}!'
        await send_message(ctx, embed=create_embed(ctx.guild, embed_title))


@bot.command(brief='Get a song lyric',
             usage='`n!lyric`  or  `n!lyric <query>`',
             description='Get a song lyric. If no query is used, will use currently playing song title.')
async def lyric(ctx, *args):
    query = " ".join(args)

    is_manual_search = True
    if len(query) == 0:
        is_manual_search = False
        current_queue = get_guild_music_queue(ctx.guild)
        if len(current_queue) != 0:
            query = current_queue[0].get('title')

    song = await get_lyric(query)
    if song is None:
        if is_manual_search:
            description = 'Try a more specific query or add the artist name on the query'
        else:
            description = 'Try searching manually using `n!lyric <query>`'
        embed = create_embed(ctx.guild, f'Lyric for {query} not found', description=description)
    else:
        song_data = song.to_dict()
        embed = create_embed(
            ctx.guild,
            song_data.get('full_title'),
            description=clean_lyric(song_data.get('lyrics')),
            url=song_data.get('url')
        )

    await send_message(ctx, embed=embed)


async def disconnect_by_inactivity(ctx, voice):
    await asyncio.sleep(60)
    vc = get(bot.voice_clients, guild=ctx.guild)
    if vc is not None and not voice.is_playing():
        embed_title = 'Disconnecting'
        embed_desc = 'No more songs in queue'

        await voice.disconnect()
        await send_message(ctx, embed=create_embed(ctx.guild, embed_title, embed_desc))


@bot.event
async def on_reaction_add(reaction, user):
    message_author = reaction.message.author
    embeds = reaction.message.embeds
    print()
    if len(embeds) > 0:
        embed = embeds[0]
        if message_author == bot.user and embed.title == 'Now playing' and reaction.emoji == '📜' and user != bot.user:
            print(embed.description)


def main():
    print(discord.__version__)
    load_dotenv()
    token = os.getenv('DISCORD_TOKEN')
    update_help_command_info(bot.commands)

    bot.run(token)


if __name__ == '__main__':
    main()
