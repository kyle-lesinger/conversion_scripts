#!/usr/bin/env python3
"""Test the S3 file existence check to understand why files aren't being skipped."""

import sys
import os
sys.path.insert(0, 'convert-files-and-move/scripts')

import boto3
from convert_utilities_improved_fixed import check_s3_file_exists

# Test with the actual files mentioned in the output
s3_client = boto3.client('s3')

test_files = [
    ("nasa-disasters", "drcs_activations_new/Sentinel-2/MNDWI/202504_SevereWx_US_JAN_S2A_MNDWI_merged_2025-04-08_day.tif"),
    ("nasa-disasters", "drcs_activations_new/Sentinel-2/MNDWI/202504_SevereWx_US_JAN_S2C_MNDWI_merged_2025-04-09_day.tif"),
    ("nasa-disasters", "drcs_activations_new/Sentinel-2/MNDWI/202504_SevereWx_US_LZK_S2B_MNDWI_merged_2025-04-07_day.tif"),
]

print("Testing S3 file existence check...")
print("=" * 50)

for bucket, key in test_files:
    try:
        exists = check_s3_file_exists(s3_client, bucket, key)
        status = "✅ EXISTS" if exists else "❌ NOT FOUND"
        print(f"{status}: s3://{bucket}/{key}")
    except Exception as e:
        print(f"ERROR checking s3://{bucket}/{key}: {e}")

print("\n" + "=" * 50)
print("Summary:")
print("If files show as EXISTS but processing still runs, there's a logic issue.")
print("If files show as NOT FOUND, they haven't been uploaded yet or are in a different location.")