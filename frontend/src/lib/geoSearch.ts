/** Client-side search over market geographies ("Indianapolis, IN"). */

const STATES: Record<string, string> = {
  alabama: "al",
  alaska: "ak",
  arizona: "az",
  arkansas: "ar",
  california: "ca",
  colorado: "co",
  connecticut: "ct",
  delaware: "de",
  florida: "fl",
  georgia: "ga",
  hawaii: "hi",
  idaho: "id",
  illinois: "il",
  indiana: "in",
  iowa: "ia",
  kansas: "ks",
  kentucky: "ky",
  louisiana: "la",
  maine: "me",
  maryland: "md",
  massachusetts: "ma",
  michigan: "mi",
  minnesota: "mn",
  mississippi: "ms",
  missouri: "mo",
  montana: "mt",
  nebraska: "ne",
  nevada: "nv",
  "new hampshire": "nh",
  "new jersey": "nj",
  "new mexico": "nm",
  "new york": "ny",
  "north carolina": "nc",
  "north dakota": "nd",
  ohio: "oh",
  oklahoma: "ok",
  oregon: "or",
  pennsylvania: "pa",
  "rhode island": "ri",
  "south carolina": "sc",
  "south dakota": "sd",
  tennessee: "tn",
  texas: "tx",
  utah: "ut",
  vermont: "vt",
  virginia: "va",
  washington: "wa",
  "west virginia": "wv",
  wisconsin: "wi",
  wyoming: "wy",
};

export function normalize(text: string): string {
  return text
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

/** Token lists to try: as typed, plus one with a full state name turned into its abbreviation. */
function queryVariants(query: string): string[][] {
  const q = normalize(query);
  const variants = [q.split(" ").filter(Boolean)];
  for (const name of Object.keys(STATES).sort((a, b) => b.length - a.length)) {
    const re = new RegExp(`\\b${name}\\b`);
    if (re.test(q)) {
      variants.push(q.replace(re, STATES[name]).split(" ").filter(Boolean));
      break;
    }
  }
  return variants;
}

function score(words: string[], flat: string, token: string): number {
  if (words[0]?.startsWith(token)) return 3;
  if (words.some((w) => w.startsWith(token))) return 2;
  if (flat.includes(token)) return 1;
  return 0;
}

export interface GeoMatch {
  geography: string;
  /** True when only some of the typed words matched (shown as "closest"). */
  partial: boolean;
}

/** All-words match first (ranked), then any-word matches as closest suggestions. */
export function searchGeographies(all: string[], query: string, limit = 8): GeoMatch[] {
  const variants = queryVariants(query);
  if (variants[0].length === 0) {
    return all.slice(0, limit).map((g) => ({ geography: g, partial: false }));
  }

  const full = new Map<string, number>();
  const partial = new Map<string, number>();
  for (const g of all) {
    const flat = normalize(g);
    const words = flat.split(" ");
    for (const tokens of variants) {
      const scores = tokens.map((t) => score(words, flat, t));
      const total = scores.reduce((a, b) => a + b, 0);
      if (scores.every((s) => s > 0)) full.set(g, Math.max(full.get(g) ?? 0, total));
      else if (total > 0) partial.set(g, Math.max(partial.get(g) ?? 0, total));
    }
  }
  const rank = (m: Map<string, number>, isPartial: boolean): GeoMatch[] =>
    [...m.entries()]
      .sort((a, b) => b[1] - a[1] || a[0].length - b[0].length || a[0].localeCompare(b[0]))
      .slice(0, limit)
      .map(([geography]) => ({ geography, partial: isPartial }));
  return full.size > 0 ? rank(full, false) : rank(partial, true);
}

/** Splits text into [text, isMatch] runs for highlighting the typed words. */
export function highlightParts(text: string, query: string): [string, boolean][] {
  const tokens = [...new Set(queryVariants(query).flat())];
  if (tokens.length === 0) return [[text, false]];
  const pattern = new RegExp(
    `(${tokens.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`,
    "ig",
  );
  return text
    .split(pattern)
    .filter((p) => p !== "")
    .map((p) => [p, tokens.some((t) => p.toLowerCase() === t)] as [string, boolean]);
}
