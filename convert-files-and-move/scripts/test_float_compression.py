#!/usr/bin/env python3
"""
Test different compression methods for float32 NDVI data.
"""

import rasterio
import numpy as np
import os

def test_compression_methods():
    """Test different compression methods for float32 data."""

    # Create test float32 data similar to NDVI (-1 to 1 range)
    print("Creating test NDVI-like float32 data...")
    width, height = 10000, 10000

    # Simulate NDVI data with realistic patterns
    np.random.seed(42)
    data = np.random.normal(0.3, 0.2, (height, width)).astype('float32')
    data = np.clip(data, -1, 1)  # NDVI range

    # Add some structure (not purely random)
    # Add some smooth gradients
    x = np.linspace(-1, 1, width)
    y = np.linspace(-1, 1, height)
    xx, yy = np.meshgrid(x, y)
    gradient = (xx + yy) * 0.1
    data += gradient
    data = np.clip(data, -1, 1)

    # Add some nodata areas
    mask = np.random.random((height, width)) > 0.9
    data[mask] = -9999  # nodata value

    print(f"Test data shape: {data.shape}")
    print(f"Data type: {data.dtype}")
    print(f"Value range: {data[data != -9999].min():.3f} to {data[data != -9999].max():.3f}")

    # Test different compression methods
    compression_tests = [
        {
            'name': 'ZSTD_predictor2',
            'compress': 'zstd',
            'zstd_level': 22,
            'predictor': 2,
        },
        {
            'name': 'ZSTD_predictor3',
            'compress': 'zstd',
            'zstd_level': 22,
            'predictor': 3,
        },
        {
            'name': 'DEFLATE_predictor3',
            'compress': 'deflate',
            'predictor': 3,
        },
        {
            'name': 'LZW_predictor3',
            'compress': 'lzw',
            'predictor': 3,
        },
    ]

    # Check if LERC is available
    try:
        test_profile = {'driver': 'GTiff', 'compress': 'lerc'}
        test_file = 'test_lerc.tif'
        with rasterio.open(test_file, 'w', width=10, height=10,
                          count=1, dtype='float32', **test_profile) as dst:
            dst.write(np.zeros((10, 10), dtype='float32'), 1)
        os.remove(test_file)

        # LERC is available, add tests
        compression_tests.extend([
            {
                'name': 'LERC',
                'compress': 'lerc',
                'max_z_error': 0.001,  # Allow 0.001 error for better compression
            },
            {
                'name': 'LERC_ZSTD',
                'compress': 'lerc_zstd',
                'max_z_error': 0.001,
                'zstd_level': 22,
            },
        ])
        print("✅ LERC compression is available")
    except:
        print("⚠️ LERC compression not available")

    print("\n" + "="*60)
    print("COMPRESSION TEST RESULTS:")
    print("="*60)

    results = []

    for test in compression_tests:
        filename = f"test_{test['name']}.tif"

        try:
            profile = {
                'driver': 'GTiff',
                'height': height,
                'width': width,
                'count': 1,
                'dtype': 'float32',
                'crs': 'EPSG:4326',
                'transform': rasterio.transform.from_bounds(0, 0, 1, 1, width, height),
                'nodata': -9999,
                'tiled': True,
                'blockxsize': 512,
                'blockysize': 512,
            }

            # Add compression settings
            profile.update(test)
            profile.pop('name')  # Remove name field

            # Write file
            with rasterio.open(filename, 'w', **profile) as dst:
                dst.write(data, 1)
                dst.build_overviews([2, 4, 8, 16], rasterio.enums.Resampling.average)

            # Check file size
            file_size_mb = os.path.getsize(filename) / (1024 * 1024)

            # Calculate compression ratio
            uncompressed_size = width * height * 4 / (1024 * 1024)  # float32 = 4 bytes
            compression_ratio = (1 - file_size_mb / uncompressed_size) * 100

            results.append({
                'method': test['name'],
                'size_mb': file_size_mb,
                'compression_ratio': compression_ratio
            })

            print(f"\n{test['name']}:")
            print(f"  File size: {file_size_mb:.1f} MB")
            print(f"  Compression ratio: {compression_ratio:.1f}%")
            print(f"  (Uncompressed would be {uncompressed_size:.1f} MB)")

            # Clean up
            os.remove(filename)

        except Exception as e:
            print(f"\n{test['name']}: FAILED - {e}")

    # Show summary
    if results:
        print("\n" + "="*60)
        print("SUMMARY (sorted by file size):")
        print("="*60)

        results.sort(key=lambda x: x['size_mb'])

        for r in results:
            print(f"{r['method']:20s}: {r['size_mb']:8.1f} MB ({r['compression_ratio']:.1f}% compression)")

        best = results[0]
        worst = results[-1]

        print(f"\n✅ Best: {best['method']} - {best['size_mb']:.1f} MB")
        print(f"❌ Worst: {worst['method']} - {worst['size_mb']:.1f} MB")
        print(f"💡 Savings: {worst['size_mb'] - best['size_mb']:.1f} MB "
              f"({(worst['size_mb'] - best['size_mb']) / worst['size_mb'] * 100:.1f}% reduction)")

if __name__ == "__main__":
    test_compression_methods()