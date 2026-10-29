"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ScrollRow } from "@/components/ScrollRow";
import { longDay } from "@/lib/format";
import { useToday } from "@/lib/hooks";
import { useMe } from "@/lib/me";

const LINKS = [
  { href: "/", label: "Hoy" },
  { href: "/partidos", label: "Partidos" },
  { href: "/sorpresas", label: "Sorpresas" },
  { href: "/evaluar", label: "Evaluar cuota" },
  { href: "/capturas", label: "Capturas" },
  { href: "/rendimiento", label: "Mis apuestas" },
  { href: "/datos", label: "Datos" },
];

export function Nav() {
  const path = usePathname();
  const { me } = useMe();
  const links = me?.ai_enabled === false ? LINKS.filter((l) => l.href !== "/capturas") : LINKS;
  return (
    <nav aria-label="Secciones">
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

/** Fecha de la edición en la cabecera, en hora de Lima */
export function EditionDate() {
  const today = useToday();
  // «miércoles, 28 de octubre»: en el celular, el día de la semana y la fecha en dos líneas
  const [weekday, date] = today ? longDay(today).split(", ") : ["", ""];
  return (
    <p className="min-w-0 pb-0.5 text-right text-nota leading-tight font-bold tracking-[0.06em] uppercase">
      <span className="block min-h-[1.25em]">
        {weekday}
        <span className="hidden sm:inline">{date && `, ${date}`}</span>
      </span>
      <span className="block sm:hidden">{date}</span>
      <span className="hidden font-semibold sm:block">Fútbol prepartido</span>
    </p>
  );
}
