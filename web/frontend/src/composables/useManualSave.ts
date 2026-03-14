import { ref, watch, onUnmounted } from "vue";
import type { Ref } from "vue";
import { useI18n } from "@/i18n";

/**
 * Manual save composable for forms whose content becomes bot messages.
 *
 * Unlike useAutoSave, changes never trigger an automatic API call.
 * Instead, `dirty` tracks unsaved changes and `save()` commits them.
 *
 * Saving is suppressed until `ready` is set to `true` — set it after the
 * initial load completes (and after nextTick) to avoid marking the form
 * dirty on first mount.
 *
 * Returns { saving, error, success, dirty, ready, save }.
 * Write load errors directly into `error` so the template can use a single ref.
 */
export function useManualSave<T>(
  source: Ref<T | null>,
  saveFn: (data: T) => Promise<T>,
) {
  const { t } = useI18n();
  const saving = ref(false);
  const error = ref<string | null>(null);
  const success = ref(false);
  const dirty = ref(false);
  const ready = ref(false);

  let _clearSuccessTimer: ReturnType<typeof setTimeout> | null = null;

  // flush: 'sync' so the guard below fires inline during `source.value = result`
  // while saving is still true, preventing the server write-back from being
  // mistaken for a user edit.
  watch(source, () => {
    if (!ready.value || !source.value) return;
    if (saving.value) return;
    dirty.value = true;
  }, { deep: true, flush: "sync" });

  onUnmounted(() => {
    if (_clearSuccessTimer) clearTimeout(_clearSuccessTimer);
  });

  async function save() {
    if (!source.value) return;
    saving.value = true;
    success.value = false;
    error.value = null;
    try {
      const result = await saveFn(source.value);
      source.value = result; // watcher fires here but saving=true, so dirty stays false
      dirty.value = false;
      success.value = true;
      if (_clearSuccessTimer) clearTimeout(_clearSuccessTimer);
      _clearSuccessTimer = setTimeout(() => (success.value = false), 2000);
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : t("common.save_failed");
    } finally {
      saving.value = false;
    }
  }

  return { saving, error, success, dirty, ready, save };
}
