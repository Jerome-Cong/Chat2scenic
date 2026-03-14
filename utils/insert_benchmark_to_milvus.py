"""
Insert Benchmark Scenarios into Milvus Vector Database

This script reads the benchmark.md file, chunks it by '###' headers,
generates embeddings, and inserts them into a Milvus collection for RAG retrieval.

Usage:
    python utilities/insert_benchmark_to_milvus.py
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Any
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
COLLECTION_NAME = "regulations"  # Use same collection as regulations
EMBEDDING_DIM = 1024  # for BAAI/bge-large-en-v1.5
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


def get_collection() -> Collection:
    """Get the existing regulations collection to append benchmark data."""
    
    # Check if collection exists
    if not utility.has_collection(COLLECTION_NAME):
        raise RuntimeError(f"Collection '{COLLECTION_NAME}' does not exist. Run insert_regulations_to_milvus.py first.")
    
    collection = Collection(name=COLLECTION_NAME, using="default")
    print(f"Using existing collection '{COLLECTION_NAME}'")
    print(f"Current entity count: {collection.num_entities}")
    
    return collection


def extract_source_from_header(header: str) -> str:
    """Extract source name from header (e.g., '### Scenarios from CARLA Leaderboard' -> 'CARLA Leaderboard')."""
    # Remove '###' and 'Scenarios from' prefix
    header = header.strip().lstrip('#').strip()
    if header.lower().startswith('scenarios from '):
        header = header[15:].strip()
    return header


def chunk_by_header(content: str) -> List[Dict[str, Any]]:
    """
    Split content by '###' headers.
    Returns list of dictionaries with regulation_id, section, and content.
    Uses same schema as regulations collection.
    """
    chunks = []
    
    # Split by ### headers
    sections = re.split(r'(^###\s+.+$)', content, flags=re.MULTILINE)
    
    current_source = "General"
    chunk_index = 0
    
    for i, section in enumerate(sections):
        section = section.strip()
        if not section:
            continue
        
        # Check if this is a header
        if section.startswith('###'):
            current_source = extract_source_from_header(section)
        else:
            # This is content - add as a chunk
            # Map to regulations schema: regulation_id, section, chunk_index, content
            if section:
                chunks.append({
                    "regulation_id": "BENCHMARK",  # Use BENCHMARK as regulation_id
                    "section": current_source,      # Use source as section
                    "chunk_index": chunk_index,
                    "content": section
                })
                chunk_index += 1
    
    return chunks


def load_benchmark_file(file_path: str) -> List[Dict[str, Any]]:
    """
    Load and chunk the benchmark markdown file.
    Returns list of dictionaries with source and content.
    """
    print(f"Loading: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Chunk by ### headers
    chunks = chunk_by_header(content)
    
    print(f"  Created {len(chunks)} chunks from benchmark file")
    
    # Print chunk distribution
    source_counts = {}
    for chunk in chunks:
        source = chunk["section"]  # Use section field (maps to source name)
        source_counts[source] = source_counts.get(source, 0) + 1
    
    print("  Chunks by source:")
    for source, count in source_counts.items():
        print(f"    - {source}: {count} chunk(s)")
    
    return chunks


def insert_benchmark(
    collection: Collection,
    benchmark_chunks: List[Dict[str, Any]],
    embedding_model: EmbeddingModel,
    batch_size: int = BATCH_SIZE
) -> int:
    """
    Insert benchmark chunks into Milvus collection (same schema as regulations).
    Returns number of successfully inserted chunks.
    """
    total_inserted = 0
    total_chunks = len(benchmark_chunks)
    
    print(f"\nInserting {total_chunks} benchmark chunks into Milvus...")
    
    # Process in batches
    for i in tqdm(range(0, total_chunks, batch_size), desc="Inserting batches"):
        batch = benchmark_chunks[i:i + batch_size]
        
        # Prepare batch data (same schema as regulations)
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
            
            # Insert into Milvus (same field order as regulations)
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
    """Main entry point for the benchmark insertion script."""
    # Configuration
    benchmark_file = project_root / "data" / "benchmark.md"
    
    print("=" * 60)
    print("Benchmark Scenarios Milvus Insertion Script")
    print("=" * 60)
    print(f"\nConfiguration:")
    print(f"  Benchmark file: {benchmark_file}")
    print(f"  Collection name: {COLLECTION_NAME}")
    print(f"  Chunk separator: '###' (markdown headers)")
    print(f"  Embedding dimension: {EMBEDDING_DIM}")
    print(f"  Batch size: {BATCH_SIZE}")
    print()
    
    # Check if file exists
    if not benchmark_file.exists():
        print(f"Error: Benchmark file not found: {benchmark_file}")
        sys.exit(1)
    
    try:
        # Connect to Milvus
        connect_to_milvus()
        
        # Get existing collection
        collection = get_collection()
        
        # Initialize embedding model
        print(f"\nInitializing embedding model...")
        print(f"  Provider: {settings.EMBEDDING_PROVIDER}")
        print(f"  Model: BAAI/bge-large-en-v1.5")
        print(f"  Device: {settings.DEVICE}")
        embedding_model = EmbeddingModel(model_name="BAAI/bge-large-en-v1.5")
        print("Embedding model initialized successfully!")
        
        # Load and chunk benchmark file
        print(f"\nLoading benchmark file...")
        benchmark_chunks = load_benchmark_file(benchmark_file)
        
        if not benchmark_chunks:
            print("No benchmark chunks found. Exiting.")
            return
        
        print(f"\nTotal chunks to insert: {len(benchmark_chunks)}")
        
        # Insert into Milvus
        inserted_count = insert_benchmark(collection, benchmark_chunks, embedding_model)
        
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
