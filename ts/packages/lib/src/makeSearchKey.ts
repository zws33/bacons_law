export function makeSearchKey(label: string): string {
  // Normalize accents + case
  const normalized = label
    .normalize("NFKD")
    .replace(/\p{Mark}/gu, "")
    .toLowerCase();

  // drop punctuation/symbols
  const alnum = normalized
    .replace(/[^\p{Letter}\p{Number}]/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (alnum.length > 0) {
    return alnum;
  }

  // fallback if title is all punctuation/symbols (e.g. "$")
  const fallback = normalized.replace(/\s+/g, " ").trim();
  if (fallback.length === 0) {
    throw new Error(`Label produced invalid search key: "${label}"`);
  }
  return fallback;
}
