import { PublicClientApplication } from "@azure/msal-browser";
import { useSyncExternalStore } from "react";

// Sign-in with Google or Microsoft. The provider hands the browser an ID token;
// it is sent to the API as `Authorization: Bearer <token>` and verified there.
// With no client ids configured (local dev), auth is off and the old demo gate shows.

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID ?? "";
const MICROSOFT_CLIENT_ID = import.meta.env.VITE_MICROSOFT_CLIENT_ID ?? "";
const MICROSOFT_TENANT_ID = import.meta.env.VITE_MICROSOFT_TENANT_ID ?? "";

export const googleEnabled = GOOGLE_CLIENT_ID !== "";
export const microsoftEnabled = MICROSOFT_CLIENT_ID !== "" && MICROSOFT_TENANT_ID !== "";
// The API has a "Try the demo" endpoint (DEMO_ENABLED); this only shows the button.
export const demoEnabled = import.meta.env.VITE_DEMO_ENABLED === "true";
export const authEnabled = googleEnabled || microsoftEnabled || demoEnabled;

const STORAGE_KEY = "dealrank.id-token";

export interface AuthUser {
  email: string;
  username: string;
}

// ---- token store ---------------------------------------------------------

let token: string | null = readStored();
const listeners = new Set<() => void>();

function readStored(): string | null {
  try {
    const stored = window.sessionStorage.getItem(STORAGE_KEY);
    return stored && !isExpired(stored) ? stored : null;
  } catch {
    return null;
  }
}

function setToken(next: string | null): void {
  token = next;
  try {
    if (next) window.sessionStorage.setItem(STORAGE_KEY, next);
    else window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    /* storage unavailable (private mode); the session just won't survive a reload */
  }
  listeners.forEach((notify) => notify());
}

function subscribe(notify: () => void): () => void {
  listeners.add(notify);
  return () => listeners.delete(notify);
}

function payloadOf(jwt: string): Record<string, unknown> {
  try {
    const part = jwt.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(part)) as Record<string, unknown>;
  } catch {
    return {};
  }
}

function isExpired(jwt: string): boolean {
  const exp = payloadOf(jwt).exp;
  return typeof exp !== "number" || exp * 1000 <= Date.now() + 5000;
}

export function userFromToken(jwt: string): AuthUser | null {
  const claims = payloadOf(jwt);
  const email = String(claims.email ?? claims.preferred_username ?? "").toLowerCase();
  if (!email.includes("@")) return null;
  if (email.endsWith("@demo.local")) return { email, username: "Demo" };
  return { email, username: email.split("@")[0] };
}

/** The signed-in user, or null. Re-renders the caller on sign-in and sign-out. */
export function useAuthUser(): AuthUser | null {
  const current = useSyncExternalStore(subscribe, () => token);
  return current && !isExpired(current) ? userFromToken(current) : null;
}

export function signOut(): void {
  setToken(null);
}

/**
 * fetch with the bearer token attached. A 401 means the token expired or was
 * rejected, so the session is cleared and the sign-in screen comes back.
 */
export async function apiFetch(url: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(url, { ...init, headers });
  if (res.status === 401 && authEnabled) setToken(null);
  return res;
}

// ---- providers -------------------------------------------------------------

interface GoogleCredentialResponse {
  credential: string;
}

interface GoogleIdApi {
  initialize(config: {
    client_id: string;
    callback: (response: GoogleCredentialResponse) => void;
    use_fedcm_for_prompt?: boolean;
  }): void;
  renderButton(parent: HTMLElement, options: Record<string, unknown>): void;
}

declare global {
  interface Window {
    google?: { accounts: { id: GoogleIdApi } };
  }
}

let googleScript: Promise<void> | null = null;

function loadGoogleScript(): Promise<void> {
  if (!googleScript) {
    googleScript = new Promise((resolve, reject) => {
      const el = document.createElement("script");
      el.src = "https://accounts.google.com/gsi/client";
      el.async = true;
      el.onload = () => resolve();
      el.onerror = () => {
        googleScript = null;
        reject(new Error("Couldn't load Google sign-in."));
      };
      document.head.appendChild(el);
    });
  }
  return googleScript;
}

/** Draws Google's own sign-in button into `parent`; signs in when the user picks an account. */
export async function renderGoogleButton(parent: HTMLElement): Promise<void> {
  await loadGoogleScript();
  const api = window.google?.accounts.id;
  if (!api) throw new Error("Google sign-in did not load.");
  api.initialize({
    client_id: GOOGLE_CLIENT_ID,
    callback: ({ credential }) => setToken(credential),
  });
  api.renderButton(parent, {
    type: "standard",
    theme: "outline",
    size: "large",
    shape: "pill",
    text: "signin_with",
    width: 280,
  });
}

/** Starts a throwaway demo account (its own copy of the sample deals) and signs in as it. */
export async function signInAsDemo(apiBaseUrl: string): Promise<void> {
  const res = await fetch(`${apiBaseUrl}/auth/demo`, { method: "POST" });
  if (res.status === 429) throw new Error("Too many demo sessions. Wait a moment and try again.");
  if (!res.ok) throw new Error("The demo isn't available right now.");
  const body = (await res.json()) as { token: string };
  setToken(body.token);
}

let msal: PublicClientApplication | null = null;

async function microsoftApp(): Promise<PublicClientApplication> {
  if (!msal) {
    msal = new PublicClientApplication({
      auth: {
        clientId: MICROSOFT_CLIENT_ID,
        authority: `https://login.microsoftonline.com/${MICROSOFT_TENANT_ID}`,
        redirectUri: window.location.origin,
      },
      cache: { cacheLocation: "sessionStorage" },
    });
    await msal.initialize();
  }
  return msal;
}

export async function signInWithMicrosoft(): Promise<void> {
  const app = await microsoftApp();
  const result = await app.loginPopup({ scopes: ["openid", "profile", "email"] });
  setToken(result.idToken);
}
