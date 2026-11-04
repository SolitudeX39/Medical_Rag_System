"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import AppTabs from "./AppTabs";
import { AUTH_EVENT, isLoggedIn } from "./authStore";

export default function AuthGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [authed, setAuthed] = useState(false);
  const isLogin = pathname === "/login";

  useEffect(() => {
    function sync() {
      setAuthed(isLoggedIn());
      setReady(true);
    }
    sync();
    window.addEventListener(AUTH_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(AUTH_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  useEffect(() => {
    if (!ready) return;
    if (!authed && !isLogin) router.replace("/login");
    if (authed && isLogin) router.replace("/");
  }, [ready, authed, isLogin, router]);

  if (!ready || (!authed && !isLogin)) {
    return (
      <div className="flex h-dvh items-center justify-center text-sm text-slate-400">
        กำลังเปิด Medical RAG AI...
      </div>
    );
  }

  if (isLogin) {
    return <div className="h-dvh">{children}</div>;
  }

  return (
    <div className="flex h-dvh overflow-hidden">
      <AppTabs />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}
