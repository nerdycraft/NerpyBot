# -*- coding: utf-8 -*-
"""
download and conversion method for Audio Content
"""

import logging
import tempfile
from io import BytesIO
from pathlib import Path

import requests
from cachetools import TTLCache
from discord import FFmpegOpusAudio
from utils.errors import NerpyValidationError
from yt_dlp import YoutubeDL

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
    "extractaudio": True,
    "audioformat": "mp3",
    "default_search": "auto",
    "source_address": "0.0.0.0",  # bind to ipv4 since ipv6 addresses cause issues sometimes
    "extractor_args": {
        "youtube": {"player_client": ["android", "tv"]}
    },  # android/tv don't require GVS PO Token or JS n-challenge solver
    "logger": LOG,
}
# noinspection PyTypeChecker
YTDL = YoutubeDL(YTDL_ARGS)


def convert(source, is_stream=True):
    """Convert downloaded file to playable ByteStream"""
    LOG.info("Converting File...")
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
    data = YTDL.extract_info(url, download=False)
    CACHE[url] = data
    return data


def download(url: str, video_id: str = None):
    """Download audio content and convert to a playable stream."""

    if video_id is None:
        req_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.7204.143 Safari/537.36",
        }

        with requests.get(url, headers=req_headers, stream=True) as response:
            response.raise_for_status()
            audio_bytes = BytesIO(response.content)

        if audio_bytes is None:
            raise NerpyValidationError(f"Could not find a valid source in: {url}")

        return convert(audio_bytes)
    else:
        dl_file = lookup_file(video_id)

        if dl_file is None:
            YTDL.download([url])
            dl_file = lookup_file(video_id)

        return convert(dl_file, is_stream=False)
