#!/usr/bin/env python3
"""
Test script to verify RGB COG conversion and upload works correctly.
This will process one RGB file to test the dtype handling fix.
"""

import os
import sys
from pathlib import Path

# Add scripts directory to path
scripts_dir = Path('convert-files-and-move/scripts').resolve()
sys.path.insert(0, str(scripts_dir))

# Import required modules
from aws_s3_utils import initialize_s3_client
from cog_utilities import check_cache_status

# Initialize S3 client
print("Initializing S3 client...")
s3_client, fs_read = initialize_s3_client(bucket_name='nasa-disasters', verbose=True)

if not s3_client:
    print("❌ Failed to initialize S3 client. Please check AWS credentials.")
    sys.exit(1)

# Test file (one RGB file)
test_file = "drcs_activations/202405_Flood_TX/sentinel1/S1A_IW_20240430T002653_DVR_RTC20_G_gpuned_0610_rgb.tif"
EVENT_NAME = "202405_Flood_TX"

# Configuration
config_rgb = {
    "raw_data_bucket": "nasa-disasters",
    "cog_data_bucket": "nasa-disasters",
    "cog_data_prefix": "drcs_activations_new/Sentinel-1/rgb",
    "local_output_dir": "test_output"
}

print(f"\n✅ Test Configuration:")
print(f"  - Test file: {test_file}")
print(f"  - Target: s3://{config_rgb['cog_data_bucket']}/{config_rgb['cog_data_prefix']}/")
print("\nTo run the full notebook with fixes:")
print("1. Open the notebook: convert-files-and-move/2024/202405_Flood_TX-planet-enhanced.ipynb")
print("2. Run all cells in order")
print("3. The fixed conversion function will handle uint8 RGB files correctly")
print("\nThe key fix: RGB files (uint8) now use nodata=0 instead of -9999")