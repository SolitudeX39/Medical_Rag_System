import { API, readError } from "./lib";

export type Department = {
  id: string;
  name: string;
  hint: string;
};

export type VisitRecord = {
  date: string;
  department: string;
  title: string;
  detail: string;
};

export type ExamResult = {
  date: string;
  name: string;
  value: string;
  range: string;
  note: string;
};

export type PatientProfile = {
  username: string;
  name: string;
  hn: string;
  age: number;
  sex: string;
  blood_type: string;
  allergies: string[];
  conditions: string[];
  department: string;
  doctor: string;
  history: VisitRecord[];
  results: ExamResult[];
  recommendations: string[];
};

export type TriageResult = {
  answer: string;
  ready: boolean;
  department?: string | null;
  urgency?: "emergency" | "urgent" | "routine" | null;
  urgency_label?: string;
  reasons?: string[];
  questions?: string[];
  summary?: string;
};

export async function loginRemote(username: string, password: string) {
  const res = await fetch(`${API}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<{ username: string; role: "staff" | "patient"; name: string }>;
}

export async function fetchPatient(username: string) {
  const res = await fetch(`${API}/patients/${encodeURIComponent(username)}`);
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<PatientProfile>;
}
