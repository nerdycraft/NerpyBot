import { defineStore } from "pinia";
import { ref } from "vue";
import type { GuildSummary } from "@/api/types";

export const useGuildStore = defineStore("guild", () => {
  const current = ref<GuildSummary | null>(null);

  function setCurrent(g: GuildSummary) {
    current.value = g;
  }

  function clear() {
    current.value = null;
  }

  return { current, setCurrent, clear };
});
