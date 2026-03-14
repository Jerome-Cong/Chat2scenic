"""
Insert UN Regulations into Milvus Vector Database

This script reads markdown regulation files from data/md/, chunks them appropriately,
generates embeddings, and inserts them into a Milvus collection for RAG retrieval.

Usage:
    python utilities/insert_regulations_to_milvus.py
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from tqdm import tqdm

# Add the project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from pymilvus import (
    connections, 
    Collection, 
    FieldSchema, 
    CollectionSchema, 
    DataType,
    utility
)
from core.embedding import EmbeddingModel
from core.config import get_settings

settings = get_settings()

# Configuration
COLLECTION_NAME = "regulations"
EMBEDDING_DIM = 1024  # for BAAI/bge-large-en-v1.5
CHUNK_SIZE = settings.CHUNK_SIZE  # 2000 chars
CHUNK_OVERLAP = settings.CHUNK_OVERLAP  # 400 chars
BATCH_SIZE = 32


def connect_to_milvus() -> None:
    """Connect to Milvus server."""
    print(f"Connecting to Milvus at {settings.MILVUS_URI}...")
    connections.connect(
        alias="default",
        uri=settings.MILVUS_URI,
        token=settings.MILVUS_TOKEN if settings.MILVUS_TOKEN else None
    )
    print("Connected to Milvus successfully!")


def disconnect_from_milvus() -> None:
    """Disconnect from Milvus server."""
    connections.disconnect("default")
    print("Disconnected from Milvus.")


def create_collection() -> Collection:
    """Create or get the regulations collection with appropriate schema."""
    
    # Check if collection exists
    if utility.has_collection(COLLECTION_NAME):
        print(f"Collection '{COLLECTION_NAME}' already exists. Dropping and recreating...")
        utility.drop_collection(COLLECTION_NAME)
    
    # Define schema
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="regulation_id", dtype=DataType.VARCHAR, max_length=50),
        FieldSchema(name="section", dtype=DataType.VARCHAR, max_length=200),
        FieldSchema(name="chunk_index", dtype=DataType.INT64),
        FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM)
    ]
    
    schema = CollectionSchema(
        fields=fields,
        description="UN Regulations for autonomous driving systems"
    )
    
    # Create collection
    collection = Collection(
        name=COLLECTION_NAME,
        schema=schema,
        using="default"
    )
    
    # Create index on embedding field
    index_params = {
        "metric_type": "COSINE",
        "index_type": "IVF_FLAT",
        "params": {"nlist": 128}
    }
    collection.create_index(field_name="embedding", index_params=index_params)
    print(f"Created collection '{COLLECTION_NAME}' with IVF_FLAT index.")
    
    return collection


def extract_regulation_id(filename: str) -> str:
    """Extract regulation ID from filename (e.g., 'R171e.md' -> 'R171')."""
    # Remove extension and language suffix
    name = Path(filename).stem
    # Extract regulation number (e.g., R171e -> R171)
    match = re.match(r'(R\d+)', name, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return name


def extract_section_from_chunk(chunk: str) -> str:
    """Extract section number from the beginning of a chunk if present."""
    # Look for section patterns like "5.1.1", "Annex 1", etc.
    lines = chunk.strip().split('\n')
    if not lines:
        return "General"
    
    first_line = lines[0].strip()
    
    # Match numbered sections (e.g., "5.1.1", "5.1.1.1")
    section_match = re.match(r'^(\d+(?:\.\d+)*)', first_line)
    if section_match:
        return section_match.group(1)
    
    # Match Annex sections
    annex_match = re.match(r'^(Annex\s+\d+)', first_line, re.IGNORECASE)
    if annex_match:
        return annex_match.group(1)
    
    # Match Appendix sections
    appendix_match = re.match(r'^(Appendix\s+\d+)', first_line, re.IGNORECASE)
    if appendix_match:
        return appendix_match.group(1)
    
    return "General"


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[Tuple[str, int]]:
    """
    Split text into overlapping chunks, trying to break at paragraph boundaries.
    Returns list of (chunk_text, chunk_index) tuples.
    """
    chunks = []
    
    # Split into paragraphs first
    paragraphs = re.split(r'\n\s*\n', text)
    
    current_chunk = ""
    chunk_index = 0
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
            
        # If adding this paragraph would exceed chunk size
        if len(current_chunk) + len(para) + 2 > chunk_size:
            if current_chunk:
                chunks.append((current_chunk.strip(), chunk_index))
                chunk_index += 1
                
                # Keep overlap from the end of current chunk
                if overlap > 0 and len(current_chunk) > overlap:
                    # Find a good break point for overlap
                    overlap_text = current_chunk[-overlap:]
                    # Try to start at a sentence or paragraph boundary
                    sentence_break = overlap_text.find('. ')
                    if sentence_break > 0:
                        overlap_text = overlap_text[sentence_break + 2:]
                    current_chunk = overlap_text + "\n\n" + para
                else:
                    current_chunk = para
            else:
                # Paragraph itself is longer than chunk_size, split it
                words = para.split()
                temp_chunk = ""
                for word in words:
                    if len(temp_chunk) + len(word) + 1 > chunk_size:
                        if temp_chunk:
                            chunks.append((temp_chunk.strip(), chunk_index))
                            chunk_index += 1
                        temp_chunk = word
                    else:
                        temp_chunk += " " + word if temp_chunk else word
                current_chunk = temp_chunk
        else:
            current_chunk += "\n\n" + para if current_chunk else para
    
    # Don't forget the last chunk
    if current_chunk.strip():
        chunks.append((current_chunk.strip(), chunk_index))
    
    return chunks


def load_regulation_files(data_dir: str) -> List[Dict[str, Any]]:
    """
    Load all markdown regulation files and chunk them.
    Returns list of dictionaries with regulation metadata and chunked content.
    """
    data_path = Path(data_dir)
    regulation_chunks = []
    
    # Find all markdown files (exclude backup files)
    md_files = [f for f in data_path.glob("*.md") if "_original" not in f.name]
    
    print(f"Found {len(md_files)} regulation file(s) to process.")
    
    for md_file in md_files:
        print(f"Processing: {md_file.name}")
        
        regulation_id = extract_regulation_id(md_file.name)
        
        with open(md_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Chunk the content
        chunks = chunk_text(content)
        print(f"  Created {len(chunks)} chunks for {regulation_id}")
        
        for chunk_text_content, chunk_idx in chunks:
            section = extract_section_from_chunk(chunk_text_content)
            regulation_chunks.append({
                "regulation_id": regulation_id,
                "section": section,
                "chunk_index": chunk_idx,
                "content": chunk_text_content
            })
    
    return regulation_chunks


def insert_regulations(
    collection: Collection,
    regulation_chunks: List[Dict[str, Any]],
    embedding_model: EmbeddingModel,
    batch_size: int = BATCH_SIZE
) -> int:
    """
    Insert regulation chunks into Milvus collection.
    Returns number of successfully inserted chunks.
    """
    total_inserted = 0
    total_chunks = len(regulation_chunks)
    
    print(f"\nInserting {total_chunks} regulation chunks into Milvus...")
    
    # Process in batches
    for i in tqdm(range(0, total_chunks, batch_size), desc="Inserting batches"):
        batch = regulation_chunks[i:i + batch_size]
        
        # Prepare batch data
        regulation_ids = []
        sections = []
        chunk_indices = []
        contents = []
        
        for chunk in batch:
            regulation_ids.append(chunk["regulation_id"])
            sections.append(chunk["section"])
            chunk_indices.append(chunk["chunk_index"])
            contents.append(chunk["content"])
        
        try:
            # Generate embeddings for the batch
            embeddings = embedding_model.embedding.embed_documents(contents)
            
            # Insert into Milvus
            data = [
                regulation_ids,
                sections,
                chunk_indices,
                contents,
                embeddings
            ]
            
            collection.insert(data)
            total_inserted += len(batch)
            
        except Exception as e:
            print(f"\nError inserting batch at index {i}: {str(e)}")
            print(f"Skipping {len(batch)} chunks...")
            continue
    
    # Flush to ensure all data is persisted
    collection.flush()
    print(f"\nSuccessfully inserted {total_inserted}/{total_chunks} chunks.")
    
    return total_inserted


def main():
    """Main entry point for the regulation insertion script."""
    # Configuration
    data_dir = project_root / "data" / "cleaned"
    
    print("=" * 60)
    print("UN Regulation Milvus Insertion Script")
    print("=" * 60)
    print(f"\nConfiguration:")
    print(f"  Data directory: {data_dir}")
    print(f"  Collection name: {COLLECTION_NAME}")
    print(f"  Chunk size: {CHUNK_SIZE}")
    print(f"  Chunk overlap: {CHUNK_OVERLAP}")
    print(f"  Embedding dimension: {EMBEDDING_DIM}")
    print(f"  Batch size: {BATCH_SIZE}")
    print()
    
    try:
        # Connect to Milvus
        connect_to_milvus()
        
        # Create collection
        collection = create_collection()
        
        # Initialize embedding model
        print(f"\nInitializing embedding model...")
        print(f"  Provider: {settings.EMBEDDING_PROVIDER}")
        print(f"  Model: BAAI/bge-large-en-v1.5")
        print(f"  Device: {settings.DEVICE}")
        embedding_model = EmbeddingModel(model_name="BAAI/bge-large-en-v1.5")
        print("Embedding model initialized successfully!")
        
        # Load and chunk regulation files
        print(f"\nLoading regulation files from {data_dir}...")
        regulation_chunks = load_regulation_files(data_dir)
        
        if not regulation_chunks:
            print("No regulation chunks found. Exiting.")
            return
        
        print(f"\nTotal chunks to insert: {len(regulation_chunks)}")
        
        # Insert into Milvus
        inserted_count = insert_regulations(collection, regulation_chunks, embedding_model)
        
        # Load collection for querying
        collection.load()
        
        # Print summary
        print("\n" + "=" * 60)
        print("Insertion Summary")
        print("=" * 60)
        print(f"Total chunks inserted: {inserted_count}")
        print(f"Collection entity count: {collection.num_entities}")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nError: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
        
    finally:
        # Clean up
        disconnect_from_milvus()
        print("\nDone!")


if __name__ == "__main__":
    main()
