import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./en.json";
import de from "./de.json";

/**
 * Spec §9: English and German at launch, all UI strings externalised.
 * Default is English; the choice is remembered per browser.
 */
const STORAGE_KEY = "tt.lang";
const saved = (() => {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
})();

void i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, de: { translation: de } },
  lng: saved ?? "en",
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});

export function setLanguage(lang: "en" | "de") {
  void i18n.changeLanguage(lang);
  try {
    localStorage.setItem(STORAGE_KEY, lang);
  } catch {
    /* private mode — non-fatal */
  }
}

export default i18n;
