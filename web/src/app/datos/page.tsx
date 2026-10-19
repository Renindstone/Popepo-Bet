import type { Metadata } from "next";
import { Suspense } from "react";
import { DatosView } from "@/components/datos/DatosView";
import { Loading } from "@/components/ui";

export const metadata: Metadata = { title: "Estado de los datos" };

export default function Page() {
  return (
    <Suspense fallback={<Loading lines={6} />}>
      <DatosView />
    </Suspense>
  );
}
