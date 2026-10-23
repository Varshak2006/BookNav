
const STOP_WORDS = new Set([
  "a", "an", "the", "and", "or", "but", "of",
  "in", "on", "at", "to", "for", "by", "with",
  "from", "as", "is", "are", "was", "were",
  "be", "this", "that", "it", "its", "about",
  "into", "their", "your", "our", "how", "what",
  "when", "where", "who", "which", "using", "learn"
]);

function normalizeText(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9\s'-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function extractKeywords(book = {}, options = {}) {
  const maxKeywords = options.maxKeywords || 20;
  const candidates = new Map();

  const fields = [
    { value: book.title, weight: 5 },
    { value: book.category, weight: 5 },
    { value: book.author, weight: 3 },
    { value: book.description, weight: 2 }
  ];

  for (const field of fields) {
    const text = normalizeText(field.value);
    if (!text) continue;

    const words = text.split(" ").filter(Boolean);

    for (const word of words) {
      if (STOP_WORDS.has(word) || word.length < 2) continue;

      candidates.set(
        word,
        (candidates.get(word) || 0) + field.weight
      );
    }

    for (let i = 0; i < words.length - 1; i++) {
      const first = words[i];
      const second = words[i + 1];

      if (
        STOP_WORDS.has(first) ||
        STOP_WORDS.has(second) ||
        first.length < 2 ||
        second.length < 2
      ) {
        continue;
      }

      const phrase = `${first} ${second}`;

      candidates.set(
        phrase,
        (candidates.get(phrase) || 0) + field.weight * 2
      );
    }
  }

  const existing = String(book.keywords || "")
    .split(/[,;\n]+/)
    .map((keyword) => keyword.trim())
    .filter(Boolean);

  const ranked = [...candidates.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, maxKeywords)
    .map(([keyword]) => keyword);

  const unique = new Map();

  for (const keyword of [...existing, ...ranked]) {
    const normalized = normalizeText(keyword);

    if (normalized && !unique.has(normalized)) {
      unique.set(normalized, keyword.trim());
    }
  }

  return [...unique.values()].join(", ");
}

module.exports = {
  extractKeywords,
  normalizeText
};
