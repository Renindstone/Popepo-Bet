import { useApi } from "@/lib/api";
import type { Me } from "@/lib/types";

/** El usuario de esta clave y si usa la IA (con la IA apagada se esconden capturas y explicaciones de Claude) */
export function useMe() {
  const { data, mutate } = useApi<Me>("/me");
  return { me: data, mutate };
}
