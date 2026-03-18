<template>
  <div class="subtab-bar">
    <slot />
  </div>
</template>

<style scoped>
.subtab-bar {
  display: flex;
  gap: 0.25rem;
  margin-bottom: 1.25rem;
  border-bottom: 1px solid var(--color-border, #333);
  padding-bottom: 0;
}

:slotted(.subtab-btn) {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.4rem 0.9rem;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  color: var(--color-text-muted, #888);
  font-size: 0.875rem;
  font-weight: 500;
  margin-bottom: -1px;
  transition: color 0.15s;
}

:slotted(.subtab-btn:hover) {
  color: var(--color-text, #fff);
}

:slotted(.subtab-btn.active) {
  color: var(--color-accent, #7289da);
  border-bottom-color: var(--color-accent, #7289da);
}
</style>
