# -*- coding: utf-8 -*-

from googleapiclient.discovery import build


def youtube(yt_key, return_type, query):
    yt = build("youtube", "v3", developerKey=yt_key)
    search_response = yt.search().list(q=query, part="id,snippet", type="video", maxResults=1).execute()
    items = search_response.get("items", [])

    if len(items) > 0:
        if return_type == "url":
            ret = f'https://www.youtube.com/watch?v={items[0]["id"]["videoId"]}'
        else:
            ret = items[0]["id"]["videoId"]
    else:
        ret = None

    return ret
