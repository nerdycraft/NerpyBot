# -*- coding: utf-8 -*-
"""
download and conversion method for Audio Content
"""

import logging
import tempfile
from io import BytesIO
from pathlib import Path

import ffmpeg
import requests
from cachetools import TTLCache
from discord import FFmpegOpusAudio
from utils.errors import NerpyValidationError
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

LOG = logging.getLogger("nerpybot")
FFMPEG_OPTIONS = {"options": "-vn"}
CACHE = TTLCache(maxsize=100, ttl=600)

DL_DIR = Path(tempfile.gettempdir()) / "nerpybot-dl"
DL_DIR.mkdir(exist_ok=True)

YTDL_ARGS = {
    "format": "bestaudio/best",
    "outtmpl": str(DL_DIR / "%(id)s"),
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
# noinspection PyTypeChecker
YTDL = YoutubeDL(YTDL_ARGS)


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
    for file in DL_DIR.iterdir():
        if file.name.startswith(file_name):
            return str(file)
    return None


def fetch_yt_infos(url: str):
    """Fetches information about a YouTube video"""
    if url in CACHE:
        LOG.info("Using cached information for URL: %s", url)
        return CACHE[url]

    LOG.info("Fetching Information about Video from Youtube...")
    data = None
    try:
        data = YTDL.extract_info(url, download=False)
    except DownloadError as e:
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
            raise NerpyValidationError(f"Could not find a valid source in: {url}")

        return convert(audio_bytes, tag)
    else:
        dl_file = lookup_file(video_id)

        if dl_file is None:
            YTDL.download([url])
            dl_file = lookup_file(video_id)

        return convert(dl_file, is_stream=False)
