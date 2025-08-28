# Earth Observation Filename Structure and Naming Conventions

## Overview
This document describes the filename structures and naming conventions used in NASA Disasters DRCS activation data for various Earth observation products.

---

## Satellite-Specific Naming Conventions

### Sentinel-1 (ESA C-band SAR)
**Pattern**: `S1[A|B]_[mode]_[date]_[time]_[product].tif`

**Examples**:
- `S1_A131_20201030_20201024_disp_cm.tif`
- `s1a_sarRGB_20200927_000158_000403.tif`
- `20210417_231440_231350_S1A_RGB_hurricaneFlorence_WGS84.tif`

**Key Identifiers**:
- `S1A`: Sentinel-1A satellite
- `S1B`: Sentinel-1B satellite
- Date format: YYYYMMDD
- Time format: HHMMSS

---

### Sentinel-2 (ESA Multispectral)
**Pattern**: `S2[A|B]_[product]_[date]_[time]_[tile].tif`

**Examples**:
- `s2a_naturalcolorRGB_20200924_190131_T10SCG.tif`
- `L1C_T18QXF_A032097_20210814T153621.tif`
- `T14TPNP_20240625T172001_SWI_20m.TIF`

**Key Identifiers**:
- `S2A`: Sentinel-2A satellite
- `S2B`: Sentinel-2B satellite
- `T[code]`: Military Grid Reference System tile ID
- Product types: naturalcolor, swir, ndvi, mndwi

---

### Landsat Series (NASA/USGS)
**Pattern**: `L[C|E|S][07|08|09]_[level]_[path][row]_[date]_[product].tif`

**Examples**:
- `LC08_044034_2020_0724_0926_dnbr.tif`
- `LS09_016040_20220920_naturalColor_wgs84.tif`
- `LC08_L1TP_021035_20160306_20170224_01_T1`

**Key Identifiers**:
- `LC08`: Landsat 8 OLI/TIRS
- `LC09`: Landsat 9 OLI-2/TIRS-2
- `LE07`: Landsat 7 ETM+
- `LS08/LS09`: Alternative scene identifiers
- Path/Row: WRS-2 coordinates (e.g., 044034)

**Processing Levels**:
- `L1TP`: Terrain Precision corrected
- `L1GT`: Systematic Terrain corrected
- `L1GS`: Systematic corrected

---

### MODIS (NASA Terra/Aqua)
**Pattern**: `[MOD|MYD][product]_[date]_[time]_[version].tif`

**Examples**:
- `MOD_DS1_GeoTIFF.tif` (Terra MODIS)
- `MYD_RGB_GeoTIFF.tif` (Aqua MODIS)
- `StVincent_20210409_165500_MYD_DS1_GeoTIFF.tif`

**Key Identifiers**:
- `MOD`: Terra satellite (morning)
- `MYD`: Aqua satellite (afternoon)
- Product codes follow NASA MODIS naming

---

### VIIRS (NOAA/NASA)
**Pattern**: `[satellite]_viirs_[product]_[location]_d[date]_t[time].tif`

**Examples**:
- `snpp_omps_so2solo_17s_130.0e_d20201129_t0036000.tif`
- `jpss1_viirs_ashindex-day_26.5n_17.0w_d20210920_t1312000.tif`
- `VN20_DS1_GeoTIFF.tif`

**Key Identifiers**:
- `snpp`: Suomi NPP satellite
- `jpss1`: NOAA-20 (JPSS-1)
- `jpss2`: NOAA-21 (JPSS-2)
- `VN20`: NOAA-20 VIIRS
- `VNP`: VIIRS product prefix

---

### Planet Labs
**Pattern**: `[date]_[time]_[sat_id]_[level]_[product].tif`

**Examples**:
- `20211212_154746_15_toa_trueColor.tif`
- `20220922_135608_44_sr_ColorInfrared.tif`
- `20201110_163951_11_225b_3B_AnalyticMS_SR.tif`

**Key Elements**:
- Date: YYYYMMDD
- Time: HHMMSS
- Processing levels: `toa` (top of atmosphere), `sr` (surface reflectance)
- Products: trueColor, ColorInfrared

---

### Maxar (WorldView/GeoEye)
**Pattern**: `[date]_[time].[microseconds]_[satellite]_[product]_[event].tif`

**Examples**:
- `20220218_162701.939_worldview3_trueColor_Ian.tif`
- WorldView Legion: 30cm resolution products

**Key Identifiers**:
- `worldview1`, `worldview2`, `worldview3`
- `geoeye1`
- High precision timestamps with microseconds

---

### ARIA (InSAR Products)
**Pattern**: `ARIA_[product]_[source]_[date1]_[date2]_v[version].tif`

**Examples**:
- `ARIA_DPM_Sentinel-1_v0.3.tif`
- `ARIA_S1_DPM_CreekFire_Sep_13_Sep_19_7am.tif`
- `200115_210113_InSAR_map_30m.tif`

**Product Types**:
- `DPM`: Damage Proxy Map
- `FPM`: Flood Proxy Map
- `InSAR`: Interferometric products

---

## Product Type Indicators

### Color/Band Composites
- `truecolor`, `trueColor`: Standard RGB
- `naturalcolor`, `naturalColor`: Enhanced natural
- `cir`, `colorIR`, `ColorInfrared`: NIR-Red-Green
- `falsecolor`: Various band combinations
- `swir`: Short-wave infrared
- `rgb`, `RGB`: General color composite

### Indices and Derived Products
- `ndvi`: Normalized Difference Vegetation Index
- `mndwi`: Modified Normalized Difference Water Index
- `dnbr`, `nbr`: (Differenced) Normalized Burn Ratio
- `waterextent`, `water_extent`: Flood mapping
- `dpm`: Damage Proxy Map
- `fpm`: Flood Proxy Map

### Thermal Products
- `tir`: Thermal Infrared
- `thermal_infrared`: Temperature products
- `lst`, `LST`: Land Surface Temperature

### SAR Products
- `amp`: Amplitude
- `coh`: Coherence
- `sigma`: Sigma naught (backscatter)
- `HH`, `VV`, `HV`, `VH`: Polarization modes

---

## Date and Time Formats

### Date Formats
- `YYYYMMDD`: Standard format (20210324)
- `YYYY_MM_DD`: Underscore separated
- `YYYYDDD`: Year + day of year (2021123)
- `YYYYmMMDD`: Month indicator (2021m0407)

### Time Formats
- `HHMMSS`: Standard time (143621)
- `HHMMSS_HHMMSS`: Time range
- `tHHMMSS`: Time prefix indicator
- `eHHMMSS`: End time indicator

### Combined DateTime
- `YYYYMMDD_HHMMSS`: Full timestamp
- `YYYYMMDDTHHMMSS`: ISO-like format

---

## Geographic Identifiers

### Coordinate Systems
- `wgs84`, `WGS84`: World Geodetic System 1984
- `utm`, `UTM`: Universal Transverse Mercator
- `epsg:[code]`: EPSG projection codes

### Location Formats
- Decimal degrees: `17.5n_130.0e`
- Tile systems: `T10SCG` (Sentinel-2 MGRS)
- Path/Row: `044034` (Landsat WRS-2)
- Named locations: `vermont_flooding`, `creek_fire`

---

## Processing Level Indicators

### Standard Levels
- `L0`: Raw data
- `L1`: Calibrated/corrected
- `L1B`, `L1C`, `L1T`: Specific L1 products
- `L2`: Derived geophysical variables
- `L3`: Gridded/mapped
- `L4`: Model output/analysis

### Atmospheric Correction
- `toa`: Top of Atmosphere
- `sr`, `SR`: Surface Reflectance
- `boa`: Bottom of Atmosphere

---

## Version and Collection Indicators

### Version Formats
- `v[0-9].[0-9]`: Version number (v0.3)
- `V[000]`: Collection version (V003)
- `01_T1`: Processing tier/collection

### Revision Indicators
- `_RT`: Real-time processing
- `_NRT`: Near real-time
- `_STD`: Standard processing

---

## Special Product Identifiers

### Night Lights/Power
- `BMHD`: Black Marble HD
- `dnb`, `DNB`: Day/Night Band
- `blackmarble`: NASA night lights

### Volcanic Products
- `so2`, `SO2`: Sulfur dioxide
- `ashindex`, `ash`: Volcanic ash
- `uvai`: UV Aerosol Index

### Water/Flood Products
- `waterextent`, `WaterExtents`
- `flood_extent`
- `fcWM`: Flood classification water mask
- `dfo`, `DFO`: Dartmouth Flood Observatory

### Fire Products
- `thermal_anomaly`
- `fire_mask`
- `burn_severity`

---

## File Extensions and Formats

### Primary Format
- `.tif`, `.TIF`: GeoTIFF (standard)
- `.TIFF`: Alternative GeoTIFF extension

### Metadata/Auxiliary
- `.xml`: Metadata files
- `.json`: Processing parameters
- `.txt`: Documentation

---

## Directory Structure Patterns

### Event-Based
```
/[year]/[event_name]/[satellite]/[product]/[files].tif
```
Example: `/2020/california_fires/sentinel2/natural/`

### Date-Based
```
/[satellite]/[date]/[product]/[files].tif
```
Example: `/landsat8/20200907/naturalColor/`

### Product-Based
```
/[product_type]/[satellite]/[date]/[files].tif
```
Example: `/water_extent/sentinel1/20210417/`

---

## Quality and Processing Flags

### Common Suffixes
- `_clip`: Subset/clipped region
- `_mosaic`: Multiple scenes combined
- `_composite`: Temporal composite
- `_masked`: Cloud/quality masked
- `_harmonized`: Cross-sensor harmonization
- `_corrected`: Additional corrections applied

---

## Example Full Filenames Decoded

1. **Sentinel-1 SAR**:
   `S1A_IW_GRDH_1SDV_20210417T231350_sigma0_VV_db_waterMask.tif`
   - S1A: Sentinel-1A
   - IW: Interferometric Wide swath
   - GRDH: Ground Range Detected High res
   - Date/Time: 2021-04-17 23:13:50
   - Product: Sigma0 backscatter, VV polarization, water mask

2. **Landsat 8**:
   `LC08_L1TP_044034_20200724_20200926_01_T1_B4B3B2_naturalColor.tif`
   - LC08: Landsat 8
   - L1TP: Level 1 Terrain Precision
   - 044034: Path 44, Row 34
   - Dates: Acquired 2020-07-24, Processed 2020-09-26
   - Bands: 4,3,2 (Natural Color)

3. **VIIRS Night Lights**:
   `SNPP_VIIRS_DNB_20210829_BlackMarble_HD_Louisiana_power_outage.tif`
   - SNPP: Suomi NPP satellite
   - DNB: Day/Night Band
   - Date: 2021-08-29
   - Product: Black Marble HD power outage analysis

---

*This document is maintained for the NASA Disasters DRCS data repository*
*Last updated based on analysis of 34,460+ TIF files from 2020-2025*