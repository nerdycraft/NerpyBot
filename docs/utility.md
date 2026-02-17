# Utility Module

General-purpose utility commands. Requires `utility.openweather` API key in config for the weather command.

## Commands

### `/ping`

Responds with "Pong." — a simple latency check.

### `/uptime`

Shows how long the bot has been running since last restart.

**Format:** `X day(s), Y hour(s), Z minute(s)`

The uptime is calculated from `bot.uptime` (set at startup) against `datetime.now(UTC)`.

### `/weather <query>`

Look up current weather for a city.

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | `str` | City name (English only — no umlauts) |

**Validation:** Rejects queries containing `ä`, `ö`, or `ü` — the OpenWeather API requires English city names.

**API:** OpenWeatherMap current weather endpoint.

**Embed layout:**

```
+---------------------------------------------+
|  Weather for CityName                        |
|  (link to openweathermap.org)                |
|                                              |
|  Condition:   Clear                          |
|  Temperature: 18.5 °C                        |
|  Humidity:    65%                             |
|  Wind:        3.2 m/s                        |
|  Min Temp:    15.0 °C                        |
|  Max Temp:    21.0 °C                        |
|  Sunrise:     06:45 UTC                      |
|  Sunset:      18:30 UTC                      |
+---------------------------------------------+
```

- Temperature is converted from Kelvin to Celsius (`K - 273.15`)
- Sunrise/sunset are formatted from UNIX timestamps
- Each field uses an emoji icon prefix

## Configuration

```yaml
utility:
  openweather: your_openweather_api_key
```
