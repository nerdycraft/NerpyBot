import { fetchEventSource } from "@microsoft/fetch-event-source";
import { onUnmounted, ref } from "vue";
import type { HealthLiveStatus } from "@/api/types";
import { useAuthStore } from "@/stores/auth";

const _MIN_RECONNECT_DELAY = 5_000;
const _MAX_RECONNECT_DELAY = 60_000;

export interface UseHealthStatusOptions {
  /** Return true when the caller is "active" — reconnects are only scheduled while this returns true. */
  isActive?: () => boolean;
}

/**
 * Composable that streams live health metrics from the bot via SSE.
 *
 * Usage:
 *   const { status, error, connected, connect, disconnect } = useHealthStatus({ isActive: () => activeTab === "health" });
 *   onMounted(() => connect());
 *
 * `connect()` opens a GET /api/operator/health/live SSE stream authenticated
 * with the current JWT. `disconnect()` aborts the stream. The stream is also
 * aborted automatically on component unmount. Transient drops (server restart,
 * proxy reset) automatically reconnect with exponential backoff while
 * `isActive()` returns true. Auth/rate-limit errors do not trigger reconnects.
 */
export function useHealthStatus(options?: UseHealthStatusOptions) {
  const status = ref<HealthLiveStatus | null>(null);
  const error = ref<string | null>(null);
  const connected = ref(false);

  let abortController: AbortController | null = null;
  let _reconnectDelay = _MIN_RECONNECT_DELAY;
  let _reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  // Set to true for permanent errors (auth/429) or intentional disconnect to suppress reconnect.
  let _permanentError = false;

  function scheduleReconnect() {
    if (_reconnectTimer !== null || _permanentError) return;
    const delay = _reconnectDelay;
    _reconnectDelay = Math.min(_reconnectDelay * 2, _MAX_RECONNECT_DELAY);
    _reconnectTimer = setTimeout(() => {
      _reconnectTimer = null;
      if (options?.isActive?.()) connect();
    }, delay);
  }

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
    _permanentError = false;

    fetchEventSource("/api/operator/health/live", {
      signal: controller.signal,
      headers: {
        Authorization: `Bearer ${token}`,
      },
      async onopen(response) {
        if (response.ok) {
          connected.value = true;
          error.value = null;
          _reconnectDelay = _MIN_RECONNECT_DELAY; // reset backoff on successful connection
          return;
        }
        // Throw on non-ok responses so fetchEventSource does not retry.
        let msg: string;
        if (response.status === 429) {
          msg = "Too many connections — close another tab and retry";
          _permanentError = true;
        } else if (response.status === 401 || response.status === 403) {
          msg = "Not authorized";
          _permanentError = true;
        } else {
          msg = `Stream error: ${response.status}`;
        }
        error.value = msg;
        throw new Error(msg);
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
        status.value = null;
        if (abortController === controller) {
          abortController = null;
        }
        // Schedule reconnect for transient drops; skip for auth/429/intentional disconnect.
        scheduleReconnect();
        // Throw to stop fetchEventSource from retrying — reconnect is handled by scheduleReconnect.
        throw err;
      },
      onclose() {
        connected.value = false;
        status.value = null;
        if (abortController === controller) {
          abortController = null;
        }
        // Schedule reconnect for server-side closes (e.g. server restart).
        scheduleReconnect();
      },
    }).catch(() => {
      connected.value = false;
      status.value = null;
      if (abortController === controller) {
        abortController = null;
      }
    });
  }

  function disconnect() {
    // Mark as intentional so onclose() (which fires async after abort) doesn't schedule a reconnect.
    _permanentError = true;
    if (_reconnectTimer !== null) {
      clearTimeout(_reconnectTimer);
      _reconnectTimer = null;
    }
    _reconnectDelay = _MIN_RECONNECT_DELAY;
    if (abortController) {
      abortController.abort();
      abortController = null;
    }
    connected.value = false;
    status.value = null;
  }

  onUnmounted(() => disconnect());

  return { status, error, connected, connect, disconnect };
}
