import { useEffect, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";

// Demo entry gate. Deliberately accepts ANY input (including empty) — it is a
// presentation-polish screen, not authentication. Do not rely on it for
// security. The unlock is remembered for the browser session only.
const STORAGE_KEY = "dealrank.demo-unlocked";
const EXIT_MS = 520;

function readUnlocked(): boolean {
  try {
    return window.sessionStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

function writeUnlocked() {
  try {
    window.sessionStorage.setItem(STORAGE_KEY, "1");
  } catch {
    /* storage unavailable (private mode); gate simply shows again on reload */
  }
}

export function EntryGate({ children }: { children: ReactNode }) {
  const [unlocked, setUnlocked] = useState(readUnlocked);
  const [leaving, setLeaving] = useState(false);
  const [value, setValue] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!unlocked) inputRef.current?.focus();
  }, [unlocked]);

  if (unlocked) return <>{children}</>;

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (leaving) return;
    setLeaving(true);
    writeUnlocked();
    window.setTimeout(() => setUnlocked(true), EXIT_MS);
  }

  return (
    <div className={`gate${leaving ? " gate--leaving" : ""}`}>
      <div className="gate__glow gate__glow--a" aria-hidden="true" />
      <div className="gate__glow gate__glow--b" aria-hidden="true" />
      <div className="gate__glow gate__glow--c" aria-hidden="true" />

      <main className="gate__card">
        <div className="gate__mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="30" height="30" fill="none">
            <rect
              x="3.5"
              y="12"
              width="4"
              height="8.5"
              rx="1.2"
              fill="currentColor"
              opacity="0.55"
            />
            <rect x="10" y="7.5" width="4" height="13" rx="1.2" fill="currentColor" opacity="0.8" />
            <rect x="16.5" y="3.5" width="4" height="17" rx="1.2" fill="currentColor" />
          </svg>
        </div>

        <h1 className="gate__title">DealRank</h1>
        <p className="gate__subtitle">Risk-adjusted deal comparison and ranking.</p>

        <form className="gate__form" onSubmit={handleSubmit}>
          <div className="gate__field">
            <input
              ref={inputRef}
              className="gate__input"
              type="password"
              name="access-code"
              placeholder="Access code"
              aria-label="Access code"
              autoComplete="off"
              value={value}
              onChange={(e) => setValue(e.target.value)}
            />
            <button className="gate__go" type="submit" aria-label="Enter DealRank">
              <svg viewBox="0 0 16 16" width="16" height="16" fill="none" aria-hidden="true">
                <path
                  d="M3 8h9M8.5 4l4 4-4 4"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          </div>
        </form>

        <p className="gate__hint">Demo access &middot; any code works</p>
      </main>

      <footer className="gate__footer">
        REAL 43905 &middot; Purdue Daniels School of Business
      </footer>
    </div>
  );
}
