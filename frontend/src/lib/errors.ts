// Extrae un mensaje legible de cualquier error (Error, objeto de Supabase, o lo
// que sea) para mostrarlo en la UI sin caer en "[object Object]".
export function toMessage(e: unknown): string {
  if (e instanceof Error) return e.message;
  if (typeof e === "object" && e !== null && "message" in e) {
    return String((e as { message: unknown }).message);
  }
  return String(e);
}
