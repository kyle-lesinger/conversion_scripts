# Detailed Earth Observation Products Analysis
## NASA Disasters DRCS Activations Data

This document provides a comprehensive breakdown of all Earth observation products found in the DRCS activations data, including their specific satellites/missions, product subsets, and data variants.

---

## 1. ARIA (Advanced Rapid Imaging and Analysis)
**Directory Types**: 30  
**Technology**: Interferometric Synthetic Aperture Radar (InSAR)

### Product Subsets:
- **Damage Proxy Map (DPM)**: Earthquake and infrastructure damage assessment
- **Flood Proxy Map (FPM)**: Flood extent mapping
- **Coherence Maps**: Surface change detection
- **Displacement Maps**: Ground deformation measurements

### Specific Missions Detected:
- ALOS-2 (Japanese L-band SAR)
- Sentinel-1 (primary data source)

### Directory Examples:
- `aria`, `aria_dpm`, `aria_fpm_20200522`
- `ARIA_DPM_20180914_230548`
- `aria_opera`, `aria_opera_dswx`
- `dpm`, `fpm`, `dist`

---

## 2. Sentinel-1 (C-band SAR)
**Directory Types**: 29  
**ESA Copernicus Programme**

### Specific Satellites:
- **Sentinel-1A**: Operational since 2014
- **Sentinel-1B**: Operated 2016-2021

### Product Subsets:
- **Water Extent**: Flood mapping products
- **Flood Proxy Map (FPM)**: Flood detection
- **RGB Composites**: False color SAR visualizations
- **Coherence**: Surface change detection
- **Amplitude**: Backscatter intensity

### Directory Examples:
- `sentinel1`, `sentinel1_msfc`
- `WaterExtents`, `water_extent`
- `rgb`, `rgbs`
- `fpm`, `gsfc_sar`
- Date-based: `20180223`, `20180225`

---

## 3. Sentinel-2 (Multispectral Optical)
**Directory Types**: 39  
**ESA Copernicus Programme**

### Specific Satellites:
- **Sentinel-2A**: Operational since 2015
- **Sentinel-2B**: Operational since 2017

### Product Subsets:
- **True Color**: Natural RGB visualization
- **Natural Color**: Enhanced natural appearance
- **Color Infrared (CIR)**: Vegetation analysis
- **SWIR (Short-Wave Infrared)**: Moisture and geology
- **NDVI**: Normalized Difference Vegetation Index
- **MNDWI**: Modified Normalized Difference Water Index
- **Flood Proxy Map (FPM)**: Flood detection
- **Water Extent**: Water body mapping

### Directory Examples:
- `sentinel2`, `sentinel`
- `trueColor`, `naturalColor`, `cir`, `swir`
- `ndvi`, `mndwi`
- `s2_swir_vermont_flooding`
- Date-based: `20190316_171039`, `20200906`

---

## 4. Landsat Series
**Directory Types**: 34  
**NASA/USGS Partnership**

### Specific Satellites Detected:
- **Landsat 7**: ETM+ sensor (1999-present)
- **Landsat 8**: OLI/TIRS sensors (2013-present)
- **Landsat 9**: OLI-2/TIRS-2 sensors (2021-present)

### Product Subsets:
- **True Color**: RGB composite
- **Natural Color**: Enhanced visualization
- **Color Infrared (CIR)**: NIR-Red-Green composite
- **Panchromatic**: High-resolution grayscale
- **Thermal Infrared (TIR)**: Temperature mapping
- **NDVI**: Vegetation index
- **MNDWI**: Water index
- **dNBR**: Burn severity index

### File Naming Patterns:
- `LC08_*`: Landsat 8 Collection data
- `LC09_*`: Landsat 9 Collection data
- `LE07_*`: Landsat 7 ETM+ data
- `LS08_*`, `LS09_*`: Scene identifiers

### Directory Examples:
- `landsat`, `landsat7`, `landsat8`
- `trueColor`, `naturalColor`, `colorIR`
- `dnbr`, `ndvi`, `mndwi`
- `panchromatic`, `tir`, `tc`

---

## 5. MODIS (Moderate Resolution Imaging Spectroradiometer)
**Directory Types**: 3  
**NASA Terra and Aqua Satellites**

### Specific Satellites:
- **Terra (MOD)**: Morning orbit (1999-present)
- **Aqua (MYD)**: Afternoon orbit (2002-present)

### Product Types:
- Thermal anomalies/Fire detection
- Land surface temperature
- Vegetation indices
- True color imagery

### Directory Examples:
- `MODIS`, `modis`
- `NLE2018`

---

## 6. VIIRS (Visible Infrared Imaging Radiometer Suite)
**Directory Types**: 42  
**NOAA/NASA Joint Polar Satellite System**

### Specific Satellites Detected:
- **Suomi NPP**: SNPP (2011-present)
- **NOAA-20/JPSS-1**: Primary operational (2017-present)
- **NOAA-21/JPSS-2**: Latest addition (2022-present)

### Product Subsets:
- **Black Marble HD (BMHD)**: High-resolution nighttime lights
- **Day/Night Band (DNB)**: Low-light imaging
- **Thermal Infrared**: Temperature products
- **True Color**: RGB imagery
- **Ash Index**: Volcanic ash detection
- **SO2**: Sulfur dioxide measurements
- **Aerosol**: Atmospheric particles
- **Flood Products**: Water extent mapping

### Directory Examples:
- `viirs`, `VIIRS`, `SNPP_VIIRS`
- `BMHD_*` (various locations/events)
- `blackmarble`, `blackmarble_hd`
- `dnb`, `dnb_sport`, `viirs_dnb`
- `thermal_infrared`, `true_color`
- `ash_index`, `ashindex`, `so2`

---

## 7. Planet Labs Constellation
**Directory Types**: 22  
**Commercial SmallSat Constellation**

### Satellites:
- **Dove/SuperDove**: 430+ satellites
- 3-meter resolution
- Daily global coverage capability

### Product Subsets:
- **True Color**: Standard RGB
- **Color Infrared (CIR)**: NIR-Red-Green
- **Water Extent**: Flood mapping
- **Surface Reflectance**: Atmospherically corrected

### Directory Examples:
- `planet`
- `TrueColor`, `tc`, `true`
- `CIR`, `cir`, `colorIR`
- `water_extents`, `new_water_extents`
- Date/location based: `20230712`, `minnesota`, `newHampshire`

---

## 8. Maxar (WorldView/GeoEye)
**Directory Types**: 2  
**Commercial Very High Resolution**

### Specific Satellites Detected:
- **WorldView-3**: 30cm resolution (2014-present)
- **WorldView Legion**: Latest 30cm constellation (2024)

### Products:
- Very high resolution optical imagery
- True color composites
- Multispectral analysis
- Change detection (`maxar_chng`)

### Directory Examples:
- `maxar`
- `maxar_chng`

---

## 9. ASTER (Advanced Spaceborne Thermal Emission and Reflection Radiometer)
**Directory Types**: 8  
**NASA/Japan METI - Terra Satellite**

### Products:
- VNIR (15m): Visible/Near-infrared
- SWIR (30m): Short-wave infrared
- TIR (90m): Thermal infrared
- Digital Elevation Models

### Directory Examples:
- `aster`, `Aster`
- `NASA_Disaster_Portal`
- `master` (related MASTER airborne sensor)

---

## 10. MASTER (MODIS/ASTER Airborne Simulator)
**Directory Types**: 3  
**NASA Airborne Platform**

### Products:
- 50-band hyperspectral imagery
- Thermal infrared
- Fire characterization
- Calibration/validation data

### Directory Examples:
- `Donnell`, `Ferguson`, `Mendocino`
- `MASTERL1B_*` products

---

## 11. ECOSTRESS
**Directory Types**: 2  
**NASA - International Space Station**

### Products:
- Land surface temperature (70m)
- Evapotranspiration
- Water stress indices
- Thermal anomalies

### Directory Examples:
- `ECOSTRESS`, `ecostress`

---

## 12. HLS (Harmonized Landsat Sentinel-2)
**Directory Types**: 4  
**NASA Fusion Product**

### Products:
- 30m harmonized surface reflectance
- Combined Landsat 8/9 + Sentinel-2A/2B
- 2-3 day revisit frequency

### Specific Satellites in Products:
- Sentinel-2A, Sentinel-2B
- Landsat 8, Landsat 9

### Directory Examples:
- `archive`, `dist_hls`
- `dswx`, `dswx_hls`

---

## 13. SMAP (Soil Moisture Active Passive)
**Directory Types**: 1  
**NASA L-band Radiometer**

### Products:
- Soil moisture (40km resolution)
- Freeze/thaw state
- ~5cm penetration depth

### Directory Examples:
- `SMAP_clip`

---

## 14. GPM/IMERG
**Directory Types**: 1  
**Global Precipitation Measurement**

### Products:
- Precipitation rate and accumulation
- 30-minute temporal resolution
- 0.1° spatial resolution

### Directory Examples:
- `gpm`

---

## 15. GOES
**Directory Types**: 1  
**NOAA Geostationary Weather Satellites**

### Products:
- Weather monitoring
- Fire detection
- 5-15 minute imaging
- Lightning mapping

### Directory Examples:
- `goes`

---

## 16. Burn Index Products
**Directory Types**: 1  
**Derived from Optical Satellites**

### Products:
- **NBR**: Normalized Burn Ratio
- **dNBR**: Differenced NBR (pre/post-fire)
- Burn severity classification

### Directory Examples:
- `dnbr`

---

## 17. Other Notable Products

### RADARSAT-2 (Canadian Space Agency)
- C-band SAR
- Directory: `radarsat2`

### ALOS-2 (JAXA)
- L-band SAR (PALSAR-2)
- InSAR products
- Directory: `alos2`

### OMPS (Ozone Mapping and Profiler Suite)
- SO2 measurements (volcanic/anthropogenic)
- UV Aerosol Index
- Directories: `omps`, `so2_*`, `uvai`

### Black Marble HD (NASA)
- High-resolution nighttime lights
- Power outage detection
- Directories: `blackmarblehd`, `BMHD_*`

### DFO (Dartmouth Flood Observatory)
- Flood extent products
- Multi-sensor composites
- Directories: `dfo`, `dartmouth_flood_observatory`

### UAVSAR (NASA JPL)
- Airborne L-band SAR
- Polarimetric data
- Directory: `uavsar`

### Satellogic
- Commercial constellation
- High-cadence imaging
- Directories: `satellogic`, various timestamp directories

### PeruSat
- Peruvian Earth observation satellite
- High-resolution optical
- Directory structure: `IMG_PER1_*`

---

## File Naming Conventions Summary

### Date Formats:
- `YYYYMMDD`: Basic date (20210324)
- `YYYYMMDD_HHMMSS`: Date + time
- `YYYYDDD`: Year + day of year

### Common Patterns:
- **Sentinel-1**: `S1A_*`, `S1B_*`
- **Sentinel-2**: `S2A_*`, `S2B_*`, `T*` (tile ID)
- **Landsat**: `LC08_*`, `LC09_*`, `LE07_*`
- **MODIS**: `MOD*` (Terra), `MYD*` (Aqua)
- **VIIRS**: `VNP*`, `VJ1*`, `SNPP_*`, `JPSS1_*`
- **Planet**: Timestamp-based with `_sr_` or `_toa_`

### Product Type Indicators:
- `_naturalcolor_`, `_truecolor_`: RGB composites
- `_cir_`, `_colorir_`: Color infrared
- `_ndvi_`, `_mndwi_`: Indices
- `_dnbr_`: Burn indices
- `_waterextent_`: Flood products
- `_dpm_`, `_fpm_`: Proxy maps

---

## Statistical Summary

- **Total unique directory types**: 200+
- **Total TIF files in dataset**: 34,460+
- **Years covered**: 2020-2025
- **Most diverse product**: VIIRS (42 directory types)
- **Most focused products**: Single directory types (GOES, GPM, SMAP, Burn Index)

---

*Document generated from analysis of drcs_activations_tif_files.json and source_products_analysis.json*