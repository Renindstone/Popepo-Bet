import type { Metadata } from "next";
import { Suspense } from "react";
import { SemanaView } from "@/components/semana/SemanaView";
import { Loading } from "@/components/ui";

export const metadata: Metadata = { title: "Semana" };

export default function Page() {
  return (
    <Suspense fallback={<Loading lines={6} />}>
      <SemanaView />
    </Suspense>
  );
}
