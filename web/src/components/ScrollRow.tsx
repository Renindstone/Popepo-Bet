"use client";

import { type ReactNode, useEffect, useRef, useState } from "react";

/**
 * Fila que se desplaza de lado cuando no cabe (el menú y las pestañas en el celular). Si queda algo fuera, ese borde
 * se difumina y aparece una flecha que avanza al tocarla: así se ve que hay más. Lleva a la vista el elemento activo
 * (`aria-current="page"` o `aria-selected="true"`) cada vez que cambia `activeKey`.
 */
export function ScrollRow({
  children,
  activeKey,
  className = "",
}: {
  children: ReactNode;
  activeKey?: string;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [edges, setEdges] = useState({ left: false, right: false });

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const update = () =>
      setEdges({ left: el.scrollLeft > 2, right: el.scrollLeft + el.clientWidth < el.scrollWidth - 2 });
    const ro = new ResizeObserver(update);
    ro.observe(el);
    el.addEventListener("scroll", update, { passive: true });
    return () => {
      ro.disconnect();
      el.removeEventListener("scroll", update);
    };
  }, []);

  useEffect(() => {
    const el = ref.current;
    const item = el?.querySelector<HTMLElement>('[aria-current="page"], [aria-selected="true"]');
    if (!el || !item) return;
    const x = item.getBoundingClientRect().left - el.getBoundingClientRect().left + el.scrollLeft;
    // Si está tapado por la flecha o fuera, se centra (sin animación: es la posición inicial)
    if (x < el.scrollLeft + 48 || x + item.offsetWidth > el.scrollLeft + el.clientWidth - 48) {
      el.scrollLeft = x - (el.clientWidth - item.offsetWidth) / 2;
    }
  }, [activeKey]);

  function nudge(dir: 1 | -1) {
    const el = ref.current;
    if (!el) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollBy({ left: dir * el.clientWidth * 0.6, behavior: reduce ? "auto" : "smooth" });
  }

  return (
    <div className={`relative ${className}`}>
      <div ref={ref} className="overflow-x-auto overflow-y-hidden [scrollbar-width:none]">
        {children}
      </div>
      {edges.left && <Arrow side="left" onClick={() => nudge(-1)} />}
      {edges.right && <Arrow side="right" onClick={() => nudge(1)} />}
    </div>
  );
}

function Arrow({ side, onClick }: { side: "left" | "right"; onClick: () => void }) {
  const right = side === "right";
  return (
    <button
      type="button"
      tabIndex={-1}
      onClick={onClick}
      aria-label={right ? "Ver más a la derecha" : "Ver más a la izquierda"}
      className={`absolute inset-y-0 flex w-12 items-center from-papel from-45% to-transparent text-grafito transition-colors hover:text-tinta ${
        right ? "right-0 justify-end bg-linear-to-l pr-2" : "left-0 justify-start bg-linear-to-r pl-2"
      }`}
    >
      <svg
        aria-hidden="true"
        viewBox="0 0 24 24"
        className="size-5"
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d={right ? "m9 6 6 6-6 6" : "m15 6-6 6 6 6"} />
      </svg>
    </button>
  );
}
