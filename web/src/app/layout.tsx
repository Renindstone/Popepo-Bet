import type { Metadata } from "next";
import { Sofia_Sans, Sofia_Sans_Condensed, Sofia_Sans_Extra_Condensed } from "next/font/google";
import Link from "next/link";
import { Suspense } from "react";
import { EditionDate, Nav } from "@/components/Nav";
import "./globals.css";

// Una familia en tres anchos: normal para leer, condensada para títulos y extracondensada para titulares y cifras
const sofia = Sofia_Sans({ variable: "--font-sofia", subsets: ["latin", "latin-ext"] });
const sofiaC = Sofia_Sans_Condensed({ variable: "--font-sofia-c", subsets: ["latin", "latin-ext"] });
const sofiaXC = Sofia_Sans_Extra_Condensed({ variable: "--font-sofia-xc", subsets: ["latin", "latin-ext"] });

export const metadata: Metadata = {
  title: { default: "Popepo-Bet", template: "%s | Popepo-Bet" },
  description: "Análisis prepartido de Premier League, Bundesliga, LaLiga, Serie A, Ligue 1, Primeira Liga, Pro League (Bélgica), Süper Lig (Turquía) y Champions League.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="es" className={`${sofia.variable} ${sofiaC.variable} ${sofiaXC.variable} antialiased`}>
      <body className="flex min-h-dvh flex-col">
        <header>
          {/* Cabecera de portada: banda amarilla con el logotipo y la fecha de la edición */}
          <div className="border-b-4 border-negro bg-amarillo text-negro">
            <div className="mx-auto flex w-full max-w-[1280px] items-end justify-between gap-6 px-4 pt-4 pb-2.5 sm:px-6 sm:pt-6 sm:pb-3">
              <Link
                href="/"
                aria-label="Popepo-Bet, portada"
                className="cond shrink-0 text-cifra-grande leading-[0.8] font-black tracking-[-0.01em] whitespace-nowrap uppercase sm:text-titulo-grande"
              >
                Popepo
                <span aria-hidden className="mx-[0.06em] inline-block size-[0.2em] rounded-full bg-rojo-portada align-[0.1em]" />
                Bet
              </Link>
              <EditionDate />
            </div>
          </div>
          <div className="border-b border-tinta bg-papel">
            <div className="mx-auto w-full max-w-[1280px] px-4 sm:px-6">
              <Suspense fallback={<div className="h-12" />}>
                <Nav />
              </Suspense>
            </div>
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1280px] flex-1 px-4 pt-6 sm:px-6">{children}</main>
        <footer className="mx-auto w-full max-w-[1280px] px-4 pt-4 pb-10 text-nota text-grafito sm:px-6">
          <p className="border-t-[3px] border-tinta pt-3">
            Herramienta de análisis para uso personal. Ningún modelo garantiza ganancias: apuesta solo lo que puedas
            permitirte perder. Todas las horas están en hora de Lima.
          </p>
        </footer>
      </body>
    </html>
  );
}
