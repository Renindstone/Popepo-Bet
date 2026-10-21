"use client";

import { useState, useSyncExternalStore } from "react";
import { apiUrl, DIRECT_API_URL } from "@/lib/api";

const noop = () => () => {};

/** Escudo del equipo (lo sirve la API desde la caché de FotMob). Si no hay escudo, no ocupa sitio. */
export function Crest({ id, size = 20, className = "" }: { id: number | null | undefined; size?: number; className?: string }) {
  const base = useSyncExternalStore(noop, apiUrl, () => DIRECT_API_URL);
  const [failed, setFailed] = useState(false);
  if (id == null || failed) return null;
  return (
    // eslint-disable-next-line @next/next/no-img-element -- imagen pequeña servida por nuestra API, sin optimizar
    <img
      src={`${base}/teams/${id}/logo`}
      alt=""
      width={size}
      height={size}
      loading="lazy"
      decoding="async"
      onError={() => setFailed(true)}
      className={`inline-block shrink-0 object-contain align-middle ${className}`}
      style={{ width: size, height: size }}
    />
  );
}
