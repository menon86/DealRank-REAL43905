import { useLayoutEffect, useRef } from "react";
import type { InputHTMLAttributes } from "react";
import { groupThousands, stripNumberInput } from "../lib/format";

type NumberInputProps = Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "value" | "onChange" | "type"
> & {
  /** The plain number string, without commas. */
  value: string;
  /** Called with the plain number string, commas removed. */
  onChange: (raw: string) => void;
};

/** Counts the characters before `end` that survive stripNumberInput. */
function significantBefore(text: string, end: number): number {
  return text.slice(0, end).replace(/[^\d.-]/g, "").length;
}

/** The position just after the `count`th character that isn't a comma. */
function caretFor(text: string, count: number): number {
  let pos = 0;
  let seen = 0;
  while (pos < text.length && seen < count) {
    if (text[pos] !== ",") seen += 1;
    pos += 1;
  }
  return pos;
}

/**
 * A money or count field that shows comma thousands separators as the user
 * types (650,000) while the value it holds and reports stays plain (650000).
 * Not for percent, month, or year fields.
 */
export function NumberInput({ value, onChange, ...rest }: NumberInputProps) {
  const ref = useRef<HTMLInputElement>(null);
  // Where the caret should land after the re-render, counted in characters
  // that aren't commas, so adding or removing a comma doesn't move it.
  const pendingCaret = useRef<number | null>(null);
  const display = groupThousands(value);

  // No dependency list: the parent may re-render with the same display text
  // (e.g. a deleted comma), and the caret still needs putting back.
  useLayoutEffect(() => {
    const input = ref.current;
    const target = pendingCaret.current;
    pendingCaret.current = null;
    if (!input || target === null || document.activeElement !== input) return;
    const pos = caretFor(input.value, target);
    input.setSelectionRange(pos, pos);
  });

  return (
    <input
      {...rest}
      ref={ref}
      type="text"
      inputMode="decimal"
      autoComplete="off"
      value={display}
      onChange={(e) => {
        const typed = e.target.value;
        const target = significantBefore(typed, e.target.selectionStart ?? typed.length);
        const raw = stripNumberInput(typed);
        if (raw === value) {
          // Only a comma changed (or a stray character was dropped), so the
          // parent won't re-render: restore the text and caret here.
          e.target.value = display;
          const pos = caretFor(display, target);
          e.target.setSelectionRange(pos, pos);
          return;
        }
        pendingCaret.current = target;
        onChange(raw);
      }}
    />
  );
}
