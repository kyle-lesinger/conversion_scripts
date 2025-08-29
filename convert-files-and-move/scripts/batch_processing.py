#!/usr/bin/env python3
"""
Batch processing utilities for COG conversion and file processing.

This module provides functions for:
- Batch processing lists of files with custom processing functions
- Automatic metadata generation and saving
- CSV logging of processed files
"""

import os
import json
import tempfile
import pandas as pd
import rasterio
import boto3
from pathlib import Path
from typing import List, Callable, Dict, Optional, Any


def process_file_batch(
    file_list: List[str],
    s3_client: boto3.client,
    config: Dict[str, Any],
    filename_creator_func: Callable[[str, Any], str],
    processing_func: Callable,
    event_name: str = None,
    save_metadata: bool = True,
    save_csv: bool = True,
    verbose: bool = True
) -> pd.DataFrame:
    """
    Process a batch of files with a custom processing function.
    
    Args:
        file_list: List of file paths to process
        s3_client: Initialized boto3 S3 client
        config: Configuration dictionary containing:
            - raw_data_bucket: Source S3 bucket
            - cog_data_bucket: Target S3 bucket
            - cog_data_prefix: Target S3 prefix
            - local_output_dir: Optional local output directory
        filename_creator_func: Function to create output filename
        processing_func: Function to process each file
        event_name: Event name for filename creation (optional)
        save_metadata: Whether to save metadata to S3
        save_csv: Whether to save CSV log to S3
        verbose: Whether to print progress messages
    
    Returns:
        DataFrame containing processed file information
    """
    # Initialize DataFrame to track processed files
    files_processed = pd.DataFrame(columns=["file_name", "COGs_created"])
    
    # Get configuration values
    raw_data_bucket = config.get("raw_data_bucket")
    cog_data_bucket = config.get("cog_data_bucket")
    cog_data_prefix = config.get("cog_data_prefix")
    local_output_dir = config.get("local_output_dir")
    
    # Create output directories if specified
    if local_output_dir:
        os.makedirs(local_output_dir, exist_ok=True)
        if verbose:
            print(f"✅ Local output directory ready: {local_output_dir}")
    
    # Process each file
    total_files = len(file_list)
    for idx, name in enumerate(sorted(file_list), 1):
        try:
            # Create output filename
            if event_name:
                cog_filename = filename_creator_func(name, event_name)
            else:
                cog_filename = filename_creator_func(name)
            
            if verbose:
                print(f"\n[{idx}/{total_files}] Processing: {name}")
                print(f"   Output filename: {cog_filename}")
            
            # Process the file
            processing_func(
                name, 
                cog_filename, 
                cog_data_bucket, 
                cog_data_prefix, 
                local_output_dir
            )
            
            # Add to tracking DataFrame
            files_processed = files_processed._append(
                {"file_name": name, "COGs_created": cog_filename},
                ignore_index=True,
            )
            
            if verbose:
                print(f"   ✅ Generated and saved COG: {cog_filename}")
                
        except Exception as e:
            print(f"   ❌ Error processing {name}: {str(e)}")
            # Optionally add failed file to DataFrame with error status
            files_processed = files_processed._append(
                {"file_name": name, "COGs_created": f"ERROR: {str(e)[:100]}"},
                ignore_index=True,
            )
    
    if verbose:
        print(f"\n✅ Batch processing complete: {len(files_processed)} files processed")
    
    # Save metadata if requested and files were processed
    if save_metadata and len(files_processed) > 0 and s3_client:
        save_processing_metadata(
            files_processed, 
            s3_client, 
            raw_data_bucket, 
            cog_data_bucket, 
            cog_data_prefix,
            verbose
        )
    
    # Save CSV log if requested
    if save_csv and len(files_processed) > 0 and s3_client:
        save_processing_csv(
            files_processed,
            s3_client,
            cog_data_bucket,
            cog_data_prefix,
            verbose
        )
    
    # Display summary if verbose
    if verbose and local_output_dir:
        print(f"📁 COGs saved locally to: {local_output_dir}")
    
    return files_processed


def save_processing_metadata(
    files_processed: pd.DataFrame,
    s3_client: boto3.client,
    raw_data_bucket: str,
    cog_data_bucket: str,
    cog_data_prefix: str,
    verbose: bool = True
) -> None:
    """
    Save metadata from processed files to S3.
    
    Args:
        files_processed: DataFrame with processed file information
        s3_client: Initialized boto3 S3 client
        raw_data_bucket: Source S3 bucket name
        cog_data_bucket: Target S3 bucket name
        cog_data_prefix: Target S3 prefix
        verbose: Whether to print progress messages
    """
    try:
        # Get first successfully processed file (not an error)
        successful_files = files_processed[~files_processed['COGs_created'].str.startswith('ERROR:', na=False)]
        
        if len(successful_files) == 0:
            if verbose:
                print("⚠️ No successfully processed files to extract metadata from")
            return
        
        sample_file = successful_files.iloc[0]['file_name']
        temp_sample_file = f"temp_{os.path.basename(sample_file)}"
        
        # Download sample file to extract metadata
        s3_client.download_file(raw_data_bucket, sample_file, temp_sample_file)
        
        with rasterio.open(temp_sample_file) as src:
            metadata = {
                "description": src.tags(),
                "driver": src.driver,
                "dtype": str(src.dtypes[0]),
                "nodata": src.nodata,
                "width": src.width,
                "height": src.height,
                "count": src.count,
                "crs": str(src.crs),
                "transform": list(src.transform),
                "bounds": list(src.bounds),
                "total_files_processed": len(successful_files),
                "total_files_attempted": len(files_processed),
                "processing_timestamp": pd.Timestamp.now().isoformat()
            }
        
        # Upload metadata
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json", delete=False) as fp:
            json.dump(metadata, fp, indent=2)
            fp.flush()
            
            s3_client.upload_file(
                Filename=fp.name,
                Bucket=cog_data_bucket,
                Key=f"{cog_data_prefix}/metadata.json",
            )
            
            # Clean up temp file
            os.unlink(fp.name)
            
        if verbose:
            print(f"📊 Uploaded metadata to s3://{cog_data_bucket}/{cog_data_prefix}/metadata.json")
        
        # Clean up sample file
        if os.path.exists(temp_sample_file):
            os.remove(temp_sample_file)
            
    except Exception as e:
        print(f"❌ Error saving metadata: {str(e)}")


def save_processing_csv(
    files_processed: pd.DataFrame,
    s3_client: boto3.client,
    cog_data_bucket: str,
    cog_data_prefix: str,
    verbose: bool = True
) -> None:
    """
    Save processing log as CSV to S3.
    
    Args:
        files_processed: DataFrame with processed file information
        s3_client: Initialized boto3 S3 client
        cog_data_bucket: Target S3 bucket name
        cog_data_prefix: Target S3 prefix
        verbose: Whether to print progress messages
    """
    try:
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".csv", delete=False) as fp:
            files_processed.to_csv(fp.name, index=False)
            fp.flush()
            
            s3_client.upload_file(
                Filename=fp.name,
                Bucket=cog_data_bucket,
                Key=f"{cog_data_prefix}/files_converted.csv",
            )
            
            # Clean up temp file
            os.unlink(fp.name)
            
        if verbose:
            print(f"📝 Saved processing log to s3://{cog_data_bucket}/{cog_data_prefix}/files_converted.csv")
            
    except Exception as e:
        print(f"❌ Error saving CSV log: {str(e)}")


def create_batch_summary(files_processed: pd.DataFrame) -> Dict[str, Any]:
    """
    Create a summary of the batch processing results.
    
    Args:
        files_processed: DataFrame with processed file information
    
    Returns:
        Dictionary containing summary statistics
    """
    successful = len(files_processed[~files_processed['COGs_created'].str.startswith('ERROR:', na=False)])
    failed = len(files_processed[files_processed['COGs_created'].str.startswith('ERROR:', na=False)])
    
    summary = {
        "total_files": len(files_processed),
        "successful": successful,
        "failed": failed,
        "success_rate": f"{(successful / len(files_processed) * 100):.1f}%" if len(files_processed) > 0 else "N/A",
        "timestamp": pd.Timestamp.now().isoformat()
    }
    
    return summary


def print_batch_summary(files_processed: pd.DataFrame) -> None:
    """
    Print a formatted summary of batch processing results.
    
    Args:
        files_processed: DataFrame with processed file information
    """
    summary = create_batch_summary(files_processed)
    
    print("\n" + "=" * 50)
    print("📊 BATCH PROCESSING SUMMARY")
    print("=" * 50)
    print(f"Total files processed: {summary['total_files']}")
    print(f"Successful: {summary['successful']}")
    print(f"Failed: {summary['failed']}")
    print(f"Success rate: {summary['success_rate']}")
    print(f"Timestamp: {summary['timestamp']}")
    print("=" * 50)


if __name__ == "__main__":
    # Example usage
    print("Batch Processing Module")
    print("This module provides batch processing functions for COG conversion")
    print("Import and use process_file_batch() for batch processing")