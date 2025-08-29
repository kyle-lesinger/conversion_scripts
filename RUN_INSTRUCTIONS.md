# Instructions to Process and Upload COG Files

## Problem Summary
The RGB files failed to upload because of a data type issue:
- RGB files use `uint8` data type (values 0-255)
- The code tried to set nodata value to -9999 (impossible for uint8)
- Only the CSV error log was uploaded, not the actual COG files

## Solution Implemented
The notebook has been fixed with smart nodata handling:
- **uint8 files (RGB)**: Uses nodata value of 0
- **Other types**: Uses nodata value of -9999

## Steps to Run the Fixed Notebook

### 1. Open Jupyter Lab/Notebook
```bash
jupyter lab
```

### 2. Navigate to the Enhanced Notebook
Open: `convert-files-and-move/2024/202405_Flood_TX-planet-enhanced.ipynb`

### 3. Run the Cells in Order

**Important cells to verify:**

- **Cell 2**: Imports custom modules
- **Cell 8**: Initializes S3 client (verify "✅ S3 client ready")
- **Cell 15-16**: Configuration for WM, RGB, and WM_diff
- **Cell 23**: Contains the FIXED conversion function with dtype handling
- **Cell 27**: Defines filename creator functions
- **Cell 30**: Batch processing that will actually upload the COGs

### 4. Monitor the Output

You should see output like:
```
[COGIFY] Creating COG...
[NODATA] Data type: uint8
[NODATA] Using nodata value 0 for uint8 data
[VALIDATE] ✅ Valid COG
[UPLOAD] Uploading to S3...
[SUCCESS] ✅ Uploaded to s3://nasa-disasters/drcs_activations_new/Sentinel-1/rgb/...
```

### 5. Verify Upload
Check the S3 bucket for uploaded files:
- Water mask files: `s3://nasa-disasters/drcs_activations_new/Sentinel-1/WM/`
- RGB files: `s3://nasa-disasters/drcs_activations_new/Sentinel-1/rgb/`
- Diff files: `s3://nasa-disasters/drcs_activations_new/Sentinel-1/WM_diff/`

## Expected Results

### For RGB Files (3 files):
- ✅ Will process successfully with nodata=0
- ✅ Will upload to S3

### For Water Mask Files (6 files):
- ✅ Will process with nodata=-9999
- ✅ Will upload to S3

### For Diff Files (2 files):
- ✅ Will process with nodata=-9999
- ✅ Will upload to S3

## Troubleshooting

If you still see errors:
1. Check AWS credentials: `aws s3 ls s3://nasa-disasters/`
2. Clear cache if needed: `rm -rf data_download/`
3. Check the dtype in error messages - it should show "Using nodata value 0 for uint8"

## Key Code Changes Made

The main fix in the conversion function:
```python
# Smart nodata value handling based on data type
if ds.dtype == 'uint8':
    nodata_value = 0  # For RGB images
elif ds.dtype == 'uint16':
    nodata_value = 0
else:
    nodata_value = -9999  # For float32, int16, etc.
```

This ensures RGB files can be processed and uploaded successfully!