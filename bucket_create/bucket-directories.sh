#!/bin/bash

# S3 bucket name
BUCKET_NAME="nasa-disasters"

# Array of satellite/sensor names
declare -a DIRECTORIES=(
    "Sentinel-1"
    "Sentinel-2"
    "Landsat"
    "MODIS"
    "VIIRS"
    "ASTER"
    "MASTER"
    "ECOSTRESS"
    "Planet"
    "Maxar"
    "HLS"
    "IMERG"
    "GOES"
    "SMAP"
    "ICESat"
    "GEDI"
    "COMSAR"
    "UAVSAR"
    "WB-57"
)

# Prefix for all directories
PREFIX="drcs_activations_new"

# Function to create a directory in S3
create_s3_directory() {
    local dir_name=$1
    local full_path="${PREFIX}/${dir_name}"
    
    # S3 doesn't have real directories, but we can create empty objects with trailing slashes
    # to simulate directory structure
    echo "Creating directory: ${full_path}/"
    
    # Using AWS CLI to create an empty object with trailing slash
    aws s3api put-object \
        --bucket "${BUCKET_NAME}" \
        --key "${full_path}/" \
        --content-length 0
    
    if [ $? -eq 0 ]; then
        echo "✓ Successfully created: ${full_path}/"
    else
        echo "✗ Failed to create: ${full_path}/"
    fi
}

# Main script execution
echo "Starting S3 directory creation for bucket: ${BUCKET_NAME}"
echo "Base path: ${PREFIX}/"
echo "================================================"

# Check if bucket exists (optional - remove if you're sure bucket exists)
aws s3api head-bucket --bucket "${BUCKET_NAME}" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Error: Bucket '${BUCKET_NAME}' does not exist or is not accessible."
    echo "Please create the bucket first or check your AWS credentials."
    exit 1
fi

# Optional: Also create the parent directory
echo "Creating parent directory: ${PREFIX}/"
aws s3api put-object \
    --bucket "${BUCKET_NAME}" \
    --key "${PREFIX}/" \
    --content-length 0

# Create each directory
for directory in "${DIRECTORIES[@]}"; do
    create_s3_directory "${directory}"
done

echo "================================================"
echo "Directory creation completed!"

# Optional: List all directories in the bucket
echo ""
echo "Listing directories in ${BUCKET_NAME}/${PREFIX}/:"
aws s3 ls "s3://${BUCKET_NAME}/${PREFIX}/" --recursive | grep "/$"