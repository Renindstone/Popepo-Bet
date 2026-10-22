"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ScrollRow } from "@/components/ScrollRow";

const LINKS = [
  { href: "/", label: "Hoy" },
  { href: "/partidos", label: "Partidos" },
  { href: "/evaluar", label: "Evaluar cuota" },
  { href: "/capturas", label: "Capturas" },
  { href: "/rendimiento", label: "Mis apuestas" },
  { href: "/datos", label: "Datos" },
];

export function Nav() {
  const path = usePathname();
  return (
    <nav aria-label="Secciones">
      {/* En el celular el menú no cabe: se desplaza de lado, con una flecha que lo indica */}
      <ScrollRow activeKey={path} className="-mx-4 sm:mx-0">
        <ul className="flex w-max gap-5 px-4 whitespace-nowrap sm:gap-7 sm:px-0">
          {LINKS.map((l) => {
            const active = l.href === "/" ? path === "/" : path.startsWith(l.href);
            return (
              <li key={l.href}>
                <Link
                  href={l.href}
                  aria-current={active ? "page" : undefined}
                  className={`semi relative block py-3 text-interfaz font-semibold transition-colors ${
                    active ? "text-tinta" : "text-grafito hover:text-tinta"
                  }`}
                >
                  {l.label}
                  {active && <span className="absolute inset-x-0 bottom-0 h-[3px] rounded-full bg-boli" />}
                </Link>
              </li>
            );
          })}
        </ul>
      </ScrollRow>
    </nav>
  );
}
