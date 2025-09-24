#!/usr/bin/env python3
"""
Analyze why ZSTD compression isn't working effectively for the COG files.
"""

import rasterio
import numpy as np
import os
from rasterio.crs import CRS

def analyze_geotiff(filepath):
    """Analyze a GeoTIFF file to understand compression issues."""

    print(f"\n{'='*60}")
    print(f"Analyzing: {filepath}")
    print(f"{'='*60}")

    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return

    file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
    file_size_gb = file_size_mb / 1024

    with rasterio.open(filepath) as src:
        print(f"\n📊 FILE INFORMATION:")
        print(f"  Size: {file_size_gb:.2f} GB ({file_size_mb:.1f} MB)")
        print(f"  Driver: {src.driver}")
        print(f"  Dimensions: {src.width} x {src.height} pixels")
        print(f"  Bands: {src.count}")
        print(f"  Data type: {src.dtypes[0]}")
        print(f"  CRS: {src.crs}")

        # Check compression
        print(f"\n🗜️ COMPRESSION INFO:")
        print(f"  Compression: {src.compression if src.compression else 'None'}")
        if src.tags().get('COMPRESSION'):
            print(f"  Tag COMPRESSION: {src.tags().get('COMPRESSION')}")

        # Check tiling
        if src.profile.get('tiled'):
            print(f"  Tiled: Yes")
            print(f"  Block size: {src.block_shapes[0] if src.block_shapes else 'N/A'}")
        else:
            print(f"  Tiled: No (striped)")

        # Check for overviews
        print(f"\n🔍 OVERVIEWS:")
        if src.overviews(1):
            print(f"  Overview factors (Band 1): {src.overviews(1)}")
        else:
            print(f"  No overviews found")

        # Check nodata
        print(f"\n❌ NODATA:")
        print(f"  Nodata value: {src.nodata}")

        # Analyze data distribution for each band
        print(f"\n📈 DATA ANALYSIS:")

        total_pixels = src.width * src.height

        for band_idx in range(1, min(src.count + 1, 4)):  # Check up to 3 bands
            print(f"\n  Band {band_idx}:")

            # Sample the data (read a subset for large files)
            if total_pixels > 10000000:  # If more than 10M pixels
                # Read a sample window
                sample_window = rasterio.windows.Window(0, 0,
                                                       min(5000, src.width),
                                                       min(2000, src.height))
                data = src.read(band_idx, window=sample_window)
                print(f"    (Sampling {data.size:,} of {total_pixels:,} pixels)")
            else:
                data = src.read(band_idx)

            # Basic statistics
            if src.nodata is not None:
                valid_data = data[data != src.nodata]
            else:
                valid_data = data.ravel()

            if len(valid_data) > 0:
                print(f"    Min: {np.min(valid_data):.2f}")
                print(f"    Max: {np.max(valid_data):.2f}")
                print(f"    Mean: {np.mean(valid_data):.2f}")
                print(f"    Std Dev: {np.std(valid_data):.2f}")

                # Check data patterns that affect compression
                unique_values = len(np.unique(data))
                print(f"    Unique values in sample: {unique_values:,}")

                # Check for data sparsity
                if src.nodata is not None:
                    nodata_count = np.sum(data == src.nodata)
                    nodata_pct = (nodata_count / data.size) * 100
                    print(f"    Nodata pixels: {nodata_pct:.1f}%")

                # Check if data is mostly zeros
                zero_count = np.sum(data == 0)
                zero_pct = (zero_count / data.size) * 100
                print(f"    Zero values: {zero_pct:.1f}%")

                # Check data entropy (randomness)
                # High entropy = hard to compress
                hist, _ = np.histogram(valid_data, bins=256)
                hist = hist[hist > 0]  # Remove zero bins
                if len(hist) > 0:
                    probs = hist / np.sum(hist)
                    entropy = -np.sum(probs * np.log2(probs + 1e-10))
                    max_entropy = np.log2(len(hist))
                    normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0
                    print(f"    Data entropy: {normalized_entropy:.2%} (higher = harder to compress)")
            else:
                print(f"    No valid data in sample")

        # Check profile for COG compliance
        print(f"\n⚙️ COG PROFILE:")
        profile = src.profile
        important_settings = ['driver', 'dtype', 'compress', 'tiled',
                            'blockxsize', 'blockysize', 'interleave']
        for key in important_settings:
            if key in profile:
                print(f"  {key}: {profile[key]}")

def suggest_improvements(filepath):
    """Suggest improvements for better compression."""

    print(f"\n{'='*60}")
    print("💡 COMPRESSION IMPROVEMENT SUGGESTIONS:")
    print(f"{'='*60}")

    with rasterio.open(filepath) as src:
        dtype = src.dtypes[0]

        print(f"\n1. DATA TYPE OPTIMIZATION:")
        if dtype == 'float64':
            print("   ⚠️ Using float64 - consider float32 for 50% size reduction")
        elif dtype == 'float32':
            print("   ℹ️ Using float32 - check if int16 or uint16 would work")
        elif dtype in ['int32', 'uint32']:
            print("   ⚠️ Using 32-bit integers - consider int16/uint16 if value range allows")
        else:
            print(f"   ✅ Using efficient dtype: {dtype}")

        print(f"\n2. COMPRESSION SETTINGS:")
        if not src.compression:
            print("   ⚠️ No compression applied!")
        elif src.compression.upper() == 'ZSTD':
            print("   ✅ Using ZSTD compression")
            print("   ℹ️ For floating-point data, consider:")
            print("      - Adding predictor=3 for float data")
            print("      - Using LERC compression for lossy but efficient compression")

        print(f"\n3. ADDITIONAL OPTIMIZATIONS:")
        print("   • Remove unnecessary precision (round float values)")
        print("   • Consider lossy compression if appropriate")
        print("   • Use LERC with ZSTD for floating-point data")
        print("   • Apply scale/offset to convert float to int if possible")

# Test files
test_files = [
    "output/202504_SevereWx_US/202504_SevereWx_US_JAN_S2C_NDVI_merged_2025-04-09_day.tif",
    # Add more files as needed
]

for filepath in test_files:
    if os.path.exists(filepath):
        analyze_geotiff(filepath)
        suggest_improvements(filepath)
    else:
        # Try alternate location
        alt_path = f"convert-files-and-move/{filepath}"
        if os.path.exists(alt_path):
            analyze_geotiff(alt_path)
            suggest_improvements(alt_path)
        else:
            print(f"\n❌ File not found: {filepath}")

print("\n" + "="*60)
print("ANALYSIS COMPLETE")
print("="*60)