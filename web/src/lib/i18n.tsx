"use client";

// Idioma del panel: español o inglés. Cada texto lleva sus dos versiones en el sitio donde se usa: tr("Hoy", "Today").
// Al cambiar de idioma se vuelve a montar todo el panel, así que tr() puede leer el idioma sin suscribirse a nada.

import { Fragment, type ReactNode, useEffect } from "react";
import { useRemembered } from "./hooks";

export type Lang = "es" | "en";

const LANGS = ["es", "en"] as const;
const STORAGE = "apuestas.idioma";

let current: Lang = "es";

/** Idioma en uso */
export function lang(): Lang {
  return current;
}

/** El texto (o el JSX) del idioma en uso */
export function tr<T>(es: T, en: T): T {
  return current === "en" ? en : es;
}

/** Formato de fechas y números del idioma en uso (el dinero siempre en soles, ver format.ts) */
export function locale(): string {
  return current === "en" ? "en-GB" : "es-PE";
}

/** Sin nada elegido, el idioma del navegador; si no es español ni inglés, español */
function browserLang(): Lang {
  return navigator.language.toLowerCase().startsWith("en") ? "en" : "es";
}

export function useLang(): [Lang, (value: Lang) => void] {
  return useRemembered(STORAGE, LANGS, browserLang);
}

function setCurrent(value: Lang) {
  current = value;
}

/** Envuelve el panel: fija el idioma antes de pintar a los hijos y los vuelve a montar al cambiarlo */
export function LangProvider({ children }: { children: ReactNode }) {
  const [value] = useLang();
  setCurrent(value);
  useEffect(() => {
    document.documentElement.lang = value;
  }, [value]);
  return <Fragment key={value}>{children}</Fragment>;
}

/** Selector ES / EN de la cabecera */
export function LangSwitch() {
  const [value, set] = useLang();
  return (
    <div role="group" aria-label="Idioma / Language" className="flex">
      {LANGS.map((l) => (
        <button
          key={l}
          type="button"
          lang={l}
          aria-pressed={value === l}
          aria-label={l === "es" ? "Español" : "English"}
          onClick={() => set(l)}
          className={`semi inline-flex min-h-7 min-w-9 items-center justify-center border border-negro px-1.5 text-nota font-bold uppercase transition-colors ${
            value === l ? "bg-negro text-amarillo" : "text-negro hover:bg-negro/10"
          }`}
        >
          {l}
        </button>
      ))}
    </div>
  );
}
