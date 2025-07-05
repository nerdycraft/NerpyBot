# -*- coding: utf-8 -*-
"""
download and conversion method for Audio Content
"""

import logging
import os
import uuid

import ffmpeg
import requests
import youtube_dl
from discord import FFmpegOpusAudio

from utils.errors import NerpyException

LOG = logging.getLogger("nerpybot")
DL_DIR = "tmp"
if not os.path.exists(DL_DIR):
    os.makedirs(DL_DIR)

FFMPEG_OPTIONS = {"options": "-vn"}

YTDL_ARGS = {
    "format": "bestaudio/best",
    "outtmpl": os.path.join(DL_DIR, "%(id)s"),
    "restrictfilenames": True,
    "noplaylist": True,
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "logtostderr": False,
    "quiet": True,
    "verbose": False,
    "no_warnings": True,
    "extractaudio": True,
    "audioformat": "mp3",
    "default_search": "auto",
    "source_address": "0.0.0.0",  # bind to ipv4 since ipv6 addresses cause issues sometimes
}

YTDL = youtube_dl.YoutubeDL(YTDL_ARGS)


def convert(source, tag=False, is_stream=False):
    """Convert downloaded file to playable ByteStream"""
    LOG.info("Converting File...")
    if tag:
        stream, _ = (
            ffmpeg.input(source)
            .filter("loudnorm")
            .output("pipe:", format="mp3", ac=2, ar="48000")
            .overwrite_output()
            .run(capture_stdout=True)
        )
        return stream
    else:
        return FFmpegOpusAudio(source, **FFMPEG_OPTIONS, pipe=is_stream)


def lookup_file(file_name):
    for file in os.listdir(f"{DL_DIR}"):
        if file.startswith(file_name):
            return os.path.join(DL_DIR, file)
    return None


def fetch_yt_infos(url: str):
    LOG.info("Fetching Information about Video from Youtube...")
    return YTDL.extract_info(url, download=False)


def cleanup(file_path: str):
    """Clean up downloaded file after processing"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            LOG.debug(f"Cleaned up file: {file_path}")
    except OSError as e:
        LOG.error(f"Error cleaning up file {file_path}: {e}")


def download(url: str, tag=False):
    """download audio content (maybe transform?)"""
    req_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    split = os.path.splitext(url)
    dlfile = None

    try:
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

        converted = convert(dlfile, tag)

        # Clean up the downloaded file after conversion
        cleanup(dlfile)

        return converted
    except Exception as e:
        # Clean up in case of error
        if dlfile:
            cleanup(dlfile)
        raise e


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
