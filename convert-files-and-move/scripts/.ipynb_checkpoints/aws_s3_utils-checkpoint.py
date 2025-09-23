#!/usr/bin/env python3
"""
AWS S3 utilities for automatic credential detection and client initialization.

This module provides functions for:
- Initializing S3 clients with automatic credential detection
- Testing S3 bucket access
- Setting up fsspec filesystem for S3 operations
"""

import boto3
import fsspec
from botocore.exceptions import NoCredentialsError, ClientError
from typing import Tuple, Optional


def initialize_s3_client(bucket_name: str = 'nasa-disasters', verbose: bool = True) -> Tuple[Optional[boto3.client], Optional[fsspec.AbstractFileSystem]]:
    """
    Initialize AWS S3 Client with automatic credential detection.
    
    This function will automatically use AWS credentials from:
    1. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    2. AWS CLI configuration (~/.aws/credentials)
    3. IAM role (if running on EC2/Lambda)
    
    Args:
        bucket_name: Name of the bucket to test access (default: 'nasa-disasters')
        verbose: If True, print status messages
    
    Returns:
        Tuple of (s3_client, fs_read) where:
        - s3_client: Initialized boto3 S3 client or None if failed
        - fs_read: Initialized fsspec filesystem or None if failed
    """
    s3_client = None
    fs_read = None
    
    try:
        # Create S3 client - will automatically use AWS credentials
        s3_client = boto3.client('s3')
        
        # Test connection
        try:
            # Try to list buckets (might fail due to permissions, that's OK)
            response = s3_client.list_buckets()
            if verbose:
                print(f"✅ S3 client initialized successfully")
                print(f"   Found {len(response.get('Buckets', []))} accessible buckets")
        except ClientError as e:
            if e.response['Error']['Code'] == 'AccessDenied':
                if verbose:
                    print(f"⚠️ S3 client initialized (limited bucket list access)")
                # Test access to specific bucket
                try:
                    s3_client.head_bucket(Bucket=bucket_name)
                    if verbose:
                        print(f"✅ Confirmed access to {bucket_name} bucket")
                except ClientError as bucket_error:
                    if verbose:
                        print(f"❌ Cannot access {bucket_name} bucket: {bucket_error}")
                    s3_client = None
                    return None, None
            else:
                raise e
        
        # Also initialize fsspec filesystem for S3
        fs_read = fsspec.filesystem("s3", anon=False, skip_instance_cache=False)
        if verbose:
            print(f"✅ S3 filesystem (fsspec) initialized")
        
    except NoCredentialsError:
        if verbose:
            print("❌ No AWS credentials found. Please configure credentials using:")
            print("   - Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)")
            print("   - AWS CLI: aws configure")
            print("   - IAM role (if on EC2)")
        s3_client = None
        fs_read = None
    except Exception as e:
        if verbose:
            print(f"❌ Error initializing S3 client: {e}")
        s3_client = None
        fs_read = None
    
    return s3_client, fs_read


def verify_s3_client(s3_client: Optional[boto3.client], bucket_name: str = 'nasa-disasters', verbose: bool = True) -> bool:
    """
    Verify that S3 client is ready for operations.
    
    Args:
        s3_client: The S3 client to verify
        bucket_name: Name of the bucket for context (default: 'nasa-disasters')
        verbose: If True, print status messages
    
    Returns:
        True if client is ready, False otherwise
    """
    if s3_client is None:
        if verbose:
            print("❌ S3 client not initialized. Please check your AWS credentials.")
            print("   The notebook will not be able to download files from S3.")
        return False
    else:
        if verbose:
            print("✅ S3 client ready for operations")
            print(f"   Bucket: {bucket_name}")
            print("   Ready to process files")
        return True


def get_all_s3_keys(s3_client: boto3.client, bucket: str, prefix: str, ext: str = ".tif") -> list:
    """
    Get a list of all keys in an S3 bucket with a specific extension.
    
    Args:
        s3_client: Initialized boto3 S3 client
        bucket: S3 bucket name
        prefix: Prefix path to search in
        ext: File extension to filter (default: ".tif")
    
    Returns:
        List of S3 keys matching the criteria
    """
    if s3_client is None:
        print("❌ S3 client not initialized")
        return []
    
    keys = []
    kwargs = {"Bucket": bucket, "Prefix": f"{prefix}/"}
    
    while True:
        try:
            resp = s3_client.list_objects_v2(**kwargs)
            if 'Contents' in resp:
                for obj in resp["Contents"]:
                    if obj["Key"].endswith(ext) and "historical" not in obj["Key"]:
                        keys.append(obj["Key"])
        except ClientError as e:
            print(f"❌ Error listing objects: {e}")
            break

        try:
            kwargs["ContinuationToken"] = resp.get("NextContinuationToken")
            if not kwargs["ContinuationToken"]:
                break
        except KeyError:
            break

    return keys


def test_s3_access(bucket_name: str = 'nasa-disasters') -> bool:
    """
    Quick test to check if S3 access is configured properly.
    
    Args:
        bucket_name: Name of the bucket to test
    
    Returns:
        True if access is working, False otherwise
    """
    try:
        s3_client = boto3.client('s3')
        s3_client.head_bucket(Bucket=bucket_name)
        return True
    except Exception:
        return False


if __name__ == "__main__":
    # Example usage
    print("AWS S3 Utilities Module")
    print("=" * 50)
    
    # Initialize S3 client
    print("\nInitializing S3 client...")
    s3_client, fs_read = initialize_s3_client()
    
    # Verify client
    if verify_s3_client(s3_client):
        print("\n✅ S3 client is ready for use!")
    else:
        print("\n❌ S3 client initialization failed")