import { type NextRequest, NextResponse } from "next/server";

// Proxy /api → API local, para que el panel funcione con un solo enlace cuando se abre por un túnel
// (cloudflared, ngrok) o desde otro equipo. Marca la petición con x-apuestas-proxy: la API no la trata como
// local y exige la clave X-API-Key (ver is_local en src/apuestas/api/app.py).
const API_URL = process.env.APUESTAS_API_INTERNAL_URL ?? "http://127.0.0.1:8000";

export function proxy(request: NextRequest) {
  const path = request.nextUrl.pathname.replace(/^\/api/, "") || "/";
  const target = new URL(`${path}${request.nextUrl.search}`, API_URL);
  const headers = new Headers(request.headers);
  headers.set("x-apuestas-proxy", "1");
  return NextResponse.rewrite(target, { request: { headers } });
}

export const config = {
  matcher: "/api/:path*",
};
