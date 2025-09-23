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

                # Open output and process with FIXED chunks
                with rasterio.open(reproject_filename, 'w', **kwargs) as dst:
                    process_with_fixed_chunks(
                        src, dst, src.crs, dst_crs, transform,
                        width, height, chunk_size, src_nodata,
                        chunk_config, initial_memory
                    )

        # Convert to COG
        print(f"   [COGIFY] Creating COG from reprojected file...")

        try:
            from rio_cogeo.cogeo import cog_translate
            from rio_cogeo.profiles import cog_profiles

            print(f"   [COGIFY] Using rio-cogeo for conversion...")

            # For large files, use current directory instead of /tmp
            file_size_mb = os.path.getsize(reproject_filename) / (1024 * 1024)
            use_local_temp = file_size_mb > 1000  # Use local dir for files > 1GB

            if use_local_temp:
                # Create temp file in current working directory
                import uuid
                tmp_name = f"temp_cog_{uuid.uuid4().hex[:8]}.tif"
                print(f"   [TEMP] Using local directory for temp file (file size: {file_size_mb:.1f} MB)")
            else:
                # Use system temp directory for smaller files
                try:
                    with tempfile.NamedTemporaryFile(suffix='.tif', delete=False) as tmp:
                        tmp_name = tmp.name
                    print(f"   [TEMP] Using system temp directory")
                except (OSError, PermissionError) as e:
                    # Fallback to current directory if temp dir fails
                    import uuid
                    tmp_name = f"temp_cog_{uuid.uuid4().hex[:8]}.tif"
                    print(f"   [TEMP] System temp failed ({e}), using local directory")

            COG_PROFILE_CONFIG = export_COG_PROFILE() if COG_PROFILE is None else COG_PROFILE
            compress_type = COG_PROFILE_CONFIG.get('compress', 'DEFLATE').lower()

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
                dst_profile['blockxsize'] = 512
                dst_profile['blockysize'] = 512


            # Get the directory for temp files (current dir if tmp_name has no dir)
            temp_dir = os.path.dirname(tmp_name) if os.path.dirname(tmp_name) else '.'

            # Ensure temp directory exists and is absolute
            if temp_dir == '.':
                temp_dir = os.getcwd()
            else:
                temp_dir = os.path.abspath(temp_dir)
            os.makedirs(temp_dir, exist_ok=True)

            # Set GDAL environment variables for temp files
            os.environ['GDAL_CACHEMAX'] = '512'  # MB
            os.environ['GDAL_TMPDIR'] = temp_dir  # Use same dir as our temp file
            os.environ['TMPDIR'] = temp_dir

            # Save current directory and change to temp directory
            original_dir = os.getcwd()

            try:
                # Change to temp directory so rio-cogeo creates files there
                os.chdir(temp_dir)
                print(f"   [TEMP] Changed working directory to: {temp_dir}")

                # Use absolute paths for source and destination
                abs_reproject_filename = os.path.abspath(os.path.join(original_dir, reproject_filename))
                abs_tmp_name = os.path.abspath(tmp_name)

                cog_translate(
                    abs_reproject_filename,
                    abs_tmp_name,
                    dst_profile,
                    use_cog_driver=True,
                    in_memory=False,
                    quiet=False,
                    config={'GDAL_TMPDIR': temp_dir}  # Also pass as config
                )
            finally:
                # Always restore original directory
                os.chdir(original_dir)
                print(f"   [TEMP] Restored working directory to: {original_dir}")

            # Validate COG (use absolute path)
            validate_cog(abs_tmp_name if 'abs_tmp_name' in locals() else tmp_name)

            # Upload to S3
            print(f"   [UPLOAD] Uploading to S3...")
            upload_file = abs_tmp_name if 'abs_tmp_name' in locals() else tmp_name
            s3_client.upload_file(
                Filename=upload_file,
                Bucket=cog_data_bucket,
                Key=s3_key
            )
            print(f"   [SUCCESS] ✅ Uploaded to s3://{cog_data_bucket}/{s3_key}")

            # Save locally if specified
            if local_output_dir:
                os.makedirs(local_output_dir, exist_ok=True)
                local_path = os.path.join(local_output_dir, cog_filename)
                copy_file = abs_tmp_name if 'abs_tmp_name' in locals() else tmp_name
                shutil.copy(copy_file, local_path)
                print(f"   [LOCAL] Saved to {local_path}")

            # Cleanup COG temp file
            if chunk_config.get('cleanup_immediate', True):
                cleanup_file = abs_tmp_name if 'abs_tmp_name' in locals() else tmp_name
                if os.path.exists(cleanup_file):
                    os.remove(cleanup_file)

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