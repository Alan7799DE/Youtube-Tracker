import { createClient } from "@supabase/supabase-js";

// Si faltan las env vars (p. ej. al previsualizar el front sin un proyecto
// Supabase real), usamos placeholders para que la app igual monte y se vea la
// UI. Con un `.env` real, auth y RLS funcionan de verdad.
const url = (import.meta.env.VITE_SUPABASE_URL as string) || "http://localhost:54321";
const anonKey = (import.meta.env.VITE_SUPABASE_ANON_KEY as string) || "public-anon-key-placeholder";

export const supabase = createClient(url, anonKey);
