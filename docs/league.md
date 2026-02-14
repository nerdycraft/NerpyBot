# League of Legends Module

Riot API integration for looking up summoner profiles. Requires `league.riot` API key in config.

## Commands

### `/summoner <region> <summoner_name>`

Look up a League of Legends summoner profile.

| Parameter | Type | Description |
|-----------|------|-------------|
| `region` | `Literal["EUW1", "NA1"]` | Server region |
| `summoner_name` | `str` | Summoner name to look up |

## How the Lookup Works

1. **Fetch summoner** via `GET /lol/summoner/v4/summoners/by-name/{name}` — returns `summoner_id`, `profileIconId`, `summonerLevel`
2. **Fetch ranked data** via `GET /lol/league/v4/entries/by-summoner/{summoner_id}` — returns tier, rank, LP, wins, losses for each queue
3. **Fetch DDragon version** via `https://ddragon.leagueoflegends.com/api/versions.json` — needed for profile icon URL

## Notification in Discord

The response is an embed containing:

```
+---------------------------------------------+
|  [Profile Icon]  SummonerName               |
|                                              |
|  Level: 350                                  |
|                                              |
|  RANKED_SOLO_5x5                             |
|  Gold II - 45 LP                             |
|  Wins: 120 | Losses: 98                      |
|                                              |
|  RANKED_FLEX_SR                              |
|  Silver I - 72 LP                            |
|  Wins: 45 | Losses: 38                       |
+---------------------------------------------+
```

- **Color:** Blue (`0x0099ff`)
- **Thumbnail:** Profile icon from DDragon CDN
- **Fields:** One field per ranked queue showing tier, rank, LP, and W/L record

## Configuration

```yaml
league:
  riot: your_riot_api_key
```

The API key is sent as `X-Riot-Token` header on all requests.
