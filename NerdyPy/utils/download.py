"""
download and conversion method for Audio Content
"""

import os
import uuid
import logging
import youtube_dl
import requests
from utils.errors import NerpyException
from discord import FFmpegPCMAudio


LOG = logging.getLogger("Nerpy")
DL_DIR = "tmp"
if not os.path.exists(DL_DIR):
    os.makedirs(DL_DIR)

FFMPEG_OPTIONS = {"options": "-vn"}

YTDL_ARGS = {
    "format": "bestaudio/best",
    "outtmpl": os.path.join(DL_DIR, "%(id)s"),
    "quiet": True,
    "extractaudio": True,
    "audioformat": "mp3",
    "default_search": "auto",
}

YTDL = youtube_dl.YoutubeDL(YTDL_ARGS)


def convert(source, is_stream=False):
    """Convert downloaded file to playable ByteStream"""
    LOG.info("Converting File...")
    return FFmpegPCMAudio(source, **FFMPEG_OPTIONS, pipe=is_stream)


def lookup_file(file_name):
    for file in os.listdir(f"{DL_DIR}"):
        if file.startswith(file_name):
            return os.path.join(DL_DIR, file)


def fetch_yt_infos(url: str):
    LOG.info("Fetching Information about Video from Youtube...")
    return YTDL.extract_info(url, download=False)


def download(url: str):
    """download audio content (maybe transform?)"""
    req_headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36"
    }

    split = os.path.splitext(url)

    if split[1] is not None and split[1] != "":
        dlfile = os.path.join(DL_DIR, f"{str(uuid.uuid4())}{split[1]}")
        with requests.get(url, headers=req_headers) as response:
            response.raise_for_status()
            with open(dlfile, "wb") as out_file:
                LOG.info("Downloading file")
                for chunk in response.iter_content():
                    out_file.write(chunk)
    else:
        video = fetch_yt_infos(url)
        song = Song(**video)
        dlfile = lookup_file(song.idn)

        if dlfile is None:
            _ = YTDL.download([song.webpage_url])
            dlfile = lookup_file(song.idn)

    if dlfile is None:
        raise NerpyException(f"could not find a download in: {url}")

    return convert(dlfile)


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
