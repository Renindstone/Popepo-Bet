import type { Metadata } from "next";
import { Archivo } from "next/font/google";
import Link from "next/link";
import { Suspense } from "react";
import { Nav } from "@/components/Nav";
import "./globals.css";

const archivo = Archivo({
  variable: "--font-archivo",
  subsets: ["latin", "latin-ext"],
  axes: ["wdth"],
});

export const metadata: Metadata = {
  title: { default: "Apuestas", template: "%s | Apuestas" },
  description: "Análisis prepartido de Premier League, Bundesliga, LaLiga y Champions League.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="es" className={`${archivo.variable} antialiased`}>
      <body className="flex min-h-dvh flex-col">
        <header className="border-b border-regla bg-papel">
          <div className="mx-auto flex w-full max-w-[1180px] flex-col px-4 sm:flex-row sm:items-end sm:gap-10 sm:px-6">
            <Link href="/" className="cond pt-4 text-[1.6rem] leading-none font-black tracking-[-0.01em] sm:pb-3">
              Apuestas
            </Link>
            <Suspense fallback={<div className="h-12" />}>
              <Nav />
            </Suspense>
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1180px] flex-1 px-4 pt-8 sm:px-6">{children}</main>
        <footer className="mx-auto w-full max-w-[1180px] px-4 pt-4 pb-10 text-nota text-grafito sm:px-6">
          <p className="max-w-[72ch] border-t border-regla pt-4">
            Herramienta de análisis para uso personal. Ningún modelo garantiza ganancias: apuesta solo lo que puedas
            permitirte perder. Todas las horas están en hora de Lima.
          </p>
        </footer>
      </body>
    </html>
  );
}
