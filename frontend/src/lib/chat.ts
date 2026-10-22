/**
 * Chat assistant client: the streaming POST /chat plus the LLM-free preset
 * endpoints (backend/app/api/chat.py). The assistant is read-only and every
 * figure in its answers comes from backend tool calls; when it can't answer
 * (rate-limited, down, not configured) the UI falls back to the presets.
 */

import { API_BASE_URL, ApiError } from "./client";
import type { Weights } from "./types";

export type ChatRole = "user" | "assistant";

export interface ChatTurn {
  role: ChatRole;
  content: string;
}

/** Why the model could not answer, so the UI can say so and offer presets. */
export type FallbackReason =
  "rate_limited" | "timeout" | "unavailable" | "provider_error" | "not_configured";

export type ChatEvent =
  | { type: "delta"; text: string }
  | { type: "tool"; name: string; status: "running" | "done" | "error"; label: string }
  | { type: "fallback"; reason: FallbackReason; message: string }
  | { type: "done"; truncated: boolean };

export interface ChatContext {
  selected_deal_ids: string[];
  ranking?: {
    dscr_minimum?: number;
    treasury_yield?: number;
    hurdle_rate?: number;
    weights?: Weights;
  };
}

export interface Preset {
  id: string;
  question: string;
}

export interface Suggestions {
  llm_available: boolean;
  suggestions: Preset[];
}

export interface PresetAnswer {
  id: string;
  question: string;
  answer: string;
}

// Mirrors the backend limits (app/api/chat.py); sending more would just be a 422.
export const MAX_MESSAGE_CHARS = 2000;
export const MAX_HISTORY_MESSAGES = 20;

/** Splits a buffer of server-sent events into complete events and the unfinished remainder. */
export function parseSse(buffer: string): { events: ChatEvent[]; rest: string } {
  const blocks = buffer.split("\n\n");
  const rest = blocks.pop() ?? "";
  const events: ChatEvent[] = [];
  for (const block of blocks) {
    let name = "";
    let data = "";
    for (const line of block.split("\n")) {
      if (line.startsWith("event: ")) name = line.slice(7).trim();
      else if (line.startsWith("data: ")) data += line.slice(6);
    }
    if (!name || !data) continue;
    let payload: Record<string, unknown>;
    try {
      payload = JSON.parse(data) as Record<string, unknown>;
    } catch {
      continue; // a malformed event shouldn't kill the stream
    }
    if (name === "delta" && typeof payload.text === "string") {
      events.push({ type: "delta", text: payload.text });
    } else if (name === "tool") {
      events.push({
        type: "tool",
        name: String(payload.name ?? ""),
        status:
          payload.status === "done" || payload.status === "error" ? payload.status : "running",
        label: String(payload.label ?? "Working"),
      });
    } else if (name === "fallback") {
      events.push({
        type: "fallback",
        reason: (payload.reason as FallbackReason) ?? "provider_error",
        message: String(payload.message ?? "The AI model is unavailable."),
      });
    } else if (name === "done") {
      events.push({ type: "done", truncated: payload.truncated === true });
    }
  }
  return { events, rest };
}

/** Trims history to what the backend accepts: non-empty turns, bounded count and length. */
export function prepareHistory(turns: ChatTurn[]): ChatTurn[] {
  return turns
    .filter((t) => t.content.trim() !== "")
    .map((t) => ({ role: t.role, content: t.content.slice(0, MAX_MESSAGE_CHARS) }))
    .slice(-MAX_HISTORY_MESSAGES);
}

/** The fallback reason for an HTTP failure of POST /chat, or null if it isn't one. */
export function fallbackReasonForStatus(status: number): FallbackReason | null {
  if (status === 503) return "not_configured";
  if (status === 429) return "rate_limited";
  return null;
}

/**
 * POST /chat, calling onEvent for each server-sent event as it arrives.
 * Throws ApiError for a non-2xx response (429 rate limit, 503 not configured).
 */
export async function streamChat(
  messages: ChatTurn[],
  context: ChatContext,
  onEvent: (event: ChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages: prepareHistory(messages), context }),
    signal,
  });
  if (!res.ok) throw new ApiError("POST", "/chat", res.status, await res.text());
  if (!res.body) throw new Error("The server sent no response body.");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parsed = parseSse(buffer);
    buffer = parsed.rest;
    parsed.events.forEach(onEvent);
  }
  // The server terminates every event with a blank line; flush a final unterminated one.
  parseSse(buffer + "\n\n").events.forEach(onEvent);
}

async function json<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new ApiError(options?.method ?? "GET", path, res.status, await res.text());
  return (await res.json()) as T;
}

export function getSuggestions(): Promise<Suggestions> {
  return json<Suggestions>("/chat/suggestions");
}

export function askPreset(presetId: string, context: ChatContext): Promise<PresetAnswer> {
  return json<PresetAnswer>("/chat/preset", {
    method: "POST",
    body: JSON.stringify({ preset_id: presetId, context }),
  });
}
