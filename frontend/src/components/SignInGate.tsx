import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { API_BASE_URL } from "../lib/client";
import {
  demoEnabled,
  googleEnabled,
  microsoftEnabled,
  renderGoogleButton,
  signInAsDemo,
  signInWithMicrosoft,
  useAuthUser,
} from "../lib/auth";

// Shows the app only once someone has signed in with Google or Microsoft.
// The API re-checks the token on every request; this screen is just the door.
export function SignInGate({ children }: { children: ReactNode }) {
  const user = useAuthUser();
  const googleRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (user || !googleEnabled || !googleRef.current) return;
    renderGoogleButton(googleRef.current).catch((err: unknown) =>
      setError(err instanceof Error ? err.message : "Couldn't start Google sign-in."),
    );
  }, [user]);

  if (user) return <>{children}</>;

  async function run(signIn: () => Promise<void>, failure: string) {
    setBusy(true);
    setError(null);
    try {
      await signIn();
    } catch (err) {
      setError(err instanceof Error ? err.message : failure);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="gate">
      <div className="gate__glow gate__glow--a" aria-hidden="true" />
      <div className="gate__glow gate__glow--b" aria-hidden="true" />
      <div className="gate__glow gate__glow--c" aria-hidden="true" />

      <main className="gate__card">
        <h1 className="gate__title">DealRank</h1>
        <p className="gate__subtitle">Sign in to see your deals.</p>

        <div className="gate__providers">
          {googleEnabled && <div ref={googleRef} className="gate__google" />}
          {microsoftEnabled && (
            <button
              type="button"
              className="gate__provider"
              onClick={() => run(signInWithMicrosoft, "Microsoft sign-in failed.")}
              disabled={busy}
            >
              <svg viewBox="0 0 21 21" width="18" height="18" aria-hidden="true">
                <rect x="1" y="1" width="9" height="9" fill="#f25022" />
                <rect x="11" y="1" width="9" height="9" fill="#7fba00" />
                <rect x="1" y="11" width="9" height="9" fill="#00a4ef" />
                <rect x="11" y="11" width="9" height="9" fill="#ffb900" />
              </svg>
              {busy ? "Signing in…" : "Sign in with Microsoft"}
            </button>
          )}
          {demoEnabled && (
            <button
              type="button"
              className="gate__provider gate__provider--demo"
              onClick={() => run(() => signInAsDemo(API_BASE_URL), "Couldn't start the demo.")}
              disabled={busy}
            >
              Try the demo
            </button>
          )}
        </div>

        {demoEnabled && (
          <p className="gate__hint">
            The demo is a private copy of sample deals. No sign-in needed.
          </p>
        )}

        {error && (
          <p className="gate__hint" role="alert">
            {error}
          </p>
        )}
      </main>

      <footer className="gate__footer">
        REAL 43905 &middot; Purdue Daniels School of Business
      </footer>
    </div>
  );
}
