/**
 * Shared cache for Discord channel and role names.
 * Module-level reactive state persists across component lifecycle, so
 * names are fetched at most once per guild per page load.
 */
import { reactive } from "vue";
import { api } from "@/api/client";
import type { DiscordChannel, DiscordRole } from "@/api/types";

const channelCache = reactive<Record<string, Record<string, string>>>({});
const roleCache = reactive<Record<string, Record<string, string>>>({});

export function useGuildEntities(guildId: string) {
  async function fetchChannels() {
    if (channelCache[guildId]) return;
    try {
      const data = await api.get<{ channels: DiscordChannel[] }>(`/guilds/${guildId}/discord/channels`);
      channelCache[guildId] = Object.fromEntries(data.channels.map((c) => [c.id, c.name]));
    } catch {
      delete channelCache[guildId];
    }
  }

  async function fetchRoles() {
    if (roleCache[guildId]) return;
    try {
      const data = await api.get<{ roles: DiscordRole[] }>(`/guilds/${guildId}/discord/roles`);
      roleCache[guildId] = Object.fromEntries(data.roles.map((r) => [r.id, r.name]));
    } catch {
      delete roleCache[guildId];
    }
  }

  function channelName(id: string | null | undefined): string {
    if (!id) return "";
    return channelCache[guildId]?.[id] ?? `#${id}`;
  }

  function roleName(id: string | null | undefined): string {
    if (!id) return "";
    return roleCache[guildId]?.[id] ?? id;
  }

  return { fetchChannels, fetchRoles, channelName, roleName };
}
