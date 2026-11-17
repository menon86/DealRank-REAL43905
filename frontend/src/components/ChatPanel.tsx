import { useCallback, useEffect, useRef, useState } from "react";
import * as chat from "../lib/chat";
import type { ChatContext, ChatTurn, FallbackReason, Preset } from "../lib/chat";
import { ApiError, describeError } from "../lib/client";

export type RankingSettings = NonNullable<ChatContext["ranking"]>;

interface ChatPanelProps {
  open: boolean;
  onClose: () => void;
  selectedDealIds: string[];
  rankingSettings: RankingSettings;
}

interface ToolLine {
  label: string;
  status: "running" | "done" | "error";
}

interface DisplayMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  tools: ToolLine[];
  // Set for answers built from engine output without the AI model.
  preset?: boolean;
  pending?: boolean;
}

const FALLBACK_COPY: Record<FallbackReason, string> = {
  not_configured: "The AI assistant isn't set up on this server.",
  rate_limited: "The AI assistant is rate-limited right now.",
  timeout: "The AI assistant timed out.",
  unavailable: "The AI assistant is unavailable right now.",
  provider_error: "The AI assistant hit an error.",
};

export function ChatPanel({ open, onClose, selectedDealIds, rankingSettings }: ChatPanelProps) {
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [presets, setPresets] = useState<Preset[]>([]);
  const [fallback, setFallback] = useState<FallbackReason | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const nextId = useRef(1);
  const listRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  const context: ChatContext = {
    selected_deal_ids: selectedDealIds,
    ranking: rankingSettings,
  };

  // Preset questions double as quick-start prompts and as the no-AI fallback.
  useEffect(() => {
    if (!open || presets.length > 0) return;
    let cancelled = false;
    chat
      .getSuggestions()
      .then((s) => {
        if (cancelled) return;
        setPresets(s.suggestions);
        if (!s.llm_available) setFallback("not_configured");
      })
      .catch(() => {
        // Offline backend: the app-level banner already says so.
      });
    return () => {
      cancelled = true;
    };
  }, [open, presets.length]);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  // Screen readers hear each reply once, when it has finished, rather than
  // every streamed fragment: the live region below only changes here.
  const [announcement, setAnnouncement] = useState("");
  const announcedId = useRef(0);
  useEffect(() => {
    const last = [...messages].reverse().find((m) => m.role === "assistant");
    if (!last || last.pending || !last.content || last.id === announcedId.current) return;
    announcedId.current = last.id;
    setAnnouncement(last.content);
  }, [messages]);

  useEffect(() => () => abortRef.current?.abort(), []);

  const patch = useCallback((id: number, fn: (m: DisplayMessage) => DisplayMessage) => {
    setMessages((all) => all.map((m) => (m.id === id ? fn(m) : m)));
  }, []);

  const send = useCallback(
    async (raw: string) => {
      const text = raw.trim();
      if (!text || busy) return;
      const userMsg: DisplayMessage = {
        id: nextId.current++,
        role: "user",
        content: text.slice(0, chat.MAX_MESSAGE_CHARS),
        tools: [],
      };
      const replyId = nextId.current++;
      const history: ChatTurn[] = [...messages, userMsg]
        .filter((m) => !m.pending)
        .map((m) => ({ role: m.role, content: m.content }));
      setMessages((all) => [
        ...all,
        userMsg,
        { id: replyId, role: "assistant", content: "", tools: [], pending: true },
      ]);
      setInput("");
      setBusy(true);
      const controller = new AbortController();
      abortRef.current = controller;

      const failWith = (reason: FallbackReason) => {
        setFallback(reason);
        patch(replyId, (m) => ({
          ...m,
          pending: false,
          content: m.content || `${FALLBACK_COPY[reason]} Try one of the preset questions below.`,
        }));
      };

      try {
        await chat.streamChat(
          history,
          context,
          (event) => {
            if (event.type === "delta") {
              patch(replyId, (m) => ({ ...m, content: m.content + event.text }));
            } else if (event.type === "tool") {
              patch(replyId, (m) => {
                const tools = [...m.tools];
                const last = tools[tools.length - 1];
                if (event.status === "running" || !last || last.label !== event.label) {
                  tools.push({ label: event.label, status: event.status });
                } else {
                  tools[tools.length - 1] = { label: event.label, status: event.status };
                }
                return { ...m, tools };
              });
            } else if (event.type === "fallback") {
              failWith(event.reason);
            } else {
              setFallback(null);
              patch(replyId, (m) => ({ ...m, pending: false }));
            }
          },
          controller.signal,
        );
        patch(replyId, (m) => ({ ...m, pending: false }));
      } catch (err) {
        if (controller.signal.aborted) return;
        if (err instanceof ApiError) {
          const reason = chat.fallbackReasonForStatus(err.status);
          if (reason) {
            failWith(reason);
            return;
          }
        }
        patch(replyId, (m) => ({
          ...m,
          pending: false,
          content: m.content || `Couldn't get an answer. ${describeError(err)}`,
        }));
      } finally {
        setBusy(false);
      }
    },
    // `context` is rebuilt each render from props; its parts are the real dependencies.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [busy, messages, patch, selectedDealIds, rankingSettings],
  );

  const askPreset = useCallback(
    async (preset: Preset) => {
      if (busy) return;
      const userMsg: DisplayMessage = {
        id: nextId.current++,
        role: "user",
        content: preset.question,
        tools: [],
      };
      const replyId = nextId.current++;
      setMessages((all) => [
        ...all,
        userMsg,
        { id: replyId, role: "assistant", content: "", tools: [], preset: true, pending: true },
      ]);
      setBusy(true);
      try {
        const res = await chat.askPreset(preset.id, context);
        patch(replyId, (m) => ({ ...m, content: res.answer, pending: false }));
      } catch (err) {
        patch(replyId, (m) => ({
          ...m,
          pending: false,
          content: `Couldn't load that answer. ${describeError(err)}`,
        }));
      } finally {
        setBusy(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [busy, patch, selectedDealIds, rankingSettings],
  );

  if (!open) return null;

  const notConfigured = fallback === "not_configured";
  const showChips = presets.length > 0 && (messages.length === 0 || fallback !== null);

  // Escape closes the panel only while focus is inside it (onKeyDown on the
  // panel, not a window listener).
  return (
    <aside
      className="chat-panel"
      role="complementary"
      aria-label="Deal assistant"
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          e.stopPropagation();
          onClose();
        }
      }}
    >
      <header className="chat-header">
        <div>
          <h2>Ask about your deals</h2>
          <p>
            Answers come from DealRank&apos;s own calculations. Not investment advice.
            {selectedDealIds.length > 0
              ? ` ${selectedDealIds.length} deal${selectedDealIds.length === 1 ? "" : "s"} selected.`
              : " No deals selected: I'll look at all of them."}
          </p>
        </div>
        <button type="button" className="link" onClick={onClose} aria-label="Close chat">
          Close
        </button>
      </header>

      <p className="sr-only" aria-live="polite" aria-atomic="true">
        {announcement}
      </p>
      <div className="chat-messages" ref={listRef} aria-busy={busy}>
        {messages.length === 0 && (
          <p className="chat-hint">
            Ask why a deal ranks where it does, what a DSCR is, who failed the DSCR gate, or how a
            hurdle is built.
          </p>
        )}
        {messages.map((m) => (
          <div key={m.id} className={`chat-message ${m.role}`}>
            {m.tools.length > 0 && (
              <ul className="chat-tools" aria-label="Lookups">
                {m.tools.map((t, i) => (
                  <li key={i} className={t.status}>
                    {t.label}
                    {t.status === "running" ? "…" : t.status === "done" ? " ✓" : " (failed)"}
                  </li>
                ))}
              </ul>
            )}
            {m.content && <p className="chat-text">{m.content}</p>}
            {m.pending && !m.content && m.tools.length === 0 && (
              <p className="chat-text chat-muted">Thinking…</p>
            )}
            {m.preset && !m.pending && (
              <p className="chat-note">Answered from engine output, without the AI model.</p>
            )}
          </div>
        ))}
      </div>

      {fallback && (
        <div className="chat-fallback" role="status">
          {FALLBACK_COPY[fallback]} You can still use the preset questions.
        </div>
      )}

      {showChips && (
        <div className="chat-chips" aria-label="Preset questions">
          {presets.map((p) => (
            <button
              key={p.id}
              type="button"
              className="chat-chip"
              disabled={busy}
              onClick={() => void askPreset(p)}
            >
              {p.question}
            </button>
          ))}
        </div>
      )}

      <form
        className="chat-form"
        onSubmit={(e) => {
          e.preventDefault();
          void send(input);
        }}
      >
        <textarea
          ref={inputRef}
          value={input}
          rows={2}
          maxLength={chat.MAX_MESSAGE_CHARS}
          placeholder={notConfigured ? "AI assistant not configured" : "Ask a question…"}
          aria-label="Your question"
          disabled={notConfigured}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void send(input);
            }
          }}
        />
        <button
          type="submit"
          className="primary"
          disabled={busy || notConfigured || input.trim() === ""}
        >
          {busy ? "Working…" : "Send"}
        </button>
      </form>
    </aside>
  );
}
