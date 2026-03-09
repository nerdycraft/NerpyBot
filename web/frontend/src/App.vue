<script setup lang="ts">
import { onMounted } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const router = useRouter();
const route = useRoute();
const auth = useAuthStore();

onMounted(() => {
  // Extract JWT handed off by /api/auth/callback redirect (?token=<jwt>)
  const token = route.query.token as string | undefined;
  if (token) {
    auth.setToken(token);
    // Remove the token from the URL without adding a history entry
    router.replace({ query: {} });
  }
});
</script>

<template>
  <RouterView />
</template>
