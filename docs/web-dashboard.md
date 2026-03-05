# Web Dashboard

REST API for managing NerpyBot guild settings via a web interface. Built with FastAPI, authenticated through Discord
OAuth2, and connected to the bot via Valkey pub/sub.

## Architecture

The web dashboard is a **standalone FastAPI service** that shares the database with the bot via SQLAlchemy. It does not
import or run any bot code directly.

```
Browser  →  FastAPI (web/)  →  SQLAlchemy (shared DB)
                            →  Valkey pub/sub  →  Bot process
```

- **Database**: Direct read/write for guild settings (language, moderator roles, leave messages, etc.)
- **Valkey**: Pub/sub channel for bot runtime commands (health check, module load/unload)
- **Auth**: Discord OAuth2 → JWT tokens for stateless API authentication

## Setup

### 1. Discord Application

In the [Discord Developer Portal](https://discord.com/developers/applications):

1. Go to your bot's application → **OAuth2**
2. Add a redirect URI: `http://localhost:8000/api/auth/callback` (or your production URL)
3. Note the **Client ID** and **Client Secret**

### 2. Environment Variables

The web service reads `NERPYBOT_WEB_*` environment variables:

| Variable                        | Required | Description                                         |
| ------------------------------- | -------- | --------------------------------------------------- |
| `NERPYBOT_WEB_CLIENT_ID`        | Yes      | Discord application client ID                       |
| `NERPYBOT_WEB_CLIENT_SECRET`    | Yes      | Discord application client secret                   |
| `NERPYBOT_WEB_REDIRECT_URI`     | Yes      | OAuth2 callback URL                                 |
| `NERPYBOT_WEB_JWT_SECRET`       | Yes      | Secret key for signing JWT tokens                   |
| `NERPYBOT_WEB_OPS`              | Yes      | Comma-separated Discord user IDs (operators)        |
| `NERPYBOT_WEB_VALKEY_URL`       | Yes      | Valkey connection URL (e.g. `valkey://valkey:6379`) |
| `NERPYBOT_WEB_DB_TYPE`          | Yes      | `sqlite` or `postgresql`                            |
| `NERPYBOT_WEB_DB_NAME`          | Yes      | Database name or file path                          |
| `NERPYBOT_WEB_DB_USERNAME`      | No       | PostgreSQL username                                 |
| `NERPYBOT_WEB_DB_PASSWORD`      | No       | PostgreSQL password                                 |
| `NERPYBOT_WEB_DB_HOST`          | No       | PostgreSQL host                                     |
| `NERPYBOT_WEB_DB_PORT`          | No       | PostgreSQL port                                     |
| `NERPYBOT_WEB_JWT_EXPIRY_HOURS` | No       | JWT token lifetime (default: 24)                    |

The bot also needs `NERPYBOT_WEB_VALKEY_URL` set to connect to Valkey for pub/sub commands.

### 3. Config File (alternative)

For the bot side, add to `config.yaml`:

```yaml
web:
  client_secret: your_discord_client_secret
  redirect_uri: http://localhost:8000/api/auth/callback
  jwt_secret: change_me_random_string
  jwt_expiry_hours: 24
  valkey_url: valkey://localhost:6379
```

## Docker Deployment

`docker-compose.yml` includes three relevant services:

```bash
# Start everything (bot + web + valkey + migrations)
docker compose up -d

# Start only the web dashboard stack
docker compose up -d valkey nerpybot-migrations nerpybot-web
```

The `nerpybot-web` service exposes port **8000** by default. The `valkey` service provides the pub/sub bridge between
the web API and the bot.

### Building Images

```bash
docker buildx build --target web -t nerpybot-web .
docker buildx build --target bot -t nerpybot .
```

## Local Development

Run the three components separately:

```bash
# 1. Start Valkey (or Redis)
docker run -d --name valkey -p 6379:6379 valkey/valkey:8-alpine

# 2. Start the bot with Valkey URL configured
NERPYBOT_WEB_VALKEY_URL=valkey://localhost:6379 uv run python NerdyPy/bot.py

# 3. Start the web service (using config file — easiest for local dev)
uv run python -m uvicorn web.app:create_app --factory --reload
```

### Config File vs Environment Variables

The web service supports both **config file** and **env vars** (env vars override file values):

**Option A: Config file** (recommended for local development) — add a `web` section to your existing
`NerdyPy/config.yaml`. The web service reads the same `config.yaml` as the bot:

```yaml
web:
  client_secret: your_discord_client_secret
  redirect_uri: http://localhost:8000/api/auth/callback
  jwt_secret: dev-secret
  valkey_url: valkey://localhost:6379
```

The `bot.client_id`, `bot.ops`, and `database` sections are shared with the bot config.

**Option B: Env vars** (used in Docker) — set `NERPYBOT_WEB_*` variables as shown in the env vars table above.

**Option C: Both** — base config in file, overrides via env vars. Env vars always win.

## API Documentation

Interactive Swagger docs are available at `/api/docs` when the service is running.

### Authentication Flow

1. **`GET /api/auth/login`** — Redirects to Discord OAuth2 authorization page
2. **Discord** — User authorizes, Discord redirects back with a `code`
3. **`GET /api/auth/callback?code=...`** — Exchanges code for Discord token, resolves guild permissions, issues a JWT
4. **Subsequent requests** — Include `Authorization: Bearer <jwt>` header
5. **`GET /api/auth/me`** — Returns current user profile and accessible guilds

### Permission Model

| Level        | Access                                                                       |
| ------------ | ---------------------------------------------------------------------------- |
| **Operator** | Full access — health, modules, all guilds                                    |
| **Admin**    | Guild settings for guilds where user is admin or has Manage Guild permission |
| **Member**   | No access (403)                                                              |

Guild permissions are resolved from Discord at login and cached in Valkey (5-minute TTL).

### Endpoints

#### Auth (`/api/auth/`)

| Method | Path        | Description                   |
| ------ | ----------- | ----------------------------- |
| GET    | `/login`    | Redirect to Discord OAuth2    |
| GET    | `/callback` | Exchange code, return JWT     |
| GET    | `/me`       | Current user profile & guilds |

#### Guild Settings (`/api/guilds/`)

All guild endpoints require admin access to the specific guild (or operator status).

| Method | Path                                     | Description                 |
| ------ | ---------------------------------------- | --------------------------- |
| GET    | `/`                                      | List accessible guilds      |
| GET    | `/{guild_id}/language`                   | Get language config         |
| PUT    | `/{guild_id}/language`                   | Update language             |
| GET    | `/{guild_id}/moderator-roles`            | List moderator roles        |
| POST   | `/{guild_id}/moderator-roles`            | Add moderator role          |
| DELETE | `/{guild_id}/moderator-roles/{role_id}`  | Remove moderator role       |
| GET    | `/{guild_id}/leave-messages`             | Get leave message config    |
| PUT    | `/{guild_id}/leave-messages`             | Update leave messages       |
| GET    | `/{guild_id}/auto-delete`                | List auto-delete rules      |
| POST   | `/{guild_id}/auto-delete`                | Create auto-delete rule     |
| PUT    | `/{guild_id}/auto-delete/{rule_id}`      | Update auto-delete rule     |
| DELETE | `/{guild_id}/auto-delete/{rule_id}`      | Remove auto-delete rule     |
| GET    | `/{guild_id}/auto-kicker`                | Get auto-kicker config      |
| PUT    | `/{guild_id}/auto-kicker`                | Update auto-kicker          |
| GET    | `/{guild_id}/reaction-roles`             | List reaction role messages |
| GET    | `/{guild_id}/role-mappings`              | List role mappings          |
| POST   | `/{guild_id}/role-mappings`              | Create role mapping         |
| DELETE | `/{guild_id}/role-mappings/{mapping_id}` | Remove role mapping         |
| GET    | `/{guild_id}/reminders`                  | List reminders              |
| GET    | `/{guild_id}/application-forms`          | List application forms      |
| GET    | `/{guild_id}/wow`                        | Get WoW config              |

#### Operator (`/api/operator/`)

All operator endpoints require operator status (user ID in ops list).

| Method | Path                     | Description         |
| ------ | ------------------------ | ------------------- |
| GET    | `/health`                | Bot health metrics  |
| GET    | `/modules`               | List loaded modules |
| POST   | `/modules/{name}/load`   | Load a bot module   |
| POST   | `/modules/{name}/unload` | Unload a bot module |

## Data Flow

### Guild Settings (read/write)

```
Client  →  GET /api/guilds/123/language
        →  JWT validated → guild access checked
        →  SQLAlchemy query → GuildLanguageConfig.get(123)
        →  JSON response
```

### Bot Commands (via Valkey)

```
Client  →  POST /api/operator/modules/music/load
        →  JWT validated → operator check
        →  Publish to Valkey channel "nerpybot:web:commands"
        →  Bot subscriber picks up message
        →  Bot executes load_extension("modules.music")
        →  Bot publishes response to "nerpybot:web:responses:{request_id}"
        →  Web reads response (2s timeout)
        →  JSON response to client
```
