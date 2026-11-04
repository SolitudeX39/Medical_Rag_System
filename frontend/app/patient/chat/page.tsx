"use client";

import { useEffect, useState } from "react";
import ChatPanel from "../../ChatPanel";
import { getAuthUser } from "../../authStore";

const PROMPTS = [
  "ผลตรวจล่าสุดของฉันหมายความว่าอะไร?",
  "ควรกินยาและดูแลตัวเองอย่างไร?",
  "อาการแบบไหนควรมาโรงพยาบาล?",
  "อาหารที่ควรเลี่ยงจากโรคที่เป็นอยู่",
];

export default function PatientChatPage() {
  const [username, setUsername] = useState("");
  useEffect(() => {
    setUsername(getAuthUser());
  }, []);
  if (!username) {
    return <p className="p-6 text-sm text-slate-400">กำลังเปิดแชทของคุณ...</p>;
  }
  return (
    <ChatPanel
      namespace={`patient-chat-${username || "guest"}`}
      eyebrow="MY HEALTH GUIDE"
      title="ปรึกษาเรื่องโรคของฉัน"
      subtitle="อธิบายประวัติ ผลตรวจ และคำแนะนำจากแพทย์ที่ดูแลคุณ"
      emptyTitle="ถามเรื่องสุขภาพของตัวเองได้เลย"
      emptyBody="ระบบจะใช้ประวัติและผลตรวจของคุณ ไม่ได้วินิจฉัยโรคใหม่ให้"
      prompts={PROMPTS}
      placeholder="เช่น HbA1c สูงควรปรับอะไรบ้าง..."
      endpoint="/patient/chat"
      extraBody={{ username }}
      busyLabel="กำลังดูประวัติและร่างคำแนะนำ..."
    />
  );
}
