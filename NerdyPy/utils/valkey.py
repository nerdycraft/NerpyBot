"""
Valkey pub/sub integration for web dashboard ↔ bot communication.

The listener loop runs as an asyncio background task. It subscribes to the
``nerpybot:cmd`` channel, dispatches each incoming command to
``handle_valkey_command``, and writes the result back under
``nerpybot:reply:<request_id>`` with a 10-second TTL.
"""

import json
from asyncio import CancelledError, run_coroutine_threadsafe, to_thread
from datetime import UTC, datetime
from importlib.metadata import version as pkg_version


def _run_in_bot_loop(bot, coro, timeout: float = 5):
    """Run a coroutine on the bot's event loop from a sync context and return its result."""
    future = run_coroutine_threadsafe(coro, bot.loop)
    return future.result(timeout=timeout)


def _is_valid_module_name(module: str) -> bool:
    """Return True if module is a valid loadable module name (lowercase alpha + underscores)."""
    return bool(module and module.replace("_", "").isalpha() and module.islower())


def _get_guild(bot, payload: dict):
    """Extract guild_id from payload and return the Guild, or None if not found."""
    guild_id = int(payload.get("guild_id", 0))
    return bot.get_guild(guild_id)


def handle_valkey_command(bot, command: str, payload: dict) -> dict:
    """
    Dispatches Valkey pub/sub commands from the web dashboard and returns a command-specific response dictionary.

    Parameters:
        bot: The running NerpyBot instance handling commands.
        command (str): The Valkey command name to execute (e.g., "health", "list_modules", "module_load").
        payload (dict): Command parameters; contents vary by command.

    Returns:
        dict: A command-specific response. Examples include:
            - health: {"guild_count", "voice_connections", "latency_ms", "uptime_seconds", "python_version", "discord_py_version", "bot_version"}
            - list_modules: {"modules": [{"name", "loaded"}, ...]}
            - module_load/module_unload: {"success": True} or {"success": False, "error": "..."}
            - get_channels: {"channels": [{"id", "name", "type"}, ...]}
            - get_roles: {"roles": [{"id", "name"}, ...]}
            - get_member_names: mapping of user ID strings to display names
            - post_apply_button: {"queued": True} or {"error": "..."}
            - search_realms: {"realms": [{"name", "slug"}, ...]} or {"error": "..."}
            - validate_wow_guild: {"valid": bool, "display_name": str or None} and optionally {"error": "..."}
            - unknown commands: {"error": "Unknown command: ..."}
    """
    if command == "health":
        import sys

        import discord

        uptime_seconds = (datetime.now(UTC) - bot.uptime).total_seconds()
        return {
            "guild_count": len(bot.guilds),
            "voice_connections": len(bot.voice_clients),
            "latency_ms": round(bot.latency * 1000, 2),
            "uptime_seconds": round(uptime_seconds, 2),
            "python_version": sys.version.split()[0],
            "discord_py_version": discord.__version__,
            "bot_version": pkg_version("NerpyBot"),
        }
    elif command == "list_modules":
        modules = []
        for ext_name in bot.extensions:
            name = ext_name.replace("modules.", "")
            modules.append({"name": name, "loaded": True})
        return {"modules": modules}
    elif command == "module_load":
        module = payload.get("module", "")
        if not _is_valid_module_name(module):
            return {"success": False, "error": "Invalid module name"}
        try:
            _run_in_bot_loop(bot, bot.load_extension(f"modules.{module}"))
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
    elif command == "module_unload":
        module = payload.get("module", "")
        if not _is_valid_module_name(module):
            return {"success": False, "error": "Invalid module name"}
        try:
            _run_in_bot_loop(bot, bot.unload_extension(f"modules.{module}"))
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
    elif command == "get_channels":
        guild = _get_guild(bot, payload)
        if guild is None:
            return {"channels": []}
        return {
            "channels": [
                {"id": str(c.id), "name": c.name, "type": c.type.value}
                for c in sorted(guild.channels, key=lambda c: c.name)
            ]
        }
    elif command == "get_roles":
        guild = _get_guild(bot, payload)
        if guild is None:
            return {"roles": []}
        return {
            "roles": [
                {"id": str(r.id), "name": r.name}
                for r in sorted(guild.roles, key=lambda r: -r.position)
                if not r.is_default()
            ]
        }
    elif command == "get_member_names":
        user_ids = [int(uid) for uid in payload.get("user_ids", [])]
        guild = _get_guild(bot, payload)
        if guild is None:
            return {}
        return {str(uid): m.display_name for uid in user_ids if (m := guild.get_member(uid))}
    elif command == "post_apply_button":
        form_id = int(payload.get("form_id", 0))
        if not form_id:
            return {"error": "form_id required"}
        from modules.views.application import post_apply_button_message

        run_coroutine_threadsafe(post_apply_button_message(bot, form_id), bot.loop)
        return {"queued": True}
    elif command == "search_realms":
        region = payload.get("region", "eu").lower()
        q = payload.get("q", "").lower().strip()
        if not q or len(q) < 2:
            return {"realms": []}
        wow_cog = bot.cogs.get("WorldofWarcraft")
        if wow_cog is None:
            return {"realms": [], "error": "WoW module not loaded"}
        try:
            _run_in_bot_loop(bot, wow_cog._ensure_realm_cache())
        except Exception:
            return {"realms": [], "error": "Realm cache unavailable"}
        matches = []
        for info in wow_cog._realm_cache.values():
            if info["region"] != region:
                continue
            if q in info["name"].lower() or q in info["slug"].lower():
                matches.append({"name": info["name"], "slug": info["slug"]})
            if len(matches) >= 25:
                break
        return {"realms": matches}
    elif command == "validate_wow_guild":
        region = payload.get("region", "eu").lower()
        realm_slug = payload.get("realm_slug", "").lower().strip()
        guild_name = payload.get("guild_name", "").lower().replace(" ", "-").strip()
        if not realm_slug or not guild_name:
            return {"valid": False, "display_name": None}
        wow_cog = bot.cogs.get("WorldofWarcraft")
        if wow_cog is None:
            return {"valid": False, "display_name": None, "error": "WoW module not loaded"}
        try:
            api = wow_cog._get_retailclient(region, "en")
            roster = api.guild_roster(realmSlug=realm_slug, nameSlug=guild_name)
            if isinstance(roster, dict) and roster.get("code") == 429:
                return {"valid": False, "display_name": None, "error": "WoW API rate limited"}
            if isinstance(roster, dict) and roster.get("code") in (404, 403):
                return {"valid": False, "display_name": None}
            if not isinstance(roster, dict) or "guild" not in roster:
                return {"valid": False, "display_name": None, "error": "Unexpected WoW API response"}
            display_name = roster["guild"].get("name", guild_name)
            return {"valid": True, "display_name": display_name}
        except Exception as e:
            bot.log.warning("validate_wow_guild failed: %s", e)
            return {"valid": False, "display_name": None, "error": str(e)}
    else:
        return {"error": f"Unknown command: {command}"}


async def valkey_listener_loop(bot, valkey_url: str) -> None:
    """Background task that subscribes to Valkey pub/sub for web dashboard commands."""
    client = None
    pubsub = None
    try:
        import valkey as valkey_lib

        client = valkey_lib.from_url(valkey_url, decode_responses=True)
        pubsub = client.pubsub()
        pubsub.subscribe("nerpybot:cmd")
        bot.log.info("Valkey pub/sub listener started")

        while not bot.is_closed():
            msg = await to_thread(pubsub.get_message, ignore_subscribe_messages=True, timeout=1.0)
            if msg and msg["type"] == "message":
                request_id = None
                try:
                    data = json.loads(msg["data"])
                    request_id = data.pop("request_id", None)
                    command = data.pop("command", "")
                    result = await to_thread(handle_valkey_command, bot, command, data)
                except Exception as e:
                    bot.log.error(f"Valkey command handler error: {e}")
                    result = {"error": str(e)}
                if request_id:
                    reply_key = f"nerpybot:reply:{request_id}"

                    def _push_reply():
                        pipe = client.pipeline()
                        pipe.lpush(reply_key, json.dumps(result))
                        pipe.expire(reply_key, 10)
                        pipe.execute()

                    await to_thread(_push_reply)
    except CancelledError:
        return
    except Exception as e:
        bot.log.error(f"Valkey listener error: {e}")
    finally:
        try:
            if pubsub is not None:
                pubsub.unsubscribe()
            if client is not None:
                client.close()
        except Exception as e:
            bot.log.debug(f"Valkey cleanup error: {e}")
