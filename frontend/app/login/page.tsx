"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getSession, homePath, loginLocal, saveSession, type AuthRole } from "../authStore";
import { loginRemote } from "../clinic";

export default function LoginPage() {
  const router = useRouter();
  const [portal, setPortal] = useState<AuthRole>("staff");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  useEffect(() => {
    const session = getSession();
    if (session) router.replace(homePath(session.role));
  }, [router]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      let session = null;
      try {
        const remote = await loginRemote(username, password);
        session = { username: remote.username, role: remote.role, name: remote.name };
        saveSession(session);
      } catch {
        session = loginLocal(username, password);
      }
      if (!session) {
        setError("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง");
        return;
      }
      router.replace(homePath(session.role));
    } finally {
      setBusy(false);
    }
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
          MEDICAL CLINIC
        </h1>
        <p className="mt-4 text-center text-xl font-semibold text-white">เข้าสู่ระบบ</p>
        <p className="mt-2 text-center text-sm text-slate-300">
          เลือกฝั่งงานคัดกรอง หรือพอร์ทัลคนไข้
        </p>

        <form onSubmit={(event) => void onSubmit(event)} className="glass-panel mt-8 rounded-3xl p-6 md:p-8">
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              className={`rounded-2xl px-3 py-3 text-sm ${
                portal === "staff"
                  ? "bg-cyan-400 font-semibold text-slate-950"
                  : "border border-white/10 text-slate-300 hover:bg-white/5"
              }`}
              onClick={() => setPortal("staff")}
            >
              เจ้าหน้าที่คัดกรอง
            </button>
            <button
              type="button"
              className={`rounded-2xl px-3 py-3 text-sm ${
                portal === "patient"
                  ? "bg-cyan-400 font-semibold text-slate-950"
                  : "border border-white/10 text-slate-300 hover:bg-white/5"
              }`}
              onClick={() => setPortal("patient")}
            >
              คนไข้
            </button>
          </div>

          <label className="mt-6 block text-xs tracking-[0.16em] text-slate-500">
            USERNAME
            <input
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
              className="mt-2 w-full rounded-2xl border border-white/10 bg-[#070b14] px-4 py-3 text-sm text-white outline-none focus:border-cyan-300/50"
              placeholder={portal === "staff" ? "staff" : "somchai"}
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

          <p className="mt-4 text-xs leading-relaxed text-slate-400">
            {portal === "staff"
              ? "เดโมเจ้าหน้าที่: staff / test1234"
              : "เดโมคนไข้: somchai, malee, nicha / test1234"}
          </p>

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
