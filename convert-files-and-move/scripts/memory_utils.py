#/usr/bin/env python3
import psutil
import os


def get_memory_usage():
    """Get current memory usage in MB"""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024

def format_bytes(bytes):
    """Format bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024.0:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.2f} PB"

def estimate_chunk_memory(width, height, bands, dtype):
    """Estimate memory requirement for a chunk"""
    dtype_sizes = {
        'uint8': 1, 'uint16': 2, 'uint32': 4,
        'int8': 1, 'int16': 2, 'int32': 4,
        'float32': 4, 'float64': 8
    }
    bytes_per_pixel = dtype_sizes.get(str(dtype), 4)
    return width * height * bands * bytes_per_pixel

def calculate_optimal_chunk_size(raster_width, raster_height, bands, dtype, memory_limit_mb=500):
    """Calculate optimal chunk size based on available memory"""
    memory_limit_bytes = memory_limit_mb * 1024 * 1024
    
    # Start with default chunk size
    chunk_size = 1024
    
    # Calculate memory for default chunk
    chunk_memory = estimate_chunk_memory(chunk_size, chunk_size, bands, dtype)
    
    # Adjust chunk size if needed
    if chunk_memory > memory_limit_bytes:
        # Calculate maximum chunk size that fits in memory
        bytes_per_pixel = chunk_memory / (chunk_size * chunk_size)
        max_pixels = memory_limit_bytes / bytes_per_pixel
        chunk_size = int(np.sqrt(max_pixels))
        # Round down to nearest power of 2 for efficiency
        chunk_size = 2 ** int(np.log2(chunk_size))
    
    # Ensure chunk size is at least 256
    chunk_size = max(256, chunk_size)
    
    print(f"📊 Optimal chunk size: {chunk_size}x{chunk_size}")
    print(f"   Estimated memory per chunk: {format_bytes(estimate_chunk_memory(chunk_size, chunk_size, bands, dtype))}")
    
    return chunk_size

print("✅ Memory monitoring utilities loaded")

def get_available_memory_mb():
    """Get available system memory in MB."""
    memory = psutil.virtual_memory()
    return memory.available / 1024 / 1024