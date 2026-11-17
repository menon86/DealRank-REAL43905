import type { Tab } from "../components/Shell";

/** One page of the click-through tutorial. */
export interface TutorialStep {
  title: string;
  body: string;
  /** View to switch to while this step is showing, so the user sees it behind the card. */
  tab?: Tab;
  /** `data-tour` value of the element to spotlight. */
  target?: string;
}

export const TUTORIAL_STEPS: TutorialStep[] = [
  {
    title: "Welcome to DealRank",
    body:
      "DealRank helps you underwrite multifamily acquisitions, compare them side by side and " +
      "rank them against your hurdle rate. This quick tour walks through each part of the app.",
    tab: "home",
  },
  {
    title: "Home",
    body:
      "Your dashboard. It shows how many deals you have, how many are selected for comparison, " +
      "and which deal currently ranks first.",
    tab: "home",
    target: "tab-home",
  },
  {
    title: "Deals",
    body:
      "Add, edit and delete deals here. Enter price, unit mix, rents, expenses and financing by " +
      "hand, or import them from an Excel or CSV file. Tick 3 to 5 deals to compare and rank them.",
    tab: "deals",
    target: "tab-deals",
  },
  {
    title: "Compare",
    body:
      "Your selected deals side by side: NOI, cap rate, DSCR, cash-on-cash, IRR and equity " +
      "multiple, plus a year-by-year projection.",
    tab: "compare",
    target: "tab-compare",
  },
  {
    title: "Rank",
    body:
      "Orders your selected deals by unlevered IRR spread over the hurdle rate, best deal first. " +
      "Change the hurdle rate here and the ranking updates.",
    tab: "rank",
    target: "tab-rank",
  },
  {
    title: "Risk-adjusted",
    body:
      "A second ranking that also weighs DSCR, leverage and downside risk, so a high-return but " +
      "fragile deal doesn't automatically come out on top.",
    tab: "risk",
    target: "tab-risk",
  },
  {
    title: "Sensitivity",
    body:
      "Flex rents, exit cap rate and interest rates to see which assumptions move returns the " +
      "most, or run a Monte Carlo simulation.",
    tab: "sensitivity",
    target: "tab-sensitivity",
  },
  {
    title: "Market check",
    body: "Test a deal's rent assumptions against market data for its metro area.",
    tab: "market",
    target: "tab-market",
  },
  {
    title: "Ask DealRank",
    body:
      "Have a question about your deals or the numbers? Open the assistant from the button in " +
      "the bottom-right corner of any page.",
    target: "chat-launcher",
  },
  {
    title: "You're all set",
    body: "You can replay this tour anytime from the Help tab.",
    target: "tab-help",
  },
];

/** Remembers that the user has seen the tutorial, so it only auto-opens on first launch. */
export const TUTORIAL_SEEN_KEY = "dealrank.tutorial-seen";

export function hasSeenTutorial(storage: Pick<Storage, "getItem"> | null = safeStorage()): boolean {
  // Storage unavailable: treat as seen rather than opening the tour on every load.
  if (!storage) return true;
  try {
    return storage.getItem(TUTORIAL_SEEN_KEY) === "1";
  } catch {
    return true;
  }
}

export function markTutorialSeen(storage: Pick<Storage, "setItem"> | null = safeStorage()): void {
  try {
    storage?.setItem(TUTORIAL_SEEN_KEY, "1");
  } catch {
    /* storage unavailable (private mode); nothing else to do */
  }
}

function safeStorage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}
