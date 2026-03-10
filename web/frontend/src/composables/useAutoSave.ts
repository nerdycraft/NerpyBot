import { ref, watch, onUnmounted } from "vue";
import type { Ref } from "vue";

/**
 * Debounced auto-save composable for config forms.
 *
 * Watches `source` deeply and calls `saveFn` after a 600 ms debounce.
 * Saving is suppressed until `ready` is set to `true` — set it after the
 * initial load completes (and after nextTick) to avoid saving on first mount.
 *
 * Returns { saving, error, success, ready }.
 * Write load errors directly into `error` so the template can use a single ref.
 */
export function useAutoSave<T>(
  source: Ref<T | null>,
  saveFn: (data: T) => Promise<T>,
) {
  const saving = ref(false);
  const error = ref<string | null>(null);
  const success = ref(false);
  const ready = ref(false);

  let _saveTimer: ReturnType<typeof setTimeout> | null = null;
  let _clearSuccessTimer: ReturnType<typeof setTimeout> | null = null;
  // Set to true when the user edits while a save is in-flight, so we can
  // re-queue after the save completes without overwriting the newer local state.
  let _dirtyWhileSaving = false;

  // flush: 'sync' is intentional: with async flush (the default), the watcher
  // callback runs after the finally block sets saving=false, so the guard
  // can't suppress the spurious re-trigger from `source.value = <api result>`.
  // Synchronous flush fires inline at the assignment while saving is still true.
  watch(source, () => {
    if (!ready.value || !source.value) return;
    if (saving.value) {
      // User edited during an in-flight save — mark dirty so we re-save after.
      _dirtyWhileSaving = true;
      return;
    }
    if (_saveTimer) clearTimeout(_saveTimer);
    _saveTimer = setTimeout(() => void doSave(), 600);
  }, { deep: true, flush: "sync" });

  onUnmounted(() => {
    if (_saveTimer) clearTimeout(_saveTimer);
    if (_clearSuccessTimer) clearTimeout(_clearSuccessTimer);
  });

  async function doSave() {
    if (!source.value) return;
    _dirtyWhileSaving = false;
    saving.value = true;
    success.value = false;
    error.value = null;
    try {
      const result = await saveFn(source.value);
      // Only apply the server response if no edits arrived during the await.
      // If the user changed something while we were saving, their version is
      // newer — applying the stale server result would silently discard it.
      if (!_dirtyWhileSaving) {
        source.value = result;
      }
      success.value = true;
      if (_clearSuccessTimer) clearTimeout(_clearSuccessTimer);
      _clearSuccessTimer = setTimeout(() => (success.value = false), 2000);
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : "Failed to save";
    } finally {
      saving.value = false;
      if (_dirtyWhileSaving) {
        // Re-queue a save for the newer state the user produced during the last save.
        if (_saveTimer) clearTimeout(_saveTimer);
        _saveTimer = setTimeout(() => void doSave(), 600);
      }
    }
  }

  return { saving, error, success, ready };
}
