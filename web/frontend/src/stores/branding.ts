import { defineStore } from "pinia";
import { ref } from "vue";
import { api } from "@/api/client";

export const useBrandingStore = defineStore("branding", () => {
  const botName = ref("NerpyBot");
  const botDescription = ref("NerpyBot - Always one step ahead!");
  let _loadPromise: Promise<void> | null = null;

  function load(): Promise<void> {
    if (_loadPromise) return _loadPromise;
    _loadPromise = (async () => {
      const { bot_name, bot_description } = await api.get<{
        bot_name: string;
        bot_description: string;
      }>("/branding");
      botName.value = bot_name;
      botDescription.value = bot_description;
    })().catch(() => {
      // Keep defaults on failure; clear promise so callers can retry
      _loadPromise = null;
    });
    return _loadPromise;
  }

  return { botName, botDescription, load };
});
