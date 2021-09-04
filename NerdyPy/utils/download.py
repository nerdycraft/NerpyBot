"""
download method for Audio Content

Needs testing!
"""

import os
import shutil
import urllib.request
import uuid
import ffmpeg
from utils.errors import NerpyException

import youtube_dl

DL_DIR = "tmp"
if not os.path.exists(DL_DIR):
    os.makedirs(DL_DIR)

YTDL_ARGS = {
    "format": "bestaudio/best",
    "outtmpl": os.path.join(DL_DIR, "%(id)s"),
    "quiet": True,
    "extractaudio": True,
    "audioformat": "mp3",
    "default_search": "auto",
}

YTDL = youtube_dl.YoutubeDL(YTDL_ARGS)


def convert(file, debug):
    """Convert downloaded file to playable ByteStream"""
    # TODO: Add better Exception handling
    stream, _ = (
        ffmpeg.input(file)
        .filter("loudnorm")
        .output("pipe:", format="mp3", ac=2, ar="48000")
        .overwrite_output()
        .run(capture_stdout=debug)
    )
    return stream


def lookup_file(file_name):
    for file in os.listdir(f"{DL_DIR}"):
        if file.startswith(file_name):
            return os.path.join(DL_DIR, file)


def fetch_yt_infos(url: str):
    video = YTDL.extract_info(url, download=False)
    if video is not None:
        return video


def download(url: str, debug):
    """download audio content (maybe transform?)"""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36"
        },
    )

    split = os.path.splitext(url)

    if split[1] is not None and split[1] != "":
        dlfile = os.path.join(DL_DIR, f"{str(uuid.uuid4())}{split[1]}")
        with urllib.request.urlopen(req) as response, open(dlfile, "wb") as out_file:
            shutil.copyfileobj(response, out_file)
    else:
        video = YTDL.extract_info(url, download=False)
        song = Song(**video)
        dlfile = lookup_file(song.idn)

        if dlfile is None:
            YTDL.download([song.webpage_url])
            dlfile = lookup_file(song.idn)

    if dlfile is None:
        raise NerpyException(f"could not find a download in: {url}")

    return convert(dlfile, debug)


class Song:
    """Song Model for YTDL"""

    def __init__(self, **kwargs):
        self.__dict__ = kwargs
        self.title = kwargs.pop("title", None)
        self.idn = kwargs.pop("id", None)
        self.url = kwargs.pop("url", None)
        self.webpage_url = kwargs.pop("webpage_url", "")
        self.duration = kwargs.pop("duration", 60)
        self.start_time = kwargs.pop("start_time", None)
        self.end_time = kwargs.pop("end_time", None)
