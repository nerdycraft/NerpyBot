# -*- coding: utf-8 -*-
"""
download and conversion method for Audio Content
"""
import logging
from io import BytesIO

import ffmpeg
import requests
import youtube_dl
from discord import FFmpegOpusAudio

from utils.errors import NerpyException

LOG = logging.getLogger("nerpybot")
FFMPEG_OPTIONS = {"options": "-vn"}
YTDL_ARGS = {
    "format": "bestaudio/best",
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

def convert(source, tag=False):
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
        return FFmpegOpusAudio(source, **FFMPEG_OPTIONS, pipe=True)


def fetch_yt_infos(url: str):
    LOG.info("Fetching Information about Video from Youtube...")
    try:
        return YTDL.extract_info(url, download=False)
    except youtube_dl.utils.DownloadError as e:
        if "Sign in to confirm you’re not a bot" in str(e):
            return YTDL.extract_info(url, download=False)


def download(url: str, title=None, tag=False):
    """download audio content (maybe transform?)"""
    req_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.7204.143 Safari/537.36",
    }

    with requests.get(url, headers=req_headers, stream=True) as response:
        response.raise_for_status()
        audio_bytes = BytesIO(response.content)

    if audio_bytes is None:
        raise NerpyException(f"could not find a valid source in: {url}")

    return convert(audio_bytes, tag)
