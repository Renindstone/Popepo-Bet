import type { Metadata } from "next";
import { Suspense } from "react";
import { CapturasGate } from "@/components/capturas/CapturasView";
import { Loading } from "@/components/ui";

export const metadata: Metadata = { title: "Capturas" };

export default function Page() {
  return (
    <Suspense fallback={<Loading lines={6} />}>
      <CapturasGate />
    </Suspense>
  );
}
