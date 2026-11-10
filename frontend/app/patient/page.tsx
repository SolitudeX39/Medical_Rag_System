"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getSession } from "../authStore";
import { fetchPatient, type PatientProfile } from "../clinic";

export default function PatientHomePage() {
  const [profile, setProfile] = useState<PatientProfile | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const session = getSession();
    if (!session?.username) return;
    fetchPatient(session.username)
      .then(setProfile)
      .catch((err) => setError(err instanceof Error ? err.message : "โหลดประวัติไม่สำเร็จ"));
  }, []);

  if (error) {
    return <p className="p-6 text-sm text-rose-300">{error}</p>;
  }

  if (!profile) {
    return <p className="p-6 text-sm text-slate-400">กำลังโหลดประวัติของคุณ...</p>;
  }

  return (
    <div className="h-full overflow-y-auto px-4 py-6 md:px-8">
      <header className="mb-6">
        <p className="text-[10px] tracking-[0.24em] text-cyan-300">PATIENT PORTAL</p>
        <h1 className="mt-1 text-2xl font-semibold text-white">{profile.name}</h1>
        <p className="mt-1 text-sm text-slate-400">
          {profile.hn} · {profile.age} ปี · {profile.sex} · กรุ๊ปเลือด {profile.blood_type}
        </p>
        <p className="mt-1 text-sm text-slate-400">
          แพทย์เจ้าของไข้ {profile.doctor} · แผนก{profile.department}
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          {profile.conditions.map((item) => (
            <span key={item} className="rounded-full border border-cyan-300/30 bg-cyan-300/10 px-3 py-1 text-xs text-cyan-100">
              {item}
            </span>
          ))}
          {profile.allergies.map((item) => (
            <span key={item} className="rounded-full border border-rose-300/30 bg-rose-400/10 px-3 py-1 text-xs text-rose-100">
              แพ้ {item}
            </span>
          ))}
        </div>
        <Link
          href="/patient/chat"
          className="mt-4 inline-flex rounded-full bg-cyan-400 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-cyan-300"
        >
          ปรึกษา chatbot เรื่องโรคของฉัน
        </Link>
      </header>

      <div className="grid gap-4 xl:grid-cols-3">
        <section className="glass-panel rounded-3xl p-5 xl:col-span-1">
          <h2 className="text-sm font-semibold tracking-[0.16em] text-cyan-300">ประวัติการรักษา</h2>
          <div className="mt-4 space-y-4">
            {profile.history.map((item) => (
              <article key={`${item.date}-${item.title}`} className="border-b border-white/10 pb-4 last:border-0 last:pb-0">
                <p className="text-xs text-slate-500">
                  {item.date} · {item.department}
                </p>
                <p className="mt-1 font-medium text-white">{item.title}</p>
                <p className="mt-1 text-sm leading-relaxed text-slate-300">{item.detail}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="glass-panel rounded-3xl p-5 xl:col-span-1">
          <h2 className="text-sm font-semibold tracking-[0.16em] text-cyan-300">ผลการตรวจ</h2>
          <div className="mt-4 space-y-4">
            {profile.results.map((item) => (
              <article key={`${item.date}-${item.name}`} className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
                <div className="flex items-start justify-between gap-3">
                  <p className="font-medium text-white">{item.name}</p>
                  <p className="text-sm text-cyan-200">{item.value}</p>
                </div>
                <p className="mt-1 text-xs text-slate-500">
                  {item.date} · เกณฑ์ {item.range}
                </p>
                <p className="mt-2 text-sm leading-relaxed text-slate-300">{item.note}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="glass-panel rounded-3xl p-5 xl:col-span-1">
          <h2 className="text-sm font-semibold tracking-[0.16em] text-cyan-300">คำแนะนำ</h2>
          <ul className="mt-4 space-y-3 text-sm leading-relaxed text-slate-200">
            {profile.recommendations.map((item) => (
              <li key={item} className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
                {item}
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
