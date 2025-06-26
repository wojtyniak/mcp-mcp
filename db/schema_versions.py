"""
Simple schema versioning for MCP-MCP precomputed data.

For our small data size (~2MB), we use simple compatibility checking
with fallback to live GitHub sources for incompatible versions.
"""

from enum import Enum


class CompatibilityLevel(Enum):
    """Compatibility levels for schema versions."""
    COMPATIBLE = "compatible"      # Use precomputed data
    INCOMPATIBLE = "incompatible"  # Fall back to live sources


# Current schema configuration
CURRENT_SCHEMA_VERSION = "1.0"
MIN_COMPATIBLE_VERSION = "1.0"
MAX_COMPATIBLE_VERSION = "1.999"  # Support all 1.x versions


def is_version_compatible(data_version: str) -> CompatibilityLevel:
    """
    Check if a data schema version is compatible with this client.
    
    Args:
        data_version: Schema version of the precomputed data
    
    Returns:
        COMPATIBLE if we can use the data, INCOMPATIBLE if fallback needed
    """
    try:
        # Parse version numbers for comparison
        def parse_version(v: str) -> tuple[int, ...]:
            parts = v.split(".")
            if len(parts) < 2:
                raise ValueError(f"Version must have major.minor format: {v}")
            if len(parts) > 3:
                raise ValueError(f"Version has too many parts: {v}")
            return tuple(int(x) for x in parts)
        
        data_ver = parse_version(data_version)
        min_ver = parse_version(MIN_COMPATIBLE_VERSION)
        max_ver = parse_version(MAX_COMPATIBLE_VERSION)
        
        if min_ver <= data_ver <= max_ver:
            return CompatibilityLevel.COMPATIBLE
        else:
            return CompatibilityLevel.INCOMPATIBLE
            
    except (ValueError, AttributeError, TypeError):
        return CompatibilityLevel.INCOMPATIBLE


def validate_data_format(data_info: dict) -> str | None:
    """
    Validate that data_info contains required fields.
    
    Args:
        data_info: Metadata from precomputed data
    
    Returns:
        Error message if validation fails, None if valid
    """
    required_fields = ["servers_count", "embeddings_shape", "model_name", "build_timestamp"]
    
    for field in required_fields:
        if field not in data_info:
            return f"Missing required field: {field}"
    
    # Check schema version format if present
    schema_version = data_info.get("schema_version")
    if schema_version:
        try:
            tuple(int(x) for x in schema_version.split("."))
        except (ValueError, AttributeError):
            return f"Invalid schema version format: {schema_version}"
    
    return None


def get_compatibility_message(data_version: str) -> str:
    """Get user-friendly message about compatibility status."""
    compatibility = is_version_compatible(data_version)
    
    if compatibility == CompatibilityLevel.COMPATIBLE:
        return f"✅ Schema v{data_version} compatible"
    else:
        return f"⚠️ Schema v{data_version} incompatible, using live sources"