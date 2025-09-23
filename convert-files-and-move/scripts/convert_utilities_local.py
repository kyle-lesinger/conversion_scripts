#!/usr/bin/env python3
import os
import shutil
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.windows import Window
import gc
from tqdm import tqdm
import numpy as np
import tempfile
import rioxarray as rxr
import sys
import shutil


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

def set_no_data_value(ds):
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

def makedirs(name):
    # Create necessary directories
    os.makedirs("reproj", exist_ok=True)
    
    # Create data_download directory for caching
    data_download_dir = "data_download"
    os.makedirs(data_download_dir, exist_ok=True)
    
    # Create subdirectory structure to match S3 path
    s3_path_parts = name.split('/')
    local_subdir = os.path.join(data_download_dir, *s3_path_parts[:-1])
    os.makedirs(local_subdir, exist_ok=True)

    # Local path for the downloaded file (persistent storage)
    local_download_path = os.path.join(data_download_dir, name)
    
    return data_download_dir, local_subdir, local_download_path

def convert_to_proper_CRS_and_cogify_chunked(local_download_path, BUCKET, cog_filename, cog_data_bucket, cog_data_prefix, s3_client, COG_PROFILE, local_output_dir=None, chunk_config=None):
    """
    Convert a file to Cloud Optimized GeoTIFF with proper CRS using chunked processing.
    
    This function includes:
    - Chunked processing for memory efficiency
    - Download caching to avoid re-downloading files
    - CRS reprojection to EPSG:4326
    - COG validation before upload
    - Upload to S3
    - Smart nodata value handling based on data type
    - Memory monitoring and progress tracking
    """
    import shutil
    if chunk_config is None:
        # Default chunk configuration
        chunk_config = {
            "default_chunk_size": 1024,  # Default chunk size in pixels
            "memory_limit_mb": 500,      # Memory limit per chunk in MB
            "show_progress": True,       # Show progress bars
            "enable_memory_monitoring": True  # Monitor memory usage
        }
    
    s3_key = f"{cog_data_prefix}/{cog_filename}"
    reproject_filename = f"reproj/{cog_filename}"

    # Check if file already exists locally
    if os.path.exists(local_download_path):
        print(f"   [CACHE HIT] Using local file: {local_download_path}")
        # Temporary file for processing
        temp_input_file = f"temp_{os.path.basename(local_download_path)}"
        shutil.copy(local_download_path, temp_input_file)
    else:
        sys.exit(f"    [ERROR] Error retrieving local file: {local_download_path} is not a real path.")
    
    # Memory monitoring
    if chunk_config.get('enable_memory_monitoring', True):
        initial_memory = get_memory_usage()
        print(f"   [MEMORY] Initial: {initial_memory:.1f} MB")

    try:
        # Open source file and get metadata
        with rasterio.open(temp_input_file) as src:
            dst_crs = "EPSG:4326"
            chunk_size = chunk_config.get('default_chunk_size', 1024)
            
            # Check if reprojection is needed
            if src.crs and src.crs.to_string() == dst_crs:
                print(f"   [REPROJECT] Already in {dst_crs}, skipping reprojection")
                import shutil
                shutil.copy(temp_input_file, reproject_filename)
            else:
                print(f"   [REPROJECT] Converting to EPSG:4326 using chunked processing...")
                
                # Calculate transform for destination
                transform, width, height = calculate_default_transform(
                    src.crs, dst_crs, src.width, src.height, *src.bounds
                )
                
                # Calculate optimal chunk size
                chunk_size = calculate_optimal_chunk_size(
                    width, height, src.count, src.dtypes[0],
                    memory_limit_mb=chunk_config.get('memory_limit_mb', 500)
                )
                
                # Get nodata value from source or determine based on dtype
                src_nodata = src.nodata if src.nodata is not None else set_no_data_value_src(src)
                
                # Special handling for RGB files with nodata=0
                # RGB files shouldn't use 0 as nodata since black is a valid color
                if src.count == 3 and src_nodata == 0 and src.dtypes[0] == 'uint8':
                    print(f"   [NODATA] RGB file detected with nodata=0, treating as regular RGB without nodata")
                    src_nodata = None
                    kwargs_nodata = None
                else:
                    print(f"   [NODATA] Source nodata value: {src_nodata}")
                    kwargs_nodata = src_nodata
                
                # Prepare output kwargs
                kwargs = src.meta.copy()
                kwargs.update({
                    "driver": "GTiff",  # Use GTiff for intermediate file
                    "compress": "DEFLATE",
                    "crs": dst_crs,
                    "transform": transform,
                    "width": width,
                    "height": height,
                    "tiled": True,
                    "blockxsize": 512,
                    "blockysize": 512,
                    "nodata": kwargs_nodata  # Use the adjusted nodata value
                })
                
                # Create output file
                with rasterio.open(reproject_filename, "w", **kwargs) as dst:
                    # Calculate number of chunks
                    n_chunks_x = (width + chunk_size - 1) // chunk_size
                    n_chunks_y = (height + chunk_size - 1) // chunk_size
                    total_chunks = n_chunks_x * n_chunks_y
                    
                    print(f"   [CHUNKS] Processing {total_chunks} chunks ({n_chunks_x}x{n_chunks_y})")
                    
                    # Process each band
                    for band_idx in range(1, src.count + 1):
                        print(f"   [BAND {band_idx}/{src.count}] Processing...")
                        
                        # Use tqdm for progress tracking if enabled
                        if chunk_config.get('show_progress', True):
                            chunk_iterator = tqdm(
                                total=total_chunks,
                                desc=f"Band {band_idx}",
                                unit="chunks",
                                leave=False
                            )
                        else:
                            chunk_iterator = None
                        
                        # Process chunks
                        for y in range(0, height, chunk_size):
                            for x in range(0, width, chunk_size):
                                # Define window for this chunk
                                win_width = min(chunk_size, width - x)
                                win_height = min(chunk_size, height - y)
                                window = Window(x, y, win_width, win_height)
                                
                                # Create temporary arrays for chunk
                                # Initialize with nodata value to properly handle empty areas
                                if src_nodata is not None:
                                    chunk_data = np.full((win_height, win_width), src_nodata, dtype=src.dtypes[0])
                                else:
                                    chunk_data = np.zeros((win_height, win_width), dtype=src.dtypes[0])
                                
                                # Reproject chunk
                                reproject_kwargs = {
                                    'source': rasterio.band(src, band_idx),
                                    'destination': chunk_data,
                                    'src_transform': src.transform,
                                    'src_crs': src.crs,
                                    'dst_transform': rasterio.windows.transform(window, transform),
                                    'dst_crs': dst_crs,
                                    'resampling': Resampling.nearest,
                                    'wrapdateline': True
                                }
                                
                                # Only add nodata parameters if we have a nodata value
                                if src_nodata is not None:
                                    reproject_kwargs['src_nodata'] = src_nodata
                                    reproject_kwargs['dst_nodata'] = src_nodata
                                
                                reproject(**reproject_kwargs)

                                # Check and fix NaN values in the chunk
                                chunk_data, nan_stats = check_and_fix_nan_values(
                                    chunk_data,
                                    nodata_value=src_nodata,
                                    dtype=src.dtypes[0],
                                    band_idx=band_idx if chunk_config.get('debug_chunks', False) else None
                                )

                                # Verify chunk has data before writing
                                if src_nodata is not None:
                                    non_nodata_count = np.count_nonzero(chunk_data != src_nodata)
                                else:
                                    non_nodata_count = np.count_nonzero(chunk_data)

                                if non_nodata_count > 0 and chunk_config.get('debug_chunks', False):
                                    print(f"     [CHUNK] Band {band_idx}, Window({x},{y},{win_width},{win_height}): {non_nodata_count} non-nodata pixels")

                                # Write chunk to output
                                dst.write(chunk_data, band_idx, window=window)
                                
                                # Update progress
                                if chunk_iterator:
                                    chunk_iterator.update(1)
                                
                                # Force garbage collection periodically
                                if (y // chunk_size * n_chunks_x + x // chunk_size) % 10 == 0:
                                    gc.collect()
                                    
                                    if chunk_config.get('enable_memory_monitoring', True):
                                        current_memory = get_memory_usage()
                                        if current_memory > initial_memory * 2:
                                            print(f"\n   [MEMORY] High usage: {current_memory:.1f} MB, forcing cleanup...")
                                            gc.collect()
                        
                        if chunk_iterator:
                            chunk_iterator.close()
        
        # Verify reprojected data
        print(f"   [VERIFY] Checking reprojected data...")
        with rasterio.open(reproject_filename) as verify_src:
            verify_nodata = verify_src.nodata
            if verify_nodata is None and src.count == 3 and src.dtypes[0] == 'uint8':
                print(f"   [VERIFY] RGB file without nodata - all pixel values are valid")
            
            for band_idx in range(1, verify_src.count + 1):
                # For large images, sample from center where data is more likely to exist
                # The edges often have nodata in reprojected images
                center_x = verify_src.width // 2
                center_y = verify_src.height // 2
                sample_size = min(1000, verify_src.width, verify_src.height)
                
                # Create a centered window
                x_start = max(0, center_x - sample_size // 2)
                y_start = max(0, center_y - sample_size // 2)
                sample_window = Window(x_start, y_start, sample_size, sample_size)
                
                sample_data = verify_src.read(band_idx, window=sample_window)
                data_min, data_max = sample_data.min(), sample_data.max()
                
                # Also get overall band statistics by sampling
                # Sample 10 smaller windows across the image
                total_non_zero = 0
                total_sampled = 0
                sample_locations = [
                    (verify_src.width * 0.25, verify_src.height * 0.25),
                    (verify_src.width * 0.75, verify_src.height * 0.25),
                    (verify_src.width * 0.25, verify_src.height * 0.75),
                    (verify_src.width * 0.75, verify_src.height * 0.75),
                    (verify_src.width * 0.5, verify_src.height * 0.5),
                ]
                
                for sx, sy in sample_locations:
                    try:
                        small_win = Window(int(sx)-50, int(sy)-50, 100, 100)
                        small_data = verify_src.read(band_idx, window=small_win)
                        if verify_nodata is not None:
                            total_non_zero += np.count_nonzero(small_data != verify_nodata)
                        else:
                            total_non_zero += np.count_nonzero(small_data)
                        total_sampled += small_data.size
                    except:
                        pass
                
                # Report both center sample and distributed samples
                if verify_nodata is not None:
                    non_zero_count = np.count_nonzero(sample_data != verify_nodata)
                else:
                    non_zero_count = np.count_nonzero(sample_data)
                
                print(f"   [VERIFY] Band {band_idx}: min={data_min}, max={data_max}, center sample non-zero={non_zero_count}/{sample_data.size}")
                
                if total_sampled > 0:
                    estimated_percent = (total_non_zero / total_sampled) * 100
                    print(f"            Estimated data coverage: {estimated_percent:.1f}% (from distributed samples)")
                
                if non_zero_count == 0 and total_non_zero == 0:
                    print(f"   [WARNING] Band {band_idx} appears to have no data after reprojection!")
        
        # COGify & upload
        print(f"   [COGIFY] Creating COG from reprojected file...")
        
        # Use rasterio to create COG
        with rasterio.open(reproject_filename) as src:
            
            # First create a temporary regular GeoTIFF with chunked processing
            profile = src.profile.copy()
            profile.update({
                'driver': 'GTiff',  # Regular GeoTIFF, not COG
                'compress': 'NONE',  # No compression for temp file to preserve data integrity
                'tiled': True,
                'blockxsize': 512,
                'blockysize': 512
            })
            profile['nodata'] = set_no_data_value_src(src)
            
            # Auto-detect and set predictor based on data type
            predictor = get_predictor_for_dtype(src.dtypes[0])
            profile['predictor'] = predictor
            print(f"   [PREDICTOR] Data type: {src.dtypes[0]}, using PREDICTOR={predictor}")
            
            # Create temporary file for regular GeoTIFF
            with tempfile.NamedTemporaryFile(suffix='_temp.tif', delete=False) as tmp_tiff:
                temp_tiff_name = tmp_tiff.name
                
                # Write regular GeoTIFF using chunked approach
                print(f"   [WRITE] Writing temporary GeoTIFF with chunked processing...")
                with rasterio.open(temp_tiff_name, 'w', **profile) as dst:
                    # Process in chunks to avoid memory issues
                    for band_idx in range(1, src.count + 1):
                        for y in range(0, src.height, chunk_size):
                            for x in range(0, src.width, chunk_size):
                                win_width = min(chunk_size, src.width - x)
                                win_height = min(chunk_size, src.height - y)
                                window = Window(x, y, win_width, win_height)

                                data = src.read(band_idx, window=window)

                                # Check and fix NaN values before writing to COG
                                data, nan_stats = check_and_fix_nan_values(
                                    data,
                                    nodata_value=src.nodata,
                                    dtype=src.dtypes[0],
                                    band_idx=None  # Suppress detailed logging during final write
                                )

                                dst.write(data, band_idx, window=window)
            
            # Now convert the complete GeoTIFF to COG using rio-cogeo for better compatibility
            print(f"   [CONVERT] Converting GeoTIFF to COG...")
            
            # Check if rio-cogeo is available, otherwise use direct method
            try:
                from rio_cogeo.cogeo import cog_translate
                from rio_cogeo.profiles import cog_profiles
                
                # Use rio-cogeo for conversion (more reliable with compression)
                print(f"   [CONVERT] Using rio-cogeo for conversion...")
                with tempfile.NamedTemporaryFile(suffix='.tif', delete=False) as tmp:
                    tmp_name = tmp.name
                    
                    # Get compression settings from COG_PROFILE
                    COG_PROFILE_CONFIG = export_COG_PROFILE() if COG_PROFILE is None else COG_PROFILE
                    compress_type = COG_PROFILE_CONFIG.get('compress', 'DEFLATE').lower()
                    
                    # Select appropriate profile
                    if compress_type == 'zstd':
                        # Use custom profile for ZSTD
                        dst_profile = {
                            'driver': 'COG',
                            'compress': 'zstd',
                            'zstd_level': COG_PROFILE_CONFIG.get('zstd_level', 9),
                            'predictor': predictor,
                            'blockxsize': 512,
                            'blockysize': 512
                        }
                    elif compress_type == 'lzw':
                        dst_profile = cog_profiles.get('lzw')
                        dst_profile['predictor'] = predictor,
                        dst_profile['blockxsize'] =  512
                        dst_profile['blockysize'] =  512
                    else:
                        dst_profile = cog_profiles.get('deflate')
                        dst_profile['predictor'] = predictor,
                        dst_profile['blockxsize'] =  512
                        dst_profile['blockysize'] =  512
                    
                    # Translate to COG
                    cog_translate(
                        temp_tiff_name,
                        tmp_name,
                        dst_profile,
                        use_cog_driver=True,  # Use GDAL COG driver if available
                        in_memory=False,
                        quiet=False
                    )
                    
            except ImportError:
                # Fallback to direct COG writing if rio-cogeo not available
                print(f"   [CONVERT] rio-cogeo not available, using direct COG writing...")
                with tempfile.NamedTemporaryFile(suffix='.tif', delete=False) as tmp:
                    tmp_name = tmp.name
                    
                    # Read the temporary GeoTIFF and write as COG
                    with rasterio.open(temp_tiff_name) as src_temp:
                        # Get the COG profile from config
                        COG_PROFILE_CONFIG = export_COG_PROFILE() if COG_PROFILE is None else COG_PROFILE
                        
                        # Create COG profile
                        cog_profile = src_temp.profile.copy()
                        cog_profile.update(COG_PROFILE_CONFIG)
                        cog_profile.update({
                            'predictor': predictor,
                            'tiled': True,
                            'blockxsize': 512,
                            'blockysize': 512,
                            'nodata': src_temp.nodata  # Preserve nodata value from source
                        })
                        
                        # Write COG with all data at once
                        print(f"   [WRITE] Writing final COG...")
                        with rasterio.open(tmp_name, 'w', **cog_profile) as dst_cog:
                            # Write all bands at once
                            for band_idx in range(1, src_temp.count + 1):
                                data = src_temp.read(band_idx)

                                # Check and fix NaN values
                                data, nan_stats = check_and_fix_nan_values(
                                    data,
                                    nodata_value=src_temp.nodata,
                                    dtype=src_temp.dtypes[0],
                                    band_idx=None  # Will log only if invalid values found
                                )

                                # Log if we found invalid values
                                if nan_stats.get('invalid_count', 0) > 0:
                                    print(f"   [NAN_CHECK] Band {band_idx}: Fixed {nan_stats['invalid_count']} invalid values")

                                # Verify data before writing
                                if np.all(data == 0) or (src_temp.nodata is not None and np.all(data == src_temp.nodata)):
                                    print(f"   [WARNING] Band {band_idx} appears to be all nodata/zeros!")
                                dst_cog.write(data, band_idx)
                
            # Clean up temporary GeoTIFF
            if os.path.exists(temp_tiff_name):
                os.remove(temp_tiff_name)
                
                # Validate COG
                validate_COG(tmp_name)
                
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
                    import shutil
                    shutil.copy(tmp_name, local_path)
        
        # Final memory report
        if chunk_config.get('enable_memory_monitoring', True):
            final_memory = get_memory_usage()
            print(f"   [MEMORY] Final: {final_memory:.1f} MB (Change: {final_memory - initial_memory:+.1f} MB)")
            
    except Exception as e:
        print(f"   [ERROR] Failed: {str(e)}")
        raise
            
    finally:
        # Clean up temporary files
        for temp_file in [temp_input_file, reproject_filename]:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        if 'tmp_name' in locals() and os.path.exists(tmp_name):
            os.remove(tmp_name)
        
        # Force final garbage collection
        gc.collect()

    print("✅ Chunked COG conversion function defined with memory-efficient processing")


def convert_to_proper_CRS_and_cogify_ultra_large(name, BUCKET, cog_filename, cog_data_bucket, cog_data_prefix, s3_client, COG_PROFILE,
                                            local_output_dir=None, chunk_config=None):
    """
    Convert ultra-large files to Cloud Optimized GeoTIFF using GDAL's streaming capabilities.
    
    Optimized for files that are too large to fit in memory (10GB+).
    Uses GDAL command-line tools for efficient processing without loading data into Python memory.
    """
    import subprocess
    import tempfile
    import os
    import boto3
    from pathlib import Path
    
    if chunk_config is None:
        chunk_config = {
            "use_vsi": True,  # Use GDAL's virtual file system
            "gdal_cache_mb": 8192,  # 8GB GDAL cache
            "num_threads": "ALL_CPUS",
            "enable_memory_monitoring": True
        }
    
    s3_key = f"{cog_data_prefix}/{cog_filename}"
    reproject_filename = f"reproj/{cog_filename}"

    if hasattr(s3_client._client_config.credentials, 'token'):
        os.environ['AWS_SESSION_TOKEN'] = s3_client._client_config.credentials.token
    
    # Memory monitoring
    if chunk_config.get('enable_memory_monitoring', True):
        initial_memory = get_memory_usage()
        print(f"   [MEMORY] Initial: {initial_memory:.1f} MB")
    
    try:
        # Use GDAL VSI for S3 access
        if chunk_config.get('use_vsi', True):
            # Direct S3 access without downloading
            input_path = f"/vsis3/{BUCKET}/{name}"
            print(f"   [VSI] Using GDAL virtual file system for S3 access")
        else:
            # Fallback to download if VSI fails
            data_download_dir, local_subdir, local_download_path = makedirs(name)
            if os.path.exists(local_download_path):
                print(f"   [CACHE HIT] Using cached file: {local_download_path}")
                input_path = local_download_path
            else:
                print(f"   [DOWNLOAD] Downloading from S3...")
                s3_client.download_file(BUCKET, name, local_download_path)
                input_path = local_download_path
        
        # Check source file info using gdalinfo
        print(f"   [INFO] Getting source file information...")
        info_cmd = ["gdalinfo", "-json", input_path]
        info_result = subprocess.run(info_cmd, capture_output=True, text=True)
        
        if info_result.returncode != 0:
            raise Exception(f"Failed to read file info: {info_result.stderr}")
        
        import json
        file_info = json.loads(info_result.stdout)
        src_crs = file_info.get('coordinateSystem', {}).get('wkt', '')
        
        # Create temporary output file
        with tempfile.NamedTemporaryFile(suffix='_cog.tif', delete=False) as tmp:
            output_path = tmp.name
        
        # Build GDAL command for COG creation with reprojection
        print(f"   [PROCESS] Converting to COG with EPSG:4326...")
        
        # Determine compression settings
        COG_PROFILE_CONFIG = export_COG_PROFILE() if COG_PROFILE is None else COG_PROFILE
        compress = COG_PROFILE_CONFIG.get('compress', 'DEFLATE').upper()
        
        # Build gdal_translate command
        cmd = [
            "gdal_translate",
            "-of", "COG",
            "-co", f"COMPRESS={compress}",
            "-co", "BIGTIFF=YES",  # Essential for large files
            "-co", "BLOCKSIZE=512",  # Good for cloud storage
            "-co", "OVERVIEWS=IGNORE_EXISTING",  # Don't rebuild if they exist
            "-co", f"NUM_THREADS={chunk_config.get('num_threads', 'ALL_CPUS')}",
            "-co", "SPARSE_OK=TRUE",  # Handle sparse data efficiently
            "--config", "GDAL_CACHEMAX", str(chunk_config.get('gdal_cache_mb', 8192)),
            "--config", "GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR",
            "--config", "CPL_VSIL_CURL_CHUNK_SIZE", "10485760",  # 10MB chunks for S3
            "--config", "GDAL_HTTP_MULTIPLEX", "YES",
            "--config", "GDAL_HTTP_VERSION", "2",
        ]
        
        # Add compression-specific options
        if compress == "ZSTD":
            cmd.extend(["-co", f"ZSTD_LEVEL={COG_PROFILE_CONFIG.get('zstd_level', 9)}"])
        
        # Add predictor based on data type (check from file info)
        if 'bands' in file_info and file_info['bands']:
            dtype = file_info['bands'][0].get('type', 'Byte')
            if dtype in ['Int16', 'UInt16', 'Int32', 'UInt32', 'Float32', 'Float64']:
                cmd.extend(["-co", "PREDICTOR=2"])
            else:
                cmd.extend(["-co", "PREDICTOR=1"])
        
        # Handle nodata
        if 'bands' in file_info and file_info['bands']:
            nodata = file_info['bands'][0].get('noDataValue')
            if nodata is not None:
                cmd.extend(["-a_nodata", str(nodata)])
        
        # Check if reprojection is needed
        if "EPSG:4326" not in src_crs and "WGS 84" not in src_crs:
            print(f"   [REPROJECT] Source is not in EPSG:4326, using gdalwarp...")
            
            # Use gdalwarp for reprojection
            with tempfile.NamedTemporaryFile(suffix='_warped.tif', delete=False) as warp_tmp:
                warp_output = warp_tmp.name
            
            warp_cmd = [
                "gdalwarp",
                "-t_srs", "EPSG:4326",
                "-r", "bilinear",  # Good for continuous data
                "-multi",  # Use multiple threads
                "-wo", f"NUM_THREADS={chunk_config.get('num_threads', 'ALL_CPUS')}",
                "-wo", f"GDAL_CACHEMAX={chunk_config.get('gdal_cache_mb', 8192)}",
                "-co", "TILED=YES",
                "-co", "COMPRESS=LZW",  # Light compression for temp file
                "-co", "BIGTIFF=YES",
                "--config", "GDAL_CACHEMAX", str(chunk_config.get('gdal_cache_mb', 8192)),
                input_path,
                warp_output
            ]
            
            print(f"   [WARP] Running: {' '.join(warp_cmd[:6])}...")
            warp_result = subprocess.run(warp_cmd, capture_output=True, text=True)
            
            if warp_result.returncode != 0:
                raise Exception(f"Warping failed: {warp_result.stderr}")
            
            # Now convert warped file to COG
            cmd.extend([warp_output, output_path])
        else:
            # Direct conversion to COG
            cmd.extend([input_path, output_path])
        
        # Run the conversion
        print(f"   [CONVERT] Running: {' '.join(cmd[:6])}...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"COG creation failed: {result.stderr}")
        
        # Clean up warped file if it exists
        if 'warp_output' in locals() and os.path.exists(warp_output):
            os.remove(warp_output)
        
        # Validate the output
        print(f"   [VALIDATE] Checking COG validity...")
        validate_cmd = ["gdalinfo", "-checksum", output_path]
        validate_result = subprocess.run(validate_cmd, capture_output=True, text=True)

        if validate_result.returncode == 0:
            print(f"   [VALIDATE] ✅ COG is valid")
        else:
            print(f"   [VALIDATE] ⚠️ Warning: COG validation had issues")

        # Check for NaN values in the output file
        print(f"   [NAN_CHECK] Checking output for invalid values...")
        try:
            with rasterio.open(output_path, 'r+') as dst:
                found_nan = False
                for band_idx in range(1, dst.count + 1):
                    # Read small chunks to check for NaN values in large files
                    for y in range(0, dst.height, 4096):
                        for x in range(0, dst.width, 4096):
                            win_width = min(4096, dst.width - x)
                            win_height = min(4096, dst.height - y)
                            window = Window(x, y, win_width, win_height)

                            data = dst.read(band_idx, window=window)

                            # Check and fix NaN values
                            fixed_data, nan_stats = check_and_fix_nan_values(
                                data,
                                nodata_value=dst.nodata,
                                dtype=dst.dtypes[0],
                                band_idx=None  # Suppress per-chunk logging
                            )

                            if nan_stats['invalid_count'] > 0:
                                found_nan = True
                                dst.write(fixed_data, band_idx, window=window)

                if found_nan:
                    print(f"   [NAN_CHECK] Fixed invalid values in output file")
        except Exception as e:
            print(f"   [NAN_CHECK] Warning: Could not check for NaN values: {e}")
        
        # Upload to S3
        print(f"   [UPLOAD] Uploading to S3...")
        
        # For very large files, use multipart upload
        file_size = os.path.getsize(output_path)
        if file_size > 100 * 1024 * 1024:  # 100MB
            print(f"   [UPLOAD] Large file ({file_size / 1024 / 1024:.1f} MB), using multipart upload...")
            
            # Configure multipart upload
            config = boto3.s3.transfer.TransferConfig(
                multipart_threshold=1024 * 25,  # 25MB
                max_concurrency=10,
                multipart_chunksize=1024 * 25,
                use_threads=True
            )
            
            s3_client.upload_file(
                Filename=output_path,
                Bucket=cog_data_bucket,
                Key=s3_key,
                Config=config
            )
        else:
            s3_client.upload_file(
                Filename=output_path,
                Bucket=cog_data_bucket,
                Key=s3_key
            )
        
        print(f"   [SUCCESS] ✅ Uploaded to s3://{cog_data_bucket}/{s3_key}")
        
        # Save locally if specified
        if local_output_dir:
            os.makedirs(local_output_dir, exist_ok=True)
            local_path = os.path.join(local_output_dir, cog_filename)
            import shutil
            shutil.move(output_path, local_path)
            print(f"   [LOCAL] Saved to {local_path}")
        else:
            # Clean up output file
            os.remove(output_path)
        
        # Final memory report
        if chunk_config.get('enable_memory_monitoring', True):
            final_memory = get_memory_usage()
            print(f"   [MEMORY] Final: {final_memory:.1f} MB (Change: {final_memory - initial_memory:+.1f} MB)")
        
    except Exception as e:
        print(f"   [ERROR] Failed: {str(e)}")
        
        # Try alternative approach if VSI failed
        if chunk_config.get('use_vsi', True) and "vsis3" in str(e):
            print(f"   [FALLBACK] VSI failed, trying with download...")
            chunk_config['use_vsi'] = False
            return convert_to_proper_CRS_and_cogify_ultra_large(
                name, BUCKET, cog_filename, cog_data_bucket, cog_data_prefix,
                s3_client, COG_PROFILE, local_output_dir, chunk_config
            )
        raise
    
    finally:
        # Clean up temporary files
        for temp_file in ['output_path', 'warp_output']:
            if temp_file in locals():
                file_path = locals()[temp_file]
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except:
                        pass
        
        # Force garbage collection
        gc.collect()
    
    print("✅ Ultra-large file COG conversion complete")