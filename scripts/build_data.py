#!/usr/bin/env python3
"""
Precomputed data generation script for MCP-MCP server.

This script fetches server data from multiple sources, deduplicates entries,
generates embeddings, and outputs data files for distribution via GitHub releases.

Supports incremental embedding computation to reduce compute costs.
"""

import asyncio
import hashlib
import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Optional

import httpx
import numpy as np

# Add the parent directory to the path so we can import from the project
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import MCPServerEntry, deduplicate_servers
from db.sources import get_all_sources
from db.semantic_search import SemanticSearchEngine, DEFAULT_MODEL, EMBEDDINGS_VERSION
from db.schema_versions import CURRENT_SCHEMA_VERSION
from settings import app_logger

logger = app_logger.getChild(__name__)

DIST_DIR = Path(__file__).parent.parent / "dist"
SERVERS_FILE = DIST_DIR / "servers.json"
EMBEDDINGS_FILE = DIST_DIR / "embeddings.npz"
DATA_INFO_FILE = DIST_DIR / "data_info.json"

# URLs for downloading previous release data for incremental processing
GITHUB_RELEASE_BASE = "https://github.com/wojtyniak/mcp-mcp/releases/download/data-latest"
PREVIOUS_SERVERS_URL = f"{GITHUB_RELEASE_BASE}/servers.json"
PREVIOUS_EMBEDDINGS_URL = f"{GITHUB_RELEASE_BASE}/embeddings.npz"
PREVIOUS_DATA_INFO_URL = f"{GITHUB_RELEASE_BASE}/data_info.json"


def compute_server_hash(server: MCPServerEntry) -> str:
    """Compute a hash for a server entry to detect changes."""
    content = {
        "name": server.name,
        "description": server.description,
        "url": server.url,
        "category": server.category,
        # Don't include source in hash since that's metadata, not content
    }
    content_str = json.dumps(content, sort_keys=True)
    return hashlib.sha256(content_str.encode()).hexdigest()[:16]


def compute_servers_hash(servers: list[MCPServerEntry]) -> str:
    """Compute overall hash of all servers for change detection."""
    server_hashes = [compute_server_hash(server) for server in servers]
    server_hashes.sort()  # Ensure consistent ordering
    combined = "|".join(server_hashes)
    return hashlib.sha256(combined.encode()).hexdigest()[:16]


async def fetch_all_servers() -> list[MCPServerEntry]:
    """Fetch servers from all sources and deduplicate."""
    logger.info("Fetching servers from all sources...")
    
    sources = get_all_sources()
    all_servers = []
    
    for source in sources:
        try:
            source_servers = await source.get_servers()
            all_servers.extend(source_servers)
            logger.info(f"Loaded {len(source_servers)} servers from {source.name}")
        except Exception as e:
            logger.error(f"Failed to load from {source.name}: {e}")
            # Continue with other sources
    
    # Deduplicate servers across sources
    deduplicated = deduplicate_servers(all_servers)
    logger.info(f"Total: {len(deduplicated)} unique servers (from {len(all_servers)} raw entries)")
    
    return deduplicated


async def download_previous_data() -> tuple[Optional[list[MCPServerEntry]], Optional[np.ndarray], Optional[dict]]:
    """Download previous release data for incremental processing."""
    logger.info("Downloading previous release data for incremental processing...")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        previous_servers = None
        previous_embeddings = None
        previous_data_info = None
        
        # Download previous servers
        try:
            response = await client.get(PREVIOUS_SERVERS_URL)
            if response.status_code == 200:
                servers_data = response.json()
                previous_servers = [MCPServerEntry(**server) for server in servers_data]
                logger.info(f"Downloaded {len(previous_servers)} servers from previous release")
            else:
                logger.info(f"No previous servers found (HTTP {response.status_code})")
        except Exception as e:
            logger.info(f"Could not download previous servers: {e}")
        
        # Download previous embeddings
        try:
            response = await client.get(PREVIOUS_EMBEDDINGS_URL)
            if response.status_code == 200:
                # Save to temporary file and load with numpy
                temp_embeddings = DIST_DIR / "temp_embeddings.npz"
                temp_embeddings.write_bytes(response.content)
                embeddings_data = np.load(temp_embeddings)
                previous_embeddings = embeddings_data['embeddings']
                temp_embeddings.unlink()  # Clean up
                logger.info(f"Downloaded embeddings matrix: {previous_embeddings.shape}")
            else:
                logger.info(f"No previous embeddings found (HTTP {response.status_code})")
        except Exception as e:
            logger.info(f"Could not download previous embeddings: {e}")
        
        # Download previous data info
        try:
            response = await client.get(PREVIOUS_DATA_INFO_URL)
            if response.status_code == 200:
                previous_data_info = response.json()
                logger.info("Downloaded previous data info")
            else:
                logger.info(f"No previous data info found (HTTP {response.status_code})")
        except Exception as e:
            logger.info(f"Could not download previous data info: {e}")
        
        return previous_servers, previous_embeddings, previous_data_info


def find_changed_servers(
    current_servers: list[MCPServerEntry], 
    previous_servers: Optional[list[MCPServerEntry]]
) -> tuple[list[int], dict[str, int]]:
    """
    Find which servers have changed and need new embeddings.
    
    Returns:
        - List of indices of changed/new servers
        - Mapping from server hash to index in previous embeddings
    """
    if not previous_servers:
        # No previous data, all servers are new
        return list(range(len(current_servers))), {}
    
    # Create mapping from hash to index for previous servers
    previous_hash_to_index = {}
    previous_hashes = set()
    for i, server in enumerate(previous_servers):
        server_hash = compute_server_hash(server)
        previous_hash_to_index[server_hash] = i
        previous_hashes.add(server_hash)
    
    # Create mapping for current servers
    current_hashes = set()
    changed_indices = []
    for i, server in enumerate(current_servers):
        server_hash = compute_server_hash(server)
        current_hashes.add(server_hash)
        if server_hash not in previous_hash_to_index:
            changed_indices.append(i)
    
    # Track removed and added servers for monitoring
    removed_servers = previous_hashes - current_hashes
    added_servers = current_hashes - previous_hashes
    
    logger.info(f"Server changes: {len(added_servers)} added, {len(removed_servers)} removed, {len(changed_indices)} total changed/new")
    if removed_servers:
        logger.info(f"Removed {len(removed_servers)} servers (embeddings will be discarded)")
    if added_servers:
        logger.info(f"Added {len(added_servers)} new servers (embeddings will be generated)")
    
    return changed_indices, previous_hash_to_index


async def generate_embeddings_incremental(
    servers: list[MCPServerEntry],
    previous_embeddings: Optional[np.ndarray],
    previous_servers: Optional[list[MCPServerEntry]]
) -> np.ndarray:
    """Generate embeddings incrementally, reusing unchanged ones."""
    
    changed_indices, previous_hash_to_index = find_changed_servers(servers, previous_servers)
    
    if not changed_indices and previous_embeddings is not None:
        logger.info("No servers changed, reusing all previous embeddings")
        return previous_embeddings
    
    # Initialize semantic search engine
    logger.info(f"Loading sentence transformer model: {DEFAULT_MODEL}")
    search_engine = SemanticSearchEngine()
    # Load model directly without initializing with servers
    from sentence_transformers import SentenceTransformer
    search_engine.model = SentenceTransformer(DEFAULT_MODEL)
    
    # Prepare final embeddings array
    num_servers = len(servers)
    if previous_embeddings is not None:
        embedding_dim = previous_embeddings.shape[1]
    else:
        # Generate one embedding to get dimensions
        sample_text = search_engine._get_server_texts([servers[0]])[0]
        sample_embedding = search_engine.model.encode([sample_text], convert_to_numpy=True)
        embedding_dim = sample_embedding.shape[1]
    
    final_embeddings = np.zeros((num_servers, embedding_dim))
    
    # Copy existing embeddings for unchanged servers
    reused_count = 0
    for i, server in enumerate(servers):
        if i not in changed_indices:
            server_hash = compute_server_hash(server)
            if server_hash in previous_hash_to_index:
                prev_index = previous_hash_to_index[server_hash]
                if previous_embeddings is not None and prev_index < len(previous_embeddings):
                    final_embeddings[i] = previous_embeddings[prev_index]
                    reused_count += 1
    
    logger.info(f"Reused {reused_count} existing embeddings")
    
    # Generate new embeddings for changed servers
    if changed_indices:
        logger.info(f"Generating embeddings for {len(changed_indices)} changed servers...")
        changed_servers = [servers[i] for i in changed_indices]
        changed_texts = search_engine._get_server_texts(changed_servers)
        
        new_embeddings = search_engine.model.encode(
            changed_texts,
            convert_to_numpy=True,
            show_progress_bar=True if len(changed_texts) > 10 else False
        )
        
        # Insert new embeddings into final array
        for idx, server_idx in enumerate(changed_indices):
            final_embeddings[server_idx] = new_embeddings[idx]
        
        logger.info(f"Generated {len(new_embeddings)} new embeddings")
    
    return final_embeddings


async def build_data() -> dict:
    """Main data building function."""
    logger.info("Starting data build process...")
    start_time = time.time()
    
    # Ensure output directory exists
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    
    # Fetch current servers
    current_servers = await fetch_all_servers()
    
    # Compute current hash
    current_hash = compute_servers_hash(current_servers)
    logger.info(f"Current servers hash: {current_hash}")
    
    # Download previous data for incremental processing
    previous_servers, previous_embeddings, previous_data_info = await download_previous_data()
    
    # Check if data has changed
    previous_hash = previous_data_info.get("servers_hash") if previous_data_info else None
    if previous_hash == current_hash:
        logger.info("No changes detected, data is up to date")
        return {
            "changed": False,
            "servers_count": len(current_servers),
            "servers_hash": current_hash,
            "build_time": time.time() - start_time
        }
    
    # Generate embeddings incrementally
    logger.info("Generating embeddings...")
    embeddings = await generate_embeddings_incremental(current_servers, previous_embeddings, previous_servers)
    
    # Save servers data
    logger.info(f"Saving {len(current_servers)} servers to {SERVERS_FILE}")
    with open(SERVERS_FILE, 'w', encoding='utf-8') as f:
        json.dump([asdict(server) for server in current_servers], f, ensure_ascii=False, indent=2)
    
    # Save embeddings
    logger.info(f"Saving embeddings matrix {embeddings.shape} to {EMBEDDINGS_FILE}")
    np.savez_compressed(EMBEDDINGS_FILE, embeddings=embeddings)
    
    # Create data info
    data_info = {
        "servers_count": len(current_servers),
        "servers_hash": current_hash,
        "embeddings_shape": list(embeddings.shape),
        "model_name": DEFAULT_MODEL,
        "embeddings_version": EMBEDDINGS_VERSION,
        "schema_version": CURRENT_SCHEMA_VERSION,
        "build_timestamp": time.time(),
        "build_date": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "sources": [source.name for source in get_all_sources()]
    }
    
    # Save data info
    logger.info(f"Saving data info to {DATA_INFO_FILE}")
    with open(DATA_INFO_FILE, 'w', encoding='utf-8') as f:
        json.dump(data_info, f, indent=2)
    
    build_time = time.time() - start_time
    logger.info(f"Data build completed in {build_time:.1f}s")
    
    return {
        "changed": True,
        "servers_count": len(current_servers),
        "servers_hash": current_hash,
        "embeddings_shape": list(embeddings.shape),
        "build_time": build_time,
        "data_info": data_info
    }


async def main():
    """Main entry point."""
    try:
        result = await build_data()
        
        # Output results for GitHub Actions
        if result["changed"]:
            print(f"✅ Data built successfully!")
            print(f"   Servers: {result['servers_count']}")
            print(f"   Embeddings: {result['embeddings_shape']}")
            print(f"   Build time: {result['build_time']:.1f}s")
            print(f"   Hash: {result['servers_hash']}")
            
            # Set GitHub Actions output
            if "GITHUB_OUTPUT" in os.environ:
                with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                    f.write(f"changed=true\\n")
                    f.write(f"servers_count={result['servers_count']}\\n")
                    f.write(f"servers_hash={result['servers_hash']}\\n")
        else:
            print("✅ No changes detected, data is up to date")
            
            # Set GitHub Actions output
            if "GITHUB_OUTPUT" in os.environ:
                with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                    f.write(f"changed=false\\n")
        
        return 0
        
    except Exception as e:
        logger.error(f"Data build failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))