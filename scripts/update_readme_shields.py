#!/usr/bin/env python3
"""
README.md server count update script for MCP-MCP.

This script updates the hardcoded server count references in README.md with the current 
count from the latest GitHub release data. It's designed to be run both by GitHub Actions
and manually via justfile commands.

Usage:
    python scripts/update_readme_shields.py
    
The script:
1. Downloads the latest data_info.json from GitHub releases
2. Extracts the current server count
3. Updates README.md with the new count (only if different)
4. Returns appropriate exit codes for automation
"""

import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Optional

import httpx

# GitHub release URLs
GITHUB_RELEASE_BASE = "https://github.com/wojtyniak/mcp-mcp/releases/download/data-latest"
DATA_INFO_URL = f"{GITHUB_RELEASE_BASE}/data_info.json"

# File paths
PROJECT_ROOT = Path(__file__).parent.parent
README_PATH = PROJECT_ROOT / "README.md"
LOCAL_DATA_INFO = PROJECT_ROOT / "dist" / "data_info.json"


async def get_current_server_count() -> Optional[int]:
    """
    Get the current server count from the latest release or local data.
    
    Returns:
        Server count as integer, or None if unable to determine
    """
    # Try local data first (for development)
    if LOCAL_DATA_INFO.exists():
        try:
            with open(LOCAL_DATA_INFO, 'r') as f:
                data = json.load(f)
                count = data.get('servers_count')
                if count:
                    print(f"Using local server count: {count}")
                    return int(count)
        except Exception as e:
            print(f"Failed to read local data info: {e}")
    
    # Try downloading from GitHub release
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(DATA_INFO_URL)
            if response.status_code == 200:
                data = response.json()
                count = data.get('servers_count')
                if count:
                    print(f"Downloaded server count from GitHub: {count}")
                    return int(count)
            else:
                print(f"Failed to download data info: HTTP {response.status_code}")
    except Exception as e:
        print(f"Failed to download data info: {e}")
    
    return None


def extract_server_count_from_readme() -> Optional[int]:
    """
    Extract the current server count from README.md.
    
    Looks for patterns like "1488+ servers" in the text.
    
    Returns:
        Current server count from README, or None if not found
    """
    if not README_PATH.exists():
        print(f"README.md not found at {README_PATH}")
        return None
    
    try:
        content = README_PATH.read_text(encoding='utf-8')
        
        # Find all server count patterns including title
        patterns = [
            r'(\d{1,3}(?:,\d{3})*)\+\s+MCP\s+Servers\s+Available',  # Title pattern
            r'(\d{1,3}(?:,\d{3})*)\+\s+(?:unique\s+)?servers',       # General pattern
        ]
        
        all_counts = []
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                count = int(match.replace(',', ''))
                all_counts.append(count)
        
        if all_counts:
            min_count = min(all_counts)
            print(f"Found server counts: {sorted(set(all_counts))} (using min: {min_count})")
            return min_count
        
        print("No server count pattern found in README.md")
        return None
        
    except Exception as e:
        print(f"Failed to read README.md: {e}")
        return None


def update_readme_server_count(new_count: int) -> bool:
    """
    Update README.md with the new server count.
    
    Args:
        new_count: New server count to use
        
    Returns:
        True if file was modified, False if no changes needed
    """
    if not README_PATH.exists():
        print(f"README.md not found at {README_PATH}")
        return False
    
    try:
        content = README_PATH.read_text(encoding='utf-8')
        original_content = content
        
        # Format the new count with commas for consistency everywhere
        formatted_count = f"{new_count:,}"
        
        # Replace all server count patterns
        patterns_and_replacements = [
            (r'(\d{1,3}(?:,\d{3})*)\+(\s+MCP\s+Servers\s+Available)', f'{formatted_count}+\\2'),  # Title
            (r'(\d{1,3}(?:,\d{3})*)\+(\s+(?:unique\s+)?servers)', f'{formatted_count}+\\2'),       # General
        ]
        
        new_content = content
        for pattern, replacement in patterns_and_replacements:
            new_content = re.sub(pattern, replacement, new_content, flags=re.IGNORECASE)
        changes_made = new_content != content
        
        if changes_made:
            README_PATH.write_text(new_content, encoding='utf-8')
            print(f"Updated README.md with server count: {new_count}")
            return True
        else:
            print("No server count patterns found to update in README.md")
            return False
            
    except Exception as e:
        print(f"Failed to update README.md: {e}")
        return False


async def main() -> int:
    """
    Main entry point for the script.
    
    Returns:
        0 if successful (changes made or no changes needed)
        1 if failed to get server count
        2 if failed to update file
    """
    print("🔄 Updating README.md server count...")
    
    # Get current server count from release data
    current_count = await get_current_server_count()
    if current_count is None:
        print("❌ Failed to get current server count")
        return 1
    
    # Check what's currently in README
    readme_count = extract_server_count_from_readme()
    
    if readme_count == current_count:
        print(f"✅ README.md already has correct server count: {current_count}")
        return 0
    
    # Update README with new count
    success = update_readme_server_count(current_count)
    if success:
        print(f"✅ Successfully updated README.md: {readme_count} → {current_count}")
        return 0
    else:
        print("❌ Failed to update README.md")
        return 2


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)