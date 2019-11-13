"""
download method for Audio Content

Needs testing!
"""

import os
import shutil
import subprocess
import urllib.request
import uuid
from utils.errors import NerpyException

import youtube_dl

DL_DIR = 'tmp'
if not os.path.exists(DL_DIR):
    os.makedirs(DL_DIR)

YTDL_ARGS = {
    'format': 'bestaudio/best',
    'outtmpl': os.path.join(DL_DIR, '%(id)s'),
    'quiet': True,
    'extractaudio': True,
    'audioformat': "mp3",
    'default_search': 'auto',
}


def download(url: str):
    """download audio content (maybe transform?)"""
    dlfile = ""
    ytdl = youtube_dl.YoutubeDL(YTDL_ARGS)

    split = os.path.splitext(url)

    if split[1] is not None and split[1] is not '':
        dlfile = os.path.join(DL_DIR, f'{str(uuid.uuid4())}{split[1]}')
        with urllib.request.urlopen(url) as response, open(dlfile, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
    else:
        video = ytdl.extract_info(url)
        song = Song(**video)

        for file in os.listdir(f"{DL_DIR}"):
            if file.startswith(song.idn):
                dlfile = os.path.join(DL_DIR, file)
                break

    if dlfile is None:
        raise NerpyException(f'could not find a download in: {url}')

    # TODO: Add better Exception handling
    outfile = f'{str(uuid.uuid4())}.mp3'
    command = ['ffmpeg',
               "-i", dlfile,
               "-f", "mp3",
               "-ar", "48000",
               "-ac", "2",
               "-loglevel", "warning",
               outfile]
    subprocess.call(command)
    # TODO use stdout to get bytes?
    return outfile


class Song:
    """Song Model for YTDL"""

    def __init__(self, **kwargs):
        self.__dict__ = kwargs
        self.title = kwargs.pop('title', None)
        self.idn = kwargs.pop('id', None)
        self.url = kwargs.pop('url', None)
        self.webpage_url = kwargs.pop('webpage_url', "")
        self.duration = kwargs.pop('duration', 60)
        self.start_time = kwargs.pop('start_time', None)
        self.end_time = kwargs.pop('end_time', None)
