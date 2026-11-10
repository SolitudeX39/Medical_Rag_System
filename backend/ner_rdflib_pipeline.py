import pandas as pd
import spacy
from rdflib import Graph, URIRef, Literal, Namespace
from rdflib.namespace import RDF, RDFS
import os
import sys

# ==========================================
# SETUP INSTRUCTIONS:
# 1. pip install pandas rdflib spacy scispacy
# 2. Symptom model (BioMedical Concepts):
#    pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_core_sci_sm-0.5.4.tar.gz
# 3. Treatment model (Chemical & Drug Specialist):
#    pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_ner_bc5cdr_md-0.5.4.tar.gz
# ==========================================

def load_symptom_model():
    """Loads the medical NER model for symptoms with UMLS entity linking."""
    try:
        print("Loading Symptom NER model (en_core_sci_sm)...")
        nlp = spacy.load("en_core_sci_sm")
        try:
            from scispacy.linking import EntityLinker
            print("Adding UMLS Entity Linker to Symptoms...")
            nlp.add_pipe("scispacy_linker", config={"resolve_abbreviations": True, "linker_name": "umls"})
        except Exception as e:
            print(f"Note: UMLS linker not attached: {e}")
    except OSError:
        print("Falling back to standard english model for symptoms...")
        try:
            nlp = spacy.load("en_core_web_sm")
        except OSError:
            spacy.cli.download("en_core_web_sm")
            nlp = spacy.load("en_core_web_sm")
    return nlp

def load_treatment_model():
    """
    Loads en_ner_bc5cdr_md specifically for extracting CHEMICALS / DRUGS from treatment text,
    with UMLS entity linking to resolve medications to CUIs.
    Ignores non-drug words like 'day', 'patient', 'times', 'risk', etc.
    """
    try:
        print("Loading Treatment Drug Specialist model (en_ner_bc5cdr_md)...")
        nlp = spacy.load("en_ner_bc5cdr_md")
        try:
            from scispacy.linking import EntityLinker
            print("Adding UMLS Entity Linker to Treatments...")
            nlp.add_pipe("scispacy_linker", config={"resolve_abbreviations": True, "linker_name": "umls"})
        except Exception as e:
            print(f"Note: UMLS linker not attached to treatments: {e}")
    except OSError:
        print("WARNING: en_ner_bc5cdr_md not found. Falling back to basic model...")
        nlp = spacy.load("en_core_web_sm")
    return nlp

def extract_symptom_entities(nlp, text):
    """Extracts symptom entities and maps to UMLS CUIs when confident."""
    if pd.isna(text) or not str(text).strip():
        return {}

    doc = nlp(str(text))
    extracted = {}
    has_linker = "scispacy_linker" in nlp.pipe_names

    for ent in doc.ents:
        entity_name = ent.text.lower().strip()
        if not entity_name or len(entity_name) < 2:
            continue
        cui_id = None
        if has_linker and ent._.kb_ents:
            best_match_cui, score = ent._.kb_ents[0]
            if score > 0.75:
                cui_id = best_match_cui
        unique_key = cui_id if cui_id else entity_name.replace(" ", "_").replace(",", "")
        extracted[unique_key] = entity_name
    return extracted

def extract_treatment_chemicals(nlp, text):
    """
    Uses en_ner_bc5cdr_md to isolate ONLY pharmaceutical chemicals/drugs,
    and maps them to UMLS CUIs when confident.
    Returns: { "unique_id": "Drug Display Name" }
    """
    if pd.isna(text) or not str(text).strip():
        return {}
    doc = nlp(str(text))
    drugs = {}
    has_linker = "scispacy_linker" in nlp.pipe_names
    for ent in doc.ents:
        if ent.label_ == "CHEMICAL":
            clean_name = ent.text.strip().lower()
            if len(clean_name) >= 3:
                cui_id = None
                if has_linker and ent._.kb_ents:
                    best_match_cui, score = ent._.kb_ents[0]
                    if score > 0.75:
                        cui_id = best_match_cui
                unique_key = cui_id if cui_id else clean_name.replace(" ", "_").replace(",", "").replace("-", "_")
                drugs[unique_key] = ent.text.strip().title()
    return drugs

def process_csv_to_rdf(csv_path="disease_data_test.csv", output_path="disease_graph.ttl", max_rows=None):
    nlp_symptoms = load_symptom_model()
    nlp_treatments = load_treatment_model()
    print(f"\nLoading data from {csv_path}...")
    df = pd.read_csv(csv_path)
    if max_rows:
        print(f"Limiting to first {max_rows} rows for testing...")
        df = df.head(max_rows)
    total_rows = len(df)
    print(f"Total rows to process: {total_rows}")
    # Extract Symptoms
    print("\n[1/2] Extracting Symptoms (Medical NER + UMLS)...")
    extracted_symptoms = []
    for i, text in enumerate(df['common_symptom'], 1):
        if i % 100 == 0 or i == total_rows:
            print(f"  Processed {i}/{total_rows} symptom rows...")
        extracted_symptoms.append(extract_symptom_entities(nlp_symptoms, text))
    df['extracted_symptoms'] = extracted_symptoms
    # Extract Treatments
    print("\n[2/2] Extracting Treatments (BC5CDR Chemical/Drug Specialist)...")
    extracted_treatments = []
    for i, text in enumerate(df['treatment'], 1):
        if i % 100 == 0 or i == total_rows:
            print(f"  Processed {i}/{total_rows} treatment rows...")
        extracted_treatments.append(extract_treatment_chemicals(nlp_treatments, text))
    df['extracted_treatments'] = extracted_treatments
    # Preview first row
    print("\n--- Extraction Preview (Row 1) ---")
    first_row = df.iloc[0]
    print(f"Disease: {first_row.get('disease')}")
    print(f"  Extracted Symptoms: {list(first_row['extracted_symptoms'].values())}")
    print(f"  Extracted Medications/Chemicals: {list(first_row['extracted_treatments'].values())}")
    # Build RDF Graph
    print("\nBuilding Semantic RDF Graph...")
    g = Graph()
    MED = Namespace("http://example.org/medical/")
    DISEASE = Namespace("http://example.org/medical/disease/")
    SYMPTOM = Namespace("http://example.org/medical/symptom/")
    TREATMENT = Namespace("http://example.org/medical/treatment/")
    UMLS = Namespace("http://linkedlifedata.com/resource/umls/id/")
    g.bind("med", MED)
    g.bind("disease", DISEASE)
    g.bind("symptom", SYMPTOM)
    g.bind("treatment", TREATMENT)
    g.bind("umls", UMLS)
    for _, row in df.iterrows():
        disease_name = str(row.get('disease', '')).strip()
        if not disease_name or disease_name == 'nan':
            continue
        disease_uri_str = disease_name.replace(" ", "_").replace(",", "").lower()
        disease_node = DISEASE[disease_uri_str]
        g.add((disease_node, RDF.type, MED.Disease))
        g.add((disease_node, RDFS.label, Literal(disease_name)))
        # Symptoms
        for unique_id, symp_name in row['extracted_symptoms'].items():
            if unique_id.startswith("C") and unique_id[1:].isdigit():
                symp_node = UMLS[unique_id]
            else:
                symp_node = SYMPTOM[unique_id]
            g.add((symp_node, RDF.type, MED.Symptom))
            g.add((symp_node, RDFS.label, Literal(symp_name.title())))
            g.add((disease_node, MED.has_symptom, symp_node))
        # Treatments
        for unique_id, treat_name in row['extracted_treatments'].items():
            if unique_id.startswith("C") and unique_id[1:].isdigit():
                treat_node = UMLS[unique_id]
            else:
                treat_node = TREATMENT[unique_id]
            g.add((treat_node, RDF.type, MED.Treatment))
            g.add((treat_node, RDFS.label, Literal(treat_name)))
            g.add((disease_node, MED.has_treatment, treat_node))
    print(f"\nSaving RDF graph to {output_path}...")
    g.serialize(destination=output_path, format="turtle")
    print(f"Success! Graph generated with {len(g)} triples.")
    return output_path
