"""
Valkey pub/sub integration for web dashboard ↔ bot communication.

The listener loop runs as an asyncio background task. It subscribes to the
``nerpybot:cmd`` channel, dispatches each incoming command to
``handle_valkey_command``, and writes the result back under
``nerpybot:reply:<request_id>`` with a 10-second TTL.
"""

import json
from asyncio import CancelledError, ensure_future, sleep, to_thread
from datetime import UTC, datetime
from importlib.metadata import version as pkg_version

import psutil

_proc = psutil.Process()
_proc.cpu_percent(interval=None)  # prime the baseline; first call always returns 0.0


# Modules that are always auto-loaded by the bot and must never be unloaded at runtime.
PROTECTED_MODULES: frozenset[str] = frozenset({"admin", "voicecontrol"})


def _is_valid_module_name(module: str) -> bool:
    """Return True if module is a valid loadable module name (lowercase alpha + underscores)."""
    return bool(module and module.replace("_", "").isalpha() and module.islower())


def _discover_available_modules(loaded_names: set[str]) -> list[str]:
    """Return module names present on disk but not currently loaded (and not protected)."""
    from pathlib import Path

    modules_dir = Path(__file__).parent.parent / "modules"
    discovered = {p.stem for p in modules_dir.glob("*.py") if p.stem != "__init__"}
    return sorted(discovered - loaded_names - PROTECTED_MODULES)


def _get_guild(bot, payload: dict):
    """Extract guild_id from payload and return the Guild, or None if not found."""
    guild_id = int(payload.get("guild_id", 0))
    return bot.get_guild(guild_id)


async def handle_valkey_command(bot, command: str, payload: dict) -> dict:
    """
    Dispatches Valkey pub/sub commands from the web dashboard and returns a command-specific response dictionary.

    Parameters:
        bot: The running NerpyBot instance handling commands.
        command (str): The Valkey command name to execute (e.g., "health", "list_modules", "module_load").
        payload (dict): Command parameters; contents vary by command.

    Returns:
        dict: A command-specific response. Examples include:
            - health: {"guild_count", "voice_connections", "latency_ms", "uptime_seconds", "python_version", "discord_py_version", "bot_version", "memory_mb", "cpu_percent", "error_count_24h", "active_reminders", "voice_details"}
            - list_modules: {"modules": [{"name", "loaded"}, ...]}
            - list_guilds: {"guilds": [{"id", "name", "icon", "member_count"}, ...]}
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
        voice_details = [
            {
                "guild_id": str(vc.guild.id),
                "guild_name": vc.guild.name,
                "channel_id": str(vc.channel.id),
                "channel_name": vc.channel.name,
            }
            for vc in bot.voice_clients
        ]
        active_reminders: int | None = None
        try:
            from models.reminder import ReminderMessage

            def _count_reminders():
                with bot.session_scope() as session:
                    return session.query(ReminderMessage).filter(ReminderMessage.Enabled == True).count()  # noqa: E712

            active_reminders = await to_thread(_count_reminders)
        except Exception as e:
            bot.log.warning("Failed to count active reminders for health response: %s", e)
        return {
            "guild_count": len(bot.guilds),
            "voice_connections": len(bot.voice_clients),
            "latency_ms": round(bot.latency * 1000, 2),
            "uptime_seconds": round(uptime_seconds, 2),
            "python_version": sys.version.split()[0],
            "discord_py_version": discord.__version__,
            "bot_version": pkg_version("NerpyBot"),
            "memory_mb": round(_proc.memory_info().rss / (1024 * 1024), 2),
            "cpu_percent": round(_proc.cpu_percent(interval=None), 2),
            "error_count_24h": bot.error_counter.count(),
            "active_reminders": active_reminders,
            "voice_details": voice_details,
        }
    elif command == "list_modules":
        loaded_names: set[str] = set()
        modules = []
        for ext_name in bot.extensions:
            name = ext_name.replace("modules.", "")
            loaded_names.add(name)
            modules.append({"name": name, "loaded": True, "protected": name in PROTECTED_MODULES})
        return {"modules": modules, "available": _discover_available_modules(loaded_names)}
    elif command == "module_load":
        module = payload.get("module", "")
        if not _is_valid_module_name(module):
            return {"success": False, "error": "Invalid module name"}
        try:
            await bot.load_extension(f"modules.{module}")
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
    elif command == "module_unload":
        module = payload.get("module", "")
        if not _is_valid_module_name(module):
            return {"success": False, "error": "Invalid module name"}
        if module in PROTECTED_MODULES:
            return {"success": False, "error": f"Module '{module}' is protected and cannot be unloaded"}
        try:
            await bot.unload_extension(f"modules.{module}")
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

        task = ensure_future(post_apply_button_message(bot, form_id))

        def _log_exc(t):
            exc = t.exception()
            if exc:
                bot.log.error("post_apply_button_message failed for form_id=%s: %s", form_id, exc)

        task.add_done_callback(_log_exc)
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
            await wow_cog._ensure_realm_cache()
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
        guild_name = payload.get("guild_name", "").strip().lower().replace(" ", "-")
        if not realm_slug or not guild_name:
            return {"valid": False, "display_name": None}
        wow_cog = bot.cogs.get("WorldofWarcraft")
        if wow_cog is None:
            return {"valid": False, "display_name": None, "error": "WoW module not loaded"}
        try:

            def _call_api():
                api = wow_cog._get_retailclient(region, "en")
                return api.guild_roster(realmSlug=realm_slug, nameSlug=guild_name)

            roster = await to_thread(_call_api)
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
    elif command == "list_guilds":
        return {
            "guilds": [
                {
                    "id": str(g.id),
                    "name": g.name,
                    "icon": g.icon.key if g.icon else None,
                    "member_count": g.member_count,
                }
                for g in bot.guilds
            ]
        }
    elif command == "support_message":
        import discord

        user_id = payload.get("user_id", "unknown")
        username = payload.get("username", "unknown")
        category = payload.get("category", "general")
        message_text = payload.get("message", "")

        category_labels = {"bug": "Bug Report", "feature": "Feature Request", "feedback": "Feedback", "other": "Other"}
        embed = discord.Embed(
            title=f"Dashboard: {category_labels.get(category, category)}",
            description=message_text,
            color=discord.Color.blue(),
            timestamp=datetime.now(UTC),
        )
        embed.set_footer(text=f"From: {username} (ID: {user_id})")

        recipients = bot.config.get("notifications", {}).get("error_recipients", [])
        sent = 0
        for uid in recipients:
            try:
                user = await bot.fetch_user(int(uid))
                await user.send(embed=embed)
                sent += 1
            except Exception:
                pass
        return {"success": True, "sent_to": sent}
    else:
        return {"error": f"Unknown command: {command}"}


async def valkey_listener_loop(bot, valkey_url: str) -> None:
    """Background task that subscribes to Valkey pub/sub for web dashboard commands."""
    import valkey as valkey_lib

    retry_delay = 1.0
    max_delay = 60.0

    try:
        while not bot.is_closed():
            client = None
            pubsub = None
            try:
                client = valkey_lib.from_url(valkey_url, decode_responses=True)
                pubsub = client.pubsub()
                pubsub.subscribe("nerpybot:cmd")
                bot.log.info("Valkey pub/sub listener started")
                retry_delay = 1.0  # reset backoff on successful connection

                while not bot.is_closed():
                    try:
                        msg = await to_thread(pubsub.get_message, ignore_subscribe_messages=True, timeout=1.0)
                        if msg and msg["type"] == "message":
                            request_id = None
                            try:
                                data = json.loads(msg["data"])
                                request_id = data.pop("request_id", None)
                                command = data.pop("command", "")
                                result = await handle_valkey_command(bot, command, data)
                            except Exception as e:
                                bot.log.error("Valkey command handler error: %s", e)
                                result = {"error": str(e)}
                            if request_id:
                                reply_key = f"nerpybot:reply:{request_id}"

                                def _push_reply():
                                    pipe = client.pipeline()
                                    pipe.lpush(reply_key, json.dumps(result))
                                    pipe.expire(reply_key, 10)
                                    pipe.execute()

                                await to_thread(_push_reply)
                    except Exception as e:
                        bot.log.error("Valkey read/reply error: %s", e)
                        await sleep(retry_delay)
                        retry_delay = min(retry_delay * 2, max_delay)
                        break  # reconnect outer loop
            except Exception as e:
                bot.log.error("Valkey listener error: %s", e)
                await sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_delay)
            finally:
                try:
                    if pubsub is not None:
                        pubsub.unsubscribe()
                    if client is not None:
                        client.close()
                except Exception as e:
                    bot.log.debug("Valkey cleanup error: %s", e)
    except CancelledError:
        return
