import type { ReactNode } from "react";

/**
 * Campo de fútbol con sus líneas, para dibujar jugadores encima con posiciones en % (`absolute` + left/top).
 * Lo usan las alineaciones de un partido y el once de la semana.
 */
export function PitchFrame({
  orientation,
  label,
  children,
}: {
  orientation: "horizontal" | "vertical";
  label: string;
  children: ReactNode;
}) {
  const horizontal = orientation === "horizontal";
  return (
    <div
      className={`relative w-full overflow-hidden rounded-[6px] bg-cesped ${horizontal ? "aspect-[105/68]" : "mx-auto aspect-[68/105] max-w-[460px]"}`}
      role="img"
      aria-label={label}
    >
      <PitchLines horizontal={horizontal} />
      {children}
    </div>
  );
}

/** Nombre corto bajo la ficha de un jugador, legible sobre el césped */
export function PitchName({ children }: { children: ReactNode }) {
  return (
    <span className="mt-0.5 max-w-full truncate rounded-[3px] bg-negro/55 px-1 text-center text-xs leading-4 md:text-etiqueta font-medium text-white">
      {children}
    </span>
  );
}

export function PitchLines({ horizontal }: { horizontal: boolean }) {
  const line = "absolute border-white/45";
  return (
    <div aria-hidden="true" className="absolute inset-[3%]">
      <div className={`${line} inset-0 border-2`} />
      {horizontal ? (
        <>
          <div className={`${line} top-0 bottom-0 left-1/2 border-l-2`} />
          <div className={`${line} top-1/2 left-1/2 aspect-square h-[27%] -translate-x-1/2 -translate-y-1/2 rounded-full border-2`} />
          <div className={`${line} top-[21%] bottom-[21%] left-0 w-[16%] border-2 border-l-0`} />
          <div className={`${line} top-[21%] right-0 bottom-[21%] w-[16%] border-2 border-r-0`} />
          <div className={`${line} top-[37%] bottom-[37%] left-0 w-[5.5%] border-2 border-l-0`} />
          <div className={`${line} top-[37%] right-0 bottom-[37%] w-[5.5%] border-2 border-r-0`} />
        </>
      ) : (
        <>
          <div className={`${line} top-1/2 right-0 left-0 border-t-2`} />
          <div className={`${line} top-1/2 left-1/2 aspect-square w-[27%] -translate-x-1/2 -translate-y-1/2 rounded-full border-2`} />
          <div className={`${line} top-0 right-[21%] left-[21%] h-[16%] border-2 border-t-0`} />
          <div className={`${line} right-[21%] bottom-0 left-[21%] h-[16%] border-2 border-b-0`} />
          <div className={`${line} top-0 right-[37%] left-[37%] h-[5.5%] border-2 border-t-0`} />
          <div className={`${line} right-[37%] bottom-0 left-[37%] h-[5.5%] border-2 border-b-0`} />
        </>
      )}
    </div>
  );
}

/** Ficha redonda de un jugador sobre el césped (clara, como la del local en las alineaciones) */
export function PitchDisc({ children }: { children: ReactNode }) {
  return (
    <span className="relative flex size-9 items-center justify-center rounded-full bg-ficha text-nota font-bold text-negro shadow">
      {children}
    </span>
  );
}
