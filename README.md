#NerpyBot

## Quickstart
I recommend using a virtualenv or container to run.

Rename or copy ``config.ini.template`` to ``config.ini`` and fill in your tokens before starting the bot.

Install dependencies first: ``python -m pip install .``

Start Bot with: ``python NerdyPy.py``

## Database
Currently tested and support are only SQLite and MariaDB or MySQL.
If you want to use any other database then the above, please specify database type and the connection helper, like so:

```ini
db_type = postgresql+psycopg2
```
For anything else the engine name is enough.

Also, do not forget to install the neccessary python packages for your helper.

Username and password are optional but highly recommended.

```ini
db_username = my_user
db_password = very$ecurepassw0rd
```

MySQL Example:
```ini
[database]
db_type = mysql
db_name = bot
db_username = bot_user
db_password = very$ecurepassw0rd
db_host = mysql_host
db_port = 3306
```

# Join NerdyBot
https://discord.com/api/oauth2/authorize?client_id=246941850223640576&permissions=2217978944&scope=bot
# Join HumanMusic
https://discord.com/api/oauth2/authorize?client_id=883656077357510697&permissions=2217978944&scope=bot
