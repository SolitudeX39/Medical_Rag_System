import os

from neo4j import GraphDatabase

from components.env import load_project_env

load_project_env()

_driver = None


def _enabled() -> bool:
    return os.getenv("NEO4J_ENABLED", "true").lower() not in {"0", "false", "no"}


def get_driver():
    global _driver
    if not _enabled():
        return None
    if _driver is None:
        uri = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "newpassword")
        _driver = GraphDatabase.driver(uri, auth=(user, password), connection_timeout=3)
    return _driver


def close_driver() -> None:
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None


def replace_graph(nodes: list[dict], relationships: list[dict], document_name: str) -> dict:
    driver = get_driver()
    if driver is None:
        return {"nodes": 0, "relationships": 0, "skipped": True}

    try:
        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            session.run(
                """
                MERGE (d:Document {name: $name})
                SET d.kind = 'document'
                """,
                name=document_name,
            )
            for node in nodes:
                session.run(
                    """
                    MERGE (t:Term {name: $name})
                    SET t.thai = $thai, t.kind = $kind, t.definition = $definition
                    WITH t
                    MATCH (d:Document {name: $document})
                    MERGE (t)-[:APPEARS_IN]->(d)
                    """,
                    name=node["name"],
                    thai=node.get("thai", ""),
                    kind=node.get("kind", "term"),
                    definition=node.get("definition", ""),
                    document=document_name,
                )
            for rel in relationships:
                session.run(
                    """
                    MATCH (a:Term {name: $from_name})
                    MATCH (b:Term {name: $to_name})
                    MERGE (a)-[r:RELATED {type: $rel_type}]->(b)
                    SET r.label = $label, r.detail = $detail
                    """,
                    from_name=rel["from"],
                    to_name=rel["to"],
                    rel_type=rel["type"],
                    label=rel.get("label", rel["type"]),
                    detail=rel.get("detail", "") or "",
                )
        return {"nodes": len(nodes), "relationships": len(relationships), "skipped": False}
    except Exception:
        close_driver()
        return {"nodes": 0, "relationships": 0, "skipped": True}


def merge_graph(nodes: list[dict], relationships: list[dict], document_name: str = "chat-graph") -> dict:
    driver = get_driver()
    if driver is None:
        return {"nodes": 0, "relationships": 0, "skipped": True}

    try:
        with driver.session() as session:
            session.run(
                """
                MERGE (d:Document {name: $name})
                SET d.kind = 'document'
                """,
                name=document_name,
            )
            for node in nodes:
                name = (node.get("name") or "").strip()
                if not name:
                    continue
                session.run(
                    """
                    MERGE (t:Term {name: $name})
                    SET t.thai = coalesce(nullif($thai, ''), t.thai),
                        t.kind = coalesce(nullif($kind, ''), t.kind, 'term'),
                        t.definition = coalesce(nullif($definition, ''), t.definition)
                    WITH t
                    MATCH (d:Document {name: $document})
                    MERGE (t)-[:APPEARS_IN]->(d)
                    """,
                    name=name,
                    thai=node.get("thai", "") or "",
                    kind=node.get("kind", "term") or "term",
                    definition=node.get("definition", "") or "",
                    document=document_name,
                )
            written_rels = 0
            for rel in relationships:
                from_name = (rel.get("from") or "").strip()
                to_name = (rel.get("to") or "").strip()
                if not from_name or not to_name:
                    continue
                rel_type = (rel.get("type") or "RELATED_TO").strip() or "RELATED_TO"
                session.run(
                    """
                    MERGE (a:Term {name: $from_name})
                    MERGE (b:Term {name: $to_name})
                    MERGE (a)-[r:RELATED {type: $rel_type}]->(b)
                    SET r.label = $label, r.detail = coalesce(nullif($detail, ''), r.detail)
                    """,
                    from_name=from_name,
                    to_name=to_name,
                    rel_type=rel_type,
                    label=rel.get("label") or rel_type,
                    detail=rel.get("detail") or "",
                )
                written_rels += 1
        return {
            "nodes": sum(1 for node in nodes if (node.get("name") or "").strip()),
            "relationships": written_rels,
            "skipped": False,
        }
    except Exception:
        close_driver()
        return {"nodes": 0, "relationships": 0, "skipped": True}


def related_terms(query: str, limit: int = 20) -> list[dict]:
    driver = get_driver()
    if driver is None or not query.strip():
        return []

    cypher = """
    MATCH (t:Term)
    WHERE toLower(t.name) CONTAINS toLower($q)
       OR toLower(coalesce(t.thai, '')) CONTAINS toLower($q)
    OPTIONAL MATCH (t)-[r:RELATED]-(n:Term)
    RETURN t.name AS name,
           t.thai AS thai,
           t.kind AS kind,
           t.definition AS definition,
           type(r) AS raw_type,
           r.type AS rel_type,
           r.label AS rel_label,
           r.detail AS rel_detail,
           startNode(r).name AS start_name,
           n.name AS other,
           n.thai AS other_thai,
           n.definition AS other_definition
    LIMIT $limit
    """
    try:
        with driver.session() as session:
            rows = session.run(cypher, q=query.strip(), limit=limit)
            facts = []
            for row in rows:
                item = {
                    "name": row["name"],
                    "thai": row["thai"],
                    "kind": row["kind"],
                    "definition": row["definition"],
                }
                if row["other"]:
                    rel = row["rel_label"] or row["rel_type"] or row["raw_type"]
                    if row["start_name"] == row["name"]:
                        item["relation"] = f"{row['name']} -[{rel}]-> {row['other']}"
                    else:
                        item["relation"] = f"{row['other']} -[{rel}]-> {row['name']}"
                    item["related_name"] = row["other"]
                    item["related_thai"] = row["other_thai"]
                    item["related_definition"] = row["other_definition"]
                    item["relation_detail"] = row["rel_detail"]
                facts.append(item)
            return facts
    except Exception:
        close_driver()
        return []


def graph_overview(limit: int = 80) -> dict:
    driver = get_driver()
    if driver is None:
        return {"nodes": [], "links": [], "skipped": True}

    try:
        with driver.session() as session:
            nodes = [
                {
                    "name": row["name"],
                    "thai": row["thai"],
                    "kind": row["kind"],
                    "definition": row["definition"],
                }
                for row in session.run(
                    """
                    MATCH (t:Term)
                    RETURN t.name AS name, t.thai AS thai, t.kind AS kind, t.definition AS definition
                    ORDER BY t.name
                    LIMIT $limit
                    """,
                    limit=limit,
                )
            ]
            links = [
                {
                    "from": row["from_name"],
                    "to": row["to_name"],
                    "type": row["rel_type"],
                    "label": row["label"],
                    "detail": row["detail"],
                }
                for row in session.run(
                    """
                    MATCH (a:Term)-[r:RELATED]->(b:Term)
                    RETURN a.name AS from_name, b.name AS to_name, r.type AS rel_type, r.label AS label, r.detail AS detail
                    LIMIT $limit
                    """,
                    limit=limit,
                )
            ]
        return {"nodes": nodes, "links": links, "skipped": False}
    except Exception:
        close_driver()
        return {"nodes": [], "links": [], "skipped": True}


def format_graph_context(facts: list[dict]) -> str:
    if not facts:
        return ""
    lines = []
    seen = set()
    for fact in facts:
        title = f"{fact['name']}"
        if fact.get("thai"):
            title += f" ({fact['thai']})"
        if fact.get("definition"):
            title += f": {fact['definition']}"
        if title not in seen:
            lines.append(f"- {title}")
            seen.add(title)
        if fact.get("relation") and fact["relation"] not in seen:
            lines.append(f"- ความสัมพันธ์: {fact['relation']}")
            seen.add(fact["relation"])
            if fact.get("relation_detail"):
                lines.append(f"  คำอธิบายเส้น: {fact['relation_detail']}")
            if fact.get("related_definition"):
                related = fact.get("related_name") or ""
                thai = f" ({fact['related_thai']})" if fact.get("related_thai") else ""
                lines.append(f"  โหนดที่เชื่อม {related}{thai}: {fact['related_definition']}")
    return "\n".join(lines)
