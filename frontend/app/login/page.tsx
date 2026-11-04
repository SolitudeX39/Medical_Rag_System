"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { isLoggedIn, login } from "../authStore";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  useEffect(() => {
    if (isLoggedIn()) router.replace("/");
  }, [router]);

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    const ok = login(username, password);
    setBusy(false);
    if (!ok) {
      setError("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง");
      return;
    }
    router.replace("/");
  }

  return (
    <div className="relative flex h-dvh items-center justify-center overflow-hidden px-5 md:justify-end md:px-16 lg:px-24">
      <div
        className="pointer-events-none absolute inset-0 bg-cover bg-center bg-no-repeat"
        style={{ backgroundImage: "url('/login-hero.jpg')" }}
      />
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-r from-[#020617]/35 via-[#020617]/55 to-[#020617]/92" />
      <div className="relative w-full max-w-lg">
        <h1 className="text-center text-4xl font-bold tracking-[0.12em] text-cyan-300 drop-shadow-[0_0_28px_rgba(34,211,238,0.45)] sm:text-5xl">
          MEDICAL RAG AI
        </h1>
        <p className="mt-4 text-center text-xl font-semibold text-white">เข้าสู่ระบบ</p>

        <form onSubmit={onSubmit} className="glass-panel mt-8 rounded-3xl p-6 md:p-8">
          <label className="block text-xs tracking-[0.16em] text-slate-500">
            USERNAME
            <input
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
              className="mt-2 w-full rounded-2xl border border-white/10 bg-[#070b14] px-4 py-3 text-sm text-white outline-none focus:border-cyan-300/50"
              placeholder="admin"
            />
          </label>
          <label className="mt-4 block text-xs tracking-[0.16em] text-slate-500">
            PASSWORD
            <span className="relative mt-2 block">
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="current-password"
                className="w-full rounded-2xl border border-white/10 bg-[#070b14] px-4 py-3 pr-16 text-sm text-white outline-none focus:border-cyan-300/50"
                placeholder="••••••••"
              />
              <button
                type="button"
                className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-cyan-200 hover:text-white"
                onClick={() => setShowPassword((open) => !open)}
                aria-pressed={showPassword}
              >
                {showPassword ? "ซ่อน" : "แสดง"}
              </button>
            </span>
          </label>

          {error && <p className="mt-4 text-sm text-rose-300">{error}</p>}

          <button
            type="submit"
            disabled={busy || !username.trim() || !password}
            className="mt-6 w-full rounded-2xl bg-cyan-400 py-3 text-sm font-semibold text-slate-950 hover:bg-cyan-300 disabled:opacity-50"
          >
            {busy ? "กำลังเข้าสู่ระบบ..." : "เข้าสู่ระบบ"}
          </button>
        </form>
      </div>
    </div>
  );
}
