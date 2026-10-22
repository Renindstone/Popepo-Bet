"use client";

import { type KeyboardEvent, type ReactNode, useRef, useSyncExternalStore } from "react";
import { ScrollRow } from "@/components/ScrollRow";

export interface TabDef {
  id: string;
  label: string;
}

function subscribe(cb: () => void) {
  window.addEventListener("hashchange", cb);
  return () => window.removeEventListener("hashchange", cb);
}

/**
 * Pestaña activa guardada en el ancla de la URL (`#cuotas`): sobrevive a recargar la página y se puede enlazar.
 * Se cambia con `replaceState`, así que «atrás» sale de la página en vez de recorrer pestañas.
 */
export function useHashTab(tabs: readonly TabDef[]): [string, (id: string) => void] {
  const hash = useSyncExternalStore(subscribe, () => window.location.hash.slice(1), () => "");
  const current = tabs.some((t) => t.id === hash) ? hash : tabs[0].id;
  function select(id: string) {
    window.history.replaceState(null, "", `#${id}`);
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  }
  return [current, select];
}

/**
 * Pestañas con el mismo trazo que el menú (subrayado azul en la activa). Se quedan fijas arriba al bajar, y al
 * cambiar de pestaña desde abajo la página vuelve al principio del contenido.
 */
export function Tabs({
  tabs,
  current,
  onSelect,
  label,
  children,
}: {
  tabs: readonly TabDef[];
  current: string;
  onSelect: (id: string) => void;
  label: string;
  children: ReactNode;
}) {
  const top = useRef<HTMLDivElement>(null);

  function choose(id: string) {
    const y = top.current ? top.current.getBoundingClientRect().top + window.scrollY : 0;
    if (window.scrollY > y) window.scrollTo({ top: y });
    onSelect(id);
  }

  function onKey(e: KeyboardEvent<HTMLButtonElement>, i: number) {
    const step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    const to = e.key === "Home" ? 0 : e.key === "End" ? tabs.length - 1 : step ? (i + step + tabs.length) % tabs.length : null;
    if (to == null) return;
    e.preventDefault();
    choose(tabs[to].id);
    document.getElementById(`tab-${tabs[to].id}`)?.focus();
  }

  return (
    <>
      <div ref={top} />
      <div className="sticky top-0 z-10 -mx-4 border-b border-regla bg-papel sm:mx-0">
        <ScrollRow activeKey={current}>
          <div role="tablist" aria-label={label} className="flex w-max gap-5 px-4 whitespace-nowrap sm:gap-7 sm:px-0">
            {tabs.map((t, i) => {
              const active = t.id === current;
              return (
                <button
                  key={t.id}
                  id={`tab-${t.id}`}
                  type="button"
                  role="tab"
                  aria-selected={active}
                  aria-controls={`panel-${t.id}`}
                  tabIndex={active ? 0 : -1}
                  onClick={() => choose(t.id)}
                  onKeyDown={(e) => onKey(e, i)}
                  className={`semi relative py-3 text-interfaz font-semibold transition-colors ${
                    active ? "text-tinta" : "text-grafito hover:text-tinta"
                  }`}
                >
                  {t.label}
                  {active && <span className="absolute inset-x-0 bottom-0 h-[3px] rounded-full bg-boli" />}
                </button>
              );
            })}
          </div>
        </ScrollRow>
      </div>
      <div
        role="tabpanel"
        id={`panel-${current}`}
        aria-labelledby={`tab-${current}`}
        className="[&>section:first-child]:border-t-0"
      >
        {children}
      </div>
    </>
  );
}
