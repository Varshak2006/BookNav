const SEARCHABLE_FIELDS = ["title", "author", "category", "keywords", "description"];

function escapeRegex(value) {
  return String(value || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function tokenizeSearchTerm(value) {
  const tokens = String(value || "")
    .toLowerCase()
    .match(/[a-z0-9]+/g);

  return Array.from(new Set(tokens || []));
}

function fieldRegexConditions(term) {
  const safeTerm = escapeRegex(term);
  if (!safeTerm) {
    return [];
  }

  return SEARCHABLE_FIELDS.map((field) => ({
    [field]: { $regex: safeTerm, $options: "i" }
  }));
}

function buildSearchFilter(searchTerm) {
  const trimmed = String(searchTerm || "").trim();
  const tokens = tokenizeSearchTerm(trimmed);
  const phraseConditions = fieldRegexConditions(trimmed);

  const tokenAndConditions = tokens.map((token) => ({
    $or: fieldRegexConditions(token)
  }));

  if (!trimmed) {
    return {};
  }

  if (tokenAndConditions.length === 0) {
    return { $or: phraseConditions };
  }

  return {
    $or: [
      ...phraseConditions,
      { $and: tokenAndConditions }
    ]
  };
}

function bookMatchesSearch(book, searchTerm) {
  const trimmed = String(searchTerm || "").trim().toLowerCase();
  if (!trimmed) {
    return true;
  }

  const values = SEARCHABLE_FIELDS
    .map((field) => String(book?.[field] || "").toLowerCase())
    .filter(Boolean);
  const combined = values.join(" ");
  const tokens = tokenizeSearchTerm(trimmed);

  return (
    values.some((value) => value.includes(trimmed)) ||
    tokens.every((token) => combined.includes(token))
  );
}

module.exports = {
  SEARCHABLE_FIELDS,
  escapeRegex,
  tokenizeSearchTerm,
  buildSearchFilter,
  bookMatchesSearch
};
