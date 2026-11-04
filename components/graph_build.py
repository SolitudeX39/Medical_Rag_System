import json
import os
import re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from components.chat_prompt import GRAPH_BUILD_ANSWER_PROMPT
from components.database import context_from_rows, search_parent_chunks
from components.env import load_project_env
from components.graph import format_graph_context, graph_overview, merge_graph, related_terms

load_project_env()

GRAPH_EXTRACT_PROMPT = """คุณอ่านเอกสารทางการแพทย์ให้เข้าใจก่อน แล้วจึงสกัดกราฟความรู้สำหรับ Neo4j
ตอบเป็น JSON อย่างเดียว ไม่มีคำอธิบาย ไม่มี markdown

รูปแบบ:
{"nodes":[{"name":"Hypertension","thai":"ความดันโลหิตสูง","kind":"disease","definition":"อธิบาย 2-4 ประโยคจากเอกสาร"}],"relationships":[{"from":"Hypertension","to":"Stroke","type":"INCREASES_RISK","label":"เพิ่มความเสี่ยง","detail":"อธิบายจากเอกสารว่าทำไมจึงเชื่อมกัน"}]}

กฎ:
- อ่าน context ทั้งก้อนให้เข้าใจความหมายก่อนค่อยเลือกโหนด
- ใช้เฉพาะข้อมูลจากข้อความผู้ใช้และ context เอกสาร
- อย่าแต่งโหนดที่ไม่มีในข้อมูล และอย่าสกัดจากคำหลักโดยไม่เข้าใจบริบท
- definition ของแต่ละโหนดต้องละเอียด 2-4 ประโยค บอกความหมายและบริบทการใช้ตามเอกสาร
- relationships.detail ต้องละเอียด 3-5 ประโยค: ความหมายของทั้งสองโหนด ทำไมจึงเชื่อมกัน กลไกหรือบริบทจากเอกสาร และผลที่ตามมาถ้ามีในข้อความ
- kind ใช้หนึ่งใน: disease, concept, symptom, sign, prefix, suffix, procedure, abbreviation, term
- type ใช้ตัวพิมพ์ใหญ่คั่นด้วยขีดล่าง
- ไม่เกิน 20 โหนด และ 25 ความสัมพันธ์
- name ใช้คำต้นฉบับที่สั้น ชัด
"""


def _parse_graph_payload(text: str) -> dict:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if match:
        raw = match.group(0)
    data = json.loads(raw)
    nodes = []
    for item in data.get("nodes") or []:
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        nodes.append(
            {
                "name": name,
                "thai": str(item.get("thai") or "").strip(),
                "kind": str(item.get("kind") or "term").strip() or "term",
                "definition": str(item.get("definition") or "").strip(),
            }
        )
    relationships = []
    for item in data.get("relationships") or []:
        from_name = str(item.get("from") or "").strip()
        to_name = str(item.get("to") or "").strip()
        if not from_name or not to_name:
            continue
        rel_type = str(item.get("type") or "RELATED_TO").strip() or "RELATED_TO"
        relationships.append(
            {
                "from": from_name,
                "to": to_name,
                "type": rel_type,
                "label": str(item.get("label") or rel_type).strip() or rel_type,
                "detail": str(item.get("detail") or "").strip(),
            }
        )
    return {"nodes": nodes[:20], "relationships": relationships[:25]}


def _llm(temperature: float):
    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        api_key=os.getenv("OPENAI_API_KEY"),
        temperature=temperature,
    )


def _history_messages(history: list | None) -> list:
    messages = []
    if not history:
        return messages
    for item in history[-8:]:
        role = item.get("role")
        content = item.get("content", "")
        if not content:
            continue
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
    return messages


def _graph_brief(extracted: dict) -> str:
    node_lines = []
    for node in extracted["nodes"]:
        title = node["name"]
        if node.get("thai"):
            title += f" ({node['thai']})"
        node_lines.append(f"- {title}: {node.get('definition') or 'ศัพท์ในกราฟ'}")
    rel_lines = []
    for rel in extracted["relationships"]:
        label = rel.get("label") or rel["type"]
        line = f"- {rel['from']} — {label} → {rel['to']}"
        if rel.get("detail"):
            line += f"\n  {rel['detail']}"
        rel_lines.append(line)
    return (
        f"โหนด:\n{chr(10).join(node_lines) or '- ไม่มี'}\n\n"
        f"ความสัมพันธ์:\n{chr(10).join(rel_lines) or '- ไม่มีเส้นเชื่อมใหม่'}"
    )


def _fallback_answer(source_name: str, extracted: dict, written: dict) -> str:
    return (
        f"บันทึกกราฟจาก {source_name} แล้ว {written.get('nodes', 0)} โหนด "
        f"และ {written.get('relationships', 0)} ความสัมพันธ์\n\n"
        f"{_graph_brief(extracted)}"
    )


def _write_graph_answer(
    query: str,
    context_text: str,
    graph_text: str,
    extracted: dict,
    written: dict,
    source_name: str,
    history: list | None,
) -> str:
    saved = (
        f"บันทึกกราฟจาก {source_name} แล้ว {written.get('nodes', 0)} โหนด "
        f"และ {written.get('relationships', 0)} ความสัมพันธ์"
    )
    user_content = f"""คำสั่งผู้ใช้:
{query}

เอกสารที่อ่าน แยกตามไฟล์:
{context_text or "ไม่มีเอกสารที่เกี่ยวข้อง ใช้เฉพาะคำสั่งผู้ใช้"}

กราฟศัพท์ที่มีอยู่ก่อนแล้ว:
{graph_text or "ยังไม่มีโหนดที่เกี่ยวข้อง"}

กราฟที่เพิ่งสกัดจากข้อความ:
{_graph_brief(extracted)}

สถานะการบันทึก:
{saved}

อ่านเอกสารให้เข้าใจก่อน แล้วอธิบายกราฟนี้ให้ผู้ใช้แบบเพื่อนร่วมงานที่อ่านมาแล้ว"""
    try:
        messages = [SystemMessage(content=GRAPH_BUILD_ANSWER_PROMPT)]
        messages.extend(_history_messages(history))
        messages.append(HumanMessage(content=user_content))
        response = _llm(0.3).invoke(messages)
        answer = (response.content or "").strip()
        if answer:
            return answer
    except Exception:
        pass
    return _fallback_answer(source_name, extracted, written)


def _facts_from_extracted(extracted: dict) -> list[dict]:
    nodes = {
        node["name"]: node
        for node in extracted["nodes"]
        if node.get("name")
    }
    facts = [
        {
            "name": node["name"],
            "thai": node.get("thai", ""),
            "kind": node.get("kind", ""),
            "definition": node.get("definition", ""),
        }
        for node in extracted["nodes"]
    ]
    for rel in extracted["relationships"]:
        source = nodes.get(rel["from"], {})
        target = nodes.get(rel["to"], {})
        facts.append(
            {
                "name": rel["from"],
                "thai": source.get("thai", ""),
                "kind": source.get("kind", ""),
                "definition": source.get("definition", ""),
                "relation": f"{rel['from']} -[{rel.get('label') or rel['type']}]-> {rel['to']}",
                "related_name": rel["to"],
                "related_thai": target.get("thai", ""),
                "related_definition": target.get("definition", ""),
                "relation_detail": rel.get("detail", ""),
            }
        )
    return facts


def build_graph_from_prompt(query: str, history: list | None = None) -> dict:
    rows = search_parent_chunks(query, limit=12)
    context_text = context_from_rows(rows)
    graph_text = format_graph_context(related_terms(query))
    source_name = next((row[3] for row in rows if row[3]), None) or "chat-graph"
    sources = [
        {
            "page": row[2],
            "text": row[1],
            "filename": row[3],
            "document_id": row[4],
        }
        for row in rows
    ]

    user_content = f"""คำสั่งผู้ใช้:
{query}

เอกสารที่ต้องอ่านให้เข้าใจก่อนสกัดกราฟ แยกตามไฟล์:
{context_text or "ไม่มีเอกสารที่เกี่ยวข้อง ใช้เฉพาะคำสั่งผู้ใช้"}

กราฟศัพท์ที่มีอยู่แล้ว ใช้ประกอบได้ถ้าเอกสารกล่าวถึง:
{graph_text or "ยังไม่มีโหนดที่เกี่ยวข้อง"}"""
    extract_messages = [SystemMessage(content=GRAPH_EXTRACT_PROMPT)]
    extract_messages.extend(_history_messages(history))
    extract_messages.append(HumanMessage(content=user_content))
    response = _llm(0).invoke(extract_messages)
    try:
        extracted = _parse_graph_payload(response.content)
    except Exception:
        return {
            "answer": "อ่านเอกสารแล้ว แต่สกัดกราฟจากข้อความไม่สำเร็จ ลองระบุศัพท์และความสัมพันธ์ให้ชัดขึ้น",
            "sources": sources,
            "graph": [],
            "overview": graph_overview(),
            "written": {"nodes": 0, "relationships": 0, "skipped": True},
        }

    if not extracted["nodes"]:
        return {
            "answer": "อ่านเอกสารที่เกี่ยวข้องแล้ว แต่ยังไม่พบศัพท์ที่ชัดพอจะสร้างกราฟ ลองระบุชื่อโหนดและความสัมพันธ์ เช่น Hypertension เพิ่มความเสี่ยง Stroke",
            "sources": sources,
            "graph": [],
            "overview": graph_overview(),
            "written": {"nodes": 0, "relationships": 0, "skipped": True},
        }

    written = merge_graph(extracted["nodes"], extracted["relationships"], source_name)
    facts = _facts_from_extracted(extracted)
    if written.get("skipped"):
        return {
            "answer": (
                _write_graph_answer(
                    query, context_text, graph_text, extracted, written, source_name, history
                )
                + "\n\nยังบันทึกลง Neo4j ไม่ได้ เปิด Docker แล้วลองอีกครั้ง"
            ),
            "sources": sources,
            "graph": facts,
            "overview": graph_overview(),
            "written": written,
        }

    return {
        "answer": _write_graph_answer(
            query, context_text, graph_text, extracted, written, source_name, history
        ),
        "sources": sources,
        "graph": facts,
        "overview": graph_overview(),
        "written": written,
    }
