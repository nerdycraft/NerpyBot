# NerpyBot

## Quickstart

I recommend using a virtualenv or container to run.

Rename or copy `config.yaml.template` to `config.yaml` and fill in your tokens before starting the bot.

Install dependencies first: `uv sync`

Start Bot with: `python NerdyPy.py`

## Database

Currently tested and support are only SQLite and MariaDB or MySQL.
If you want to use any other database then the above, please specify database type and the connection helper, like so:

```yaml
database:
  db_type: postgresql+psycopg2
```

For anything else the engine name is enough.

Also, do not forget to install the necessary python packages for your helper.

Username and password are optional but highly recommended:

```yaml
database:
  db_username: my_user
  db_password: very$ecurepassw0rd
```

MySQL Example:

```yaml
database:
  db_type: mysql
  db_name: bot
  db_username: bot_user
  db_password: very$ecurepassw0rd
  db_host: mysql_host
  db_port: 3306
```

## Configuration Example

Here's a full example of the config.yaml structure:

```yaml
bot:
  client_id: your_client_id_here
  token: your_bot_token_here
  ops:
    - your_discord_id_here
  error_spam_threshold: 5
  modules:
    - admin
    - fun
    - league
    - moderation
    - music
    - random
    - reminder
    - search
    - tagging
    - utility
    - wow

database:
  db_type: sqlite
  db_name: db.db

audio:
  buffer_limit: 5

search:
  imgur: your_imgur_key
  genius: your_genius_key
  omdb: your_omdb_key
  igdb_client_id: your_igdb_client_id
  igdb_client_secret: your_igdb_client_secret
  ytkey: your_youtube_key

utility:
  openweather: your_openweather_key

league:
  riot: your_riot_api_key

wow:
  wow_id: your_wow_client_id
  wow_secret: your_wow_client_secret
```

# Join NerdyBot

https://discord.com/api/oauth2/authorize?client_id=246941850223640576&permissions=582632143842386&scope=applications.commands+bot

# Join HumanMusic

https://discord.com/api/oauth2/authorize?client_id=883656077357510697&permissions=414467959360&scope=applications.commands+bot
