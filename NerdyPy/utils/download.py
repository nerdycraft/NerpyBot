# -*- coding: utf-8 -*-
"""
download and conversion method for Audio Content
"""

import logging
import os
from io import BytesIO

import ffmpeg
import requests
import youtube_dl
from cachetools import TTLCache
from discord import FFmpegOpusAudio
from utils.errors import NerpyException

LOG = logging.getLogger("nerpybot")
FFMPEG_OPTIONS = {"options": "-vn"}
CACHE = TTLCache(maxsize=100, ttl=600)

DL_DIR = "tmp"
if not os.path.exists(DL_DIR):
    os.makedirs(DL_DIR)

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


def convert(source, tag=False, is_stream=True):
    """Convert downloaded file to playable ByteStream"""
    LOG.info("Converting File...")
    if tag:
        process = (
            ffmpeg.input("pipe:")
            .filter("loudnorm")
            .output(filename="pipe:", format="mp3", ac=2, ar="48000")
            .run_async(pipe_stdin=True, pipe_stdout=True, quiet=True, overwrite_output=True)
        )
        stream, _ = process.communicate(input=source.read())
        return stream
    else:
        return FFmpegOpusAudio(source, **FFMPEG_OPTIONS, pipe=is_stream)


def lookup_file(file_name):
    for file in os.listdir(f"{DL_DIR}"):
        if file.startswith(file_name):
            return os.path.join(DL_DIR, file)
    return None


def fetch_yt_infos(url: str):
    """Fetches information about a youtube video"""
    if url in CACHE:
        LOG.info("Using cached information for URL: %s", url)
        return CACHE[url]

    LOG.info("Fetching Information about Video from Youtube...")
    data = None
    try:
        data = YTDL.extract_info(url, download=False)
    except youtube_dl.utils.DownloadError as e:
        if "Sign in to confirm you’re not a bot" in str(e):
            data = YTDL.extract_info(url, download=False)

    CACHE[url] = data
    return data


def download(url: str, tag: bool = False, video_id: str = None):
    """download audio content (maybe transform?)"""

    if video_id is None:
        req_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.7204.143 Safari/537.36",
        }

        with requests.get(url, headers=req_headers, stream=True) as response:
            response.raise_for_status()
            audio_bytes = BytesIO(response.content)

        if audio_bytes is None:
            raise NerpyException(f"could not find a valid source in: {url}")

        return convert(audio_bytes, tag)
    else:
        dlfile = lookup_file(video_id)

        if dlfile is None:
            _ = YTDL.download([url])
            dlfile = lookup_file(video_id)

        return convert(dlfile, is_stream=False)
