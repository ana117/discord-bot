import os

from dotenv import load_dotenv
from lyricsgenius import Genius

load_dotenv()
genius_token = os.getenv('GENIUS_TOKEN')
genius = Genius(genius_token)
genius.remove_section_headers = True
genius.verbose = False


def find_song_data(title, artist=''):
    song = genius.search_song(title, artist)
    return song
