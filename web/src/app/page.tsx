import { Suspense } from "react";
import { HoyView } from "@/components/hoy/HoyView";
import { Loading } from "@/components/ui";

export default function Page() {
  return (
    <Suspense fallback={<Loading lines={4} />}>
      <HoyView />
    </Suspense>
  );
}
