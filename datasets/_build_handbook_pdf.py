from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "medical_terms_handbook.pdf"

FONT_CANDIDATES = [
    Path(r"C:\Windows\Fonts\tahoma.ttf"),
    Path(r"C:\Windows\Fonts\tahomabd.ttf"),
    Path(r"C:\Windows\Fonts\leelawad.ttf"),
    Path(r"C:\Windows\Fonts\LeelawUI.ttf"),
    Path(r"C:\Windows\Fonts\angular.ttf"),
    Path(r"C:\Windows\Fonts\cordia.ttf"),
]


def register_font() -> str:
    regular = next((path for path in FONT_CANDIDATES if path.exists()), None)
    if regular is None:
        raise FileNotFoundError("ไม่พบฟอนต์ภาษาไทยบนเครื่อง")
    pdfmetrics.registerFont(TTFont("Thai", str(regular)))
    bold = Path(r"C:\Windows\Fonts\tahomabd.ttf")
    pdfmetrics.registerFont(TTFont("Thai-Bold", str(bold if bold.exists() else regular)))
    return "Thai"


PAGES = [
    (
        "คู่มือศัพท์ปฏิบัติการทางการแพทย์",
        """เอกสารนี้เป็นชุดข้อมูล PDF สำหรับ Medical RAG AI ใช้คู่กับไฟล์ CSV ชื่อ medical_terms_glossary.csv
PDF อธิบายบริบทและการใช้คำในวอร์ด ส่วน CSV เก็บศัพท์เป็นตาราง term, thai, kind, definition

บทที่ 1 แนวคิดที่ใช้แยกอาการและโรค
Symptom คือสิ่งที่ผู้ป่วยบอกเอง เช่น ปวด หิวน้ำ หายใจลำบาก
Sign คือสิ่งที่ผู้ตรวจวัดหรือเห็นได้ เช่น ไข้ ความดันโลหิต เขียวคล้ำ
Diagnosis คือการสรุปโรคจากประวัติ ตรวจร่างกาย และผลแล็บ
Differential diagnosis คือรายชื่อโรคที่ต้องแยกก่อนสรุป
ตัวอย่าง: ผู้ป่วยบอกว่าเหนื่อย (symptom) ผู้ตรวจพบ cyanosis และ SpO2 ต่ำ (sign) จึงคิดถึง hypoxia และโรคปอดหรือหัวใจ
เอกสารนี้ไม่ใช่แนวทางรักษา ให้ใช้เพื่อทบทวนศัพท์เท่านั้น""",
    ),
    (
        "บทที่ 2 ศัพท์ห้องปฏิบัติการที่พบบ่อย",
        """CBC คือการตรวจความสมบูรณ์ของเม็ดเลือด
- Anemia หมายถึงฮีโมโกลบินต่ำ ผู้ป่วยซีด เหนื่อยง่าย
- Leukocytosis เม็ดเลือดขาวสูง มักสัมพันธ์กับ infection
- Thrombocytopenia เกล็ดเลือดต่ำ เสี่ยงเลือดออก
น้ำตาลในเลือด:
- Hyperglycemia พบบ่อยใน diabetes mellitus
- Hypoglycemia อันตราย เพราะอาจสับสนหรือหมดสติ
เมื่อสงสัยการติดเชื้อรุนแรง ต้องคิดถึง sepsis คือการตอบสนองต่อการติดเชื้อจนอวัยวะล้มเหลว
คำที่ใช้คู่กัน: infection คือการติดเชื้อ inflammation คือการอักเสบ ซึ่งอาจมีหรือไม่มีเชื้อ""",
    ),
    (
        "บทที่ 3 หัวใจ หลอดเลือด และสมอง",
        """Hypertension คือความดันโลหิตสูงเรื้อรัง เพิ่มความเสี่ยง stroke และโรคไต
Hypotension คือความดันต่ำ อาจจาก dehydration หรือช็อก
Ischemia คือเนื้อเยื่อขาดเลือด หากเกิดที่หัวใจจนเซลล์ตายเรียก myocardial infarction
Heart failure คือหัวใจสูบฉีดไม่พอ มักมี dyspnea และ edema ที่ขา
Arrhythmia ครอบคลุมทั้ง tachycardia (เร็ว) และ bradycardia (ช้า)
Stroke คือสมองขาดเลือดหรือเลือดออกเฉียบพลัน สังเกตพูดไม่ชัด ปากเบี้ยว อ่อนแรงซีกหนึ่ง
Syncope คือเป็นลมจากเลือดไปเลี้ยงสมองลดลง ต้องแยกจาก seizure
ถ้ามี chest pain ร่วมเหงื่อออกเย็น ให้คิดถึง myocardial infarction จนกว่าจะพิสูจน์ว่าไม่ใช่""",
    ),
    (
        "บทที่ 4 ระบบหายใจและทางเดินอาหาร",
        """Dyspnea คือหายใจลำบาก พบใน pneumonia, asthma, COPD และ heart failure
Cyanosis คือเขียวคล้ำ เป็น sign ของ hypoxia
Pneumonia คือปอดอักเสบจากเชื้อ มีไข้ ไอ ออกซิเจนต่ำ
Asthma เป็นพักๆ จากหลอดลมตีบ COPD มักเรื้อรังในผู้สูบบุหรี่
ทางเดินอาหาร:
- Hematemesis คืออาเจียนเป็นเลือด
- Melena คืออุจจาระดำจากเลือดส่วนบน
- Jaundice คือตาเหลืองจากบิลิรูบินสูง พบบ่อยใน hepatitis และ cirrhosis
Appendicitis คือไส้ติ่งอักเสบ รักษาด้วย appendectomy
Endoscopy ใช้ส่องทางเดินอาหารส่วนบน โดยเฉพาะเมื่อมี hematemesis ผู้ป่วยมักต้อง NPO ก่อนทำ""",
    ),
    (
        "บทที่ 5 คำสั่งในวอร์ดและคำย่อ",
        """NPO งดน้ำงดอาหาร ใช้ก่อนส่องกล้องหรือผ่าตัด
PRN ให้เมื่อมีอาการ เช่นยาแก้ปวดเมื่อมี pain
BID วันละ 2 ครั้ง TID วันละ 3 ครั้ง
IV เข้าหลอดเลือดดำ IM เข้ากล้ามเนื้อ
BMI ดัชนีมวลกาย สัมพันธ์กับความเสี่ยง diabetes mellitus
Polyuria คือปัสสาวะมาก Polydipsia คือกระหายน้ำมาก มักพบด้วยกันในเบาหวานที่ไม่ควบคุม
Pain ต้องถามตำแหน่ง ลักษณะ ระยะเวลา สิ่งกระตุ้น และสิ่งที่บรรเทา
Fever เป็น sign ร่วมของการติดเชื้อได้บ่อย แต่ไม่มีไข้ก็ยังเป็น sepsis ได้
วิธีใช้เอกสารคู่กัน: อ่านคำอธิบายยาวใน PDF นี้ แล้วเปิดตาราง CSV เพื่อดู kind และความสัมพันธ์ระหว่างศัพท์""",
    ),
]


def build() -> None:
    register_font()
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "ThaiTitle",
        parent=styles["Title"],
        fontName="Thai-Bold",
        fontSize=16,
        leading=22,
        spaceAfter=10,
    )
    body = ParagraphStyle(
        "ThaiBody",
        parent=styles["Normal"],
        fontName="Thai",
        fontSize=11,
        leading=17,
    )
    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="คู่มือศัพท์ปฏิบัติการทางการแพทย์",
        author="Medical RAG AI",
    )
    story = []
    for heading, text in PAGES:
        story.append(Paragraph(heading, title))
        for block in text.strip().split("\n"):
            story.append(Paragraph(block.replace("\n", "<br/>"), body))
            story.append(Spacer(1, 4))
        story.append(Spacer(1, 10))
    doc.build(story)
    print(OUT)


if __name__ == "__main__":
    build()
