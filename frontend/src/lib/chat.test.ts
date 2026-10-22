import { describe, expect, it } from "vitest";
import { fallbackReasonForStatus, parseSse, prepareHistory } from "./chat";

const ev = (name: string, data: unknown) => `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`;

describe("parseSse", () => {
  it("parses every event type", () => {
    const text =
      ev("delta", { text: "Hi" }) +
      ev("tool", { name: "get_metrics", status: "running", label: "Computing deal metrics" }) +
      ev("fallback", { reason: "rate_limited", message: "Slow down." }) +
      ev("done", { truncated: true });
    const { events, rest } = parseSse(text);
    expect(rest).toBe("");
    expect(events).toEqual([
      { type: "delta", text: "Hi" },
      { type: "tool", name: "get_metrics", status: "running", label: "Computing deal metrics" },
      { type: "fallback", reason: "rate_limited", message: "Slow down." },
      { type: "done", truncated: true },
    ]);
  });

  it("keeps an incomplete trailing event for the next chunk", () => {
    const first = ev("delta", { text: "a" }) + 'event: delta\ndata: {"text":"b';
    const a = parseSse(first);
    expect(a.events).toEqual([{ type: "delta", text: "a" }]);
    const b = parseSse(a.rest + '"}\n\n');
    expect(b.events).toEqual([{ type: "delta", text: "b" }]);
  });

  it("skips malformed and unknown events without throwing", () => {
    const text = "event: delta\ndata: {oops\n\n" + ev("mystery", {}) + ev("done", {});
    expect(parseSse(text).events).toEqual([{ type: "done", truncated: false }]);
  });

  it("treats an unrecognised tool status as running", () => {
    const { events } = parseSse(ev("tool", { name: "x", status: "weird", label: "L" }));
    expect(events[0]).toMatchObject({ status: "running" });
  });
});

describe("prepareHistory", () => {
  it("drops empty turns and caps count and length", () => {
    const turns = Array.from({ length: 30 }, (_, i) => ({
      role: i % 2 === 0 ? ("user" as const) : ("assistant" as const),
      content: `m${i}`,
    }));
    turns.push({ role: "assistant", content: "   " });
    turns.push({ role: "user", content: "x".repeat(3000) });
    const out = prepareHistory(turns);
    expect(out).toHaveLength(20);
    expect(out[out.length - 1].content).toHaveLength(2000);
    expect(out.every((t) => t.content.trim() !== "")).toBe(true);
  });
});

describe("fallbackReasonForStatus", () => {
  it("maps the documented statuses", () => {
    expect(fallbackReasonForStatus(503)).toBe("not_configured");
    expect(fallbackReasonForStatus(429)).toBe("rate_limited");
    expect(fallbackReasonForStatus(422)).toBeNull();
  });
});
