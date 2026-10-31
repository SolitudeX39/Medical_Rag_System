import os
import sys
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

# Ensure Windows terminal doesn't crash on utf-8 characters
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ==========================================
# SETUP INSTRUCTIONS:
# pip install neo4j
# ==========================================

def test_connection_and_query(uri, passwords, usernames):
    print(f"Connecting to Neo4j Aura at: {uri}\n")
    
    driver = None
    connected = False
    working_user = None
    working_pwd = None

    for user in usernames:
        for pwd in passwords:
            try:
                print(f"Testing credentials -> Username: '{user}' ...")
                test_driver = GraphDatabase.driver(uri, auth=(user, pwd))
                test_driver.verify_connectivity()
                print(f"✅ SUCCESS: Connected with Username '{user}'!\n")
                driver = test_driver
                connected = True
                working_user = user
                working_pwd = pwd
                break
            except Exception as e:
                err_str = str(e)
                if "Unauthorized" in err_str:
                    print(f"   ❌ Authentication failed for '{user}'.")
                elif "DatabaseNotFound" in err_str:
                    print(f"   ⚠️  Database routed differently or paused: {err_str}")
                else:
                    print(f"   ❌ Error: {err_str}")
        if connected:
            break

    if not connected:
        print("\n" + "="*60)
        print("❌ ALL CREDENTIAL ATTEMPTS FAILED")
        print("="*60)
        print("Most common reasons on Neo4j Aura:")
        print("1. [INSTANCE PAUSED]: Free Aura instances pause after 3 days.")
        print("   -> Go to https://console.neo4j.io and click 'Resume' on your instance.")
        print("2. [PASSWORD RESET]: If you reset your password in Aura Console,")
        print("   paste the new password into this script.")
        print("="*60)
        return

    try:
        with driver.session() as session:
            count_result = session.run("MATCH (n) RETURN count(n) AS total_nodes")
            total_nodes = count_result.single()["total_nodes"]
            print(f"📊 Graph Size: Found {total_nodes} total nodes in the database.")
            
            if total_nodes == 0:
                print("⚠️  Database is connected, but currently empty.")
            else:
                print("\n🔍 Sample Disease -> Symptom triples:")
                symptom_query = """
                MATCH (d:med__Disease)-[r:med__has_symptom]->(s)
                RETURN coalesce(d.rdfs__label, d.uri) AS d,
                       coalesce(s.rdfs__label, s.uri) AS s
                LIMIT 3
                """
                for r in session.run(symptom_query):
                    print(f"   - [{r['d']}] -> HAS_SYMPTOM -> [{r['s']}]")

                print("\n💊 Sample Disease -> Treatment triples:")
                treatment_query = """
                MATCH (d:med__Disease)-[r:med__has_treatment]->(t)
                RETURN coalesce(d.rdfs__label, d.uri) AS d,
                       coalesce(t.rdfs__label, t.uri) AS t
                LIMIT 3
                """
                for r in session.run(treatment_query):
                    print(f"   - [{r['d']}] -> HAS_TREATMENT -> [{r['t']}]")
                    
        print("\n✅ Verification Complete!")
    except Exception as e:
        print(f"Query error: {e}")
    finally:
        if driver:
            driver.close()

if __name__ == "__main__":
    AURA_URI = os.getenv("NEO4J_URI", "neo4j+s://9477a102.databases.neo4j.io")
    
    # Standard username on Aura is 'neo4j'
    default_user = os.getenv("NEO4J_USERNAME", "9477a102")
    USERNAMES_TO_TRY = [default_user]
    if "9477a102" not in USERNAMES_TO_TRY:
        USERNAMES_TO_TRY.append("9477a102")
    if "neo4j" not in USERNAMES_TO_TRY:
        USERNAMES_TO_TRY.append("neo4j")
    
    # Passwords to try (check .env first, then hardcoded fallback)
    env_pwd = os.getenv("NEO4J_PASSWORD")
    PASSWORDS_TO_TRY = []
    if env_pwd:
        PASSWORDS_TO_TRY.append(env_pwd)
    default_hardcoded_pwd = "Am6H5wH0IMLBkBe30lN9Rf365Tf9vqQvPUJmj1uUWtI"
    if default_hardcoded_pwd not in PASSWORDS_TO_TRY:
        PASSWORDS_TO_TRY.append(default_hardcoded_pwd)
    
    test_connection_and_query(AURA_URI, PASSWORDS_TO_TRY, USERNAMES_TO_TRY)
