import { fetchEventSource } from "@microsoft/fetch-event-source";
import { onUnmounted, ref } from "vue";
import type { HealthLiveStatus } from "@/api/types";
import { useAuthStore } from "@/stores/auth";

/**
 * Composable that streams live health metrics from the bot via SSE.
 *
 * Usage:
 *   const { status, error, connected, connect, disconnect } = useHealthStatus();
 *   onMounted(() => connect());
 *
 * `connect()` opens a GET /api/operator/health/live SSE stream authenticated
 * with the current JWT. `disconnect()` aborts the stream. The stream is also
 * aborted automatically on component unmount.
 */
export function useHealthStatus() {
  const status = ref<HealthLiveStatus | null>(null);
  const error = ref<string | null>(null);
  const connected = ref(false);

  let abortController: AbortController | null = null;

  function connect() {
    if (abortController) {
      return; // already connected
    }

    const auth = useAuthStore();
    const token = auth.jwt;
    if (!token) {
      error.value = "Not authenticated";
      return;
    }

    const controller = new AbortController();
    abortController = controller;
    error.value = null;

    fetchEventSource("/api/operator/health/live", {
      signal: controller.signal,
      headers: {
        Authorization: `Bearer ${token}`,
      },
      onopen(response) {
        if (response.ok) {
          connected.value = true;
          error.value = null;
          return Promise.resolve();
        }
        // Throw on non-ok responses so fetchEventSource does not retry.
        if (response.status === 429) {
          error.value = "Too many connections — close another tab and retry";
        } else if (response.status === 401 || response.status === 403) {
          error.value = "Not authorized";
        } else {
          error.value = `Stream error: ${response.status}`;
        }
        throw new Error(error.value!);
      },
      onmessage(ev) {
        if (ev.event === "health") {
          try {
            const incoming = JSON.parse(ev.data) as HealthLiveStatus;
            // Guard against spurious Vue reactivity when data hasn't changed.
            if (incoming.ts !== status.value?.ts) {
              status.value = incoming;
            }
          } catch {
            // malformed frame — ignore
          }
        }
      },
      onerror(err) {
        error.value = err instanceof Error ? err.message : "Stream error";
        connected.value = false;
        // Null before throwing so connect() can be called again immediately
        // (e.g. from a watch on error) without hitting the stale-guard early return.
        if (abortController === controller) {
          abortController = null;
        }
        // Throw to stop fetchEventSource from retrying.
        throw err;
      },
      onclose() {
        connected.value = false;
        // Null the controller so connect() can be called again after a
        // clean server-side stream close (e.g. server restart).
        if (abortController === controller) {
          abortController = null;
        }
      },
    }).catch(() => {
      connected.value = false;
      // Guard against nulling a controller from a subsequent connect() call.
      if (abortController === controller) {
        abortController = null;
      }
    });
  }

  function disconnect() {
    if (abortController) {
      abortController.abort();
      abortController = null;
    }
    connected.value = false;
  }

  onUnmounted(() => disconnect());

  return { status, error, connected, connect, disconnect };
}
