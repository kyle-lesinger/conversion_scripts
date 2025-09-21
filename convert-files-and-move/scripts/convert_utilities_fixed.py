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
import boto3
from botocore.exceptions import ClientError


# Import COG and cache utilities
from cog_utilities import (
    check_cache_status,
    clear_cache,
    validate_cog,
    export_COG_PROFILE
)


from memory_utils import (
    get_memory_usage,
    calculate_optimal_chunk_size,
    estimate_chunk_memory,
    format_bytes

)


def check_s3_file_exists(s3_client, bucket, key):
    """
    Check if a file already exists in S3.

    Args:
        s3_client: Boto3 S3 client
        bucket: S3 bucket name
        key: S3 object key

    Returns:
        bool: True if file exists, False otherwise
    """
    try:
        s3_client.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as e:
        # If a 404 error, the file does not exist
        if e.response['Error']['Code'] == '404':
            return False
        # For other errors, re-raise
        raise

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


def convert_to_proper_CRS_and_cogify_ultra_large_fixed(name, BUCKET, cog_filename, cog_data_bucket, cog_data_prefix, s3_client, COG_PROFILE,
                                            local_output_dir=None, chunk_config=None):
    """
    Convert ultra-large files to Cloud Optimized GeoTIFF using GDAL's streaming capabilities.
    
    This is a FIXED version that properly handles AWS credentials.
    
    Optimized for files that are too large to fit in memory (10GB+).
    Uses GDAL command-line tools for efficient processing without loading data into Python memory.
    """
    import subprocess
    import tempfile
    import os
    from pathlib import Path
    import boto3
    
    if chunk_config is None:
        chunk_config = {
            "use_vsi": True,  # Use GDAL's virtual file system
            "gdal_cache_mb": 8192,  # 8GB GDAL cache
            "num_threads": "ALL_CPUS",
            "enable_memory_monitoring": True
        }
    
    s3_key = f"{cog_data_prefix}/{cog_filename}"

    # Check if the renamed file already exists in S3
    print(f"   [CHECK] Checking if file already exists in S3: s3://{cog_data_bucket}/{s3_key}")
    if check_s3_file_exists(s3_client, cog_data_bucket, s3_key):
        print(f"   [SKIP] File already exists in S3, skipping processing: {cog_filename}")
        return

    reproject_filename = f"reproj/{cog_filename}"

    # FIXED: Proper credential handling
    try:
        # Try to get credentials from the s3_client
        credentials = None
        
        # Method 1: Try to get from client's session
        if hasattr(s3_client, '_request_signer') and hasattr(s3_client._request_signer, '_credentials'):
            credentials = s3_client._request_signer._credentials
        
        # Method 2: Get fresh credentials from boto3 session
        if not credentials:
            session = boto3.Session()
            credentials = session.get_credentials()
        
        # Set environment variables if we have credentials
        if credentials:
            if hasattr(credentials, 'access_key'):
                os.environ['AWS_ACCESS_KEY_ID'] = credentials.access_key
            if hasattr(credentials, 'secret_key'):
                os.environ['AWS_SECRET_ACCESS_KEY'] = credentials.secret_key
            if hasattr(credentials, 'token') and credentials.token:
                os.environ['AWS_SESSION_TOKEN'] = credentials.token
                print("   [CREDENTIALS] Using temporary AWS credentials")
        
    except Exception as e:
        print(f"   [CREDENTIALS] Warning: Could not extract credentials: {e}")
        print("   [CREDENTIALS] GDAL will use instance credentials or environment variables")
    
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
            return convert_to_proper_CRS_and_cogify_ultra_large_fixed(
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