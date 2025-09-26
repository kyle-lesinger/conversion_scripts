#!/usr/bin/env python3
"""
Utilities for COG (Cloud Optimized GeoTIFF) validation and cache management.

This module provides functions for:
- Validating Cloud Optimized GeoTIFF files
- Managing download cache for S3 files
- Checking cache status and clearing cache
"""

import os
import shutil
import numpy as np
from typing import Tuple, Dict, List, Optional


def export_COG_PROFILE(compression_type="zstd"):
    """
    Export COG profile with specified compression type.
    
    Args:
        compression_type: One of "zstd", "lzw", "deflate", "none"
        
    Returns:
        Dictionary with COG profile settings
    """
    base_profile = {
        "driver": "COG",
        "bigtiff": "IF_SAFER",
        "num_threads": "ALL_CPUS"
    }
    
    if compression_type.lower() == "zstd":
        base_profile.update({
            "compress": "zstd",
            "zstd_level": 22  # Reasonable compression level (1-22, higher = more compression)
        })
    elif compression_type.lower() == "lzw":
        base_profile.update({
            "compress": "LZW"
            # LZW doesn't have compression levels
        })
    elif compression_type.lower() == "deflate":
        base_profile.update({
            "compress": "DEFLATE",
            "zlevel": 9  # Deflate compression level (1-9, default 6)
        })
    elif compression_type.lower() == "none":
        # No compression
        pass
    else:
        # Default to ZSTD if unknown type
        base_profile.update({
            "compress": "zstd",
            "zstd_level": 22
        })
    
    return base_profile



def check_cache_status(data_download_dir: str = "data_download") -> Tuple[int, int]:
    """
    Check the status of the download cache.
    
    Args:
        data_download_dir: Directory path for cached downloads
    
    Returns:
        Tuple of (total_files, total_size_in_bytes)
    """
    if not os.path.exists(data_download_dir):
        print(f"📁 Cache directory does not exist: {data_download_dir}/")
        print(f"   Creating cache directory...")
        os.makedirs(data_download_dir, exist_ok=True)
        print(f"✅ Cache directory created: {data_download_dir}/")
        return 0, 0
    
    # Count files and calculate total size
    total_files = 0
    total_size = 0
    file_list = []
    
    for root, dirs, files in os.walk(data_download_dir):
        for file in files:
            if file.endswith('.tif'):
                file_path = os.path.join(root, file)
                file_size = os.path.getsize(file_path)
                total_files += 1
                total_size += file_size
                file_list.append((file_path.replace(data_download_dir + '/', ''), file_size))
    
    print(f"📊 Cache Status:")
    print(f"  - Directory: {data_download_dir}/")
    print(f"  - Total files: {total_files}")
    print(f"  - Total size: {total_size / (1024**3):.2f} GB")
    
    if file_list:
        print(f"\n📁 Cached files (first 10):")
        for file_path, file_size in sorted(file_list)[:10]:
            print(f"  - {file_path} ({file_size / (1024**2):.1f} MB)")
        if len(file_list) > 10:
            print(f"  ... and {len(file_list) - 10} more files")
    
    return total_files, total_size


def clear_cache(confirm: bool = False, data_download_dir: str = "data_download") -> None:
    """
    Clear the download cache.
    
    Args:
        confirm: If True, actually delete the cache. If False, just show warning.
        data_download_dir: Directory path for cached downloads
    """
    if not os.path.exists(data_download_dir):
        print(f"Cache directory does not exist: {data_download_dir}/")
        return
    
    if not confirm:
        print("⚠️ This will delete all cached downloads!")
        print(f"Directory: {data_download_dir}/")
        print("To confirm, run: clear_cache(confirm=True)")
        return
    
    shutil.rmtree(data_download_dir)
    print(f"✅ Cache cleared: {data_download_dir}/ removed")


def check_and_fix_nan_values(data: np.ndarray, nodata_value=None, dtype=None, band_idx=None) -> Tuple[np.ndarray, Dict]:
    """
    Check for and fix NaN, inf, and other invalid values in raster data.

    Args:
        data: numpy array containing the raster data
        nodata_value: the nodata value to use for replacement (if None, will be determined from dtype)
        dtype: the data type of the array (used to determine appropriate nodata value)
        band_idx: optional band index for logging purposes

    Returns:
        tuple: (fixed_data, stats_dict) where fixed_data is the array with invalid values replaced
               and stats_dict contains information about what was found and fixed
    """
    stats = {
        'nan_count': 0,
        'inf_count': 0,
        'neginf_count': 0,
        'invalid_count': 0,
        'total_pixels': data.size,
        'percent_invalid': 0,
        'replacement_value': nodata_value
    }

    # Determine data type if not provided
    if dtype is None:
        dtype = data.dtype

    # Only check for NaN/inf in float types
    if np.issubdtype(dtype, np.floating):
        # Create mask for invalid values
        nan_mask = np.isnan(data)
        inf_mask = np.isinf(data) & (data > 0)
        neginf_mask = np.isinf(data) & (data < 0)

        # Count invalid values
        stats['nan_count'] = np.count_nonzero(nan_mask)
        stats['inf_count'] = np.count_nonzero(inf_mask)
        stats['neginf_count'] = np.count_nonzero(neginf_mask)

        # Combine all invalid masks
        invalid_mask = nan_mask | inf_mask | neginf_mask
        stats['invalid_count'] = np.count_nonzero(invalid_mask)

        # Determine replacement value if not provided
        if nodata_value is None:
            if dtype in [np.float32, np.float64]:
                nodata_value = -9999.0
            else:
                nodata_value = 0

        stats['replacement_value'] = nodata_value

        # Replace invalid values
        if stats['invalid_count'] > 0:
            data = data.copy()  # Don't modify original
            data[invalid_mask] = nodata_value

            stats['percent_invalid'] = (stats['invalid_count'] / stats['total_pixels']) * 100

            # Log the replacement
            band_str = f"Band {band_idx}" if band_idx is not None else "Data"
            print(f"   [NAN_CHECK] {band_str}: Found and replaced {stats['invalid_count']:,} invalid values ({stats['percent_invalid']:.2f}%)")
            if stats['nan_count'] > 0:
                print(f"                - NaN values: {stats['nan_count']:,}")
            if stats['inf_count'] > 0:
                print(f"                - Inf values: {stats['inf_count']:,}")
            if stats['neginf_count'] > 0:
                print(f"                - -Inf values: {stats['neginf_count']:,}")
            print(f"                - Replaced with: {nodata_value}")

    elif np.issubdtype(dtype, np.integer):
        # For integer types, check for sentinel values that might represent undefined
        # This is less common but can happen with certain data sources

        # Determine potential undefined values based on dtype
        if dtype == np.uint8:
            # For uint8, 255 is sometimes used as undefined
            undefined_vals = []  # Usually 0 is used as nodata for uint8
        elif dtype == np.uint16:
            # For uint16, 65535 might be undefined
            undefined_vals = [65535]
        elif dtype == np.int16:
            # For int16, -32768 might be undefined
            undefined_vals = [-32768]
        elif dtype == np.int32:
            # For int32, -2147483648 might be undefined
            undefined_vals = [-2147483648]
        else:
            undefined_vals = []

        # Check for these values only if they seem suspicious (all pixels have this value in a region)
        for val in undefined_vals:
            if val in data:
                count = np.count_nonzero(data == val)
                # Only consider it invalid if it appears in more than 1% of pixels
                # This avoids false positives with legitimate data
                if count > data.size * 0.01:
                    if band_idx is not None:
                        print(f"   [NAN_CHECK] Band {band_idx}: Found {count:,} pixels with suspicious value {val}")

    return data, stats


def validate_cog(filepath: str) -> Tuple[bool, Dict]:
    """
    Validate that a file is a proper Cloud Optimized GeoTIFF.
    
    Args:
        filepath: Path to the file to validate
    
    Returns:
        tuple: (is_valid, details_dict) where is_valid is boolean and 
               details_dict contains validation information
    """
    import rasterio
    from rasterio.env import Env
    
    validation_details = {
        'is_cog': False,
        'has_tiles': False,
        'has_overviews': False,
        'tile_size': None,
        'overview_levels': [],
        'compression': None,
        'driver': None,
        'errors': []
    }
    
    try:
        with Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR'):
            with rasterio.open(filepath) as src:
                # Check driver
                validation_details['driver'] = src.driver
                
                # Check if it's a GeoTIFF
                if src.driver != 'GTiff' and src.driver != 'COG':
                    validation_details['errors'].append(f"Invalid driver: {src.driver}, expected GTiff or COG")
                    return False, validation_details
                
                # Check for tiling
                if src.profile.get('tiled', False):
                    validation_details['has_tiles'] = True
                    validation_details['tile_size'] = (
                        src.profile.get('blockxsize', 0),
                        src.profile.get('blockysize', 0)
                    )
                else:
                    validation_details['errors'].append("File is not tiled")
                
                # Check for overviews
                overviews = src.overviews(1)  # Check band 1
                if overviews:
                    validation_details['has_overviews'] = True
                    validation_details['overview_levels'] = overviews
                else:
                    validation_details['errors'].append("No overviews found")
                
                # Check compression
                compression = src.profile.get('compress', None)
                validation_details['compression'] = compression
                if compression.upper() not in ['DEFLATE', 'LZW', 'ZSTD', 'WEBP', 'JPEG']:
                    validation_details['errors'].append(f"Compression '{compression}' may not be optimal for COG")
                
                # Check if file structure is cloud optimized
                # A COG should have IFD (Image File Directory) offsets arranged properly
                # This is a simplified check - true COG validation would check IFD ordering
                is_likely_cog = (
                    validation_details['has_tiles'] and 
                    validation_details['has_overviews'] and
                    validation_details['compression'] in ['DEFLATE', 'LZW', 'ZSTD', 'WEBP', 'JPEG']
                )
                
                validation_details['is_cog'] = is_likely_cog
                
                # Additional check for internal structure
                if hasattr(src, 'is_tiled') and src.is_tiled:
                    # Check tile size is reasonable (typically 256 or 512)
                    tile_x, tile_y = validation_details['tile_size']
                    if tile_x not in [256, 512, 1024] or tile_y not in [256, 512, 1024]:
                        validation_details['errors'].append(f"Non-standard tile size: {tile_x}x{tile_y}")
                
                return is_likely_cog, validation_details
                
    except Exception as e:
        validation_details['errors'].append(f"Validation error: {str(e)}")
        return False, validation_details


if __name__ == "__main__":
    # Example usage
    print("COG Utilities Module")
    print("=" * 50)
    
    # Check cache status
    print("\nChecking cache status...")
    total_files, total_size = check_cache_status()
    
    if total_files > 0:
        print(f"\nFound {total_files} files totaling {total_size / (1024**3):.2f} GB")