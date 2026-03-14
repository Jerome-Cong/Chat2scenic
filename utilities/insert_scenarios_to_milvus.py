import json
import os
from pathlib import Path
from typing import List, Dict
from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility
from core.embedding import EmbeddingModel
from core.config import get_settings

settings = get_settings()


def create_collection():
    collection_name = "scenario_components"
    
    if utility.has_collection(collection_name):
        print(f"Collection '{collection_name}' already exists - will append new chunks.")
        collection = Collection(name=collection_name)
        try:
            index_params = {
                "index_type": "IVF_FLAT",
                "metric_type": "COSINE",
                "params": {"nlist": 128}
            }
            collection.create_index(field_name="embedding", index_params=index_params)
        except Exception:
            pass
        return collection

    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="scenario_id", dtype=DataType.VARCHAR, max_length=128),
        FieldSchema(name="component_type", dtype=DataType.VARCHAR, max_length=128),
        FieldSchema(name="description", dtype=DataType.VARCHAR, max_length=4096),
        FieldSchema(name="code", dtype=DataType.VARCHAR, max_length=16384),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=384)
    ]
    
    schema = CollectionSchema(fields=fields)
    collection = Collection(name=collection_name, schema=schema)
    
    index_params = {
        "index_type": "IVF_FLAT",
        "metric_type": "COSINE",
        "params": {"nlist": 128}
    }
    collection.create_index(field_name="embedding", index_params=index_params)
    
    return collection


def load_json_files(directory: str) -> List[Dict]:
    json_files = sorted(Path(directory).glob("*.json"))
    scenarios = []
    
    for json_file in json_files:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            scenarios.append({
                "scenario_id": json_file.stem,
                "data": data
            })
    
    return scenarios


def insert_scenarios(collection: Collection, scenarios: List[Dict], embedding_model: EmbeddingModel, batch_size: int = 32):
    component_types = [
        "Scenario",
        "Spatial Relation",
        "Requirement and restrictions"
    ]
    
    inserted_count = 0
    skipped_count = 0
    skipped_details = []
    
    batch_scenario_ids = []
    batch_component_types = []
    batch_descriptions = []
    batch_codes = []
    batch_texts_for_embedding = []
    
    for idx, scenario in enumerate(scenarios):
        scenario_id = scenario["scenario_id"]
        data = scenario["data"]
        
        print(f"Processing scenario {idx + 1}/{len(scenarios)}: {scenario_id}")
        
        scenario_inserted = 0
        scenario_skipped = 0
        
        for component_type in component_types:
            if component_type in data:
                component_data = data[component_type]
                
                # Skip if component_data is None, empty, or not a dictionary
                if not component_data or not isinstance(component_data, dict):
                    skipped_count += 1
                    scenario_skipped += 1
                    skipped_details.append(f"{scenario_id}/{component_type}: null/empty/invalid")
                    continue
                
                # Safely get description and code with default values
                description = component_data.get("description", "")
                code = component_data.get("code", "")
                
                # Handle None values
                if description is None:
                    description = ""
                if code is None:
                    code = ""
                
                # Strip whitespace
                description = description.strip()
                code = code.strip()
                
                # Skip if both are empty
                if not description and not code:
                    skipped_count += 1
                    scenario_skipped += 1
                    skipped_details.append(f"{scenario_id}/{component_type}: empty description and code")
                    continue
                
                # Skip if either is empty (we need both for proper indexing)
                if not description or not code:
                    skipped_count += 1
                    scenario_skipped += 1
                    skipped_details.append(f"{scenario_id}/{component_type}: missing {'description' if not description else 'code'}")
                    continue
                
                # This component is valid - add it to the batch
                batch_scenario_ids.append(scenario_id)
                batch_component_types.append(component_type)
                batch_descriptions.append(description)
                batch_codes.append(code)
                batch_texts_for_embedding.append(description)
                scenario_inserted += 1
        
        if "Egos" in data and isinstance(data["Egos"], list):
            for i, ego in enumerate(data["Egos"]):
                if not ego or not isinstance(ego, dict):
                    skipped_count += 1
                    scenario_skipped += 1
                    skipped_details.append(f"{scenario_id}/Ego_{i}: null/empty/invalid")
                    continue
                
                description = ego.get("description", "")
                code = ego.get("code", "")
                
                if description is None:
                    description = ""
                if code is None:
                    code = ""
                
                description = description.strip()
                code = code.strip()
                
                if not description and not code:
                    skipped_count += 1
                    scenario_skipped += 1
                    skipped_details.append(f"{scenario_id}/Ego_{i}: empty description and code")
                    continue
                
                if not description or not code:
                    skipped_count += 1
                    scenario_skipped += 1
                    skipped_details.append(f"{scenario_id}/Ego_{i}: missing {'description' if not description else 'code'}")
                    continue
                
                batch_scenario_ids.append(scenario_id)
                batch_component_types.append("Ego")
                batch_descriptions.append(description)
                batch_codes.append(code)
                batch_texts_for_embedding.append(description)
                scenario_inserted += 1
        
        if "Adversarials" in data and isinstance(data["Adversarials"], list):
            for i, adversarial in enumerate(data["Adversarials"]):
                if not adversarial or not isinstance(adversarial, dict):
                    skipped_count += 1
                    scenario_skipped += 1
                    skipped_details.append(f"{scenario_id}/Adversarial_{i}: null/empty/invalid")
                    continue
                
                description = adversarial.get("description", "")
                code = adversarial.get("code", "")
                
                if description is None:
                    description = ""
                if code is None:
                    code = ""
                
                description = description.strip()
                code = code.strip()
                
                if not description and not code:
                    skipped_count += 1
                    scenario_skipped += 1
                    skipped_details.append(f"{scenario_id}/Adversarial_{i}: empty description and code")
                    continue
                
                if not description or not code:
                    skipped_count += 1
                    scenario_skipped += 1
                    skipped_details.append(f"{scenario_id}/Adversarial_{i}: missing {'description' if not description else 'code'}")
                    continue
                
                batch_scenario_ids.append(scenario_id)
                batch_component_types.append("Adversarial")
                batch_descriptions.append(description)
                batch_codes.append(code)
                batch_texts_for_embedding.append(description)
                scenario_inserted += 1
        
        if len(batch_texts_for_embedding) >= batch_size:
            try:
                embeddings = embedding_model.embedding.embed_documents(batch_texts_for_embedding)
                
                data_to_insert = [
                    batch_scenario_ids,
                    batch_component_types,
                    batch_descriptions,
                    batch_codes,
                    embeddings
                ]
                
                collection.insert(data_to_insert)
                collection.flush()
                inserted_count += len(batch_texts_for_embedding)
                
                batch_scenario_ids = []
                batch_component_types = []
                batch_descriptions = []
                batch_codes = []
                batch_texts_for_embedding = []
            except Exception as e:
                print(f"Error inserting batch: {e}")
                skipped_count += len(batch_texts_for_embedding)
                batch_scenario_ids = []
                batch_component_types = []
                batch_descriptions = []
                batch_codes = []
                batch_texts_for_embedding = []
        
        if scenario_skipped > 0:
            print(f"  → Inserted: {scenario_inserted}, Skipped: {scenario_skipped}")
            scenario_skips = [s for s in skipped_details if s.startswith(f"{scenario_id}/")]
            for skip in scenario_skips[-scenario_skipped:]:  # Only show recent skips for this scenario
                print(f"     • {skip}")
        else:
            print(f"  → Inserted: {scenario_inserted}")
    
    if batch_texts_for_embedding:
        try:
            embeddings = embedding_model.embedding.embed_documents(batch_texts_for_embedding)
            
            data_to_insert = [
                batch_scenario_ids,
                batch_component_types,
                batch_descriptions,
                batch_codes,
                embeddings
            ]
            
            collection.insert(data_to_insert)
            collection.flush()
            inserted_count += len(batch_texts_for_embedding)
        except Exception as e:
            print(f"Error inserting final batch: {e}")
            skipped_count += len(batch_texts_for_embedding)
    
    print(f"Inserted: {inserted_count}, Skipped: {skipped_count}")


def main():
    connections.connect(uri=settings.MILVUS_URI, token=settings.MILVUS_TOKEN)
    
    device = "cuda" if settings.DEVICE == "cuda" else "cpu"
    embedding_model = EmbeddingModel(provider="huggingface", model_name="sentence-transformers/all-MiniLM-L6-v2", device=device)
    
    print(f"Using device: {device}")
    
    collection = create_collection()
    
    json_directory = "data/chatscene"
    scenarios = load_json_files(json_directory)
    
    print(f"Inserting {len(scenarios)} scenarios into Milvus...")
    insert_scenarios(collection, scenarios, embedding_model, batch_size=32)
    
    collection.load()
    
    print(f"Inserted {collection.num_entities} components into collection 'scenario_components'")
    
    connections.disconnect("default")


if __name__ == "__main__":
    main()

