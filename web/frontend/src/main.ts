import { createPinia } from "pinia";
import piniaPluginPersistedstate from "pinia-plugin-persistedstate";
import { createApp, watch } from "vue";
import { useBrandingStore } from "@/stores/branding";
import App from "./App.vue";
import router from "./router";
import "./style.css";

const pinia = createPinia();
pinia.use(piniaPluginPersistedstate);

createApp(App).use(pinia).use(router).mount("#app");

const branding = useBrandingStore();
branding.load();
watch(
  () => branding.botName,
  (name) => {
    document.title = `${name} Dashboard`;
  },
  { immediate: true },
);
