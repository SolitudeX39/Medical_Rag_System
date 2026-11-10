import json
import os
import re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from components.database import query_database
from components.env import load_project_env

load_project_env()

DEPARTMENTS = [
    {"id": "er", "name": "ห้องฉุกเฉิน", "hint": "อาการรุนแรง หายใจลำบาก เจ็บหน้าอก หมดสติ"},
    {"id": "internal", "name": "อายุรกรรม", "hint": "ไข้ ไอ เบาหวาน ความดัน โรคเรื้อรัง"},
    {"id": "cardio", "name": "อายุรกรรมหัวใจ", "hint": "เจ็บอก ใจสั่น เหนื่อยง่าย"},
    {"id": "neuro", "name": "อายุรกรรมประสาท", "hint": "ปวดหัวรุนแรง ชา อ่อนแรง ชัก"},
    {"id": "surgery", "name": "ศัลยกรรม", "hint": "แผล ไส้เลื่อน ปวดท้องเฉียบพลัน"},
    {"id": "ortho", "name": "ออร์โธปิดิกส์", "hint": "กระดูก ข้อ กล้ามเนื้อ ปวดหลัง"},
    {"id": "peds", "name": "กุมารเวชกรรม", "hint": "เด็กอายุต่ำกว่า 15 ปี"},
    {"id": "obgyn", "name": "สูติ-นรีเวชกรรม", "hint": "ตั้งครรภ์ ประจำเดือน เต้านม"},
    {"id": "ent", "name": "หู คอ จมูก", "hint": "เจ็บคอ ไซนัส หูอื้อ วิงเวียน"},
    {"id": "eye", "name": "จักษุ", "hint": "ตาแดง ตามัว เจ็บตา"},
    {"id": "derm", "name": "ผิวหนัง", "hint": "ผื่น คัน สิว แผลเรื้อรังที่ผิว"},
    {"id": "psych", "name": "จิตเวช", "hint": "เครียด นอนไม่หลับ ซึมเศร้า วิตกกังวล"},
    {"id": "dental", "name": "ทันตกรรม", "hint": "ปวดฟัน เหงือก ช่องปาก"},
    {"id": "gp", "name": "เวชศาสตร์ทั่วไป", "hint": "อาการทั่วไป ตรวจสุขภาพ"},
]

TRIAGE_PROMPTS = [
    "มีไข้ ไอ เจ็บคอ มา 3 วัน",
    "เจ็บหน้าอกซ้าย แน่น อึดอัด",
    "ลูกอายุ 2 ขวบ ตัวร้อน อาเจียน",
    "ตั้งครรภ์ 28 สัปดาห์ มีเลือดออก",
    "ล้มแล้วข้อเท้าบวมเดินไม่ได้",
]

PATIENT_PROMPTS = [
    "ผลตรวจล่าสุดของฉันหมายความว่าอะไร?",
    "ควรกินยาและดูแลตัวเองอย่างไร?",
    "อาการแบบไหนควรมาโรงพยาบาล?",
    "อาหารที่ควรเลี่ยงจากโรคที่เป็นอยู่",
]

TRIAGE_SYSTEM_PROMPT = """คุณเป็นพยาบาลคัดกรองที่เคาน์เตอร์โรงพยาบาล
คุยภาษาไทย สุภาพ กระชับ ถามทีละ 1-2 ข้อ ไม่ตัดสินวินิจฉัยโรค

แผนกที่ใช้ได้:
ห้องฉุกเฉิน, อายุรกรรม, อายุรกรรมหัวใจ, อายุรกรรมประสาท, ศัลยกรรม, ออร์โธปิดิกส์, กุมารเวชกรรม, สูติ-นรีเวชกรรม, หู คอ จมูก, จักษุ, ผิวหนัง, จิตเวช, ทันตกรรม, เวชศาสตร์ทั่วไป

urgency ใช้ค่า emergency | urgent | routine เท่านั้น
- emergency: เสี่ยงชีวิต ต้องห้องฉุกเฉินทันที
- urgent: ควรพบแพทย์วันนี้
- routine: นัดแผนกตามอาการได้

ตอบเป็น JSON ล้วน ไม่มี markdown:
{
  "answer": "ข้อความคุยกับผู้ป่วย",
  "ready": false,
  "department": "ชื่อแผนกหรือ null",
  "urgency": "emergency|urgent|routine|null",
  "reasons": ["เหตุผลสั้นๆ"],
  "questions": ["คำถามต่อถ้ายังไม่พร้อมส่งต่อ"],
  "summary": "สรุปอาการเมื่อ ready"
}

กฎ:
- ถ้าข้อมูลยังไม่พอ ให้ ready=false แล้วถามอายุ เพศ ระยะเวลา ความรุนแรง อาการร่วม
- เด็กอายุต่ำกว่า 15 ปี ส่งกุมารเวช ยกเว้นฉุกเฉิน
- ตั้งครรภ์หรืออาการทางนรีเวช ส่งสูติ-นรีเวช ยกเว้นฉุกเฉิน
- เจ็บหน้าอก หายใจไม่ออก หมดสติ ชัก อ่อนแรงครึ่งซีก เลือดออกมาก ให้ห้องฉุกเฉินและ ready=true ได้เลย
- เมื่อ ready=true ต้องมี department, urgency, summary
- ห้ามบอกว่าเป็นโรคใดอย่างฟันธง บอกได้แค่แผนกที่ควรไป
"""

PATIENT_CHAT_PROMPT = """คุณเป็นผู้ช่วยสุขภาพส่วนตัวในพอร์ทัลคนไข้
ใช้ประวัติ ผลตรวจ และคำแนะนำของคนไข้คนนี้เป็นหลัก เสริมด้วยเอกสารคลังถ้ามี

แนวทาง:
- ตอบภาษาไทย อบอุ่น ชัดเจน
- อธิบายผลตรวจและโรคที่เป็นอยู่ด้วยภาษาเข้าใจง่าย
- ยึดคำแนะนำที่แพทย์ให้ไว้แล้ว ห้ามสั่งยาใหม่หรือเปลี่ยนขนาดยาเอง
- ถ้าอาการเข้าข่ายฉุกเฉิน ให้แนะนำไปห้องฉุกเฉินทันที
- ปิดท้ายสั้นๆ ว่าข้อมูลนี้ไม่ใช่การวินิจฉัย ควรปรึกษาแพทย์ที่ดูแล
- อย่าแต่งผลตรวจที่ไม่มีในประวัติ
"""

ACCOUNTS = {
    "admin": {"password": "test1234", "role": "staff", "name": "เจ้าหน้าที่คัดกรอง"},
    "staff": {"password": "test1234", "role": "staff", "name": "พยาบาลคัดกรอง"},
    "somchai": {"password": "test1234", "role": "patient", "name": "สมชาย ใจดี"},
    "malee": {"password": "test1234", "role": "patient", "name": "มาลี สุขใจ"},
    "nicha": {"password": "test1234", "role": "patient", "name": "ณิชา วงศ์ศิลป์"},
}

PATIENTS = {
    "somchai": {
        "username": "somchai",
        "name": "สมชาย ใจดี",
        "hn": "HN-10482",
        "age": 58,
        "sex": "ชาย",
        "blood_type": "O+",
        "allergies": ["ยาซัลฟา"],
        "conditions": ["ความดันโลหิตสูง", "เบาหวานชนิดที่ 2"],
        "department": "อายุรกรรม",
        "doctor": "พญ.วราภรณ์ ตั้งตรง",
        "history": [
            {
                "date": "12 ต.ค. 2026",
                "department": "อายุรกรรม",
                "title": "ติดตามเบาหวานและความดัน",
                "detail": "ยังมีน้ำตาลสูงหลังอาหาร ปรับ Metformin และเน้นลดแป้งขาว",
            },
            {
                "date": "3 ก.ค. 2026",
                "department": "จักษุ",
                "title": "ตรวจจอประสาทตา",
                "detail": "ยังไม่พบ diabetic retinopathy นัดตรวจซ้ำปีละครั้ง",
            },
            {
                "date": "18 ม.ค. 2026",
                "department": "อายุรกรรม",
                "title": "ตรวจสุขภาพประจำปี",
                "detail": "วินิจฉัยเบาหวานชนิดที่ 2 ร่วมกับความดันโลหิตสูง เริ่มยาและปรับพฤติกรรม",
            },
        ],
        "results": [
            {
                "date": "12 ต.ค. 2026",
                "name": "HbA1c",
                "value": "7.8%",
                "range": "เป้า < 7.0%",
                "note": "สูงกว่าเป้า ควบคุมน้ำตาลยังไม่ถึงเกณฑ์",
            },
            {
                "date": "12 ต.ค. 2026",
                "name": "ความดันโลหิต",
                "value": "148/92 mmHg",
                "range": "< 130/80 mmHg",
                "note": "สูง ควรวัดซ้ำที่บ้านและกินยาสม่ำเสมอ",
            },
            {
                "date": "12 ต.ค. 2026",
                "name": "น้ำตาลขณะอดอาหาร",
                "value": "156 mg/dL",
                "range": "70–100 mg/dL",
                "note": "สูง เลี่ยงน้ำหวานและของทอด",
            },
            {
                "date": "12 ต.ค. 2026",
                "name": "LDL คอเลสเตอรอล",
                "value": "132 mg/dL",
                "range": "< 100 mg/dL",
                "note": "สูงเล็กน้อย เพิ่มการเดินและลดของมัน",
            },
        ],
        "recommendations": [
            "กินยา Metformin และยาลดความดันทุกวันหลังอาหาร ห้ามหยุดเอง",
            "เดินเร็วอย่างน้อย 30 นาที 5 วันต่อสัปดาห์",
            "ลดเค็ม ลดแป้งขาว น้ำหวาน และของทอด",
            "วัดความดันที่บ้านช่วงเช้า บันทึกมาให้แพทย์ทุกครั้ง",
            "ถ้ามีเจ็บหน้าอก ปากเบี้ยว หรือพูดไม่ชัด ให้มาห้องฉุกเฉินทันที",
        ],
    },
    "malee": {
        "username": "malee",
        "name": "มาลี สุขใจ",
        "hn": "HN-22109",
        "age": 34,
        "sex": "หญิง",
        "blood_type": "A+",
        "allergies": ["ฝุ่นไรฝุ่น", "ขนแมว"],
        "conditions": ["หอบหืด", "ภูมิแพ้จมูก"],
        "department": "อายุรกรรม",
        "doctor": "นพ.กิตติพงศ์ แสงทอง",
        "history": [
            {
                "date": "28 ก.ย. 2026",
                "department": "อายุรกรรม",
                "title": "หอบหืดกำเริบหลังเป็นหวัด",
                "detail": "ได้ยาพ่น Steroid ประจำและยาพ่นฉุกเฉิน แนะนำเลี่ยงฝุ่นและควัน",
            },
            {
                "date": "2 พ.ค. 2026",
                "department": "หู คอ จมูก",
                "title": "ภูมิแพ้จมูกเรื้อรัง",
                "detail": "คัดจมูก คันตา ได้ยาแก้แพ้ตามอาการ และล้างจมูกน้ำเกลือ",
            },
        ],
        "results": [
            {
                "date": "28 ก.ย. 2026",
                "name": "Peak flow",
                "value": "320 L/min",
                "range": "ค่าปกติของคนไข้ ~ 380 L/min",
                "note": "ต่ำกว่าเบสไลน์ ยังมีทางเดินหายใจตีบ",
            },
            {
                "date": "28 ก.ย. 2026",
                "name": "ออกซิเจนปลายนิ้ว",
                "value": "97%",
                "range": "≥ 95%",
                "note": "อยู่ในเกณฑ์ ยังไม่ต้องให้ออกซิเจน",
            },
            {
                "date": "2 พ.ค. 2026",
                "name": "IgE",
                "value": "สูง",
                "range": "ตามแล็บ",
                "note": "เข้ากับภูมิแพ้ เลี่ยงขนแมวและฝุ่นจัด",
            },
        ],
        "recommendations": [
            "พ่นยาควบคุมทุกเช้า-เย็น แม้ไม่มีอาการ",
            "พกยาพ่นฉุกเฉินไว้เสมอ ถ้าพ่นแล้วไม่ดีขึ้นใน 15 นาที ให้มาห้องฉุกเฉิน",
            "เลี่ยงฝุ่น ควันบุหรี่ และขนแมว ปิดหน้าต่างช่วงที่อากาศแล้ง",
            "ล้างจมูกด้วยน้ำเกลือเมื่อคัดแน่น",
            "ถ้าหายใจหอบ พูดไม่ครบประโยค หรือริมฝีปากคล้ำ ให้มาโรงพยาบาลทันที",
        ],
    },
    "nicha": {
        "username": "nicha",
        "name": "ณิชา วงศ์ศิลป์",
        "hn": "HN-33815",
        "age": 29,
        "sex": "หญิง",
        "blood_type": "B+",
        "allergies": [],
        "conditions": ["ตั้งครรภ์ 28 สัปดาห์"],
        "department": "สูติ-นรีเวชกรรม",
        "doctor": "พญ.ปิยะนุช รุ่งเรือง",
        "history": [
            {
                "date": "20 ต.ค. 2026",
                "department": "สูติ-นรีเวชกรรม",
                "title": "ฝากครรภ์ครั้งที่ 5",
                "detail": "ครรภ์เดี่ยว 28 สัปดาห์ ลูกดิ้นดี ความดันปกติ นัดอัลตราซาวด์การเจริญเติบโต",
            },
            {
                "date": "8 ก.ย. 2026",
                "department": "สูติ-นรีเวชกรรม",
                "title": "ตรวจน้ำตาลขณะตั้งครรภ์",
                "detail": "ผลคัดกรองเบาหวานขณะตั้งครรภ์ปกติ",
            },
        ],
        "results": [
            {
                "date": "20 ต.ค. 2026",
                "name": "น้ำหนัก",
                "value": "64.2 กก.",
                "range": "เพิ่มประมาณ 0.4 กก./สัปดาห์",
                "note": "ขึ้นตามเกณฑ์",
            },
            {
                "date": "20 ต.ค. 2026",
                "name": "ความดันโลหิต",
                "value": "112/68 mmHg",
                "range": "< 140/90 mmHg",
                "note": "ปกติ",
            },
            {
                "date": "20 ต.ค. 2026",
                "name": "ฮีโมโกลบิน",
                "value": "11.2 g/dL",
                "range": "≥ 11.0 g/dL",
                "note": "ต่ำเล็กน้อย เสริมธาตุเหล็กต่อ",
            },
            {
                "date": "8 ก.ย. 2026",
                "name": "OGTT",
                "value": "ปกติ",
                "range": "ตามเกณฑ์ฝากครรภ์",
                "note": "ยังไม่เข้าเกณฑ์เบาหวานขณะตั้งครรภ์",
            },
        ],
        "recommendations": [
            "กินวิตามินคนท้องและธาตุเหล็กทุกวันหลังอาหาร",
            "นอนตะแคงซ้าย นับลูกดิ้นเช้า-เย็น",
            "ถ้ามีเลือดออก น้ำเดิน ปวดท้องเป็นพักๆ หรือลูกดิ้นน้อยลง ให้มาห้องฉุกเฉินทันที",
            "ดื่มน้ำให้พอ เลี่ยงของดิบ และงานยกของหนัก",
            "มาตามนัดฝากครรภ์ทุกครั้ง ห้ามหยุดยาเอง",
        ],
    },
}

KEYWORD_RULES = [
    (["หมดสติ", "ไม่รู้สึกตัว", "ชัก", "หายใจไม่ออก", "เจ็บหน้าอก", "เลือดออกมาก", "ปากเบี้ยว", "พูดไม่ชัด"], "ห้องฉุกเฉิน", "emergency"),
    (["ตั้งครรภ์", "ประจำเดือน", "ตกขาว", "เลือดออกทางช่องคลอด", "ฝากครรภ์"], "สูติ-นรีเวชกรรม", "urgent"),
    (["เด็ก", "ขวบ", "ทารก", "ลูก"], "กุมารเวชกรรม", "urgent"),
    (["ปวดฟัน", "เหงือก", "ฟันคุด"], "ทันตกรรม", "routine"),
    (["ตาแดง", "ตามัว", "เจ็บตา"], "จักษุ", "urgent"),
    (["ผื่น", "คัน", "สิว", "ผิวหนัง"], "ผิวหนัง", "routine"),
    (["กระดูก", "ข้อ", "ข้อเท้า", "ปวดหลัง", "เคล็ด", "หกล้ม"], "ออร์โธปิดิกส์", "urgent"),
    (["เจ็บคอ", "หูอื้อ", "ไซนัส", "น้ำมูก", "เสียงแหบ"], "หู คอ จมูก", "routine"),
    (["เครียด", "ซึมเศร้า", "นอนไม่หลับ", "วิตก"], "จิตเวช", "routine"),
    (["แผล", "ไส้เลื่อน", "ปวดท้องรุนแรง"], "ศัลยกรรม", "urgent"),
    (["ใจสั่น", "เหนื่อยง่าย"], "อายุรกรรมหัวใจ", "urgent"),
    (["ปวดหัวรุนแรง", "ชา", "อ่อนแรง"], "อายุรกรรมประสาท", "urgent"),
    (["ไข้", "ไอ", "เบาหวาน", "ความดัน", "หอบ"], "อายุรกรรม", "routine"),
]


def authenticate(username: str, password: str) -> dict | None:
    account = ACCOUNTS.get((username or "").strip().lower())
    if not account or account["password"] != password:
        return None
    key = (username or "").strip().lower()
    return {"username": key, "role": account["role"], "name": account["name"]}


def get_patient(username: str) -> dict | None:
    return PATIENTS.get((username or "").strip().lower())


def format_patient_context(patient: dict) -> str:
    history = "\n".join(
        f"- {item['date']} · {item['department']} · {item['title']}: {item['detail']}"
        for item in patient.get("history") or []
    )
    results = "\n".join(
        f"- {item['date']} · {item['name']}: {item['value']} (เกณฑ์ {item['range']}) — {item['note']}"
        for item in patient.get("results") or []
    )
    recs = "\n".join(f"- {item}" for item in patient.get("recommendations") or [])
    allergies = ", ".join(patient.get("allergies") or []) or "ไม่มี"
    conditions = ", ".join(patient.get("conditions") or []) or "ไม่มี"
    return f"""โปรไฟล์คนไข้:
ชื่อ {patient['name']} HN {patient['hn']} อายุ {patient['age']} ปี เพศ {patient['sex']} กรุ๊ปเลือด {patient['blood_type']}
โรค/ภาวะ: {conditions}
แพ้: {allergies}
แพทย์เจ้าของไข้: {patient.get('doctor')} แผนก {patient.get('department')}

ประวัติการรักษา:
{history}

ผลตรวจ:
{results}

คำแนะนำที่แพทย์ให้ไว้:
{recs}
"""


def _rule_department(text: str) -> tuple[str, str] | None:
    blob = text.lower()
    for keywords, department, urgency in KEYWORD_RULES:
        if any(word in blob for word in keywords):
            return department, urgency
    return None


def _fallback_triage(message: str, history: list) -> dict:
    turns = [item.get("content", "") for item in history if item.get("role") == "user"]
    turns.append(message)
    blob = " ".join(turns)
    matched = _rule_department(blob)
    user_turns = len(turns)
    emergency = matched and matched[1] == "emergency"
    ready = bool(emergency or (matched and user_turns >= 2))
    department, urgency = matched if matched else ("เวชศาสตร์ทั่วไป", "routine")
    if not ready:
        return {
            "answer": "รับทราบอาการแล้ว ช่วยบอกอายุ เพศ อาการเป็นมานานแค่ไหน และมีอาการอื่นร่วมด้วยไหม เช่น ไข้ เจ็บหน้าอก หายใจลำบาก หรือปวดมาก",
            "ready": False,
            "department": None,
            "urgency": None,
            "reasons": [],
            "questions": ["อายุและเพศ", "ระยะเวลาและความรุนแรง", "อาการร่วมที่น่าห่วง"],
            "summary": "",
        }
    labels = {"emergency": "ฉุกเฉิน", "urgent": "เร่งด่วน", "routine": "ปกติ"}
    return {
        "answer": (
            f"จากอาการที่เล่ามา แนะนำส่งต่อไปแผนก{department} "
            f"ระดับความเร่งด่วน: {labels[urgency]}\n\n"
            "นี่เป็นการคัดกรองเบื้องต้น ไม่ใช่การวินิจฉัย กรุณาติดต่อแผนกตามบัตรคิว"
        ),
        "ready": True,
        "department": department,
        "urgency": urgency,
        "reasons": ["คัดจากอาการที่ผู้ป่วยเล่า"],
        "questions": [],
        "summary": blob[:280],
    }


def _parse_triage_json(raw: str) -> dict | None:
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fenced:
        text = fenced.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    if not isinstance(data, dict) or not data.get("answer"):
        return None
    return data


def _normalize_triage(data: dict) -> dict:
    urgency = data.get("urgency")
    if urgency not in {"emergency", "urgent", "routine"}:
        urgency = None
    department = data.get("department") or None
    ready = bool(data.get("ready") and department)
    labels = {"emergency": "ฉุกเฉิน", "urgent": "เร่งด่วน", "routine": "ปกติ"}
    return {
        "answer": str(data.get("answer") or "").strip(),
        "ready": ready,
        "department": department if ready else None,
        "urgency": urgency if ready else None,
        "urgency_label": labels.get(urgency or "", "") if ready else "",
        "reasons": [str(item) for item in (data.get("reasons") or []) if str(item).strip()][:4],
        "questions": [str(item) for item in (data.get("questions") or []) if str(item).strip()][:4],
        "summary": str(data.get("summary") or "").strip(),
    }


def triage_chat(message: str, history: list | None = None) -> dict:
    history = history or []
    fallback = _fallback_triage(message, history)
    blob = " ".join(
        [item.get("content", "") for item in history if item.get("role") == "user"] + [message]
    )
    matched = _rule_department(blob)
    if matched and matched[1] == "emergency":
        return _normalize_triage(fallback)
    if not os.getenv("OPENAI_API_KEY"):
        return _normalize_triage(fallback)

    transcript = []
    for item in history[-8:]:
        role = "ผู้ป่วย" if item.get("role") == "user" else "พยาบาล"
        transcript.append(f"{role}: {item.get('content', '')}")
    transcript.append(f"ผู้ป่วย: {message}")

    llm = ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        api_key=os.getenv("OPENAI_API_KEY"),
        temperature=0.2,
    )
    try:
        response = llm.invoke(
            [
                SystemMessage(content=TRIAGE_SYSTEM_PROMPT),
                HumanMessage(content="บทสนทนาคัดกรอง:\n" + "\n".join(transcript)),
            ]
        )
        parsed = _parse_triage_json(getattr(response, "content", "") or "")
        if parsed:
            result = _normalize_triage(parsed)
            blob = " ".join(
                [item.get("content", "") for item in history if item.get("role") == "user"] + [message]
            )
            matched = _rule_department(blob)
            if matched and matched[1] == "emergency" and not result["ready"]:
                return _normalize_triage(fallback)
            return result
    except Exception:
        pass
    return _normalize_triage(fallback)


def patient_chat(username: str, message: str, history: list | None = None) -> dict:
    patient = get_patient(username)
    if not patient:
        raise ValueError("ไม่พบบัญชีคนไข้")
    extra = format_patient_context(patient)
    try:
        result = query_database(
            message,
            history=history,
            system_prompt=PATIENT_CHAT_PROMPT,
            extra_context=extra,
        )
        if result.get("answer"):
            return result
    except Exception:
        pass

    recs = "\n".join(f"- {item}" for item in patient.get("recommendations") or [])
    conditions = ", ".join(patient.get("conditions") or [])
    latest = patient.get("results") or []
    latest_text = "\n".join(
        f"- {item['name']}: {item['value']} ({item['note']})" for item in latest[:4]
    )
    return {
        "answer": (
            f"จากประวัติของคุณ มีภาวะ {conditions}\n\n"
            f"ผลตรวจล่าสุด:\n{latest_text}\n\n"
            f"คำแนะนำที่แพทย์ให้ไว้:\n{recs}\n\n"
            "ข้อมูลนี้สรุปจากประวัติในระบบ ไม่ใช่การวินิจฉัย หากอาการแย่ลงควรติดต่อแพทย์ที่ดูแลหรือห้องฉุกเฉิน"
        ),
        "sources": [],
        "graph": [],
    }
