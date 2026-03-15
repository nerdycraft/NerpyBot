import { createRouter, createWebHistory } from "vue-router";
import { api } from "@/api/client";
import type { UserInfo } from "@/api/types";
import { useAuthStore } from "@/stores/auth";
import { useGuildStore } from "@/stores/guild";

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
      path: "/terms",
      component: () => import("@/views/TermsView.vue"),
      meta: { public: true },
    },
    {
      path: "/privacy",
      component: () => import("@/views/PrivacyView.vue"),
      meta: { public: true },
    },
    {
      path: "/impressum",
      component: () => import("@/views/ImpressumView.vue"),
      meta: { public: true },
    },
    {
      path: "/guilds",
      component: () => import("@/views/guild/GuildDetailView.vue"),
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

  // Extract JWT handed off by /api/auth/callback redirect (#token=<jwt>).
  // Fragment is used instead of query param so the token never appears in server logs.
  if (to.hash.startsWith("#token=")) {
    auth.setToken(to.hash.slice("#token=".length));
    return { path: to.path, hash: "", replace: true };
  }

  // Public routes — no auth check needed (must come before error check to avoid
  // redirect loop: backend sends /login?error=... → guard would re-redirect forever)
  if (to.meta.public) return true;

  // Handle error redirects from /api/auth/callback (e.g. ?error=premium_required)
  if (to.query.error) {
    return { path: "/login", query: { error: to.query.error }, replace: true };
  }

  // No token — redirect to login
  if (!auth.jwt) return "/login";

  // JWT expired client-side — clear it (keep user for "session expired" display) and redirect
  if (auth.isJwtExpired()) {
    auth.clearJwt();
    return { path: "/login", query: { error: "session_expired" }, replace: true };
  }

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

  // Premium check — clear cached user so the next visit re-checks via /auth/me
  // (allows access once an operator grants premium without requiring re-OAuth)
  if (!auth.user?.is_premium) {
    auth.clearUser();
    return { path: "/login", query: { error: "premium_required" }, replace: true };
  }

  // /guilds (no id) — redirect to first managed guild so the sidebar is always visible.
  // If the user has no managed guilds, fall through to GuildDetailView at /guilds with no
  // guildId, which hides all guild-specific tabs and shows only the server overview.
  if (to.path === "/guilds") {
    const firstManaged = auth.guilds.find((g) => g.bot_present);
    if (firstManaged) {
      guild.setCurrent(firstManaged);
      return { path: `/guilds/${firstManaged.id}`, replace: true };
    }
    return true; // no managed guilds — GuildDetailView renders with empty guild context
  }

  // Guild route — verify access and bot presence
  if (to.params.id) {
    const guildId = to.params.id as string;
    const g = auth.guildById(guildId);
    if (!g || !g.bot_present) {
      // Operators can browse any guild the bot is in (support mode)
      if (!auth.user?.is_operator) return "/guilds";
      // Let operator through without setting guild context — GuildDetailView handles this
    } else {
      guild.setCurrent(g);
    }
  }

  return true;
});

export default router;
