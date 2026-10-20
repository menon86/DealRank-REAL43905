import { useEffect, useMemo, useRef, useState } from "react";
import { highlightParts, searchGeographies } from "../lib/geoSearch";

interface GeographyComboboxProps {
  id: string;
  options: string[];
  value: string;
  onChange: (value: string) => void;
}

export function GeographyCombobox({ id, options, value, onChange }: GeographyComboboxProps) {
  const [query, setQuery] = useState(value);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const blurTimer = useRef<number | undefined>(undefined);

  // Pick up a value set from outside (e.g. the default once data loads).
  useEffect(() => {
    if (value) setQuery(value);
  }, [value]);

  const matches = useMemo(() => searchGeographies(options, query), [options, query]);
  const isExact = options.includes(value) && query === value;
  const showList = open && !isExact;
  const listId = `${id}-list`;
  const closest = matches.length > 0 && matches[0].partial;

  function choose(geography: string) {
    setQuery(geography);
    onChange(geography);
    setOpen(false);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setActive((a) => Math.min(a + 1, matches.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter" && showList && matches[active]) {
      e.preventDefault();
      choose(matches[active].geography);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  return (
    <div className="combo">
      <input
        id={id}
        role="combobox"
        aria-expanded={showList}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={showList && matches[active] ? `${id}-opt-${active}` : undefined}
        autoComplete="off"
        value={query}
        placeholder="Search a city or metro, e.g. Indianapolis or IN"
        onFocus={(e) => {
          window.clearTimeout(blurTimer.current);
          setOpen(true);
          e.currentTarget.select();
        }}
        onBlur={() => {
          blurTimer.current = window.setTimeout(() => setOpen(false), 120);
        }}
        onKeyDown={onKeyDown}
        onChange={(e) => {
          setQuery(e.target.value);
          // Only exact market names are checkable; clear the selection while typing.
          onChange(options.includes(e.target.value) ? e.target.value : "");
          setActive(0);
          setOpen(true);
        }}
      />
      {showList && (
        <ul id={listId} role="listbox" className="combo-list">
          {matches.length === 0 ? (
            <li className="combo-empty" role="presentation">
              No market matches &ldquo;{query}&rdquo;. Try a nearby metro or the state.
            </li>
          ) : (
            <>
              {closest && (
                <li className="combo-empty" role="presentation">
                  No exact match. Closest markets:
                </li>
              )}
              {matches.map((m, i) => (
                <li
                  key={m.geography}
                  id={`${id}-opt-${i}`}
                  role="option"
                  aria-selected={i === active}
                  className={i === active ? "combo-option active" : "combo-option"}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    choose(m.geography);
                  }}
                  onMouseEnter={() => setActive(i)}
                >
                  {highlightParts(m.geography, query).map(([text, hit], j) =>
                    hit ? <mark key={j}>{text}</mark> : <span key={j}>{text}</span>,
                  )}
                </li>
              ))}
            </>
          )}
        </ul>
      )}
    </div>
  );
}
