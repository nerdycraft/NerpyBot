# Search Module

Multi-source search integration across several APIs. Each command queries a different service and returns results as Discord embeds.

## Commands

### `/imgur <query>`

Search Imgur for viral memes/images.

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | `str` | Search term |

**API:** Imgur Gallery Search with `sort=viral`
**Auth:** `Client-ID` header from `config.search.imgur`
**Returns:** Top result link.

### `/urban <query>`

Look up a term on Urban Dictionary.

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | `str` | Term to define |

**API:** `https://api.urbandictionary.com/v0/define?term={query}`
**Returns:** Embed with definition text, author, and permalink to the full entry.

### `/lyrics <query>`

Search for song lyrics on Genius.

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | `str` | Song or artist name |

**API:** `https://api.genius.com/search?q={query}`
**Auth:** `Bearer` token from `config.search.genius`
**Returns:** Embed with song title, thumbnail, and link to full lyrics on Genius.

### `/youtube <query>`

Search YouTube and return the top result.

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | `str` | Search terms |

**API:** YouTube Data API v3 via `utils/helpers.py:youtube()`
**Auth:** API key from `config.search.ytkey`
**Returns:** Direct video URL of the first search result.

### `/imdb <query_type> <query>`

Look up movies, series, or episodes on OMDB.

| Parameter | Type | Description |
|-----------|------|-------------|
| `query_type` | `Literal["movie", "series", "episode"]` | Type of media |
| `query` | `str` | Title to search |

**API:** `https://www.omdbapi.com/?t={query}&type={type}&apikey={key}`
**Auth:** API key from `config.search.omdb`

**Embed fields:**
- Title, year, rated, runtime
- Genre, director, actors, country, language
- Plot summary
- Poster image as thumbnail

### `/games <query>`

Search for video games on IGDB.

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | `str` | Game title |

**API:** `https://api.igdb.com/v4/games` with a GraphQL-like query body
**Auth:** Twitch OAuth2 (client credentials flow)

**How IGDB Authentication Works:**
1. On first call (or when token expires), request a token from `https://id.twitch.tv/oauth2/token`
2. Cache the token with its expiry time (`self.igdb_token`, `self.igdb_token_expires`)
3. Subsequent calls reuse the cached token until expiry
4. Send as `Client-ID` + `Authorization: Bearer` headers

**Embed fields:**
- Game name, release date, rating
- Genres, summary
- Cover image as thumbnail
- If multiple results, lists up to 5 alternatives

## Configuration

```yaml
search:
  imgur: your_imgur_client_id
  genius: your_genius_bearer_token
  omdb: your_omdb_api_key
  ytkey: your_youtube_api_key
  igdb_client_id: your_twitch_client_id
  igdb_client_secret: your_twitch_client_secret
```

All keys are optional — commands for unconfigured services will fail gracefully with an error message.
