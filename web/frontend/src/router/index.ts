import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import { useGuildStore } from "@/stores/guild";
import { api } from "@/api/client";
import type { UserInfo } from "@/api/types";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/guilds" },
    {
      path: "/login",
      component: () => import("@/views/LoginView.vue"),
      meta: { public: true },
    },
    {
      path: "/guilds",
      component: () => import("@/views/GuildSelectView.vue"),
    },
    {
      path: "/guilds/:id",
      component: () => import("@/views/guild/GuildDetailView.vue"),
    },
    {
      path: "/guilds/:id/forms/:formId/submissions",
      component: () => import("@/views/guild/FormSubmissionsView.vue"),
    },
  ],
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  const guild = useGuildStore();

  // Extract JWT handed off by /api/auth/callback redirect (?token=<jwt>)
  if (to.query.token) {
    auth.setToken(to.query.token as string);
    return { path: to.path, query: {}, replace: true };
  }

  // Public routes — no auth check needed
  if (to.meta.public) return true;

  // No token — redirect to login
  if (!auth.jwt) return "/login";

  // Hydrate user from /api/auth/me if token present but user missing
  if (!auth.user) {
    try {
      const me = await api.get<UserInfo>("/auth/me");
      auth.setUser(me);
    } catch {
      auth.clear();
      return "/login";
    }
  }

  // Guild route — verify access and bot presence
  if (to.params.id) {
    const guildId = to.params.id as string;
    const g = auth.guildById(guildId);
    if (!g || !g.bot_present) return "/guilds";
    guild.setCurrent(g);
  }

  return true;
});

export default router;
