#!/usr/bin/env python3
"""
Module for loading and querying DRCS TIF files from pre-analyzed S3 crawler data.

This module provides functions to:
- Load DRCS activation data from JSON files
- Query TIF files from specific directory paths
- List available directories at any level
"""

import json
from pathlib import Path
from typing import List, Dict, Optional, Union


def load_drcs_data(json_path: Union[str, Path] = None) -> Optional[Dict]:
    """
    Load the pre-analyzed DRCS TIF files data from JSON.
    
    Args:
        json_path: Path to the drcs_activations_tif_files.json file.
                  If None, tries common locations.
    
    Returns:
        Dictionary containing DRCS data or None if not found
    """
    if json_path is None:
        # Try common locations
        possible_paths = [
            Path('../../s3-crawler/drcs_activations_tif_files.json'),
            Path('../s3-crawler/drcs_activations_tif_files.json'),
            Path('s3-crawler/drcs_activations_tif_files.json'),
            Path('drcs_activations_tif_files.json'),
        ]
    else:
        possible_paths = [Path(json_path)]
    
    for path in possible_paths:
        if path.exists():
            with open(path, 'r') as f:
                drcs_data = json.load(f)
            print(f"✅ Loaded DRCS data from {path}")
            return drcs_data
    
    print(f"⚠️ DRCS data file not found. Tried paths: {possible_paths}")
    return None


def get_tif_files_from_path(path_old: str, 
                           drcs_data: Dict = None, 
                           dir_base: str = 'drcs_activations',
                           json_path: Union[str, Path] = None) -> List[str]:
    """
    Extract .tif files from the specified path in DRCS data.
    
    Args:
        path_old: Path like 'drcs_activations/202405_Flood_TX/planet'
        drcs_data: The loaded DRCS JSON data (if None, will load it)
        dir_base: Base directory name to strip from path (default: 'drcs_activations')
        json_path: Path to JSON file if drcs_data is None
    
    Returns:
        List of .tif filenames found in that directory
    """
    # Load data if not provided
    if drcs_data is None:
        drcs_data = load_drcs_data(json_path)
    
    if not drcs_data or 'drcs_activations' not in drcs_data:
        return []
    
    # Parse the path
    path_parts = path_old.replace(dir_base, '').strip('/').split('/')
    
    if len(path_parts) < 1:
        print(f"⚠️ Invalid path: {path_old}")
        return []
    
    # Navigate through the JSON structure
    current = drcs_data['drcs_activations']
    
    for part in path_parts:
        if part and part in current:
            current = current[part]
        else:
            print(f"⚠️ Directory '{part}' not found in path: {path_old}")
            
            # Suggest available directories
            if isinstance(current, dict):
                available = [k for k in current.keys() if k not in ['_files', '_metadata']]
                if available:
                    print(f"   Available directories at this level: {', '.join(available[:5])}")
                    if len(available) > 5:
                        print(f"   ... and {len(available) - 5} more")
            return []
    
    # Get files if they exist
    if isinstance(current, dict) and '_files' in current:
        return current['_files']
    else:
        print(f"⚠️ No files found in: {path_old}")
        return []


def list_available_directories(base_path: str = 'drcs_activations',
                              drcs_data: Dict = None,
                              json_path: Union[str, Path] = None) -> List[str]:
    """
    List all available directories at a given path level.
    
    Args:
        base_path: Path to list directories from (e.g., 'drcs_activations/202405_Flood_TX')
        drcs_data: The loaded DRCS JSON data (if None, will load it)
        json_path: Path to JSON file if drcs_data is None
    
    Returns:
        List of directory names available at that path
    """
    # Load data if not provided
    if drcs_data is None:
        drcs_data = load_drcs_data(json_path)
    
    if not drcs_data or 'drcs_activations' not in drcs_data:
        return []
    
    # Navigate to the specified path
    path_parts = base_path.strip('/').split('/')
    current = drcs_data
    
    for part in path_parts:
        if part and part in current:
            current = current[part]
        else:
            print(f"⚠️ Path not found: {base_path}")
            return []
    
    # Get directories (exclude special keys)
    if isinstance(current, dict):
        directories = [k for k in current.keys() if k not in ['_files', '_metadata']]
        return sorted(directories)
    
    return []


def get_files_with_full_paths(path_old: str,
                             drcs_data: Dict = None,
                             dir_base: str = 'drcs_activations',
                             json_path: Union[str, Path] = None) -> List[str]:
    """
    Get .tif files with full S3-style paths prepended.
    
    Args:
        path_old: Path like 'drcs_activations/202405_Flood_TX/planet'
        drcs_data: The loaded DRCS JSON data (if None, will load it)
        dir_base: Base directory name (default: 'drcs_activations')
        json_path: Path to JSON file if drcs_data is None
    
    Returns:
        List of full paths like 'drcs_activations/202405_Flood_TX/planet/file.tif'
    """
    tif_files = get_tif_files_from_path(path_old, drcs_data, dir_base, json_path)
    
    if tif_files:
        return [f"{path_old}/{file}" for file in tif_files]
    return []


def main():
    """Main function for testing the module."""
    # Example usage
    DIR_OLD_BASE = 'drcs_activations'
    EVENT_NAME = '202405_Flood_TX'
    PRODUCT_NAME = 'sentinel1'
    PATH_OLD = f'{DIR_OLD_BASE}/{EVENT_NAME}/{PRODUCT_NAME}'
    
    # Load DRCS data
    drcs_data = load_drcs_data()
    
    if drcs_data:
        # Get TIF files from the specified path
        tif_files = get_tif_files_from_path(PATH_OLD, drcs_data, DIR_OLD_BASE)
        
        if tif_files:
            print(f"\n📁 Found {len(tif_files)} .tif files in {PATH_OLD}:")
            print("\nFirst 10 files:")
            for i, file in enumerate(tif_files[:10], 1):
                print(f"  {i:2d}. {file}")
            if len(tif_files) > 10:
                print(f"  ... and {len(tif_files) - 10} more files")
            
            # Get full paths
            files_to_process = get_files_with_full_paths(PATH_OLD, drcs_data, DIR_OLD_BASE)
            print(f"\n✅ Files ready for processing. Found {len(files_to_process)} files.")
        else:
            print(f"\n❌ No files found in {PATH_OLD}")
        
        # Example: List available directories
        print("\n📂 Available activation events:")
        events = list_available_directories('drcs_activations', drcs_data)
        for event in events[:10]:
            print(f"  - {event}")
        if len(events) > 10:
            print(f"  ... and {len(events) - 10} more")


if __name__ == "__main__":
    main()