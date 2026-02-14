# Random Module

Random content generators pulling from various public APIs. No database or configuration required beyond the bot's `send_messages` permission.

## Commands

### `/lenny`

Returns a random Lenny face from 9 hardcoded variants (e.g., `( ͡° ͜ʖ ͡°)`, `(ノ͡° ͜ʖ ͡°)ノ︵┻┻`).

No API call — purely local randomization.

### `/quote`

Fetches a random design quote.

**API:** `https://quotesondesign.com/wp-json/wp/v2/posts/?orderby=rand`

**Response:** Quote text with HTML stripped, followed by the author name.

### `/trump`

Fetches a random Trump quote.

**API:** `https://api.whatdoestrumpthink.com/api/v1/quotes/random`

**Response:** The `message` field from the JSON response.

### `/xkcd`

Fetches a random XKCD comic.

**Process:**
1. Fetch `https://xkcd.com/info.0.json` to get the latest comic number
2. Pick a random number between 1 and the latest
3. Fetch `https://xkcd.com/{num}/info.0.json` for that comic
4. Display as an embed with the comic image and alt text

### `/bunny`

Fetches a random bunny GIF.

**API:** `https://api.bunnies.io/v2/loop/random/?media=gif`

**Response:** The GIF URL from the `media.gif` field, displayed as an embed image.
