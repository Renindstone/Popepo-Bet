// Marca de bolígrafo dibujada a mano sobre un elemento: un óvalo que lo rodea o un tachón

const PATHS = {
  circle: "M78 9 C58 -1 16 2 6 19 C-3 35 26 48 56 46 C86 44 99 31 94 16 C90 6 72 2 46 5",
  slash: "M8 44 C30 33 58 18 92 6",
};

export function PenMark({ kind = "circle", className = "" }: { kind?: keyof typeof PATHS; className?: string }) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 100 50"
      preserveAspectRatio="none"
      className={`pointer-events-none absolute overflow-visible text-boli ${className}`}
    >
      <path
        d={PATHS[kind]}
        pathLength={1}
        fill="none"
        stroke="currentColor"
        strokeWidth={2.4}
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
        className="trazo"
      />
    </svg>
  );
}
