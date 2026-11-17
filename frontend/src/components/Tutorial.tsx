import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { TUTORIAL_STEPS } from "../lib/tutorial";
import type { Tab } from "./Shell";

interface TutorialProps {
  onClose: () => void;
  onNavigate: (tab: Tab) => void;
}

interface Rect {
  top: number;
  left: number;
  width: number;
  height: number;
}

const SPOTLIGHT_PAD = 6;

/** Finds the element a step points at and tracks where it is on screen. */
function useTargetRect(target: string | undefined, stepIndex: number): Rect | null {
  const [rect, setRect] = useState<Rect | null>(null);

  const measure = useCallback(() => {
    const el = target ? document.querySelector<HTMLElement>(`[data-tour="${target}"]`) : null;
    if (!el) {
      setRect(null);
      return;
    }
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) {
      setRect(null);
      return;
    }
    setRect({
      top: r.top - SPOTLIGHT_PAD,
      left: r.left - SPOTLIGHT_PAD,
      width: r.width + SPOTLIGHT_PAD * 2,
      height: r.height + SPOTLIGHT_PAD * 2,
    });
  }, [target]);

  useLayoutEffect(() => {
    const el = target ? document.querySelector<HTMLElement>(`[data-tour="${target}"]`) : null;
    // On narrow screens the tab strip scrolls sideways; bring the tab into view.
    el?.scrollIntoView?.({ block: "nearest", inline: "nearest" });
    measure();
    // The view behind may still be rendering after a tab switch; measure again once it settles.
    const id = window.setTimeout(measure, 60);
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, true);
    return () => {
      window.clearTimeout(id);
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", measure, true);
    };
  }, [measure, target, stepIndex]);

  return rect;
}

export function Tutorial({ onClose, onNavigate }: TutorialProps) {
  const [index, setIndex] = useState(0);
  const step = TUTORIAL_STEPS[index];
  const isFirst = index === 0;
  const isLast = index === TUTORIAL_STEPS.length - 1;
  const rect = useTargetRect(step.target, index);
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const nextRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (step.tab) onNavigate(step.tab);
  }, [step.tab, onNavigate]);

  useEffect(() => {
    nextRef.current?.focus();
  }, [index]);

  const next = useCallback(() => {
    if (isLast) onClose();
    else setIndex((i) => i + 1);
  }, [isLast, onClose]);
  const back = useCallback(() => setIndex((i) => Math.max(0, i - 1)), []);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      } else if (event.key === "ArrowRight") {
        next();
      } else if (event.key === "ArrowLeft") {
        back();
      } else if (event.key === "Tab") {
        // Keep keyboard focus inside the tutorial card while it's open.
        const focusable =
          dialogRef.current?.querySelectorAll<HTMLElement>("button:not([disabled])");
        if (!focusable || focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [next, back, onClose]);

  return (
    <div className="tour" role="presentation">
      {rect ? (
        <div
          className="tour__spotlight"
          aria-hidden="true"
          style={{ top: rect.top, left: rect.left, width: rect.width, height: rect.height }}
        />
      ) : (
        <div className="tour__backdrop" aria-hidden="true" />
      )}

      <div
        ref={dialogRef}
        className="tour__card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="tour-title"
        aria-describedby="tour-body"
      >
        <button type="button" className="tour__close" aria-label="Close tutorial" onClick={onClose}>
          <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">
            <path d="M4 4l8 8M12 4l-8 8" />
          </svg>
        </button>

        <p className="tour__count">
          Step {index + 1} of {TUTORIAL_STEPS.length}
        </p>
        <h2 id="tour-title" className="tour__title">
          {step.title}
        </h2>
        <p id="tour-body" className="tour__body">
          {step.body}
        </p>

        <div className="tour__footer">
          <div className="tour__dots" aria-hidden="true">
            {TUTORIAL_STEPS.map((_, i) => (
              <span key={i} className={i === index ? "active" : ""} />
            ))}
          </div>
          <div className="tour__actions">
            {!isFirst && (
              <button type="button" className="secondary" onClick={back}>
                Back
              </button>
            )}
            <button ref={nextRef} type="button" className="primary" onClick={next}>
              {isLast ? "Finish" : "Next"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
