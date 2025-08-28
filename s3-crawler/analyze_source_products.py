#!/usr/bin/env python3
"""
Analyze source products from DRCS activations TIF files.
"""

import json
import re
from collections import defaultdict
from typing import Dict, Set, List, Tuple

def extract_source_products(data: Dict) -> Dict[str, List[str]]:
    """
    Extract all unique source products from the DRCS data.
    """
    source_products = defaultdict(set)
    file_examples = defaultdict(list)
    
    def traverse(obj, path=""):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == "_files" and isinstance(value, list):
                    # Analyze files in this directory
                    parent_dir = path.split("/")[-1] if path else ""
                    
                    for file in value:
                        file_lower = file.lower()
                        
                        # Identify source products based on patterns
                        if "sentinel" in file_lower or file_lower.startswith("s1") or file_lower.startswith("s2"):
                            if "s1" in file_lower or "sentinel-1" in file_lower:
                                source = "Sentinel-1"
                            else:
                                source = "Sentinel-2"
                            source_products[source].add(parent_dir)
                            if len(file_examples[source]) < 3:
                                file_examples[source].append(f"{path}/{file}")
                        
                        elif "landsat" in file_lower or file_lower.startswith("lc08") or file_lower.startswith("le07"):
                            source = "Landsat"
                            source_products[source].add(parent_dir)
                            if len(file_examples[source]) < 3:
                                file_examples[source].append(f"{path}/{file}")
                        
                        elif "modis" in file_lower:
                            source = "MODIS"
                            source_products[source].add(parent_dir)
                            if len(file_examples[source]) < 3:
                                file_examples[source].append(f"{path}/{file}")
                        
                        elif "viirs" in file_lower or "vnp" in file_lower or "vj1" in file_lower:
                            source = "VIIRS"
                            source_products[source].add(parent_dir)
                            if len(file_examples[source]) < 3:
                                file_examples[source].append(f"{path}/{file}")
                        
                        elif "aster" in parent_dir.lower():
                            source = "ASTER"
                            source_products[source].add(parent_dir)
                            if len(file_examples[source]) < 3:
                                file_examples[source].append(f"{path}/{file}")
                        
                        elif "master" in parent_dir.lower() or "master" in file_lower:
                            source = "MASTER"
                            source_products[source].add(parent_dir)
                            if len(file_examples[source]) < 3:
                                file_examples[source].append(f"{path}/{file}")
                        
                        elif "aria" in parent_dir.lower() or "aria" in file_lower:
                            source = "ARIA"
                            source_products[source].add(parent_dir)
                            if len(file_examples[source]) < 3:
                                file_examples[source].append(f"{path}/{file}")
                        
                        elif "planet" in file_lower or parent_dir.lower() == "planet":
                            source = "Planet"
                            source_products[source].add(parent_dir)
                            if len(file_examples[source]) < 3:
                                file_examples[source].append(f"{path}/{file}")
                        
                        elif "maxar" in file_lower or parent_dir.lower() == "maxar":
                            source = "Maxar"
                            source_products[source].add(parent_dir)
                            if len(file_examples[source]) < 3:
                                file_examples[source].append(f"{path}/{file}")
                        
                        elif "hls" in file_lower or parent_dir.lower() == "hls":
                            source = "HLS (Harmonized Landsat Sentinel)"
                            source_products[source].add(parent_dir)
                            if len(file_examples[source]) < 3:
                                file_examples[source].append(f"{path}/{file}")
                        
                        elif "emit" in file_lower or parent_dir.lower() == "emit":
                            source = "EMIT"
                            source_products[source].add(parent_dir)
                            if len(file_examples[source]) < 3:
                                file_examples[source].append(f"{path}/{file}")
                        
                        elif "ecostress" in file_lower or parent_dir.lower() == "ecostress":
                            source = "ECOSTRESS"
                            source_products[source].add(parent_dir)
                            if len(file_examples[source]) < 3:
                                file_examples[source].append(f"{path}/{file}")
                        
                        elif "icesat" in file_lower:
                            source = "ICESat"
                            source_products[source].add(parent_dir)
                            if len(file_examples[source]) < 3:
                                file_examples[source].append(f"{path}/{file}")
                        
                        elif "smap" in file_lower:
                            source = "SMAP"
                            source_products[source].add(parent_dir)
                            if len(file_examples[source]) < 3:
                                file_examples[source].append(f"{path}/{file}")
                        
                        elif "gpm" in file_lower or "imerg" in file_lower:
                            source = "GPM/IMERG"
                            source_products[source].add(parent_dir)
                            if len(file_examples[source]) < 3:
                                file_examples[source].append(f"{path}/{file}")
                        
                        elif "goes" in file_lower:
                            source = "GOES"
                            source_products[source].add(parent_dir)
                            if len(file_examples[source]) < 3:
                                file_examples[source].append(f"{path}/{file}")
                        
                        elif "worldview" in file_lower:
                            source = "WorldView"
                            source_products[source].add(parent_dir)
                            if len(file_examples[source]) < 3:
                                file_examples[source].append(f"{path}/{file}")
                        
                        elif parent_dir in ["dnbr", "dnbr_v2", "nbr"]:
                            source = "Burn Index Products (dNBR/NBR)"
                            source_products[source].add(parent_dir)
                            if len(file_examples[source]) < 3:
                                file_examples[source].append(f"{path}/{file}")
                        
                        elif parent_dir in ["dem", "elevation"]:
                            source = "DEM (Digital Elevation Model)"
                            source_products[source].add(parent_dir)
                            if len(file_examples[source]) < 3:
                                file_examples[source].append(f"{path}/{file}")
                        
                        elif parent_dir in ["flood_extent", "flood", "water"]:
                            source = "Flood/Water Products"
                            source_products[source].add(parent_dir)
                            if len(file_examples[source]) < 3:
                                file_examples[source].append(f"{path}/{file}")
                        
                        elif parent_dir == "natural" or parent_dir == "falsecolor":
                            # These are usually processed products, skip standalone categorization
                            pass
                        
                        elif parent_dir == "gis" or parent_dir == "vector":
                            source = "GIS/Vector Products"
                            source_products[source].add(parent_dir)
                            if len(file_examples[source]) < 3:
                                file_examples[source].append(f"{path}/{file}")
                        
                        # Additional pattern matching for files
                        elif "gedi" in file_lower:
                            source = "GEDI"
                            source_products[source].add(parent_dir)
                            if len(file_examples[source]) < 3:
                                file_examples[source].append(f"{path}/{file}")
                        
                        elif parent_dir and parent_dir not in ["tif", "tiff", "processed", "output"]:
                            # Capture other directory names as potential sources
                            source = f"Other/{parent_dir}"
                            source_products[source].add(parent_dir)
                            if len(file_examples[source]) < 3:
                                file_examples[source].append(f"{path}/{file}")
                
                elif key != "_files" and key != "_metadata":
                    new_path = f"{path}/{key}" if path else key
                    traverse(value, new_path)
    
    # Start traversal
    if "drcs_activations" in data:
        traverse(data["drcs_activations"])
    
    # Convert sets to lists and combine with examples
    result = {}
    for source, dirs in source_products.items():
        result[source] = {
            "directories": sorted(list(dirs)),
            "example_files": file_examples[source][:3],
            "count": len(dirs)
        }
    
    return result

def analyze_all_directories(data: Dict) -> Dict[str, int]:
    """
    Count files in each unique directory name across all events.
    """
    dir_counts = defaultdict(int)
    
    def traverse(obj, path=""):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == "_files" and isinstance(value, list):
                    parent_dir = path.split("/")[-1] if path else ""
                    if parent_dir:
                        dir_counts[parent_dir] += len(value)
                elif key != "_files" and key != "_metadata":
                    new_path = f"{path}/{key}" if path else key
                    traverse(value, new_path)
    
    if "drcs_activations" in data:
        traverse(data["drcs_activations"])
    
    return dict(sorted(dir_counts.items(), key=lambda x: x[1], reverse=True))

def main():
    # Load the JSON file
    with open('drcs_activations_tif_files.json', 'r') as f:
        data = json.load(f)
    
    # Extract source products
    source_products = extract_source_products(data)
    
    # Analyze all directories
    dir_counts = analyze_all_directories(data)
    
    # Print results
    print("=" * 80)
    print("EARTH OBSERVATION SOURCE PRODUCTS IN NASA DISASTERS DRCS ACTIVATIONS")
    print("=" * 80)
    
    print("\n## Identified Source Products:\n")
    
    for source in sorted(source_products.keys()):
        info = source_products[source]
        print(f"\n### {source}")
        print(f"   Found in {info['count']} directory type(s): {', '.join(info['directories'][:5])}")
        if len(info['directories']) > 5:
            print(f"   ... and {len(info['directories']) - 5} more")
        print(f"   Example files:")
        for ex in info['example_files'][:2]:
            print(f"      - {ex}")
    
    print("\n" + "=" * 80)
    print("## Directory Statistics (Top 20):\n")
    
    for dir_name, count in list(dir_counts.items())[:20]:
        print(f"   {dir_name:30s} : {count:5d} files")
    
    # Save to JSON for further analysis
    output = {
        "source_products": source_products,
        "directory_statistics": dir_counts
    }
    
    with open('source_products_analysis.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print("\n" + "=" * 80)
    print("Analysis saved to source_products_analysis.json")

if __name__ == "__main__":
    main()