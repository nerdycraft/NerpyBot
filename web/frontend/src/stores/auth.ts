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

    function clear() {
      jwt.value = null;
      user.value = null;
    }

    function guildById(id: string): GuildSummary | undefined {
      return guilds.value.find((g) => g.id === id);
    }

    return { jwt, user, isLoggedIn, guilds, setToken, setUser, clear, guildById };
  },
  { persist: true },
);
