import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import * as client from "../lib/client";

// Username/password sign-in (backend/app/auth.py). The app only renders once
// the server has accepted the saved session; a 401 from any API call later
// (SIGNED_OUT_EVENT) brings this screen back.
const EXIT_MS = 520;

interface AuthState {
  username: string;
  signOut: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

/** The signed-in user, for components inside the gate (e.g. the sidebar). */
export function useAuth(): AuthState | null {
  return useContext(AuthContext);
}

type Mode = "login" | "register";

/** The server's error detail, or a fallback for network failures. */
function signInError(err: unknown): string {
  if (err instanceof client.ApiError) {
    try {
      const detail = (JSON.parse(err.body) as { detail?: unknown }).detail;
      if (typeof detail === "string") return detail;
    } catch {
      /* not JSON */
    }
    return `Sign-in failed (${err.status}).`;
  }
  return "Couldn't reach the DealRank API. Check that the backend is running.";
}

export function EntryGate({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<client.SignedInUser | null>(null);
  const [checking, setChecking] = useState(() => client.getToken() !== null);
  const [leaving, setLeaving] = useState(false);
  const [mode, setMode] = useState<Mode>("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const usernameRef = useRef<HTMLInputElement>(null);

  // Resume a saved session.
  useEffect(() => {
    if (!checking) return;
    client
      .currentUser()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setChecking(false));
  }, [checking]);

  useEffect(() => {
    const onSignedOut = () => setUser(null);
    window.addEventListener(client.SIGNED_OUT_EVENT, onSignedOut);
    return () => window.removeEventListener(client.SIGNED_OUT_EVENT, onSignedOut);
  }, []);

  useEffect(() => {
    if (!user && !checking) usernameRef.current?.focus();
  }, [user, checking]);

  const signOut = useCallback(() => {
    void client.logout().finally(() => {
      setUser(null);
      setPassword("");
      setLeaving(false);
    });
  }, []);

  if (user && !leaving) {
    return (
      <AuthContext.Provider value={{ username: user.username, signOut }}>
        {/* Keyed by user, so switching accounts starts the app fresh. */}
        <div key={user.username} style={{ display: "contents" }}>
          {children}
        </div>
      </AuthContext.Provider>
    );
  }

  if (checking) {
    return <div className="gate" aria-busy="true" />;
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (submitting || leaving) return;
    setError(null);
    setSubmitting(true);
    try {
      const signedIn =
        mode === "login"
          ? await client.login(username, password)
          : await client.register(username, password);
      setPassword("");
      setLeaving(true);
      setUser(signedIn);
      window.setTimeout(() => setLeaving(false), EXIT_MS);
    } catch (err) {
      setError(signInError(err));
    } finally {
      setSubmitting(false);
    }
  }

  function switchMode() {
    setMode((m) => (m === "login" ? "register" : "login"));
    setError(null);
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
        <p className="gate__subtitle">
          {mode === "login" ? "Sign in to continue." : "Create an account."}
        </p>

        <form className="gate__form" onSubmit={handleSubmit}>
          <input
            ref={usernameRef}
            className="gate__input gate__input--plain"
            type="text"
            name="username"
            placeholder="Username"
            aria-label="Username"
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            required
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
          <div className="gate__field">
            <input
              className="gate__input"
              type="password"
              name="password"
              placeholder="Password"
              aria-label="Password"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              minLength={mode === "register" ? 8 : undefined}
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <button
              className="gate__go"
              type="submit"
              disabled={submitting}
              aria-label={mode === "login" ? "Sign in" : "Create account"}
            >
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
          {error && (
            <p className="gate__error" role="alert">
              {error}
            </p>
          )}
        </form>

        <p className="gate__hint">
          {mode === "login" ? "No account yet? " : "Already have an account? "}
          <button type="button" className="gate__switch" onClick={switchMode}>
            {mode === "login" ? "Create one" : "Sign in"}
          </button>
        </p>
      </main>

      <footer className="gate__footer">
        REAL 43905 &middot; Purdue Daniels School of Business
      </footer>
    </div>
  );
}
