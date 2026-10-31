"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ScrollRow } from "@/components/ScrollRow";
import { longDay } from "@/lib/format";
import { useToday } from "@/lib/hooks";
import { LangSwitch, tr } from "@/lib/i18n";
import { useMe } from "@/lib/me";

export function Nav() {
  const path = usePathname();
  const { me } = useMe();
  const all = [
    { href: "/", label: tr("Hoy", "Today") },
    { href: "/partidos", label: tr("Partidos", "Matches") },
    { href: "/sorpresas", label: tr("Sorpresas", "Surprises") },
    { href: "/evaluar", label: tr("Evaluar cuota", "Check odds") },
    { href: "/capturas", label: tr("Capturas", "Screenshots") },
    { href: "/rendimiento", label: tr("Mis apuestas", "My bets") },
    { href: "/datos", label: tr("Datos", "Data") },
  ];
  const links = me?.ai_enabled === false ? all.filter((l) => l.href !== "/capturas") : all;
  return (
    <nav aria-label={tr("Secciones", "Sections")}>
      {/* En el celular el menú no cabe: se desplaza de lado, con una flecha que lo indica */}
      <ScrollRow activeKey={path} className="-mx-4 sm:mx-0">
        <ul className="flex w-max gap-5 px-4 whitespace-nowrap sm:gap-7 sm:px-0">
          {links.map((l) => {
            const active = l.href === "/" ? path === "/" : path.startsWith(l.href);
            return (
              <li key={l.href}>
                <Link
                  href={l.href}
                  aria-current={active ? "page" : undefined}
                  className={`semi relative block py-3 text-base font-bold transition-colors ${
                    active ? "text-tinta" : "text-grafito hover:text-tinta"
                  }`}
                >
                  {l.label}
                  {active && <span className="absolute inset-x-0 bottom-0 h-1 bg-tinta" />}
                </Link>
              </li>
            );
          })}
        </ul>
      </ScrollRow>
    </nav>
  );
}

/** Logotipo de la cabecera: lleva a la portada */
export function Logo() {
  return (
    <Link
      href="/"
      aria-label={tr("Popepo-Bet, portada", "Popepo-Bet, front page")}
      className="cond shrink-0 text-cifra-grande leading-[0.8] font-black tracking-[-0.01em] whitespace-nowrap uppercase sm:text-titulo-grande"
    >
      Popepo
      <span aria-hidden className="mx-[0.06em] inline-block size-[0.2em] rounded-full bg-rojo-portada align-[0.1em]" />
      Bet
    </Link>
  );
}

/** Fecha de la edición en la cabecera, en hora de Lima, con el selector de idioma encima */
export function EditionDate() {
  const today = useToday();
  // «miércoles, 28 de octubre» o «Wednesday 28 October»: en el celular, el día de la semana y la fecha en dos líneas
  const [weekday = "", ...rest] = today ? longDay(today).split(/,? /) : [];
  const date = rest.join(" ");
  return (
    <div className="flex min-w-0 flex-col items-end gap-2">
      <LangSwitch />
      <p className="min-w-0 pb-0.5 text-right text-nota leading-tight font-bold tracking-[0.06em] uppercase">
        <span className="block min-h-[1.25em]">
          {weekday}
          <span className="hidden sm:inline">{date && `, ${date}`}</span>
        </span>
        <span className="block sm:hidden">{date}</span>
        <span className="hidden font-semibold sm:block">{tr("Fútbol prepartido", "Pre-match football")}</span>
      </p>
    </div>
  );
}

export function SiteFooter() {
  return (
    <footer className="mx-auto w-full max-w-[1280px] px-4 pt-4 pb-10 text-nota text-grafito sm:px-6">
      <p className="border-t-[3px] border-tinta pt-3">
        {tr(
          "Herramienta de análisis para uso personal. Ningún modelo garantiza ganancias: apuesta solo lo que puedas permitirte perder. Todas las horas están en hora de Lima.",
          "Analysis tool for personal use. No model guarantees profits: only bet what you can afford to lose. All times are Lima time.",
        )}
      </p>
    </footer>
  );
}
