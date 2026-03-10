<script setup lang="ts">
import { ref, computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Icon } from "@iconify/vue";
import { useAuthStore } from "@/stores/auth";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const isPremiumRequired = computed(() => route.query.error === "premium_required");
const isSessionExpired = computed(() => route.query.error === "session_expired");
const showExpiredModal = ref(isSessionExpired.value);

function login() {
  // If the user already has a valid (non-expired) JWT, skip Discord OAuth and
  // retry the dashboard — the router guard will re-check /auth/me for premium status.
  if (auth.jwt && !auth.isJwtExpired()) {
    router.push("/guilds");
  } else {
    window.location.href = "/api/auth/login";
  }
}
</script>

<template>
  <!-- Animated background -->
  <div class="login-bg" aria-hidden="true">
    <div class="orb orb-indigo" />
    <div class="orb orb-violet" />
    <div class="orb orb-teal" />
    <div class="grid-overlay" />
  </div>

  <!-- Session expired modal -->
  <Transition name="fade">
    <div
      v-if="showExpiredModal"
      class="fixed inset-0 z-50 flex items-start justify-center pt-8 px-4"
      @click.self="showExpiredModal = false"
    >
      <div class="modal-toast">
        <Icon icon="mdi:clock-alert-outline" class="w-5 h-5 text-muted-foreground flex-shrink-0 mt-0.5" />
        <div class="flex-1 min-w-0">
          <p class="text-sm font-medium">
            <template v-if="auth.user?.username">Hey {{ auth.user.username }}, your</template>
            <template v-else>Your</template>
            session has expired.
          </p>
          <p class="text-xs text-muted-foreground mt-0.5">Please log in again to continue.</p>
        </div>
        <button
          class="text-muted-foreground hover:text-foreground transition-colors flex-shrink-0"
          aria-label="Dismiss"
          @click="showExpiredModal = false"
        >
          <Icon icon="mdi:close" class="w-4 h-4" />
        </button>
      </div>
    </div>
  </Transition>

  <!-- Login card -->
  <div class="min-h-screen flex items-center justify-center relative z-10 px-4">
    <div class="login-card">
      <!-- Robot logo -->
      <div class="logo-wrap" aria-hidden="true">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" class="logo-svg">
          <rect width="32" height="32" rx="7" fill="#5865F2"/>
          <rect x="8" y="11" width="16" height="13" rx="2.5" fill="white"/>
          <rect x="15" y="6" width="2" height="4" rx="1" fill="white"/>
          <circle cx="16" cy="5.5" r="2" fill="white"/>
          <rect x="10.5" y="14" width="4" height="3.5" rx="1" fill="#5865F2"/>
          <rect x="17.5" y="14" width="4" height="3.5" rx="1" fill="#5865F2"/>
          <rect x="11" y="20" width="10" height="1.5" rx="0.75" fill="#5865F2"/>
        </svg>
      </div>

      <!-- Title -->
      <div class="text-center">
        <h1 class="login-title">NerpyBot</h1>
        <p class="login-subtitle">Dashboard</p>
      </div>

      <!-- Premium required notice -->
      <div v-if="isPremiumRequired" class="w-full bg-yellow-400/10 border border-yellow-400/30 rounded-lg px-4 py-3 flex items-start gap-3">
        <Icon icon="mdi:crown-outline" class="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
        <div>
          <p class="text-sm font-medium text-yellow-300">Premium required</p>
          <p class="text-xs text-yellow-400/70 mt-0.5">
            Dashboard access is a premium feature. Contact a bot operator to request access.
          </p>
        </div>
      </div>

      <p v-else class="login-tagline">
        Sign in with your Discord account to manage your servers.
      </p>

      <!-- Discord login button -->
      <button class="discord-btn" @click="login">
        <Icon icon="simple-icons:discord" class="w-5 h-5" aria-hidden="true" />
        Login with Discord
      </button>
    </div>
  </div>
</template>

<style scoped>
/* ── Background ── */
.login-bg {
  position: fixed;
  inset: 0;
  overflow: hidden;
  z-index: 0;
  background: hsl(222, 47%, 8%);
}

.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(100px);
}

.orb-indigo {
  width: 650px;
  height: 650px;
  background: radial-gradient(circle, hsla(224, 76%, 58%, 0.45), transparent 70%);
  bottom: -200px;
  left: -150px;
  animation: drift-1 16s ease-in-out infinite;
}

.orb-violet {
  width: 520px;
  height: 520px;
  background: radial-gradient(circle, hsla(270, 70%, 60%, 0.35), transparent 70%);
  top: -120px;
  right: -100px;
  animation: drift-2 20s ease-in-out infinite;
}

.orb-teal {
  width: 360px;
  height: 360px;
  background: radial-gradient(circle, hsla(185, 80%, 50%, 0.28), transparent 70%);
  top: 30%;
  right: 22%;
  animation: drift-3 13s ease-in-out infinite;
}

.grid-overlay {
  position: absolute;
  inset: 0;
  background-image: radial-gradient(circle, rgba(255, 255, 255, 0.055) 1px, transparent 1px);
  background-size: 36px 36px;
}

@keyframes drift-1 {
  0%, 100% { transform: translate(0, 0); }
  50%       { transform: translate(70px, -50px); }
}
@keyframes drift-2 {
  0%, 100% { transform: translate(0, 0); }
  50%       { transform: translate(-50px, 60px); }
}
@keyframes drift-3 {
  0%, 100% { transform: translate(0, 0); }
  50%       { transform: translate(-55px, -40px); }
}

/* ── Card ── */
.login-card {
  position: relative;
  background: rgba(10, 14, 28, 0.72);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border: 1px solid rgba(255, 255, 255, 0.09);
  border-radius: 20px;
  padding: 2.75rem 2.25rem;
  width: 100%;
  max-width: 390px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1.25rem;
  box-shadow:
    0 32px 64px rgba(0, 0, 0, 0.55),
    0 0 0 1px rgba(88, 101, 242, 0.18),
    inset 0 1px 0 rgba(255, 255, 255, 0.08);
  animation: card-appear 0.5s cubic-bezier(0.16, 1, 0.3, 1) both;
}

@keyframes card-appear {
  from { opacity: 0; transform: translateY(24px) scale(0.97); }
  to   { opacity: 1; transform: translateY(0)    scale(1); }
}

/* ── Logo ── */
.logo-wrap {
  filter: drop-shadow(0 0 18px rgba(88, 101, 242, 0.7))
          drop-shadow(0 0 40px rgba(88, 101, 242, 0.25));
}

.logo-svg {
  width: 72px;
  height: 72px;
  border-radius: 16px;
  animation: logo-pulse 4s ease-in-out infinite;
}

@keyframes logo-pulse {
  0%, 100% { filter: brightness(1); }
  50%       { filter: brightness(1.15); }
}

/* ── Typography ── */
.login-title {
  font-family: 'Syne', sans-serif;
  font-size: 2.1rem;
  font-weight: 800;
  background: linear-gradient(135deg, #ffffff 0%, hsl(224, 100%, 82%) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  letter-spacing: -0.025em;
  line-height: 1.1;
}

.login-subtitle {
  font-size: 0.7rem;
  font-weight: 600;
  color: hsl(215, 20%, 48%);
  letter-spacing: 0.22em;
  text-transform: uppercase;
  margin-top: 0.3rem;
}

.login-tagline {
  color: hsl(215, 20%, 58%);
  font-size: 0.875rem;
  text-align: center;
  line-height: 1.6;
  max-width: 260px;
}

/* ── Discord button ── */
.discord-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.625rem;
  background: linear-gradient(135deg, #5865F2 0%, #4752C4 100%);
  color: white;
  font-family: 'Figtree', sans-serif;
  font-weight: 600;
  font-size: 0.9375rem;
  padding: 0.8125rem 1.5rem;
  border-radius: 10px;
  border: none;
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
  box-shadow: 0 4px 16px rgba(88, 101, 242, 0.45), 0 1px 3px rgba(0, 0, 0, 0.3);
}

.discord-btn:hover {
  background: linear-gradient(135deg, #6875f5 0%, #5865f2 100%);
  box-shadow: 0 6px 22px rgba(88, 101, 242, 0.58), 0 2px 6px rgba(0, 0, 0, 0.3);
  transform: translateY(-1px);
}

.discord-btn:active {
  transform: translateY(0);
  box-shadow: 0 2px 8px rgba(88, 101, 242, 0.4);
}

/* ── Toast modal ── */
.modal-toast {
  background: rgba(13, 17, 35, 0.9);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.5);
  padding: 1.25rem;
  max-width: 24rem;
  width: 100%;
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
}

/* ── Transitions ── */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
