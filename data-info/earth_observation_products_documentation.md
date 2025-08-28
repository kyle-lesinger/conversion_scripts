# Earth Observation Source Products in NASA Disasters DRCS Activations

## Overview
This document provides comprehensive information about all Earth observation source products identified in the NASA Disasters Response Coordination System (DRCS) activation data. These products are crucial for disaster monitoring, assessment, and response activities.

## Satellite and Sensor Products

### 1. ARIA (Advanced Rapid Imaging and Analysis)
**Provider**: NASA/JPL-Caltech  
**Technology**: Interferometric Synthetic Aperture Radar (InSAR)  
**Primary Use**: Ground deformation detection, earthquake damage assessment, landslide monitoring  

**Technical Specifications**:
- Uses Sentinel-1 SAR data as primary input
- Produces displacement maps with centimeter-level accuracy
- Temporal baseline: 6-12 days (Sentinel-1 revisit)
- Spatial resolution: ~90m for standard products
- Coverage: Global, on-demand processing

**Products Found**: 30 directory types including natural, falsecolor, coherence maps
**Applications**: Earthquakes, landslides, volcanic activity, infrastructure monitoring

---

### 2. Sentinel-1
**Provider**: European Space Agency (ESA)  
**Launch**: Sentinel-1A (2014), Sentinel-1B (2016-2021)  
**Type**: C-band Synthetic Aperture Radar (SAR)  

**Technical Specifications**:
- Frequency: 5.405 GHz (C-band)
- Resolution: 5×20m (IW mode), 5×5m (SM mode)
- Swath width: 250 km (IW mode)
- Revisit time: 6 days (12 days single satellite)
- Polarization: Dual (VV+VH, HH+HV)

**Applications**: All-weather imaging, flood mapping, oil spill detection, sea ice monitoring, land deformation

---

### 3. Sentinel-2
**Provider**: European Space Agency (ESA)  
**Launch**: Sentinel-2A (2015), Sentinel-2B (2017)  
**Type**: Multispectral optical imaging  

**Technical Specifications**:
- 13 spectral bands (443-2190 nm)
- Spatial resolution: 10m (visible/NIR), 20m (red edge/SWIR), 60m (atmospheric)
- Swath width: 290 km
- Revisit time: 5 days (at equator with both satellites)

**Applications**: Land monitoring, agriculture, forestry, disaster mapping, water quality

---

### 4. Landsat Series
**Provider**: NASA/USGS  
**Current Operations**: Landsat 8 (2013), Landsat 9 (2021)  
**Type**: Multispectral optical/thermal  

**Technical Specifications**:
- Spatial resolution: 30m (multispectral), 15m (panchromatic), 100m (thermal)
- Spectral bands: 11 bands total
- Swath width: 185 km
- Revisit time: 16 days (8 days with both satellites)
- Temporal coverage: Continuous since 1972

**Applications**: Long-term land cover change, thermal anomaly detection, vegetation monitoring

---

### 5. MODIS (Moderate Resolution Imaging Spectroradiometer)
**Provider**: NASA  
**Platforms**: Terra (1999), Aqua (2002)  
**Type**: Multispectral radiometer  

**Technical Specifications**:
- 36 spectral bands (0.4-14.4 μm)
- Spatial resolution: 250m (bands 1-2), 500m (bands 3-7), 1000m (bands 8-36)
- Swath width: 2330 km
- Temporal resolution: Daily global coverage
- Radiometric resolution: 12-bit

**Applications**: Fire detection, land/ocean/atmosphere monitoring, cloud properties

---

### 6. VIIRS (Visible Infrared Imaging Radiometer Suite)
**Provider**: NOAA/NASA  
**Platforms**: Suomi NPP (2011), NOAA-20 (2017)  
**Type**: Multispectral radiometer  

**Technical Specifications**:
- 22 spectral bands (0.4-12.5 μm)
- Spatial resolution: 375m (I-bands), 750m (M-bands)
- Swath width: 3060 km
- Day/Night Band: 0.5-0.9 μm (nighttime lights)

**Applications**: Fire detection, nighttime lights, ocean color, atmospheric properties

---

### 7. ASTER (Advanced Spaceborne Thermal Emission and Reflection Radiometer)
**Provider**: NASA/METI (Japan)  
**Platform**: Terra satellite  
**Type**: Multispectral imaging  

**Technical Specifications**:
- 14 spectral bands
- Spatial resolution: 15m (VNIR), 30m (SWIR), 90m (TIR)
- Swath width: 60 km
- Spectral range: 0.52-11.65 μm
- Stereo capability for DEM generation

**Note**: TIR operations interrupted Nov 2024 - Apr 2025 due to power issues

**Applications**: Surface temperature mapping, mineral exploration, volcanic monitoring

---

### 8. MASTER (MODIS/ASTER Airborne Simulator)
**Provider**: NASA  
**Platform**: Airborne (ER-2, DC-8)  
**Type**: Thermal/multispectral scanner  

**Technical Specifications**:
- 50 spectral bands (0.4-13 μm)
- Spatial resolution: Variable (5-50m depending on altitude)
- Flight altitude: Up to 20 km
- Swath width: Variable based on altitude

**Applications**: Wildfire characterization, volcanic emissions, calibration/validation

---

### 9. ECOSTRESS (ECOsystem Spaceborne Thermal Radiometer Experiment)
**Provider**: NASA/JPL  
**Platform**: International Space Station  
**Type**: Thermal infrared radiometer  

**Technical Specifications**:
- 6 spectral bands (including 5 TIR bands 8-12.5 μm)
- Spatial resolution: 38×69m (resampled to 70m)
- Temperature sensitivity: <0.1 K
- Revisit: 1-7 days (variable ISS orbit)
- Non-sun-synchronous orbit enables diurnal sampling

**Applications**: Evapotranspiration, water stress, urban heat islands, agricultural monitoring

---

### 10. Planet Labs Satellites
**Provider**: Planet Labs Inc.  
**Constellation**: 430+ Dove/SuperDove satellites  
**Type**: Multispectral optical  

**Technical Specifications**:
- Spatial resolution: 3 meters
- Spectral bands: 4 (original) to 8 (SuperDoves)
- Daily global coverage capability
- Scene size: 280-630 km²
- CubeSat form factor: 10×10×30 cm

**Applications**: Daily change detection, rapid response, agriculture monitoring

---

### 11. Maxar (WorldView/GeoEye)
**Provider**: Maxar Technologies  
**Satellites**: WorldView-1/2/3, WorldView Legion, GeoEye-1  
**Type**: Very high resolution optical  

**Technical Specifications (WorldView Legion 2024)**:
- Spatial resolution: 30 cm panchromatic, 1.2m multispectral
- 8 spectral bands including red edge
- Swath width: 10 km
- Collection capacity: 6.6 million km²/day (full constellation)
- Revisit: Up to 15 times/day in high-demand areas

**Applications**: Infrastructure damage assessment, detailed mapping, change detection

---

### 12. HLS (Harmonized Landsat Sentinel-2)
**Provider**: NASA  
**Type**: Fusion product  
**Data Sources**: Landsat 8/9 + Sentinel-2A/2B  

**Technical Specifications**:
- Spatial resolution: 30m (harmonized)
- Temporal resolution: 2-3 days
- Spectral bands: Common bands between Landsat and Sentinel-2
- Radiometric consistency between sensors

**Applications**: High-frequency land monitoring, phenology, agricultural applications

---

### 13. EMIT (Earth Surface Mineral Dust Source Investigation)
**Provider**: NASA/JPL  
**Platform**: International Space Station  
**Type**: Imaging spectrometer  

**Technical Specifications**:
- Spectral range: 380-2500 nm
- Spectral resolution: 7.4 nm
- Spatial resolution: 60m
- 285 spectral channels
- Swath width: 75 km

**Applications**: Mineral mapping, methane detection, vegetation analysis

---

### 14. GPM/IMERG (Global Precipitation Measurement/Integrated Multi-satellite Retrievals)
**Provider**: NASA/JAXA  
**Type**: Precipitation measurement  

**Technical Specifications**:
- Spatial resolution: 0.1° × 0.1° (~10 km)
- Temporal resolution: 30 minutes
- Coverage: 60°N to 60°S
- Combines data from multiple satellites

**Applications**: Flood forecasting, drought monitoring, precipitation analysis

---

### 15. GOES (Geostationary Operational Environmental Satellite)
**Provider**: NOAA  
**Type**: Geostationary weather satellite  

**Technical Specifications**:
- Spatial resolution: 0.5-2 km (visible/infrared)
- Temporal resolution: 5-15 minutes
- 16 spectral bands
- Coverage: Full disk, CONUS, mesoscale

**Applications**: Weather monitoring, fire detection, lightning mapping

---

### 16. SMAP (Soil Moisture Active Passive)
**Provider**: NASA  
**Launch**: 2015  
**Type**: Microwave radiometer  

**Technical Specifications**:
- L-band radiometer (1.41 GHz)
- Spatial resolution: 40 km
- Revisit time: 2-3 days
- Soil penetration: ~5 cm

**Applications**: Soil moisture monitoring, freeze/thaw detection, drought assessment

---

### 17. ICESat/ICESat-2
**Provider**: NASA  
**Type**: Laser altimeter (LiDAR)  

**Technical Specifications (ICESat-2)**:
- Green laser (532 nm)
- Footprint: ~17m diameter
- Along-track spacing: 0.7m
- Vertical precision: <10 cm
- 6 laser beams in 3 pairs

**Applications**: Ice sheet elevation, forest canopy height, water surface elevation

---

### 18. GEDI (Global Ecosystem Dynamics Investigation)
**Provider**: NASA  
**Platform**: International Space Station  
**Type**: LiDAR  

**Technical Specifications**:
- 3 lasers producing 8 ground tracks
- Footprint: 25m diameter
- Along-track spacing: 60m
- Cross-track spacing: 600m
- Vertical resolution: 1 cm

**Applications**: Forest structure, biomass estimation, habitat quality

---

## Derived Products

### Burn Index Products (dNBR/NBR)
**Type**: Derived from optical satellites  
**Description**: Normalized Burn Ratio products for fire severity assessment  
**Resolution**: Typically 30m (Landsat) or 20m (Sentinel-2)  

### DEM (Digital Elevation Model)
**Sources**: SRTM, ASTER GDEM, LiDAR  
**Resolution**: 1-90m depending on source  
**Applications**: Flood modeling, landslide susceptibility, viewshed analysis  

### Flood/Water Products
**Type**: Derived from SAR and optical data  
**Products**: Water extent maps, flood depth estimates  
**Resolution**: Variable (10-100m)  

### GIS/Vector Products
**Type**: Derived analytical products  
**Format**: Shapefiles, GeoJSON, KML  
**Content**: Damage assessments, infrastructure impacts, administrative boundaries  

## Data Access and Processing Notes

### File Naming Conventions
- Sentinel: S1A_*, S2A_*, S2B_*
- Landsat: LC08_*, LE07_*
- MODIS: MOD*, MYD*
- VIIRS: VNP*, VJ1*

### Temporal Coverage in DRCS
- Years covered: 2020-2025
- Total events processed: 100+
- Total TIF files: 34,460+

### Processing Levels
- L0: Raw data
- L1: Calibrated radiance/reflectance
- L2: Derived geophysical variables
- L3/L4: Gridded, temporal composites

## Usage in Disaster Response

### Rapid Response Timeline
1. **0-6 hours**: GOES, VIIRS for initial assessment
2. **6-24 hours**: Planet daily imagery, Sentinel-1 (if available)
3. **1-3 days**: Maxar tasking, ARIA processing
4. **3-7 days**: Landsat, Sentinel-2 (cloud permitting)
5. **7+ days**: Time series analysis, change detection products

### Product Selection Criteria
- **Floods**: SAR priority (Sentinel-1, ARIA)
- **Fires**: Thermal sensors (MODIS, VIIRS, GOES)
- **Earthquakes**: InSAR (ARIA, Sentinel-1)
- **Landslides**: Optical + DEM (Sentinel-2, Planet, elevation data)
- **Infrastructure**: VHR optical (Maxar, Planet)

## References and Resources

- [NASA Disasters Mapping Portal](https://maps.disasters.nasa.gov)
- [ESA Copernicus Emergency Management Service](https://emergency.copernicus.eu)
- [USGS EarthExplorer](https://earthexplorer.usgs.gov)
- [NASA Earthdata](https://www.earthdata.nasa.gov)
- [Planet Explorer](https://www.planet.com/explorer)

---

*Document generated from analysis of drcs_activations_tif_files.json containing 34,460 geospatial files across 100+ disaster events from 2020-2025.*