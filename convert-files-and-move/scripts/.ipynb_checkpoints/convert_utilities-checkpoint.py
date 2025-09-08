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

def convert_to_proper_CRS_and_cogify(name, BUCKET, cog_filename, cog_data_bucket, cog_data_prefix, s3_client, local_output_dir=None):
    """
    Convert a file to Cloud Optimized GeoTIFF with proper CRS.
    
    This function includes:
    - Download caching to avoid re-downloading files
    - CRS reprojection to EPSG:4326
    - COG validation before upload
    - Upload to S3
    - Smart nodata value handling based on data type
    """
    s3_key = f"{cog_data_prefix}/{cog_filename}"
    reproject_filename = f"reproj/{cog_filename}"
    
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
    
    # Temporary file for processing
    temp_input_file = f"temp_{os.path.basename(name)}"

    try:
        # Check if file already exists locally
        if os.path.exists(local_download_path):
            print(f"   [CACHE HIT] Using cached file: {local_download_path}")
            import shutil
            shutil.copy(local_download_path, temp_input_file)
        else:
            # Download the file from S3
            print(f"   [DOWNLOAD] Downloading from S3...")
            s3_client.download_file(BUCKET, name, local_download_path)
            print(f"   [DOWNLOAD] ✅ Saved to cache")
            import shutil
            shutil.copy(local_download_path, temp_input_file)
        
        # Reproject to EPSG:4326
        print(f"   [REPROJECT] Converting to EPSG:4326...")
        with rasterio.open(temp_input_file) as src:
            dst_crs = "EPSG:4326"
            
            # Check if reprojection is needed
            if src.crs and src.crs.to_string() == dst_crs:
                print(f"   [REPROJECT] Already in {dst_crs}, skipping reprojection")
                import shutil
                shutil.copy(temp_input_file, reproject_filename)
            else:
                transform, width, height = calculate_default_transform(
                    src.crs, dst_crs, src.width, src.height, *src.bounds
                )
                kwargs = src.meta.copy()
                kwargs.update({
                    "driver": "COG",
                    "compress": "DEFLATE",
                    "crs": dst_crs,
                    "transform": transform,
                    "width": width,
                    "height": height
                })

                with rasterio.open(reproject_filename, "w", **kwargs) as dst:
                    for band_idx in range(1, src.count + 1):
                        reproject(
                            source=rasterio.band(src, band_idx),
                            destination=rasterio.band(dst, band_idx),
                            src_transform=src.transform,
                            src_crs=src.crs,
                            dst_transform=transform,
                            dst_crs=dst_crs,
                            resampling=Resampling.nearest,
                            wrapdateline=True
                        )

        # COGify & upload
        print(f"   [COGIFY] Creating COG...")
        
        # Try using rio-cogeo first for better compatibility
        try:
            from rio_cogeo.cogeo import cog_translate
            from rio_cogeo.profiles import cog_profiles
            
            print(f"   [COGIFY] Using rio-cogeo for conversion...")
            
            # Get COG_PROFILE and predictor
            COG_PROFILE = export_COG_PROFILE()
            with rasterio.open(reproject_filename) as src:
                predictor = get_predictor_for_dtype(src.dtypes[0])
                print(f"   [PREDICTOR] Data type: {src.dtypes[0]}, using PREDICTOR={predictor}")
            
            # Get compression type
            compress_type = COG_PROFILE.get('compress', 'DEFLATE').lower()
            
            # Create appropriate profile
            if compress_type == 'zstd':
                dst_profile = {
                    'driver': 'COG',
                    'compress': 'zstd',
                    'zstd_level': COG_PROFILE.get('zstd_level', 9),
                    'predictor': predictor
                }
            elif compress_type == 'lzw':
                dst_profile = cog_profiles.get('lzw')
                dst_profile['predictor'] = predictor
            else:
                dst_profile = cog_profiles.get('deflate')
                dst_profile['predictor'] = predictor
            
            with tempfile.NamedTemporaryFile(suffix='.tif', delete=False) as tmp:
                tmp_name = tmp.name
                # Use rio-cogeo translate
                cog_translate(
                    reproject_filename,
                    tmp_name,
                    dst_profile,
                    use_cog_driver=True,
                    in_memory=False,
                    quiet=False
                )
                
        except ImportError:
            # Fallback to rioxarray method
            print(f"   [COGIFY] rio-cogeo not available, using rioxarray...")
            ds = rxr.open_rasterio(reproject_filename)
            
            # Get COG_PROFILE
            COG_PROFILE = export_COG_PROFILE()
            
            # Auto-detect and set predictor
            with rasterio.open(reproject_filename) as src:
                predictor = get_predictor_for_dtype(src.dtypes[0])
                # Update COG_PROFILE with predictor
                cog_profile_with_predictor = COG_PROFILE.copy()
                cog_profile_with_predictor['predictor'] = predictor
                print(f"   [PREDICTOR] Data type: {src.dtypes[0]}, using PREDICTOR={predictor}")
        
            # Handle coordinate naming
            if "y" in ds.dims and "x" in ds.dims:
                ds = ds.rename({"y": "lat", "x": "lon"})
                ds.rio.set_spatial_dims("lon", "lat", inplace=True)
            
            #Smart nodata handling
            ds.rio.write_nodata(set_no_data_value(ds), inplace=True)

            with tempfile.NamedTemporaryFile(suffix='.tif', delete=False) as tmp:
                tmp_name = tmp.name
                ds.rio.to_raster(tmp_name, **cog_profile_with_predictor)
            
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

    print("✅ COG conversion function defined with smart nodata handling")


def convert_to_proper_CRS_and_cogify_chunked(name, BUCKET, cog_filename, cog_data_bucket, cog_data_prefix, s3_client, COG_PROFILE,
                                            local_output_dir=None, chunk_config=None):
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

    #Make directories
    data_download_dir, local_subdir, local_download_path = makedirs(name)
    
    # Temporary file for processing
    temp_input_file = f"temp_{os.path.basename(name)}"
    
    # Memory monitoring
    if chunk_config.get('enable_memory_monitoring', True):
        initial_memory = get_memory_usage()
        print(f"   [MEMORY] Initial: {initial_memory:.1f} MB")

    try:
        import shutil
        
        # Check if file already exists locally
        if os.path.exists(local_download_path):
            print(f"   [CACHE HIT] Using cached file: {local_download_path}")
            shutil.copy(local_download_path, temp_input_file)
        else:
            # Download the file from S3
            print(f"   [DOWNLOAD] Downloading from S3...")
            s3_client.download_file(BUCKET, name, local_download_path)
            print(f"   [DOWNLOAD] ✅ Saved to cache")
            shutil.copy(local_download_path, temp_input_file)
        
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
                    "blockysize": 512
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
                                chunk_data = np.zeros((win_height, win_width), dtype=src.dtypes[0])
                                
                                # Reproject chunk
                                reproject(
                                    source=rasterio.band(src, band_idx),
                                    destination=chunk_data,
                                    src_transform=src.transform,
                                    src_crs=src.crs,
                                    dst_transform=transform * rasterio.windows.transform(window, transform),
                                    dst_crs=dst_crs,
                                    resampling=Resampling.nearest,
                                    wrapdateline=True
                                )
                                
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
            for band_idx in range(1, verify_src.count + 1):
                # Read a sample to check if data exists
                sample_window = Window(0, 0, min(1000, verify_src.width), min(1000, verify_src.height))
                sample_data = verify_src.read(band_idx, window=sample_window)
                data_min, data_max = sample_data.min(), sample_data.max()
                non_zero_count = np.count_nonzero(sample_data)
                print(f"   [VERIFY] Band {band_idx}: min={data_min}, max={data_max}, non-zero pixels={non_zero_count}/{sample_data.size}")
                if non_zero_count == 0:
                    print(f"   [WARNING] Band {band_idx} has no non-zero data after reprojection!")
        
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