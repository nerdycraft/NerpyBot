import { type SupportedLocale, useLocaleStore } from "@/stores/locale";
import { de } from "./locales/de";
import { en } from "./locales/en";

type Locales = typeof en;

/** Recursive type that produces a union of all valid dot-path keys in the translation schema. */
type FlatKeys<T, P extends string = ""> = {
  [K in keyof T & string]: T[K] extends Record<string, unknown>
    ? FlatKeys<T[K], P extends "" ? K : `${P}.${K}`>
    : P extends ""
      ? K
      : `${P}.${K}`;
}[keyof T & string];

/** Union of all valid translation key dot-paths. Exported for use in component type annotations. */
export type I18nKey = FlatKeys<Locales>;

const locales: Record<SupportedLocale, Locales> = { en, de };

const warnedMissingKeys = new Set<string>();

function getByPath(obj: unknown, path: string): string | undefined {
  let cur: unknown = obj;
  for (const k of path.split(".")) {
    if (cur == null || typeof cur !== "object") return undefined;
    cur = (cur as Record<string, unknown>)[k];
  }
  return typeof cur === "string" ? cur : undefined;
}

function interpolate(str: string, params?: Record<string, string | number>): string {
  if (!params) return str;
  return str.replace(/\{(\w+)\}/g, (_, k: string) => String(params[k] ?? `{${k}}`));
}

export function useI18n() {
  const locale = useLocaleStore();

  function t(key: I18nKey, params?: Record<string, string | number>): string {
    const translations = locales[locale.current] ?? en;
    const raw = getByPath(translations, key) ?? (translations !== en ? getByPath(en, key) : undefined) ?? key;
    if (raw === key && import.meta.env.DEV && !warnedMissingKeys.has(key)) {
      warnedMissingKeys.add(key);
      console.warn(`[i18n] Missing key: ${key}`);
    }
    return interpolate(raw, params);
  }

  return { t, locale };
}
