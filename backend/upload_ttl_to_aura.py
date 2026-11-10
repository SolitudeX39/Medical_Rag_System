import os
from neo4j import GraphDatabase
from rdflib import Graph

def upload_ttl_to_aura(ttl_path: str, uri: str, username: str, password: str) -> None:
    """Upload a Turtle RDF file to Neo4j Aura using the n10s plugin.

    Parameters
    ----------
    ttl_path: str
        Path to the .ttl file to upload.
    uri: str
        Neo4j Bolt URI (e.g., "neo4j+s://<instance>.databases.neo4j.io").
    username: str
        Neo4j username.
    password: str
        Neo4j password.
    """
    driver = GraphDatabase.driver(uri, auth=(username, password))
    with driver.session() as session:
        # Ensure neosemantics (n10s) is initialized – this is a no‑op if already done.
        session.run("CALL n10s.graphconfig.init()")
        # Read the TTL content
        with open(ttl_path, "r", encoding="utf-8") as f:
            ttl_data = f.read()
        # Import the RDF via n10s
        session.run(
            "CALL n10s.rdf.import.inline($rdf, 'Turtle')",
            rdf=ttl_data,
        )
    driver.close()

# Convenience variables taken from .env by the caller
if __name__ == "__main__":
    from components.env import load_project_env
    load_project_env()
    AURA_URI = os.getenv("NEO4J_URI")
    AURA_USERNAME = os.getenv("NEO4J_USERNAME")
    AURA_PASSWORD = os.getenv("NEO4J_PASSWORD")
    # Example usage: python upload_ttl_to_aura.py path/to/file.ttl
    import sys
    if len(sys.argv) != 2:
        print("Usage: upload_ttl_to_aura.py <ttl_file>")
        sys.exit(1)
    upload_ttl_to_aura(sys.argv[1], AURA_URI, AURA_USERNAME, AURA_PASSWORD)
