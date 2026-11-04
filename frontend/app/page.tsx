"use client";

import ChatPanel from "./ChatPanel";
import type { StoredMessage } from "./chatStore";
import type { TriageResult } from "./clinic";

const PROMPTS = [
  "มีไข้ ไอ เจ็บคอ มา 3 วัน",
  "เจ็บหน้าอกซ้าย แน่น อึดอัด",
  "ลูกอายุ 2 ขวบ ตัวร้อน อาเจียน",
  "ตั้งครรภ์ 28 สัปดาห์ มีเลือดออก",
  "ล้มแล้วข้อเท้าบวมเดินไม่ได้",
];

const URGENCY_STYLE: Record<string, string> = {
  emergency: "border-rose-400/40 bg-rose-500/15 text-rose-100",
  urgent: "border-amber-300/40 bg-amber-400/15 text-amber-100",
  routine: "border-cyan-300/40 bg-cyan-300/10 text-cyan-100",
};

function TriageCard({ message }: { message: StoredMessage }) {
  const triage = message.triage as TriageResult | undefined;
  if (!triage?.ready || !triage.department) return null;
  const tone = URGENCY_STYLE[triage.urgency || "routine"] || URGENCY_STYLE.routine;
  return (
    <div className={`mt-3 rounded-2xl border px-4 py-3 ${tone}`}>
      <p className="text-[10px] tracking-[0.18em]">ส่งต่อไปแผนก</p>
      <p className="mt-1 text-lg font-semibold">{triage.department}</p>
      <p className="mt-1 text-sm">ความเร่งด่วน: {triage.urgency_label || triage.urgency}</p>
      {triage.summary && <p className="mt-2 text-sm opacity-90">{triage.summary}</p>}
      {triage.reasons && triage.reasons.length > 0 && (
        <ul className="mt-2 list-disc space-y-1 pl-4 text-sm opacity-90">
          {triage.reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function Home() {
  return (
    <ChatPanel
      namespace="triage-chat"
      eyebrow="STAFF TRIAGE"
      title="คัดกรองผู้ป่วย"
      subtitle="ถามอาการแล้วระบบจะแนะนำแผนกที่ควรไป"
      emptyTitle="เริ่มคัดกรองจากอาการ"
      emptyBody="ถามอายุ เพศ อาการหลัก ระยะเวลา และความรุนแรง ระบบจะส่งต่อไปแผนกที่เหมาะสม"
      prompts={PROMPTS}
      placeholder="เล่าอาการของผู้ป่วย เช่น ไข้ ไอ เจ็บหน้าอก..."
      endpoint="/triage"
      busyLabel="กำลังประเมินอาการและเลือกแผนก..."
      renderExtra={(message) => <TriageCard message={message} />}
    />
  );
}
