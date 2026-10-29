import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  // «Semana» pasó a llamarse «Sorpresas» (29-10-2026); los enlaces viejos conservan su ?semana=
  async redirects() {
    return [{ source: "/semana", destination: "/sorpresas", permanent: false }];
  },
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
