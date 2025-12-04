"""GIS MCP Server - Main entry point."""

import logging
from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from gis_mcp.config import get_config

# Import all tool implementations
from gis_mcp.tools.elevation import get_elevation, get_elevation_profile
from gis_mcp.tools.files import (
    read_geo_file,
    write_geo_file,
    spatial_join as _spatial_join,
    clip_features as _clip_features,
    dissolve_features as _dissolve_features,
    overlay_features as _overlay_features,
    merge_features as _merge_features,
)
from gis_mcp.tools.geocoding import geocode_address, reverse_geocode_coords
from gis_mcp.tools.geometry import (
    calculate_buffer,
    calculate_distance,
    perform_spatial_query,
    transform_coordinates,
    get_centroid as _get_centroid,
    simplify_geometry as _simplify_geometry,
    get_convex_hull as _get_convex_hull,
    get_envelope as _get_envelope,
    validate_geometry as _validate_geometry,
    calculate_area as _calculate_area,
    calculate_length as _calculate_length,
    get_utm_zone as _get_utm_zone,
    get_crs_info as _get_crs_info,
)
from gis_mcp.tools.routing import calculate_isochrone, calculate_route
from gis_mcp.tools.raster import (
    read_raster as _read_raster,
    calculate_ndvi as _calculate_ndvi,
    calculate_hillshade as _calculate_hillshade,
    calculate_slope as _calculate_slope,
    zonal_statistics as _zonal_statistics,
    reproject_raster as _reproject_raster,
    raster_calculator as _raster_calculator,
)
from gis_mcp.tools.visualization import (
    create_static_map as _create_static_map,
    create_web_map as _create_web_map,
    create_choropleth_map as _create_choropleth_map,
)
from gis_mcp.tools.statistics import (
    calculate_moran_i as _calculate_moran_i,
    calculate_local_moran as _calculate_local_moran,
    calculate_getis_ord as _calculate_getis_ord,
    create_spatial_weights as _create_spatial_weights,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("GIS Server")


# =============================================================================
# GEOCODING TOOLS
# =============================================================================

@mcp.tool()
async def geocode(
    address: Annotated[str, Field(description="Address to geocode")]
) -> dict:
    """Convert an address to geographic coordinates (latitude/longitude)."""
    return await geocode_address(address)


@mcp.tool()
async def reverse_geocode(
    lat: Annotated[float, Field(description="Latitude (-90 to 90)")],
    lon: Annotated[float, Field(description="Longitude (-180 to 180)")]
) -> dict:
    """Convert coordinates to an address (reverse geocoding)."""
    return await reverse_geocode_coords(lat, lon)


# =============================================================================
# GEOMETRY TOOLS (Basic)
# =============================================================================

@mcp.tool()
async def distance(
    lat1: Annotated[float, Field(description="Latitude of first point")],
    lon1: Annotated[float, Field(description="Longitude of first point")],
    lat2: Annotated[float, Field(description="Latitude of second point")],
    lon2: Annotated[float, Field(description="Longitude of second point")],
    method: Annotated[str, Field(description="Method: 'haversine' or 'geodesic'")] = "geodesic"
) -> dict:
    """Calculate the distance between two geographic points."""
    return await calculate_distance(lat1, lon1, lat2, lon2, method)


@mcp.tool()
async def buffer(
    geometry: Annotated[dict, Field(description="GeoJSON geometry")],
    distance_meters: Annotated[float, Field(description="Buffer distance in meters")],
    resolution: Annotated[int, Field(description="Segments for curved edges")] = 16
) -> dict:
    """Create a buffer zone around a geometry."""
    return await calculate_buffer(geometry, distance_meters, resolution)


@mcp.tool()
async def spatial_query(
    geometry1: Annotated[dict, Field(description="First GeoJSON geometry")],
    geometry2: Annotated[dict, Field(description="Second GeoJSON geometry")],
    operation: Annotated[str, Field(description="Operation: intersection/union/difference/contains/within/intersects")]
) -> dict:
    """Perform spatial operations between two geometries."""
    return await perform_spatial_query(geometry1, geometry2, operation)


@mcp.tool()
async def transform_crs(
    geometry: Annotated[dict, Field(description="GeoJSON geometry to transform")],
    source_crs: Annotated[str, Field(description="Source CRS (e.g., 'EPSG:4326')")],
    target_crs: Annotated[str, Field(description="Target CRS (e.g., 'EPSG:3857')")]
) -> dict:
    """Transform coordinates between coordinate reference systems."""
    return await transform_coordinates(geometry, source_crs, target_crs)


# =============================================================================
# GEOMETRY TOOLS (Advanced Shapely)
# =============================================================================

@mcp.tool()
async def centroid(
    geometry: Annotated[dict, Field(description="GeoJSON geometry")]
) -> dict:
    """Get the centroid (center point) of a geometry."""
    return await _get_centroid(geometry)


@mcp.tool()
async def simplify(
    geometry: Annotated[dict, Field(description="GeoJSON geometry")],
    tolerance: Annotated[float, Field(description="Simplification tolerance")],
    preserve_topology: Annotated[bool, Field(description="Preserve topology")] = True
) -> dict:
    """Simplify a geometry using Douglas-Peucker algorithm."""
    return await _simplify_geometry(geometry, tolerance, preserve_topology)


@mcp.tool()
async def convex_hull(
    geometry: Annotated[dict, Field(description="GeoJSON geometry")]
) -> dict:
    """Get the convex hull of a geometry."""
    return await _get_convex_hull(geometry)


@mcp.tool()
async def envelope(
    geometry: Annotated[dict, Field(description="GeoJSON geometry")]
) -> dict:
    """Get the bounding box (envelope) of a geometry."""
    return await _get_envelope(geometry)


@mcp.tool()
async def validate(
    geometry: Annotated[dict, Field(description="GeoJSON geometry")]
) -> dict:
    """Validate a geometry and fix it if invalid."""
    return await _validate_geometry(geometry)


@mcp.tool()
async def area(
    geometry: Annotated[dict, Field(description="GeoJSON Polygon or MultiPolygon")]
) -> dict:
    """Calculate the area of a polygon geometry in multiple units."""
    return await _calculate_area(geometry)


@mcp.tool()
async def length(
    geometry: Annotated[dict, Field(description="GeoJSON geometry")]
) -> dict:
    """Calculate the length/perimeter of a geometry."""
    return await _calculate_length(geometry)


# =============================================================================
# PYPROJ TOOLS
# =============================================================================

@mcp.tool()
async def utm_zone(
    lat: Annotated[float, Field(description="Latitude")],
    lon: Annotated[float, Field(description="Longitude")]
) -> dict:
    """Get the UTM zone for a given coordinate."""
    return await _get_utm_zone(lat, lon)


@mcp.tool()
async def crs_info(
    crs_code: Annotated[str, Field(description="CRS identifier (e.g., 'EPSG:4326')")]
) -> dict:
    """Get detailed information about a coordinate reference system."""
    return await _get_crs_info(crs_code)


# =============================================================================
# ROUTING TOOLS
# =============================================================================

@mcp.tool()
async def route(
    start_lat: Annotated[float, Field(description="Start point latitude")],
    start_lon: Annotated[float, Field(description="Start point longitude")],
    end_lat: Annotated[float, Field(description="End point latitude")],
    end_lon: Annotated[float, Field(description="End point longitude")],
    profile: Annotated[str, Field(description="Profile: driving/walking/cycling")] = "driving"
) -> dict:
    """Calculate a route between two points."""
    return await calculate_route(start_lat, start_lon, end_lat, end_lon, profile)


@mcp.tool()
async def isochrone(
    lat: Annotated[float, Field(description="Center point latitude")],
    lon: Annotated[float, Field(description="Center point longitude")],
    time_minutes: Annotated[int, Field(description="Travel time in minutes")],
    profile: Annotated[str, Field(description="Profile: driving/walking/cycling")] = "driving"
) -> dict:
    """Calculate an isochrone (area reachable within a time limit)."""
    return await calculate_isochrone(lat, lon, time_minutes, profile)


# =============================================================================
# ELEVATION TOOLS
# =============================================================================

@mcp.tool()
async def elevation(
    lat: Annotated[float, Field(description="Latitude")],
    lon: Annotated[float, Field(description="Longitude")]
) -> dict:
    """Get elevation for a single point (meters above sea level)."""
    return await get_elevation(lat, lon)


@mcp.tool()
async def elevation_profile(
    geometry: Annotated[dict, Field(description="GeoJSON LineString geometry")],
    samples: Annotated[int, Field(description="Number of sample points")] = 100
) -> dict:
    """Get elevation profile along a line."""
    return await get_elevation_profile(geometry, samples)


# =============================================================================
# FILE I/O TOOLS
# =============================================================================

@mcp.tool()
async def read_file(
    file_path: Annotated[str, Field(description="Path to geospatial file")],
    layer: Annotated[str | None, Field(description="Layer name")] = None,
    limit: Annotated[int | None, Field(description="Max features to return")] = None
) -> dict:
    """Read a geospatial file (GeoJSON, Shapefile, GeoPackage, etc.)."""
    return await read_geo_file(file_path, layer, limit)


@mcp.tool()
async def write_file(
    features: Annotated[dict, Field(description="GeoJSON FeatureCollection")],
    file_path: Annotated[str, Field(description="Output file path")],
    driver: Annotated[str, Field(description="Format: GeoJSON/Shapefile/GPKG")] = "GeoJSON"
) -> dict:
    """Write features to a geospatial file."""
    return await write_geo_file(features, file_path, driver)


# =============================================================================
# GEOPANDAS TOOLS
# =============================================================================

@mcp.tool()
async def spatial_join(
    left_features: Annotated[dict, Field(description="Left GeoJSON FeatureCollection")],
    right_features: Annotated[dict, Field(description="Right GeoJSON FeatureCollection")],
    how: Annotated[str, Field(description="Join type: inner/left/right")] = "inner",
    predicate: Annotated[str, Field(description="Spatial predicate: intersects/contains/within")] = "intersects"
) -> dict:
    """Perform a spatial join between two feature collections."""
    return await _spatial_join(left_features, right_features, how, predicate)


@mcp.tool()
async def clip(
    features: Annotated[dict, Field(description="GeoJSON FeatureCollection to clip")],
    clip_geometry: Annotated[dict, Field(description="GeoJSON geometry to clip by")]
) -> dict:
    """Clip features to a boundary geometry."""
    return await _clip_features(features, clip_geometry)


@mcp.tool()
async def dissolve(
    features: Annotated[dict, Field(description="GeoJSON FeatureCollection")],
    by: Annotated[str | None, Field(description="Field to dissolve by")] = None,
    aggfunc: Annotated[str, Field(description="Aggregation: first/last/sum/mean")] = "first"
) -> dict:
    """Dissolve features, optionally by a property."""
    return await _dissolve_features(features, by, aggfunc)


@mcp.tool()
async def overlay(
    features1: Annotated[dict, Field(description="First GeoJSON FeatureCollection")],
    features2: Annotated[dict, Field(description="Second GeoJSON FeatureCollection")],
    how: Annotated[str, Field(description="Operation: intersection/union/difference")] = "intersection"
) -> dict:
    """Perform overlay operation between two feature collections."""
    return await _overlay_features(features1, features2, how)


@mcp.tool()
async def merge(
    feature_collections: Annotated[list[dict], Field(description="List of GeoJSON FeatureCollections")]
) -> dict:
    """Merge multiple feature collections into one."""
    return await _merge_features(feature_collections)


# =============================================================================
# RASTER TOOLS
# =============================================================================

@mcp.tool()
async def read_raster(
    file_path: Annotated[str, Field(description="Path to raster file")],
    band: Annotated[int | None, Field(description="Band number (1-indexed)")] = None
) -> dict:
    """Read a raster file and return metadata and statistics."""
    return await _read_raster(file_path, band)


@mcp.tool()
async def ndvi(
    red_band_path: Annotated[str, Field(description="Path to red band raster")],
    nir_band_path: Annotated[str, Field(description="Path to NIR band raster")],
    output_path: Annotated[str | None, Field(description="Output file path")] = None
) -> dict:
    """Calculate NDVI (Normalized Difference Vegetation Index)."""
    return await _calculate_ndvi(red_band_path, nir_band_path, output_path)


@mcp.tool()
async def hillshade(
    dem_path: Annotated[str, Field(description="Path to DEM raster")],
    output_path: Annotated[str | None, Field(description="Output file path")] = None,
    azimuth: Annotated[float, Field(description="Sun azimuth (degrees)")] = 315,
    altitude: Annotated[float, Field(description="Sun altitude (degrees)")] = 45
) -> dict:
    """Calculate hillshade from a Digital Elevation Model."""
    return await _calculate_hillshade(dem_path, output_path, azimuth, altitude)


@mcp.tool()
async def slope(
    dem_path: Annotated[str, Field(description="Path to DEM raster")],
    output_path: Annotated[str | None, Field(description="Output file path")] = None,
    units: Annotated[str, Field(description="Output units: degrees/percent")] = "degrees"
) -> dict:
    """Calculate slope from a Digital Elevation Model."""
    return await _calculate_slope(dem_path, output_path, units)


@mcp.tool()
async def zonal_stats(
    raster_path: Annotated[str, Field(description="Path to raster file")],
    zones_path: Annotated[str, Field(description="Path to vector zones file")],
    band: Annotated[int, Field(description="Band number")] = 1
) -> dict:
    """Calculate zonal statistics for a raster using vector zones."""
    return await _zonal_statistics(raster_path, zones_path, band)


@mcp.tool()
async def reproject_raster(
    input_path: Annotated[str, Field(description="Input raster path")],
    output_path: Annotated[str, Field(description="Output raster path")],
    target_crs: Annotated[str, Field(description="Target CRS (e.g., 'EPSG:4326')")],
    resampling: Annotated[str, Field(description="Resampling: nearest/bilinear/cubic")] = "nearest"
) -> dict:
    """Reproject a raster to a different CRS."""
    return await _reproject_raster(input_path, output_path, target_crs, resampling)


@mcp.tool()
async def raster_calc(
    expression: Annotated[str, Field(description="Math expression (e.g., 'A + B')")],
    rasters: Annotated[dict[str, str], Field(description="Variable to file path mapping")],
    output_path: Annotated[str, Field(description="Output file path")]
) -> dict:
    """Perform raster algebra using a mathematical expression."""
    return await _raster_calculator(expression, rasters, output_path)


# =============================================================================
# VISUALIZATION TOOLS
# =============================================================================

@mcp.tool()
async def static_map(
    features: Annotated[dict, Field(description="GeoJSON features")],
    output_path: Annotated[str | None, Field(description="Output file path")] = None,
    title: Annotated[str | None, Field(description="Map title")] = None
) -> dict:
    """Create a static map image from GeoJSON features (requires matplotlib)."""
    return await _create_static_map(features, output_path, title)


@mcp.tool()
async def web_map(
    features: Annotated[dict, Field(description="GeoJSON features")],
    output_path: Annotated[str | None, Field(description="Output HTML file path")] = None,
    title: Annotated[str | None, Field(description="Map title")] = None,
    basemap: Annotated[str, Field(description="Basemap provider")] = "OpenStreetMap"
) -> dict:
    """Create an interactive web map (requires folium)."""
    return await _create_web_map(features, output_path, title=title, basemap=basemap)


@mcp.tool()
async def choropleth_map(
    features: Annotated[dict, Field(description="GeoJSON FeatureCollection")],
    value_field: Annotated[str, Field(description="Property field for coloring")],
    output_path: Annotated[str | None, Field(description="Output HTML file path")] = None,
    title: Annotated[str | None, Field(description="Map title")] = None
) -> dict:
    """Create a choropleth (thematic) map based on a property value."""
    return await _create_choropleth_map(features, value_field, output_path, title=title)


# =============================================================================
# SPATIAL STATISTICS TOOLS
# =============================================================================

@mcp.tool()
async def moran_i(
    features: Annotated[dict, Field(description="GeoJSON FeatureCollection")],
    value_field: Annotated[str, Field(description="Numeric property field")],
    weight_type: Annotated[str, Field(description="Weight type: queen/rook/knn")] = "queen"
) -> dict:
    """Calculate Global Moran's I for spatial autocorrelation (requires libpysal)."""
    return await _calculate_moran_i(features, value_field, weight_type)


@mcp.tool()
async def local_moran(
    features: Annotated[dict, Field(description="GeoJSON FeatureCollection")],
    value_field: Annotated[str, Field(description="Numeric property field")],
    weight_type: Annotated[str, Field(description="Weight type: queen/rook/knn")] = "queen"
) -> dict:
    """Calculate Local Moran's I (LISA) for cluster detection."""
    return await _calculate_local_moran(features, value_field, weight_type)


@mcp.tool()
async def hotspot_analysis(
    features: Annotated[dict, Field(description="GeoJSON FeatureCollection")],
    value_field: Annotated[str, Field(description="Numeric property field")],
    weight_type: Annotated[str, Field(description="Weight type: distance/queen")] = "distance"
) -> dict:
    """Perform Getis-Ord Gi* hot spot analysis."""
    return await _calculate_getis_ord(features, value_field, weight_type)


@mcp.tool()
async def spatial_weights(
    features: Annotated[dict, Field(description="GeoJSON FeatureCollection")],
    weight_type: Annotated[str, Field(description="Type: queen/rook/knn/distance")] = "queen",
    k: Annotated[int, Field(description="Number of neighbors for KNN")] = 5
) -> dict:
    """Create and analyze a spatial weights matrix."""
    return await _create_spatial_weights(features, weight_type, k)


def main():
    """Run the MCP server."""
    logger.info("Starting GIS MCP Server...")
    config = get_config()
    logger.info(f"Nominatim URL: {config.nominatim.base_url}")
    logger.info(f"OSRM URL: {config.osrm.base_url}")
    logger.info("Tools: Geocoding, Geometry, Routing, Files, Raster, Visualization, Statistics")
    mcp.run()


if __name__ == "__main__":
    main()
