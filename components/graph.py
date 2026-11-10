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
        user = os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "newpassword")
        _driver = GraphDatabase.driver(uri, auth=(user, password), connection_timeout=5)
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
            session.run("MATCH (n:Term) DETACH DELETE n")
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


def related_terms(query: str, limit: int = 25) -> list[dict]:
    driver = get_driver()
    if driver is None or not query.strip():
        return []

    q = query.strip()
    facts = []

    # 1. Search RDF Knowledge Graph (Diseases, Symptoms, Treatments)
    rdf_cypher = """
    MATCH (d:med__Disease)
    WHERE toLower(coalesce(d.rdfs__label, '')) CONTAINS toLower($q)
    OPTIONAL MATCH (d)-[r]->(target)
    RETURN coalesce(d.rdfs__label, d.uri) AS name,
           'disease' AS kind,
           coalesce(d.uri, '') AS definition,
           type(r) AS raw_type,
           coalesce(target.rdfs__label, target.uri) AS other,
           labels(target) AS other_labels
    LIMIT $limit
    """

    rdf_reverse_cypher = """
    MATCH (target)
    WHERE (target:med__Symptom OR target:med__Treatment)
      AND toLower(coalesce(target.rdfs__label, '')) CONTAINS toLower($q)
    OPTIONAL MATCH (d:med__Disease)-[r]->(target)
    RETURN coalesce(target.rdfs__label, target.uri) AS name,
           case when 'med__Symptom' IN labels(target) then 'symptom' else 'treatment' end AS kind,
           coalesce(target.uri, '') AS definition,
           type(r) AS raw_type,
           coalesce(d.rdfs__label, d.uri) AS other,
           ['med__Disease'] AS other_labels
    LIMIT $limit
    """

    term_cypher = """
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
            # Query disease matches
            for row in session.run(rdf_cypher, q=q, limit=limit):
                rel_label = "has_symptom" if "symptom" in (row["raw_type"] or "").lower() else "has_treatment"
                other_kind = "symptom" if "symptom" in (row["raw_type"] or "").lower() else "treatment"
                facts.append({
                    "name": row["name"],
                    "thai": "",
                    "kind": "disease",
                    "definition": row["definition"],
                    "relation": f"{row['name']} -[{rel_label}]-> {row['other']}" if row["other"] else "",
                    "related_name": row["other"],
                    "related_thai": "",
                    "related_kind": other_kind,
                    "related_definition": "",
                    "relation_detail": f"ความสัมพันธ์ทางการแพทย์: {rel_label}",
                })

            # Query symptom/treatment reverse matches
            for row in session.run(rdf_reverse_cypher, q=q, limit=limit):
                rel_label = "has_symptom" if row["kind"] == "symptom" else "has_treatment"
                facts.append({
                    "name": row["name"],
                    "thai": "",
                    "kind": row["kind"],
                    "definition": row["definition"],
                    "relation": f"{row['other']} -[{rel_label}]-> {row['name']}" if row["other"] else "",
                    "related_name": row["other"],
                    "related_thai": "",
                    "related_kind": "disease",
                    "related_definition": "",
                    "relation_detail": f"ความสัมพันธ์ทางการแพทย์: {rel_label}",
                })

            # Query traditional Term nodes
            for row in session.run(term_cypher, q=q, limit=limit):
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
    except Exception as exc:
        print(f"Warning: related_terms query failed: {exc}")
        close_driver()

    return facts


def graph_overview(limit: int = 100) -> dict:
    driver = get_driver()
    if driver is None:
        return {"nodes": [], "links": [], "skipped": True}

    nodes_dict = {}
    links = []

    try:
        with driver.session() as session:
            # 1. Fetch RDF triples (med__Disease -> med__has_symptom / med__has_treatment)
            rdf_query = """
            MATCH (d:med__Disease)-[r]->(target)
            RETURN coalesce(d.rdfs__label, d.uri) AS disease_name,
                   d.uri AS disease_uri,
                   type(r) AS rel_type,
                   coalesce(target.rdfs__label, target.uri) AS target_name,
                   target.uri AS target_uri,
                   labels(target) AS target_labels
            LIMIT $limit
            """
            for row in session.run(rdf_query, limit=limit):
                d_name = row["disease_name"]
                t_name = row["target_name"]
                rel = row["rel_type"] or ""
                is_symp = "symptom" in rel.lower() or "med__Symptom" in (row["target_labels"] or [])
                t_kind = "symptom" if is_symp else "treatment"
                rel_label = "อาการ" if is_symp else "การรักษา"

                if d_name not in nodes_dict:
                    nodes_dict[d_name] = {
                        "name": d_name,
                        "thai": "",
                        "kind": "disease",
                        "definition": row["disease_uri"] or "โรค",
                    }
                if t_name not in nodes_dict:
                    nodes_dict[t_name] = {
                        "name": t_name,
                        "thai": "",
                        "kind": t_kind,
                        "definition": row["target_uri"] or ("อาการ" if is_symp else "ยา / การรักษา"),
                    }

                links.append({
                    "from": d_name,
                    "to": t_name,
                    "type": rel,
                    "label": rel_label,
                    "detail": f"{d_name} -> {rel_label} -> {t_name}",
                })

            # 2. Fetch Term nodes if available
            term_nodes = session.run(
                """
                MATCH (t:Term)
                RETURN t.name AS name, t.thai AS thai, t.kind AS kind, t.definition AS definition
                ORDER BY t.name
                LIMIT $limit
                """,
                limit=limit,
            )
            for row in term_nodes:
                name = row["name"]
                if name not in nodes_dict:
                    nodes_dict[name] = {
                        "name": name,
                        "thai": row["thai"] or "",
                        "kind": row["kind"] or "term",
                        "definition": row["definition"] or "",
                    }

            term_links = session.run(
                """
                MATCH (a:Term)-[r:RELATED]->(b:Term)
                RETURN a.name AS from_name, b.name AS to_name, r.type AS rel_type, r.label AS label, r.detail AS detail
                LIMIT $limit
                """,
                limit=limit,
            )
            for row in term_links:
                links.append({
                    "from": row["from_name"],
                    "to": row["to_name"],
                    "type": row["rel_type"] or "RELATED",
                    "label": row["label"] or "เกี่ยวข้อง",
                    "detail": row["detail"] or "",
                })

        return {"nodes": list(nodes_dict.values()), "links": links, "skipped": False}
    except Exception as exc:
        print(f"Warning: graph_overview query failed: {exc}")
        close_driver()
        return {"nodes": [], "links": [], "skipped": True}


def facts_to_graph_dict(facts: list[dict]) -> dict:
    """Converts related_terms() facts into a GraphView-compatible dict."""
    if not facts:
        return {"nodes": [], "links": [], "skipped": False}
    nodes_map = {}
    links = []

    for fact in facts:
        name = fact.get("name")
        if not name:
            continue
        if name not in nodes_map:
            nodes_map[name] = {
                "name": name,
                "thai": fact.get("thai", ""),
                "kind": fact.get("kind", "concept"),
                "definition": fact.get("definition", ""),
            }

        other = fact.get("related_name")
        if other:
            if other not in nodes_map:
                nodes_map[other] = {
                    "name": other,
                    "thai": fact.get("related_thai", ""),
                    "kind": fact.get("related_kind", "concept"),
                    "definition": fact.get("related_definition", ""),
                }
            rel_label = "เกี่ยวข้อง"
            if fact.get("relation"):
                if "has_symptom" in fact["relation"]:
                    rel_label = "อาการ"
                elif "has_treatment" in fact["relation"]:
                    rel_label = "การรักษา"
            links.append({
                "from": name if (fact.get("relation") or "").startswith(name) else other,
                "to": other if (fact.get("relation") or "").startswith(name) else name,
                "label": rel_label,
                "detail": fact.get("relation_detail", ""),
            })

    return {"nodes": list(nodes_map.values()), "links": links, "skipped": False}


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
