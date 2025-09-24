#!/usr/bin/env python3
"""
Fixed version of convert_utilities_improved that addresses the striping issue.
The problem was that chunk_size was being modified during iteration, causing gaps.
"""
import os
import shutil
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.windows import Window
from rasterio.enums import Resampling
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
    format_bytes,
    get_available_memory_mb
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


def set_no_data_value(ds):
    """
    Set appropriate nodata value based on data type for a dataset object.

    Args:
        ds: Dataset object with dtype attribute

    Returns:
        Appropriate nodata value for the data type
    """
    print(f"   [NODATA] Data type: {ds.dtype}")
    if ds.dtype == 'uint8':
        # For RGB images (uint8), use 0 as nodata (black pixels)
        nodata_value = 0
        print(f"   [NODATA] Using nodata value {nodata_value} for uint8 data")
    elif ds.dtype == 'uint16':
        # For uint16, use 0 as nodata
        nodata_value = 0
        print(f"   [NODATA] Using nodata value {nodata_value} for uint16 data")
    elif ds.dtype == 'int8':
        # For int8, must use value within -128 to 127 range
        nodata_value = -128
        print(f"   [NODATA] Using nodata value {nodata_value} for int8 data")
    elif ds.dtype == 'int16':
        # For int16, -9999 is fine
        nodata_value = -9999
        print(f"   [NODATA] Using nodata value {nodata_value} for int16 data")
    else:
        # For float32, int32, etc., use -9999
        nodata_value = -9999
        print(f"   [NODATA] Using nodata value {nodata_value} for {ds.dtype} data")

    return nodata_value


def set_no_data_value_src(src):
    """
    Set appropriate nodata value based on data type for a rasterio source.

    Args:
        src: Rasterio source object with dtypes attribute

    Returns:
        Appropriate nodata value for the data type
    """
    print(f"   [NODATA] Data type: {src.dtypes[0]}")
    if src.dtypes[0] == 'uint8':
        # For RGB images (uint8), use 0 as nodata (black pixels)
        nodata_value = 0
        print(f"   [NODATA] Using nodata value {nodata_value} for uint8 data")
    elif src.dtypes[0] == 'uint16':
        # For uint16, use 0 as nodata
        nodata_value = 0
        print(f"   [NODATA] Using nodata value {nodata_value} for uint16 data")
    elif src.dtypes[0] == 'int8':
        # For int8, must use value within -128 to 127 range
        nodata_value = -128
        print(f"   [NODATA] Using nodata value {nodata_value} for int8 data")
    elif src.dtypes[0] == 'int16':
        # For int16, -9999 is fine
        nodata_value = -9999
        print(f"   [NODATA] Using nodata value {nodata_value} for int16 data")
    else:
        # For float32, int32, etc., use -9999
        nodata_value = -9999
        print(f"   [NODATA] Using nodata value {nodata_value} for {src.dtypes[0]} data")

    return nodata_value


def validate_COG(tmp_name):
    """
    Validate if a file is a proper Cloud Optimized GeoTIFF.

    Args:
        tmp_name: Path to the file to validate

    Returns:
        None (prints validation results)
    """
    print(f"   [VALIDATE] Checking COG validity...")
    is_valid_cog, validation_details = validate_cog(tmp_name)

    if is_valid_cog:
        print(f"   [VALIDATE] ✅ Valid COG")
    else:
        print(f"   [VALIDATE] ⚠️ COG validation warnings")
        critical_errors = [e for e in validation_details['errors'] if 'Invalid driver' in e]
        if critical_errors:
            raise ValueError(f"Critical COG validation failed")
        if 'errors' in validation_details:
            for error in validation_details['errors']:
                print(f"      - {error}")
        if 'warnings' in validation_details:
            for warning in validation_details['warnings']:
                print(f"      - {warning}")
    return


def get_predictor_for_dtype(dtype):
    """
    Determine the appropriate predictor based on data type.

    Args:
        dtype: numpy dtype or string representation of dtype

    Returns:
        int: Predictor value (1, 2, or 3)
    """
    dtype_str = str(dtype)

    # Integer types use predictor 2
    if dtype_str in ['uint8', 'uint16', 'uint32', 'int8', 'int16', 'int32']:
        return 2
    # Floating-point types use predictor 3
    elif dtype_str in ['float32', 'float64']:
        return 3
    # Default to no predictor
    else:
        return 1





def adaptive_chunk_size(width, height, bands, dtype, target_memory_mb=None):
    """
    Calculate adaptive chunk size based on current memory availability.
    """
    if target_memory_mb is None:
        available_mb = get_available_memory_mb()
        target_memory_mb = min(available_mb * 0.25, 1000)

    dtype_sizes = {
        'uint8': 1, 'uint16': 2, 'uint32': 4,
        'int8': 1, 'int16': 2, 'int32': 4,
        'float32': 4, 'float64': 8
    }
    bytes_per_pixel = dtype_sizes.get(str(dtype), 4) * bands

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

        if hasattr(s3_client, '_request_signer') and hasattr(s3_client._request_signer, '_credentials'):
            credentials = s3_client._request_signer._credentials

        if not credentials:
            session = boto3.Session()
            credentials = session.get_credentials()

        if credentials:
            os.environ['AWS_ACCESS_KEY_ID'] = credentials.access_key
            os.environ['AWS_SECRET_ACCESS_KEY'] = credentials.secret_key
            if hasattr(credentials, 'token') and credentials.token:
                os.environ['AWS_SESSION_TOKEN'] = credentials.token

            os.environ['GDAL_DISABLE_READDIR_ON_OPEN'] = 'YES'
            os.environ['CPL_VSIL_CURL_ALLOWED_EXTENSIONS'] = '.tif,.tiff,.TIF,.TIFF'
            os.environ['VSI_CACHE'] = 'TRUE'
            os.environ['VSI_CACHE_SIZE'] = '1000000000'

            return True
    except Exception as e:
        print(f"   [WARNING] Could not setup VSI credentials: {e}")
        return False


def process_with_fixed_chunks(src, dst, src_crs, dst_crs, transform, width, height,
                              chunk_size, src_nodata, chunk_config, initial_memory):
    """
    Process file with FIXED chunk size throughout the entire operation.
    This prevents the striping issue caused by changing chunk sizes mid-loop.
    """
    # Calculate fixed grid dimensions at the start
    n_chunks_x = (width + chunk_size - 1) // chunk_size
    n_chunks_y = (height + chunk_size - 1) // chunk_size
    total_chunks = n_chunks_x * n_chunks_y * src.count

    print(f"   [CHUNKS] Processing {total_chunks} chunks ({n_chunks_x}x{n_chunks_y}) with fixed size {chunk_size}x{chunk_size}")

    # Progress bar
    if chunk_config.get('show_progress', True):
        pbar = tqdm(total=total_chunks, desc="Processing chunks", unit="chunks")
    else:
        pbar = None

    # Track memory for adaptive behavior
    high_memory_detected = False
    fallback_chunk_size = max(128, chunk_size // 2)

    for band_idx in range(1, src.count + 1):
        print(f"   [BAND {band_idx}/{src.count}] Processing...")

        # Process with fixed grid positions
        for y_idx in range(n_chunks_y):
            for x_idx in range(n_chunks_x):
                # Calculate actual positions based on fixed chunk size
                y = y_idx * chunk_size
                x = x_idx * chunk_size

                # Calculate actual window size (may be smaller at edges)
                win_width = min(chunk_size, width - x)
                win_height = min(chunk_size, height - y)

                # Check memory and decide on processing approach
                current_memory = get_memory_usage()
                if current_memory > initial_memory * 2 and not high_memory_detected:
                    high_memory_detected = True
                    print(f"\n   [MEMORY] High usage detected ({current_memory:.1f} MB), using memory-safe mode")

                # Process smaller sub-chunks if memory is high
                if high_memory_detected and chunk_config.get('aggressive_gc', True):
                    # Process in smaller sub-chunks but maintain grid alignment
                    sub_chunk_size = fallback_chunk_size

                    for sub_y in range(0, win_height, sub_chunk_size):
                        for sub_x in range(0, win_width, sub_chunk_size):
                            sub_win_width = min(sub_chunk_size, win_width - sub_x)
                            sub_win_height = min(sub_chunk_size, win_height - sub_y)

                            # Window in destination coordinates
                            dst_window = Window(x + sub_x, y + sub_y, sub_win_width, sub_win_height)

                            # Initialize chunk
                            chunk_data = np.full(
                                (sub_win_height, sub_win_width),
                                src_nodata if src_nodata is not None else 0,
                                dtype=src.dtypes[0]
                            )

                            # Reproject sub-chunk
                            reproject(
                                source=rasterio.band(src, band_idx),
                                destination=chunk_data,
                                src_transform=src.transform,
                                src_crs=src_crs,
                                dst_transform=rasterio.windows.transform(dst_window, transform),
                                dst_crs=dst_crs,
                                resampling=Resampling.nearest,
                                src_nodata=src_nodata,
                                dst_nodata=src_nodata
                            )

                            # Fix NaN values
                            chunk_data, _ = check_and_fix_nan_values(
                                chunk_data, src_nodata, src.dtypes[0], band_idx=None
                            )

                            # Write sub-chunk
                            dst.write(chunk_data, band_idx, window=dst_window)

                            del chunk_data
                            gc.collect()
                else:
                    # Normal processing for full chunk
                    window = Window(x, y, win_width, win_height)

                    # Initialize chunk
                    chunk_data = np.full(
                        (win_height, win_width),
                        src_nodata if src_nodata is not None else 0,
                        dtype=src.dtypes[0]
                    )

                    # Reproject chunk
                    reproject(
                        source=rasterio.band(src, band_idx),
                        destination=chunk_data,
                        src_transform=src.transform,
                        src_crs=src_crs,
                        dst_transform=rasterio.windows.transform(window, transform),
                        dst_crs=dst_crs,
                        resampling=Resampling.nearest,
                        src_nodata=src_nodata,
                        dst_nodata=src_nodata
                    )

                    # Fix NaN values
                    chunk_data, _ = check_and_fix_nan_values(
                        chunk_data, src_nodata, src.dtypes[0], band_idx=None
                    )

                    # Write chunk
                    dst.write(chunk_data, band_idx, window=window)

                    del chunk_data

                # Update progress
                if pbar:
                    pbar.update(1)

                # Periodic garbage collection
                if (y_idx * n_chunks_x + x_idx) % 10 == 0:
                    gc.collect()

        # Force cleanup after each band
        if chunk_config.get('aggressive_gc', True):
            gc.collect()
            current_memory = get_memory_usage()
            print(f"      Memory after band {band_idx}: {current_memory:.1f} MB")

    if pbar:
        pbar.close()


def convert_to_proper_CRS_and_cogify_improved_fixed(
    name, BUCKET, cog_filename, cog_data_bucket, cog_data_prefix, s3_client,
    COG_PROFILE=None, local_output_dir=None, chunk_config=None):
    """
    FIXED version that prevents striping issues in large files.

    Key fix: Maintains consistent chunk grid throughout processing.
    """

    # Enhanced default configuration
    if chunk_config is None:
        chunk_config = {
            "default_chunk_size": 512,
            "memory_limit_mb": 500,
            "aggressive_gc": True,
            "use_streaming": True,
            "single_band_mode": False,
            "cleanup_immediate": True,
            "adaptive_chunks": True,
            "max_retries": 3,
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

    try:
        if chunk_config.get('use_streaming', True) and setup_gdal_vsi_credentials(s3_client):
            input_path = f"/vsis3/{BUCKET}/{name}"
            print(f"   [STREAM] Attempting to stream from S3: {input_path}")

            try:
                with rasterio.open(input_path) as test_src:
                    _ = test_src.profile
                print(f"   [STREAM] ✅ Successfully opened file via streaming")
            except Exception as e:
                print(f"   [STREAM] ❌ Streaming failed: {e}")
                print(f"   [STREAM] Falling back to download method")
                input_path = None

        if input_path is None:
            data_download_dir = "data_download"
            os.makedirs(data_download_dir, exist_ok=True)
            local_download_path = os.path.join(data_download_dir, name)

            if os.path.exists(local_download_path):
                print(f"   [CACHE HIT] Using cached file: {local_download_path}")
                input_path = local_download_path
            else:
                print(f"   [DOWNLOAD] Downloading from S3...")
                s3_path_parts = name.split('/')
                local_subdir = os.path.join(data_download_dir, *s3_path_parts[:-1])
                os.makedirs(local_subdir, exist_ok=True)
                s3_client.download_file(BUCKET, name, local_download_path)
                print(f"   [DOWNLOAD] ✅ Saved to cache")
                input_path = local_download_path

        # Process the file
        with rasterio.open(input_path) as src:
            dst_crs = "EPSG:4326"

            # Determine FIXED chunk size for entire operation
            if chunk_config.get('adaptive_chunks', True):
                chunk_size = adaptive_chunk_size(
                    src.width, src.height, src.count, src.dtypes[0],
                    target_memory_mb=chunk_config.get('memory_limit_mb', 500)
                )
                chunk_size = max(
                    chunk_config.get('min_chunk_size', 256),
                    min(chunk_config.get('max_chunk_size', 2048), chunk_size)
                )
                print(f"   [ADAPTIVE] Using FIXED chunk size for entire operation: {chunk_size}x{chunk_size}")
            else:
                chunk_size = chunk_config.get('default_chunk_size', 512)
                print(f"   [CHUNKS] Using FIXED chunk size: {chunk_size}x{chunk_size}")

            # Check if reprojection is needed
            if src.crs and src.crs.to_string() == dst_crs:
                print(f"   [REPROJECT] Already in {dst_crs}, skipping reprojection")
                shutil.copy(input_path, reproject_filename)
            else:
                print(f"   [REPROJECT] Converting to EPSG:4326 using fixed-grid chunked processing...")

                # Calculate transform
                transform, width, height = calculate_default_transform(
                    src.crs, dst_crs, src.width, src.height, *src.bounds
                )

                # Get or set appropriate nodata value
                if src.nodata is not None:
                    src_nodata = src.nodata
                else:
                    # Use helper function to set appropriate nodata
                    src_nodata = set_no_data_value_src(src)

                # Get appropriate predictor for data type
                predictor = get_predictor_for_dtype(src.dtypes[0])

                # Prepare output profile with ZSTD compression
                kwargs = src.meta.copy()
                kwargs.update({
                    'driver': 'GTiff',
                    'compress': 'ZSTD',      # Use ZSTD for better compression
                    'zstd_level': 9,         # Good balance for intermediate file
                    'predictor': predictor,  # Use appropriate predictor for data type
                    'crs': dst_crs,
                    'transform': transform,
                    'width': width,
                    'height': height,
                    'tiled': True,
                    'blockxsize': 512,
                    'blockysize': 512,
                    'nodata': src_nodata
                })

                # Open output and process with FIXED chunks
                with rasterio.open(reproject_filename, 'w', **kwargs) as dst:
                    process_with_fixed_chunks(
                        src, dst, src.crs, dst_crs, transform,
                        width, height, chunk_size, src_nodata,
                        chunk_config, initial_memory
                    )

        # Upload reprojected file directly or create COG
        print(f"   [COGIFY] Preparing file for upload...")

        try:
            # First check if the reprojected file is already a valid COG
            from rio_cogeo.cogeo import cog_validate

            try:
                cog_validate(reproject_filename)
                print(f"   [COG] Reprojected file is already a valid COG!")
                is_valid_cog = True
            except:
                print(f"   [COG] File needs COG optimization")
                is_valid_cog = False

            # Always rebuild as COG with overviews and compression, even if already valid
            # This ensures we have overviews and optimal compression
            if is_valid_cog and 'errors' not in validation_info:
                print(f"   [COG] Reprojected file is already a valid COG, but rebuilding with overviews...")
            else:
                print(f"   [COG] Creating optimized COG using rasterio...")

            # Get file size for progress info
            file_size_mb = os.path.getsize(reproject_filename) / (1024 * 1024)
            print(f"   [COG] Processing {file_size_mb:.1f} MB file...")

            try:
                # Create COG using rasterio with proper tiling and compression
                with rasterio.open(reproject_filename, 'r') as src:
                        # Get the COG profile
                        COG_PROFILE_CONFIG = export_COG_PROFILE() if COG_PROFILE is None else COG_PROFILE

                        # Create profile for COG with maximum ZSTD compression
                        profile = src.profile.copy()

                        # Force ZSTD compression for best file size
                        compress_type = 'zstd'  # Use lowercase for rasterio

                        # Use helper function to determine predictor
                        predictor = get_predictor_for_dtype(src.dtypes[0])
                        print(f"   [COG] Using ZSTD compression with predictor={predictor} for {src.dtypes[0]} data")

                        profile.update({
                            'driver': 'GTiff',
                            'compress': compress_type,    # lowercase for rasterio
                            'zstd_level': 22,             # Maximum compression level
                            'predictor': predictor,       # Appropriate predictor for data type
                            'tiled': True,
                            'blockxsize': 512,
                            'blockysize': 512,
                            'bigtiff': 'YES' if file_size_mb > 3000 else 'IF_SAFER',
                            'num_threads': 'ALL_CPUS'
                        })

                        # Create a temporary local COG file
                        import uuid
                        temp_cog = f"cog_{uuid.uuid4().hex[:8]}.tif"

                        print(f"   [COG] Writing optimized COG...")
                        with rasterio.open(temp_cog, 'w', **profile) as dst:
                            # Copy data band by band
                            for band_idx in range(1, src.count + 1):
                                dst.write(src.read(band_idx), band_idx)

                            # Build overviews for COG
                            print(f"   [COG] Building overviews...")
                            factors = [2, 4, 8, 16, 32]
                            dst.build_overviews(factors, Resampling.average)

                            # Update tags for COG
                            dst.update_tags(ns='rio_overview', resampling='average')

                # Upload the COG to S3
                print(f"   [UPLOAD] Uploading COG to S3...")
                s3_client.upload_file(
                    Filename=temp_cog,
                    Bucket=cog_data_bucket,
                    Key=s3_key
                )
                print(f"   [SUCCESS] ✅ Uploaded to s3://{cog_data_bucket}/{s3_key}")

                # Clean up temp COG file
                if os.path.exists(temp_cog):
                    os.remove(temp_cog)
                    print(f"   [CLEANUP] Removed temporary COG file")

            except Exception as e:
                print(f"   [WARNING] Rasterio COG creation failed: {e}")
                print(f"   [FALLBACK] Uploading reprojected file as-is...")

                # Fallback: Just upload the reprojected file
                s3_client.upload_file(
                    Filename=reproject_filename,
                    Bucket=cog_data_bucket,
                    Key=s3_key
                )
                print(f"   [SUCCESS] ✅ Uploaded to s3://{cog_data_bucket}/{s3_key}")

            # Save locally if specified
            if local_output_dir:
                os.makedirs(local_output_dir, exist_ok=True)
                local_path = os.path.join(local_output_dir, cog_filename)
                shutil.copy(reproject_filename, local_path)
                print(f"   [LOCAL] Saved to {local_path}")

        except ImportError:
            print(f"   [COGIFY] rio-cogeo not available, using fallback method")
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
            print(f"   [RETRY] Retrying with smaller fixed chunks...")

            # Reduce chunk size and retry
            new_config = chunk_config.copy()
            new_config['default_chunk_size'] = max(128, chunk_config.get('default_chunk_size', 512) // 2)
            new_config['memory_limit_mb'] = chunk_config.get('memory_limit_mb', 500) // 2
            new_config['max_retries'] = chunk_config.get('max_retries', 3) - 1
            new_config['single_band_mode'] = True

            gc.collect()

            return convert_to_proper_CRS_and_cogify_improved_fixed(
                name, BUCKET, cog_filename, cog_data_bucket, cog_data_prefix,
                s3_client, COG_PROFILE, local_output_dir, new_config
            )
        else:
            print(f"   [ERROR] Max retries exceeded")
            raise

    except Exception as e:
        print(f"   [ERROR] Unexpected error: {e}")
        raise

    finally:
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


print("✅ Fixed conversion utilities loaded - striping issue resolved!")
print("\nKey fix: Maintains consistent chunk grid throughout processing")
print("Use convert_to_proper_CRS_and_cogify_improved_fixed() for large files")