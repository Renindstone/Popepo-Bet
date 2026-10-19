import type { Metadata } from "next";
import { Suspense } from "react";
import { PartidoView } from "@/components/partido/PartidoView";
import { Loading } from "@/components/ui";

export const metadata: Metadata = { title: "Partido" };

export default function Page() {
  return (
    <Suspense fallback={<Loading lines={6} />}>
      <PartidoView />
    </Suspense>
  );
}
