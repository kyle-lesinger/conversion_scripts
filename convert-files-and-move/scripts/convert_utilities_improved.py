#!/usr/bin/env python3
"""
Improved version of convert_utilities with better large file handling.
Optimized for processing files > 10GB with minimal memory usage.
"""
import os
import shutil
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.windows import Window
import gc
from tqdm import tqdm
import numpy as np
import tempfile
import boto3
from botocore.exceptions import ClientError
import subprocess
import psutil

# Import COG and cache utilities
from cog_utilities import (
    check_cache_status,
    clear_cache,
    validate_cog,
    export_COG_PROFILE,
    check_and_fix_nan_values
)

from memory_utils import (
    get_memory_usage,
    calculate_optimal_chunk_size,
    estimate_chunk_memory,
    format_bytes
)


def check_s3_file_exists(s3_client, bucket, key):
    """Check if a file already exists in S3."""
    try:
        s3_client.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            return False
        raise


def get_available_memory_mb():
    """Get available system memory in MB."""
    memory = psutil.virtual_memory()
    return memory.available / 1024 / 1024


def adaptive_chunk_size(width, height, bands, dtype, target_memory_mb=None):
    """
    Calculate adaptive chunk size based on current memory availability.

    Args:
        width: Raster width
        height: Raster height
        bands: Number of bands
        dtype: Data type
        target_memory_mb: Target memory usage (defaults to 25% of available)
    """
    if target_memory_mb is None:
        # Use 25% of available memory by default
        available_mb = get_available_memory_mb()
        target_memory_mb = min(available_mb * 0.25, 1000)  # Cap at 1GB

    # Calculate bytes per pixel
    dtype_sizes = {
        'uint8': 1, 'uint16': 2, 'uint32': 4,
        'int8': 1, 'int16': 2, 'int32': 4,
        'float32': 4, 'float64': 8
    }
    bytes_per_pixel = dtype_sizes.get(str(dtype), 4) * bands

    # Calculate maximum chunk size that fits in target memory
    # Account for both source and destination buffers (2x memory)
    max_pixels = (target_memory_mb * 1024 * 1024) / (bytes_per_pixel * 2)
    chunk_size = int(np.sqrt(max_pixels))

    # Round down to nearest power of 2 for efficiency
    if chunk_size > 0:
        chunk_size = 2 ** int(np.log2(chunk_size))

    # Apply min/max limits
    chunk_size = max(256, min(2048, chunk_size))

    return chunk_size


def setup_gdal_vsi_credentials(s3_client):
    """Setup GDAL VSI credentials for S3 streaming."""
    try:
        credentials = None

        # Try to get credentials from s3_client
        if hasattr(s3_client, '_request_signer') and hasattr(s3_client._request_signer, '_credentials'):
            credentials = s3_client._request_signer._credentials

        # Fallback to boto3 session
        if not credentials:
            session = boto3.Session()
            credentials = session.get_credentials()

        # Set environment variables for GDAL
        if credentials:
            os.environ['AWS_ACCESS_KEY_ID'] = credentials.access_key
            os.environ['AWS_SECRET_ACCESS_KEY'] = credentials.secret_key
            if hasattr(credentials, 'token') and credentials.token:
                os.environ['AWS_SESSION_TOKEN'] = credentials.token

            # GDAL-specific settings
            os.environ['GDAL_DISABLE_READDIR_ON_OPEN'] = 'YES'
            os.environ['CPL_VSIL_CURL_ALLOWED_EXTENSIONS'] = '.tif,.tiff,.TIF,.TIFF'
            os.environ['VSI_CACHE'] = 'TRUE'
            os.environ['VSI_CACHE_SIZE'] = '1000000000'  # 1GB cache

            return True
    except Exception as e:
        print(f"   [WARNING] Could not setup VSI credentials: {e}")
        return False


def convert_to_proper_CRS_and_cogify_improved(
    name, BUCKET, cog_filename, cog_data_bucket, cog_data_prefix, s3_client,
    COG_PROFILE=None, local_output_dir=None, chunk_config=None):
    """
    Improved conversion function with better large file handling.

    Key improvements:
    - Streaming from S3 when possible
    - Adaptive chunk sizing based on available memory
    - Single-band processing option for huge files
    - Immediate cleanup of temporary files
    - Better error handling and retry logic
    """

    # Enhanced default configuration
    if chunk_config is None:
        chunk_config = {
            "default_chunk_size": 512,      # Smaller default for large files
            "memory_limit_mb": 500,          # Memory limit per chunk
            "aggressive_gc": True,           # Force gc after each band
            "use_streaming": True,           # Try to stream from S3
            "single_band_mode": False,       # Process one band at a time
            "cleanup_immediate": True,       # Delete temp files ASAP
            "adaptive_chunks": True,         # Adjust chunk size dynamically
            "max_retries": 3,               # Retry with smaller chunks on failure
            "show_progress": True,
            "enable_memory_monitoring": True,
            "min_chunk_size": 256,
            "max_chunk_size": 2048
        }

    s3_key = f"{cog_data_prefix}/{cog_filename}"

    # Check if file already exists in S3
    print(f"   [CHECK] Checking if file already exists in S3: s3://{cog_data_bucket}/{s3_key}")
    if check_s3_file_exists(s3_client, cog_data_bucket, s3_key):
        print(f"   [SKIP] File already exists in S3, skipping processing: {cog_filename}")
        return

    # Setup directories
    os.makedirs("reproj", exist_ok=True)
    reproject_filename = f"reproj/{cog_filename}"

    # Memory monitoring
    if chunk_config.get('enable_memory_monitoring', True):
        initial_memory = get_memory_usage()
        available_memory = get_available_memory_mb()
        print(f"   [MEMORY] Initial: {initial_memory:.1f} MB, Available: {available_memory:.1f} MB")

    # Determine input path (streaming vs download)
    input_path = None
    cleanup_input = False

    try:
        if chunk_config.get('use_streaming', True) and setup_gdal_vsi_credentials(s3_client):
            # Try streaming from S3
            input_path = f"/vsis3/{BUCKET}/{name}"
            print(f"   [STREAM] Attempting to stream from S3: {input_path}")

            # Test if streaming works
            try:
                with rasterio.open(input_path) as test_src:
                    _ = test_src.profile
                print(f"   [STREAM] ✅ Successfully opened file via streaming")
            except Exception as e:
                print(f"   [STREAM] ❌ Streaming failed: {e}")
                print(f"   [STREAM] Falling back to download method")
                input_path = None

        # Fallback to download if streaming failed or disabled
        if input_path is None:
            data_download_dir = "data_download"
            os.makedirs(data_download_dir, exist_ok=True)
            local_download_path = os.path.join(data_download_dir, name)

            # Check cache
            if os.path.exists(local_download_path):
                print(f"   [CACHE HIT] Using cached file: {local_download_path}")
                input_path = local_download_path
            else:
                # Download from S3
                print(f"   [DOWNLOAD] Downloading from S3...")

                # Create subdirectories
                s3_path_parts = name.split('/')
                local_subdir = os.path.join(data_download_dir, *s3_path_parts[:-1])
                os.makedirs(local_subdir, exist_ok=True)

                s3_client.download_file(BUCKET, name, local_download_path)
                print(f"   [DOWNLOAD] ✅ Saved to cache")
                input_path = local_download_path

        # Process the file
        with rasterio.open(input_path) as src:
            dst_crs = "EPSG:4326"

            # Determine chunk size
            if chunk_config.get('adaptive_chunks', True):
                chunk_size = adaptive_chunk_size(
                    src.width, src.height, src.count, src.dtypes[0],
                    target_memory_mb=chunk_config.get('memory_limit_mb', 500)
                )
                # Apply limits
                chunk_size = max(
                    chunk_config.get('min_chunk_size', 256),
                    min(chunk_config.get('max_chunk_size', 2048), chunk_size)
                )
                print(f"   [ADAPTIVE] Using adaptive chunk size: {chunk_size}x{chunk_size}")
            else:
                chunk_size = chunk_config.get('default_chunk_size', 512)

            # Check if reprojection is needed
            if src.crs and src.crs.to_string() == dst_crs:
                print(f"   [REPROJECT] Already in {dst_crs}, skipping reprojection")
                shutil.copy(input_path, reproject_filename)
            else:
                print(f"   [REPROJECT] Converting to EPSG:4326 using chunked processing...")

                # Calculate transform
                transform, width, height = calculate_default_transform(
                    src.crs, dst_crs, src.width, src.height, *src.bounds
                )

                # Get nodata value
                src_nodata = src.nodata if src.nodata is not None else None

                # Prepare output profile
                kwargs = src.meta.copy()
                kwargs.update({
                    'driver': 'GTiff',
                    'compress': 'DEFLATE',
                    'crs': dst_crs,
                    'transform': transform,
                    'width': width,
                    'height': height,
                    'tiled': True,
                    'blockxsize': 512,
                    'blockysize': 512,
                    'nodata': src_nodata
                })

                # Process based on mode
                if chunk_config.get('single_band_mode', False) and src.count > 1:
                    print(f"   [MODE] Using single-band processing mode")

                    # Process each band separately to minimize memory usage
                    with rasterio.open(reproject_filename, 'w', **kwargs) as dst:
                        for band_idx in range(1, src.count + 1):
                            print(f"   [BAND {band_idx}/{src.count}] Processing band separately...")

                            # Process band in chunks
                            for y in range(0, height, chunk_size):
                                for x in range(0, width, chunk_size):
                                    win_width = min(chunk_size, width - x)
                                    win_height = min(chunk_size, height - y)
                                    window = Window(x, y, win_width, win_height)

                                    # Initialize chunk
                                    chunk_data = np.full((win_height, win_width),
                                                        src_nodata if src_nodata is not None else 0,
                                                        dtype=src.dtypes[0])

                                    # Reproject chunk
                                    reproject(
                                        source=rasterio.band(src, band_idx),
                                        destination=chunk_data,
                                        src_transform=src.transform,
                                        src_crs=src.crs,
                                        dst_transform=rasterio.windows.transform(window, transform),
                                        dst_crs=dst_crs,
                                        resampling=Resampling.nearest,
                                        src_nodata=src_nodata,
                                        dst_nodata=src_nodata
                                    )

                                    # Fix NaN values
                                    chunk_data, _ = check_and_fix_nan_values(
                                        chunk_data, src_nodata, src.dtypes[0]
                                    )

                                    # Write chunk
                                    dst.write(chunk_data, band_idx, window=window)

                                    # Cleanup
                                    del chunk_data
                                    if chunk_config.get('aggressive_gc', True):
                                        gc.collect()

                            # Force cleanup after each band
                            if chunk_config.get('aggressive_gc', True):
                                gc.collect()
                                current_memory = get_memory_usage()
                                print(f"      Memory after band {band_idx}: {current_memory:.1f} MB")
                else:
                    # Standard multi-band processing
                    print(f"   [MODE] Using standard multi-band processing")

                    with rasterio.open(reproject_filename, 'w', **kwargs) as dst:
                        # Calculate chunks
                        n_chunks_x = (width + chunk_size - 1) // chunk_size
                        n_chunks_y = (height + chunk_size - 1) // chunk_size
                        total_chunks = n_chunks_x * n_chunks_y * src.count

                        # Progress bar
                        if chunk_config.get('show_progress', True):
                            pbar = tqdm(total=total_chunks, desc="Processing chunks", unit="chunks")
                        else:
                            pbar = None

                        for band_idx in range(1, src.count + 1):
                            for y in range(0, height, chunk_size):
                                for x in range(0, width, chunk_size):
                                    # Adaptive chunk sizing based on current memory
                                    if chunk_config.get('adaptive_chunks', True):
                                        current_memory = get_memory_usage()
                                        if current_memory > initial_memory * 2:
                                            # Reduce chunk size if memory usage is high
                                            chunk_size = max(256, chunk_size // 2)
                                            print(f"\n   [ADAPTIVE] High memory, reducing chunk size to {chunk_size}")

                                    win_width = min(chunk_size, width - x)
                                    win_height = min(chunk_size, height - y)
                                    window = Window(x, y, win_width, win_height)

                                    # Process chunk
                                    chunk_data = np.full((win_height, win_width),
                                                        src_nodata if src_nodata is not None else 0,
                                                        dtype=src.dtypes[0])

                                    reproject(
                                        source=rasterio.band(src, band_idx),
                                        destination=chunk_data,
                                        src_transform=src.transform,
                                        src_crs=src.crs,
                                        dst_transform=rasterio.windows.transform(window, transform),
                                        dst_crs=dst_crs,
                                        resampling=Resampling.nearest,
                                        src_nodata=src_nodata,
                                        dst_nodata=src_nodata
                                    )

                                    # Fix NaN values
                                    chunk_data, _ = check_and_fix_nan_values(
                                        chunk_data, src_nodata, src.dtypes[0]
                                    )

                                    # Write chunk
                                    dst.write(chunk_data, band_idx, window=window)

                                    # Update progress
                                    if pbar:
                                        pbar.update(1)

                                    # Cleanup
                                    del chunk_data

                                    # Periodic garbage collection
                                    if (y // chunk_size * n_chunks_x + x // chunk_size) % 10 == 0:
                                        gc.collect()

                        if pbar:
                            pbar.close()

        # Convert to COG
        print(f"   [COGIFY] Creating COG from reprojected file...")

        # Try rio-cogeo first for better reliability
        try:
            from rio_cogeo.cogeo import cog_translate
            from rio_cogeo.profiles import cog_profiles

            print(f"   [COGIFY] Using rio-cogeo for conversion...")

            with tempfile.NamedTemporaryFile(suffix='.tif', delete=False) as tmp:
                tmp_name = tmp.name

                # Get COG profile
                COG_PROFILE_CONFIG = export_COG_PROFILE() if COG_PROFILE is None else COG_PROFILE
                compress_type = COG_PROFILE_CONFIG.get('compress', 'DEFLATE').lower()

                # Determine profile
                if compress_type == 'zstd':
                    dst_profile = {
                        'driver': 'COG',
                        'compress': 'zstd',
                        'zstd_level': COG_PROFILE_CONFIG.get('zstd_level', 9),
                        'blockxsize': 512,
                        'blockysize': 512
                    }
                else:
                    dst_profile = cog_profiles.get(compress_type, cog_profiles['deflate'])

                # Convert to COG
                cog_translate(
                    reproject_filename,
                    tmp_name,
                    dst_profile,
                    use_cog_driver=True,
                    in_memory=False,
                    quiet=False
                )

                # Validate COG
                validate_cog(tmp_name)

                # Upload to S3
                print(f"   [UPLOAD] Uploading to S3...")
                s3_client.upload_file(
                    Filename=tmp_name,
                    Bucket=cog_data_bucket,
                    Key=s3_key
                )
                print(f"   [SUCCESS] ✅ Uploaded to s3://{cog_data_bucket}/{s3_key}")

                # Save locally if specified
                if local_output_dir:
                    os.makedirs(local_output_dir, exist_ok=True)
                    local_path = os.path.join(local_output_dir, cog_filename)
                    shutil.copy(tmp_name, local_path)
                    print(f"   [LOCAL] Saved to {local_path}")

                # Cleanup COG temp file
                if chunk_config.get('cleanup_immediate', True):
                    os.remove(tmp_name)

        except ImportError:
            print(f"   [COGIFY] rio-cogeo not available, using fallback method")
            # Fallback implementation here...
            raise NotImplementedError("Fallback COG creation not implemented in this version")

        # Final cleanup
        if chunk_config.get('cleanup_immediate', True) and os.path.exists(reproject_filename):
            os.remove(reproject_filename)
            print(f"   [CLEANUP] Removed temporary reprojection file")

        # Final memory report
        if chunk_config.get('enable_memory_monitoring', True):
            final_memory = get_memory_usage()
            print(f"   [MEMORY] Final: {final_memory:.1f} MB (Change: {final_memory - initial_memory:+.1f} MB)")

    except MemoryError as e:
        print(f"   [ERROR] Memory error encountered: {e}")

        if chunk_config.get('max_retries', 3) > 0:
            print(f"   [RETRY] Retrying with smaller chunks...")

            # Reduce chunk size and retry
            new_config = chunk_config.copy()
            new_config['default_chunk_size'] = chunk_config.get('default_chunk_size', 512) // 2
            new_config['memory_limit_mb'] = chunk_config.get('memory_limit_mb', 500) // 2
            new_config['max_retries'] = chunk_config.get('max_retries', 3) - 1
            new_config['single_band_mode'] = True  # Force single-band mode

            # Cleanup and retry
            gc.collect()

            return convert_to_proper_CRS_and_cogify_improved(
                name, BUCKET, cog_filename, cog_data_bucket, cog_data_prefix,
                s3_client, COG_PROFILE, local_output_dir, new_config
            )
        else:
            print(f"   [ERROR] Max retries exceeded, falling back to ultra_large function")
            # Import and use ultra_large function as fallback
            from convert_utilities import convert_to_proper_CRS_and_cogify_ultra_large
            return convert_to_proper_CRS_and_cogify_ultra_large(
                name, BUCKET, cog_filename, cog_data_bucket, cog_data_prefix,
                s3_client, COG_PROFILE, local_output_dir
            )

    except Exception as e:
        print(f"   [ERROR] Unexpected error: {e}")
        raise

    finally:
        # Ensure cleanup happens
        gc.collect()

        # Clean up any remaining temp files
        temp_files = [
            reproject_filename,
            'tmp_name' in locals() and tmp_name
        ]

        for temp_file in temp_files:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                    print(f"   [CLEANUP] Removed {temp_file}")
                except:
                    pass


print("✅ Improved conversion utilities loaded with enhanced large file handling")