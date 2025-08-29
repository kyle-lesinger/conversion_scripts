# Load the pre-analyzed DRCS TIF files data
import json
from pathlib import Path

# Load the drcs_activations_tif_files.json
drcs_json_path = Path('../../s3-crawler/drcs_activations_tif_files.json')

if drcs_json_path.exists():
    with open(drcs_json_path, 'r') as f:
        drcs_data = json.load(f)
    print(f"✅ Loaded DRCS data from {drcs_json_path}")
else:
    print(f"⚠️ DRCS data file not found at {drcs_json_path}")
    drcs_data = None

# Function to get TIF files from a specific directory path
def get_tif_files_from_path(path_old, drcs_data):
    """
    Extract .tif files from the specified path in DRCS data.
    
    Args:
        path_old: Path like 'drcs_activations/202405_Flood_TX/planet'
        drcs_data: The loaded DRCS JSON data
    
    Returns:
        List of .tif filenames found in that directory
    """
    if not drcs_data or 'drcs_activations' not in drcs_data:
        return []
    
    # Parse the path
    path_parts = path_old.replace(DIR_OLD_BASE, '').strip('/').split('/')
    
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
            return []
    
    # Get files if they exist
    if isinstance(current, dict) and '_files' in current:
        return current['_files']
    else:
        print(f"⚠️ No files found in: {path_old}")
        return []

# Get TIF files from the specified PATH_OLD
tif_files = get_tif_files_from_path(PATH_OLD, drcs_data)

if tif_files:
    print(f"\n📁 Found {len(tif_files)} .tif files in {PATH_OLD}:")
    print("\nFirst 10 files:")
    for i, file in enumerate(tif_files[:10], 1):
        print(f"  {i:2d}. {file}")
    if len(tif_files) > 10:
        print(f"  ... and {len(tif_files) - 10} more files")
    
    # Store in a variable for later use
    files_to_process = [f"{PATH_OLD}/{file}" for file in tif_files]
    print(f"\n✅ Files ready for processing. Stored in 'files_to_process' variable.")
else:
    print(f"\n❌ No files found. Please check the PATH_OLD variable.")
    files_to_process = []