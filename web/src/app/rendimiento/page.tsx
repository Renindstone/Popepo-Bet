import type { Metadata } from "next";
import { Suspense } from "react";
import { RendimientoView } from "@/components/rendimiento/RendimientoView";
import { Loading } from "@/components/ui";

export const metadata: Metadata = { title: "Mis apuestas" };

export default function Page() {
  return (
    <Suspense fallback={<Loading lines={6} />}>
      <RendimientoView />
    </Suspense>
  );
}
