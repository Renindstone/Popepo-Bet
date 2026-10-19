import type { Metadata } from "next";
import { Suspense } from "react";
import { EvaluarView } from "@/components/evaluar/EvaluarView";
import { Loading } from "@/components/ui";

export const metadata: Metadata = { title: "Evaluar cuota" };

export default function Page() {
  return (
    <Suspense fallback={<Loading lines={6} />}>
      <EvaluarView />
    </Suspense>
  );
}
