#!/usr/bin/env python3
"""
Enhanced version of the Sentinel-2 processing notebook with improved large file handling.
This script shows the key changes needed to update the notebook.
"""

# ============================================================================
# CELL 2 - Updated imports (ADD this to existing imports)
# ============================================================================
"""
# Import the improved conversion function
from convert_utilities_improved import (
    convert_to_proper_CRS_and_cogify_improved,
)
"""

# ============================================================================
# CELL 8 - Enhanced configuration for large files
# ============================================================================
"""
# Define COG profile for rasterio (DO NOT CHANGE)
COG_PROFILE = export_COG_PROFILE()

# Standard chunked processing configuration
CHUNK_CONFIG = {
    "default_chunk_size": 1024,  # Default chunk size in pixels
    "memory_limit_mb": 500,      # Memory limit per chunk in MB
    "show_progress": True,       # Show progress bars
    "enable_memory_monitoring": True  # Monitor memory usage
}

# Enhanced configuration for very large Sentinel-2 files
LARGE_FILE_CONFIG = {
    "default_chunk_size": 256,       # Smaller chunks for large files
    "memory_limit_mb": 250,          # Conservative memory limit
    "aggressive_gc": True,           # Force gc after each band
    "single_band_mode": False,       # Sentinel-2 has multiple bands but manageable
    "use_streaming": True,           # Stream from S3 to avoid download
    "cleanup_immediate": True,       # Delete temp files ASAP
    "adaptive_chunks": True,         # Dynamic chunk sizing
    "max_retries": 3,               # Retry on failure
    "min_chunk_size": 256,
    "max_chunk_size": 1024          # Cap at 1024 for Sentinel-2
}

# Ultra-large file config (for files > 10GB)
ULTRA_LARGE_CONFIG = {
    "default_chunk_size": 128,       # Very small chunks
    "memory_limit_mb": 150,          # Very conservative memory
    "aggressive_gc": True,
    "single_band_mode": True,        # Process bands one at a time
    "use_streaming": True,
    "cleanup_immediate": True,
    "adaptive_chunks": True,
    "max_retries": 5,
    "min_chunk_size": 128,
    "max_chunk_size": 512
}
"""

# ============================================================================
# CELL 11 - Updated simple_process_files function
# ============================================================================
import re
import os
import pandas as pd

def simple_process_files_improved(keys, filter_str, rename_func, target_dir, EVENT_NAME,
                                  use_improved=True, file_size_threshold_gb=5):
    """
    Enhanced wrapper to process files with improved large file handling.

    Args:
        keys: List of all S3 keys
        filter_str: Can be:
            - String to filter files (e.g. 'S1_WTR')
            - Regex pattern object (e.g. re.compile(r'.*S2A.*mosaic'))
            - Callable function that returns True/False
        rename_func: Your custom rename function
        target_dir: Target directory (e.g. "Sentinel-2/NDVI")
        EVENT_NAME: Event name
        use_improved: Whether to use the improved converter (default: True)
        file_size_threshold_gb: Threshold in GB to switch to large file config

    Returns:
        Processing results DataFrame
    """
    # 1. Filter files based on type of filter_str
    if callable(filter_str):
        filtered_files = [i for i in keys if filter_str(i)]
    elif hasattr(filter_str, 'search'):
        filtered_files = [i for i in keys if filter_str.search(i)]
    elif isinstance(filter_str, str) and filter_str.startswith('r"') or filter_str.startswith("r'"):
        pattern = re.compile(filter_str[2:-1])
        filtered_files = [i for i in keys if pattern.search(i)]
    else:
        filtered_files = [i for i in keys if filter_str in i]

    # 2. Test renaming
    print(f"Testing filenames:")
    for f in filtered_files[:5]:  # Show first 5 examples
        print(f"  {rename_func(f, EVENT_NAME)}")
    if len(filtered_files) > 5:
        print(f"  ... and {len(filtered_files) - 5} more files")

    # 3. Setup config
    config = {
        "data_acquisition_method": "s3",
        "raw_data_bucket": BUCKET,
        "raw_data_prefix": PATH_OLD,
        "cog_data_bucket": BUCKET,
        "cog_data_prefix": f'{DIR_NEW_BASE}/{target_dir}',
        "local_output_dir": f"output/{EVENT_NAME}",
        "transformation": {}
    }
    return_bucket_info(config)

    # 4. Process files
    print("\n" + "="*50)
    print(f"🚀 Processing {len(filtered_files)} Files")
    if use_improved:
        print("   Using IMPROVED converter with adaptive memory management")
    else:
        print("   Using standard chunked converter")
    print("="*50)

    def get_file_size_gb(s3_client, bucket, key):
        """Get file size in GB from S3."""
        try:
            response = s3_client.head_object(Bucket=bucket, Key=key)
            size_gb = response['ContentLength'] / (1024**3)
            return size_gb
        except:
            return 0

    def improved_converter(name, BUCKET, cog_filename, cog_data_bucket, cog_data_prefix,
                          s3_client, local_output_dir=None):
        """Wrapper for improved converter with automatic config selection."""
        # Check file size
        file_size_gb = get_file_size_gb(s3_client, BUCKET, name)

        # Select appropriate config based on file size
        if file_size_gb > 10:
            print(f"   📦 Ultra-large file detected ({file_size_gb:.1f} GB), using ULTRA config")
            chunk_config = ULTRA_LARGE_CONFIG
        elif file_size_gb > file_size_threshold_gb:
            print(f"   📦 Large file detected ({file_size_gb:.1f} GB), using LARGE config")
            chunk_config = LARGE_FILE_CONFIG
        else:
            print(f"   📦 Standard file ({file_size_gb:.1f} GB), using standard config")
            chunk_config = CHUNK_CONFIG

        return convert_to_proper_CRS_and_cogify_improved(
            name, BUCKET, cog_filename, cog_data_bucket, cog_data_prefix,
            s3_client, COG_PROFILE, local_output_dir, chunk_config
        )

    def standard_converter(name, BUCKET, cog_filename, cog_data_bucket, cog_data_prefix,
                          s3_client, local_output_dir=None):
        """Standard chunked converter."""
        return convert_to_proper_CRS_and_cogify_chunked(
            name, BUCKET, cog_filename, cog_data_bucket, cog_data_prefix,
            s3_client, COG_PROFILE, local_output_dir, chunk_config=CHUNK_CONFIG
        )

    # Select converter
    if use_improved:
        converter_func = improved_converter
    else:
        converter_func = standard_converter

    # Process files
    results = process_file_batch(
        file_list=filtered_files,
        s3_client=s3_client,
        config=config,
        filename_creator_func=rename_func,
        processing_func=converter_func,
        event_name=EVENT_NAME,
        save_metadata=True,
        save_csv=True,
        verbose=True,
        BUCKET=BUCKET
    )

    print_batch_summary(results)
    return results

# ============================================================================
# CELL 18 - Updated processing call for NDVI files
# ============================================================================
"""
# Process NDVI files with improved large file handling
results1 = simple_process_files_improved(
    keys=keys,
    filter_str=filter_str,
    rename_func=create_cog_filename,
    target_dir="Sentinel-2/NDVI",
    EVENT_NAME=EVENT_NAME,
    use_improved=True,  # Use improved converter
    file_size_threshold_gb=3  # Files > 3GB use large config
)
"""

# ============================================================================
# Additional monitoring function you can add
# ============================================================================
def monitor_processing(results_df):
    """
    Monitor processing results and identify problematic files.

    Args:
        results_df: DataFrame with processing results
    """
    if 'status' in results_df.columns:
        # Check for failures
        failed = results_df[results_df['status'] == 'failed']
        if not failed.empty:
            print("\n⚠️ Failed files:")
            for idx, row in failed.iterrows():
                print(f"  - {row['original_file']}: {row.get('error', 'Unknown error')}")

        # Check for skipped files (already exist)
        skipped = results_df[results_df['status'] == 'skipped']
        if not skipped.empty:
            print(f"\n✅ {len(skipped)} files skipped (already exist in S3)")

        # Memory usage analysis if available
        if 'peak_memory_mb' in results_df.columns:
            print(f"\n📊 Memory Usage Statistics:")
            print(f"  Average: {results_df['peak_memory_mb'].mean():.1f} MB")
            print(f"  Maximum: {results_df['peak_memory_mb'].max():.1f} MB")
            print(f"  Minimum: {results_df['peak_memory_mb'].min():.1f} MB")

        # Processing time analysis if available
        if 'processing_time_s' in results_df.columns:
            total_time = results_df['processing_time_s'].sum()
            print(f"\n⏱️ Processing Time:")
            print(f"  Total: {total_time/60:.1f} minutes")
            print(f"  Average per file: {results_df['processing_time_s'].mean():.1f} seconds")

# ============================================================================
# Example usage for different file types
# ============================================================================
"""
# Process MNDWI files (might be larger)
if mndwi:
    print("\n🌊 Processing MNDWI files...")
    results_mndwi = simple_process_files_improved(
        keys=keys,
        filter_str='MNDWI',
        rename_func=create_cog_filename,
        target_dir="Sentinel-2/MNDWI",
        EVENT_NAME=EVENT_NAME,
        use_improved=True,
        file_size_threshold_gb=3
    )
    monitor_processing(results_mndwi)

# Process True Color files (usually largest)
if true:
    print("\n🎨 Processing True Color files...")
    results_true = simple_process_files_improved(
        keys=keys,
        filter_str='trueColor',
        rename_func=create_cog_filename,
        target_dir="Sentinel-2/RGB",
        EVENT_NAME=EVENT_NAME,
        use_improved=True,
        file_size_threshold_gb=2  # Lower threshold for RGB
    )
    monitor_processing(results_true)
"""

print("✅ Script template for improved Sentinel-2 processing created!")
print("\nKey improvements:")
print("1. Automatic file size detection and config selection")
print("2. S3 streaming support to avoid large downloads")
print("3. Adaptive memory management")
print("4. Automatic retry with smaller chunks on memory errors")
print("5. Skip files that already exist in S3")
print("6. Better monitoring and error handling")