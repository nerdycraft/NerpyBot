import { ref } from "vue";

export type MockupLevel = "admin" | "mod" | "member" | null;

// Module-level singleton — shared across all component instances
const mockupLevel = ref<MockupLevel>(null);

export function useMockup() {
  function setMockupLevel(level: MockupLevel) {
    mockupLevel.value = level;
  }

  function clearMockup() {
    mockupLevel.value = null;
  }

  return {
    mockupLevel,
    setMockupLevel,
    clearMockup,
  };
}
