import { describe, expect, it } from "vitest";
import { TUTORIAL_SEEN_KEY, TUTORIAL_STEPS, hasSeenTutorial, markTutorialSeen } from "./tutorial";

function memoryStorage() {
  const data = new Map<string, string>();
  return {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => void data.set(key, value),
  };
}

describe("tutorial seen flag", () => {
  it("is unseen on first launch and seen after marking", () => {
    const storage = memoryStorage();
    expect(hasSeenTutorial(storage)).toBe(false);
    markTutorialSeen(storage);
    expect(storage.getItem(TUTORIAL_SEEN_KEY)).toBe("1");
    expect(hasSeenTutorial(storage)).toBe(true);
  });

  it("treats unavailable storage as seen so the tour doesn't reopen on every load", () => {
    const throwing = {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("blocked");
      },
    };
    expect(hasSeenTutorial(throwing)).toBe(true);
    expect(hasSeenTutorial(null)).toBe(true);
    expect(() => markTutorialSeen(throwing)).not.toThrow();
  });
});

describe("tutorial steps", () => {
  it("covers every main view and ends on the Help tab", () => {
    const tabs = new Set(TUTORIAL_STEPS.map((s) => s.tab).filter(Boolean));
    for (const tab of ["home", "deals", "compare", "rank", "risk", "sensitivity", "market"]) {
      expect(tabs.has(tab as never)).toBe(true);
    }
    expect(TUTORIAL_STEPS[TUTORIAL_STEPS.length - 1].target).toBe("tab-help");
  });
});
