"""Semantic search functionality for MCP server discovery using sentence transformers."""

import hashlib
import json
import os
from pathlib import Path
from typing import Optional

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from .database import MCPServerEntry
from settings import app_logger

logger = app_logger.getChild(__name__)

# Model configuration
DEFAULT_MODEL = "all-MiniLM-L6-v2"  # Fast, lightweight, good quality
EMBEDDINGS_VERSION = "v1"  # Increment when changing embedding logic


def get_cache_dir() -> Path:
    """Get cache directory following XDG Base Directory Specification."""
    # Try XDG_CACHE_HOME first, fallback to ~/.cache
    xdg_cache_home = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache_home:
        cache_base = Path(xdg_cache_home)
    else:
        cache_base = Path.home() / ".cache"
    
    cache_dir = cache_base / "mcp-mcp" / "embeddings"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


class SemanticSearchEngine:
    """Semantic search engine for MCP servers using sentence transformers."""
    
    def __init__(self, model_name: str = DEFAULT_MODEL):
        self.model_name = model_name
        self.model: Optional[SentenceTransformer] = None
        self.server_embeddings: Optional[np.ndarray] = None
        self.servers: list[MCPServerEntry] = []
        self.embeddings_hash: Optional[str] = None
        
        # Cache directory will be created by get_cache_dir()
    
    def _get_server_texts(self, servers: list[MCPServerEntry]) -> list[str]:
        """Extract text content from servers for embedding."""
        texts = []
        for server in servers:
            # Combine name, description, and category for richer context
            text = f"{server.name}. {server.description}. Category: {server.category}"
            texts.append(text)
        return texts
    
    def _compute_content_hash(self, servers: list[MCPServerEntry]) -> str:
        """Compute hash of server content for cache invalidation."""
        content = []
        for server in servers:
            content.append({
                "name": server.name,
                "description": server.description,
                "category": server.category,
                "url": server.url
            })
        
        # Sort for consistent hashing
        content.sort(key=lambda x: x["name"])
        content_str = json.dumps(content, sort_keys=True)
        
        # Include model name and version in hash
        hash_input = f"{EMBEDDINGS_VERSION}:{self.model_name}:{content_str}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]
    
    def _get_cache_path(self, content_hash: str) -> Path:
        """Get path for cached embeddings file."""
        return get_cache_dir() / f"embeddings_{content_hash}.npy"
    
    def _load_cached_embeddings(self, content_hash: str) -> Optional[np.ndarray]:
        """Load embeddings from cache if available."""
        cache_path = self._get_cache_path(content_hash)
        if cache_path.exists():
            try:
                embeddings = np.load(cache_path)
                logger.debug(f"Loaded cached embeddings from {cache_path}")
                return embeddings
            except Exception as e:
                logger.warning(f"Failed to load cached embeddings: {e}")
                # Delete corrupted cache file
                cache_path.unlink(missing_ok=True)
        return None
    
    def _save_embeddings_to_cache(self, embeddings: np.ndarray, content_hash: str):
        """Save embeddings to cache."""
        cache_path = self._get_cache_path(content_hash)
        try:
            np.save(cache_path, embeddings)
            logger.debug(f"Saved embeddings to cache: {cache_path}")
        except Exception as e:
            logger.warning(f"Failed to save embeddings to cache: {e}")
    
    def _cleanup_old_cache_files(self):
        """Remove old cache files to prevent disk bloat."""
        try:
            cache_dir = get_cache_dir()
            cache_files = list(cache_dir.glob("embeddings_*.npy"))
            # Keep only the most recent 5 cache files
            if len(cache_files) > 5:
                cache_files.sort(key=lambda p: p.stat().st_mtime)
                for old_file in cache_files[:-5]:
                    old_file.unlink()
                    logger.debug(f"Removed old cache file: {old_file}")
        except Exception as e:
            logger.warning(f"Failed to cleanup cache files: {e}")
    
    async def initialize(self, servers: list[MCPServerEntry]):
        """Initialize the semantic search engine with server data."""
        self.servers = servers
        content_hash = self._compute_content_hash(servers)
        self.embeddings_hash = content_hash
        
        # Try to load from cache first
        cached_embeddings = self._load_cached_embeddings(content_hash)
        if cached_embeddings is not None:
            self.server_embeddings = cached_embeddings
            logger.info(f"Using cached embeddings for {len(servers)} servers")
            return
        
        # Load model if not already loaded
        if self.model is None:
            logger.info(f"Loading sentence transformer model: {self.model_name}")
            try:
                self.model = SentenceTransformer(self.model_name)
                logger.info("Model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load model {self.model_name}: {e}")
                raise
        
        # Generate embeddings
        logger.info(f"Generating embeddings for {len(servers)} servers...")
        texts = self._get_server_texts(servers)
        
        try:
            # Generate embeddings in batch for efficiency
            self.server_embeddings = self.model.encode(
                texts,
                convert_to_numpy=True,
                show_progress_bar=True if len(texts) > 10 else False
            )
            logger.info("Embeddings generated successfully")
            
            # Save to cache
            self._save_embeddings_to_cache(self.server_embeddings, content_hash)
            
            # Cleanup old cache files
            self._cleanup_old_cache_files()
            
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise
    
    async def initialize_with_precomputed_embeddings(
        self, 
        servers: list[MCPServerEntry], 
        precomputed_embeddings: np.ndarray
    ):
        """Initialize the semantic search engine with precomputed embeddings."""
        self.servers = servers
        self.server_embeddings = precomputed_embeddings
        
        # Validate that embeddings match server count
        if len(servers) != precomputed_embeddings.shape[0]:
            raise ValueError(
                f"Server count ({len(servers)}) does not match embeddings count "
                f"({precomputed_embeddings.shape[0]})"
            )
        
        # Load model for query encoding (still needed for search)
        if self.model is None:
            logger.info(f"Loading sentence transformer model: {self.model_name}")
            try:
                self.model = SentenceTransformer(self.model_name)
                logger.info("Model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load model {self.model_name}: {e}")
                raise
        
        # Generate a simple hash for the precomputed data
        content_hash = f"precomputed_{len(servers)}_{precomputed_embeddings.shape[1]}"
        self.embeddings_hash = content_hash
        
        logger.info(f"Initialized with precomputed embeddings for {len(servers)} servers")
    
    def semantic_search(
        self, 
        query: str, 
        top_k: int = 10,
        similarity_threshold: float = 0.1
    ) -> list[tuple[MCPServerEntry, float]]:
        """
        Perform semantic search for MCP servers.
        
        Args:
            query: Search query
            top_k: Maximum number of results to return
            similarity_threshold: Minimum similarity score (0-1)
            
        Returns:
            List of (server, similarity_score) tuples, sorted by similarity
        """
        if self.model is None:
            raise RuntimeError("Model not loaded. Call initialize() first.")
        
        if self.server_embeddings is None:
            raise RuntimeError("Server embeddings not available. Call initialize() first.")
        
        # Generate query embedding
        try:
            query_embedding = self.model.encode([query], convert_to_numpy=True)
        except Exception as e:
            logger.error(f"Failed to encode query: {e}")
            return []
        
        # Compute similarities
        try:
            similarities = cosine_similarity(query_embedding, self.server_embeddings)[0]
        except Exception as e:
            logger.error(f"Failed to compute similarities: {e}")
            return []
        
        # Create results with similarity scores
        results = []
        for i, similarity in enumerate(similarities):
            if similarity >= similarity_threshold:
                results.append((self.servers[i], float(similarity)))
        
        # Sort by similarity (highest first) and limit results
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
    
    def is_available(self) -> bool:
        """Check if semantic search is available (model loaded and embeddings ready)."""
        return (
            self.model is not None and 
            self.server_embeddings is not None and 
            len(self.servers) > 0
        )
    
    def get_cache_info(self) -> dict:
        """Get information about the current cache state."""
        cache_dir = get_cache_dir()
        cache_files = list(cache_dir.glob("embeddings_*.npy"))
        current_cache = None
        if self.embeddings_hash:
            current_cache = self._get_cache_path(self.embeddings_hash)
        
        return {
            "cache_dir": str(cache_dir),
            "total_cache_files": len(cache_files),
            "current_cache_file": str(current_cache) if current_cache else None,
            "current_cache_exists": current_cache.exists() if current_cache else False,
            "model_loaded": self.model is not None,
            "embeddings_ready": self.server_embeddings is not None,
            "num_servers": len(self.servers)
        }