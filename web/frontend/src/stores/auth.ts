import { defineStore } from "pinia";
import { ref, computed } from "vue";
import type { UserInfo, GuildSummary } from "@/api/types";

export const useAuthStore = defineStore(
  "auth",
  () => {
    const jwt = ref<string | null>(null);
    const user = ref<UserInfo | null>(null);

    const isLoggedIn = computed(() => !!jwt.value);
    const guilds = computed(() => user.value?.guilds ?? []);

    function setToken(token: string) {
      jwt.value = token;
    }

    function setUser(u: UserInfo) {
      user.value = u;
    }

    /** Clear only the JWT — keeps user data for display (e.g. "session expired, username"). */
    function clearJwt() {
      jwt.value = null;
    }

    /** Clear only the user object — forces a fresh /auth/me check on next navigation. */
    function clearUser() {
      user.value = null;
    }

    function clear() {
      jwt.value = null;
      user.value = null;
    }

    function guildById(id: string): GuildSummary | undefined {
      return guilds.value.find((g) => g.id === id);
    }

    /** Returns true if the cached JWT is past its expiry without making any network call. */
    function isJwtExpired(): boolean {
      if (!jwt.value) return true;
      try {
        const parts = jwt.value.split(".");
        if (parts.length < 2) return true;
        const payload = JSON.parse(atob(parts[1]!));
        return typeof payload.exp === "number" && payload.exp * 1000 < Date.now();
      } catch {
        return true;
      }
    }

    return { jwt, user, isLoggedIn, guilds, setToken, setUser, clearJwt, clearUser, clear, guildById, isJwtExpired };
  },
  { persist: true },
);
