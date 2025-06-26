"""Tests for simple schema versioning."""

import pytest
from .schema_versions import (
    is_version_compatible, validate_data_format, get_compatibility_message, 
    CompatibilityLevel, CURRENT_SCHEMA_VERSION
)


class TestSchemaVersioning:
    """Test simple schema versioning functionality."""
    
    def test_current_version_is_compatible(self):
        """Current schema version should be compatible."""
        compatibility = is_version_compatible(CURRENT_SCHEMA_VERSION)
        assert compatibility == CompatibilityLevel.COMPATIBLE
    
    def test_same_major_version_compatibility(self):
        """Versions in the same major version should be compatible."""
        compatibility = is_version_compatible("1.0")
        assert compatibility == CompatibilityLevel.COMPATIBLE
        
        compatibility = is_version_compatible("1.1")
        assert compatibility == CompatibilityLevel.COMPATIBLE
        
        compatibility = is_version_compatible("1.5")
        assert compatibility == CompatibilityLevel.COMPATIBLE
    
    def test_different_major_version_incompatible(self):
        """Different major versions should be incompatible."""
        compatibility = is_version_compatible("2.0")
        assert compatibility == CompatibilityLevel.INCOMPATIBLE
        
        compatibility = is_version_compatible("0.9")
        assert compatibility == CompatibilityLevel.INCOMPATIBLE
    
    def test_invalid_version_format(self):
        """Invalid version formats should be incompatible."""
        compatibility = is_version_compatible("invalid")
        assert compatibility == CompatibilityLevel.INCOMPATIBLE
        
        compatibility = is_version_compatible("1.2.3.4.5")
        assert compatibility == CompatibilityLevel.INCOMPATIBLE
        
        compatibility = is_version_compatible("")
        assert compatibility == CompatibilityLevel.INCOMPATIBLE
    
    def test_validate_data_format_valid(self):
        """Valid data format should pass validation."""
        valid_data = {
            "servers_count": 100,
            "embeddings_shape": [100, 384],
            "model_name": "all-MiniLM-L6-v2",
            "build_timestamp": 1234567890,
            "schema_version": "1.0"
        }
        
        error = validate_data_format(valid_data)
        assert error is None
    
    def test_validate_data_format_missing_fields(self):
        """Data with missing required fields should fail validation."""
        invalid_data = {
            "servers_count": 100,
            # Missing other required fields
        }
        
        error = validate_data_format(invalid_data)
        assert error is not None
        assert "Missing required field" in error
    
    def test_incompatible_version_prevents_usage(self):
        """Ensure incompatible versions are properly rejected."""
        # Version 2.0 should be incompatible with v1.x client
        compatibility = is_version_compatible("2.0")
        assert compatibility == CompatibilityLevel.INCOMPATIBLE
        
        # Version 0.5 should be incompatible with v1.x client  
        compatibility = is_version_compatible("0.5")
        assert compatibility == CompatibilityLevel.INCOMPATIBLE
        
        # This ensures fallback to live sources, preventing process breakage
    
    def test_compatibility_messages(self):
        """Test user-friendly compatibility messages."""
        # Compatible version
        message = get_compatibility_message("1.0")
        assert "✅" in message
        assert "compatible" in message
        
        # Incompatible version
        message = get_compatibility_message("2.0")
        assert "⚠️" in message
        assert "incompatible" in message
    
    def test_version_parsing_edge_cases(self):
        """Test edge cases in version parsing."""
        # Single digit versions
        compatibility = is_version_compatible("1")
        assert compatibility == CompatibilityLevel.INCOMPATIBLE
        
        # Leading zeros are OK
        compatibility = is_version_compatible("01.00")
        assert compatibility == CompatibilityLevel.COMPATIBLE


if __name__ == "__main__":
    pytest.main([__file__, "-v"])