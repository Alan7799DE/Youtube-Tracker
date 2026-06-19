import { useState } from "react";
import { supabase } from "../lib/supabase";

export function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const { error } =
      mode === "login"
        ? await supabase.auth.signInWithPassword({ email, password })
        : await supabase.auth.signUp({ email, password });
    if (error) setError(error.message);
  }

  return (
    <form onSubmit={submit}>
      <h1>{mode === "login" ? "Ingresar" : "Crear cuenta"}</h1>
      <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" />
      <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Contraseña" />
      <button type="submit">{mode === "login" ? "Ingresar" : "Registrarme"}</button>
      <button type="button" onClick={() => setMode(mode === "login" ? "signup" : "login")}>
        {mode === "login" ? "Crear cuenta" : "Ya tengo cuenta"}
      </button>
      {error && <p role="alert">{error}</p>}
    </form>
  );
}
