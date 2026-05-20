import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { Lang } from "@/types";
import { t, type TKey } from "@/lib/i18n";

interface LangCtxType {
  lang: Lang;
  setLang: (l: Lang) => void;
  toggle: () => void;
  t: (key: TKey) => string;
  dir: "ltr" | "rtl";
}

const LangCtx = createContext<LangCtxType | null>(null);

export function LangProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLang] = useState<Lang>(() => {
    const saved = localStorage.getItem("naftscan_lang");
    return (saved === "ar" || saved === "en") ? saved : "en";
  });

  useEffect(() => {
    localStorage.setItem("naftscan_lang", lang);
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  }, [lang]);

  const value = useMemo<LangCtxType>(
    () => ({
      lang,
      setLang,
      toggle: () => setLang(lang === "ar" ? "en" : "ar"),
      t: (key: TKey) => t(lang, key),
      dir: lang === "ar" ? "rtl" : "ltr",
    }),
    [lang]
  );

  return <LangCtx.Provider value={value}>{children}</LangCtx.Provider>;
}

export function useLang() {
  const ctx = useContext(LangCtx);
  if (!ctx) throw new Error("useLang must be used inside LangProvider");
  return ctx;
}
