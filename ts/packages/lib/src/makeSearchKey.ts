export function makeSearchKey(label: string): string {
  return label
    .normalize("NFKD")
    .replace(/\p{Mark}/gu, "")
    .toLocaleLowerCase()
    .replace(/[^\p{Letter}\p{Number}]/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}
