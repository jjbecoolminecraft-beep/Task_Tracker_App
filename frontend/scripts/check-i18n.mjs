// Fails if en.json and de.json have different key sets (spec §9 / ADR 0004).
import en from "../src/i18n/en.json" with { type: "json" };
import de from "../src/i18n/de.json" with { type: "json" };

const flatten = (obj, prefix = "") =>
  Object.entries(obj).flatMap(([k, v]) =>
    v && typeof v === "object" ? flatten(v, `${prefix}${k}.`) : [`${prefix}${k}`],
  );

const a = new Set(flatten(en));
const b = new Set(flatten(de));
const missingInDe = [...a].filter((k) => !b.has(k));
const missingInEn = [...b].filter((k) => !a.has(k));

if (missingInDe.length || missingInEn.length) {
  if (missingInDe.length) console.error("Missing in de.json:", missingInDe);
  if (missingInEn.length) console.error("Missing in en.json:", missingInEn);
  process.exit(1);
}
console.log(`i18n OK — ${a.size} keys in both locales`);
