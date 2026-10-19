import type { Metadata } from "next";
import { Suspense } from "react";
import { PartidosView } from "@/components/partidos/PartidosView";
import { Loading } from "@/components/ui";

export const metadata: Metadata = { title: "Partidos" };

export default function Page() {
  return (
    <Suspense fallback={<Loading lines={6} />}>
      <PartidosView />
    </Suspense>
  );
}
