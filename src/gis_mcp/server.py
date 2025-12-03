"""GIS MCP Server - Main entry point."""

import logging
from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from gis_mcp.config import get_config
from gis_mcp.tools.files import read_geo_file, write_geo_file
from gis_mcp.tools.geocoding import geocode_address, reverse_geocode_coords
from gis_mcp.tools.geometry import (
    calculate_buffer,
    calculate_distance,
    perform_spatial_query,
    transform_coordinates,
)
from gis_mcp.tools.routing import calculate_isochrone, calculate_route

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
    """Convert an address to geographic coordinates (latitude/longitude).

    Uses Nominatim (OpenStreetMap) for geocoding. Rate limited to 1 request/second.

    Returns coordinates, display name, bounding box, and confidence score.
    """
    return await geocode_address(address)


@mcp.tool()
async def reverse_geocode(
    lat: Annotated[float, Field(description="Latitude (-90 to 90)")],
    lon: Annotated[float, Field(description="Longitude (-180 to 180)")]
) -> dict:
    """Convert coordinates to an address (reverse geocoding).

    Uses Nominatim (OpenStreetMap). Rate limited to 1 request/second.

    Returns the address components and display name for the given coordinates.
    """
    return await reverse_geocode_coords(lat, lon)


# =============================================================================
# GEOMETRY TOOLS
# =============================================================================

@mcp.tool()
async def distance(
    lat1: Annotated[float, Field(description="Latitude of first point")],
    lon1: Annotated[float, Field(description="Longitude of first point")],
    lat2: Annotated[float, Field(description="Latitude of second point")],
    lon2: Annotated[float, Field(description="Longitude of second point")],
    method: Annotated[str, Field(description="Method: 'haversine' or 'geodesic'")] = "geodesic"
) -> dict:
    """Calculate the distance between two geographic points.

    Supports two methods:
    - haversine: Faster, assumes spherical Earth, ~0.3% error
    - geodesic: More accurate, uses WGS84 ellipsoid

    Returns distance in meters, kilometers, miles, and feet.
    """
    return await calculate_distance(lat1, lon1, lat2, lon2, method)


@mcp.tool()
async def buffer(
    geometry: Annotated[dict, Field(description="GeoJSON geometry")],
    distance_meters: Annotated[float, Field(description="Buffer distance in meters")],
    resolution: Annotated[int, Field(description="Segments for curved edges")] = 16
) -> dict:
    """Create a buffer zone around a geometry.

    Accepts GeoJSON geometry and returns a buffered polygon.
    The buffer is calculated using a local UTM projection for accuracy.

    Example input geometry:
    {"type": "Point", "coordinates": [2.3522, 48.8566]}
    """
    return await calculate_buffer(geometry, distance_meters, resolution)


@mcp.tool()
async def spatial_query(
    geometry1: Annotated[dict, Field(description="First GeoJSON geometry")],
    geometry2: Annotated[dict, Field(description="Second GeoJSON geometry")],
    operation: Annotated[str, Field(description="Spatial operation to perform")]
) -> dict:
    """Perform spatial operations between two geometries.

    Operations:
    - intersection: Area where both geometries overlap
    - union: Combined area of both geometries
    - difference: Area of geometry1 not in geometry2
    - contains: Check if geometry1 contains geometry2 (returns boolean)
    - within: Check if geometry1 is within geometry2 (returns boolean)
    - intersects: Check if geometries intersect (returns boolean)
    - overlaps: Check if geometries overlap (returns boolean)

    Returns the resulting geometry or boolean for predicate operations.
    """
    return await perform_spatial_query(geometry1, geometry2, operation)


@mcp.tool()
async def transform_crs(
    geometry: Annotated[dict, Field(description="GeoJSON geometry to transform")],
    source_crs: Annotated[str, Field(description="Source CRS (e.g., 'EPSG:4326')")],
    target_crs: Annotated[str, Field(description="Target CRS (e.g., 'EPSG:3857')")]
) -> dict:
    """Transform coordinates between coordinate reference systems.

    Common CRS codes:
    - EPSG:4326 - WGS84 (GPS coordinates)
    - EPSG:3857 - Web Mercator (Google Maps, OpenStreetMap)
    - EPSG:2154 - RGF93 / Lambert-93 (France)
    - EPSG:32632 - WGS84 / UTM zone 32N (Central Europe)

    Returns the geometry in the target CRS.
    """
    return await transform_coordinates(geometry, source_crs, target_crs)


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
    """Calculate a route between two points.

    Uses OSRM (Open Source Routing Machine) for routing calculations.
    Returns distance, duration, and route geometry as GeoJSON.

    Profiles:
    - driving: Car routing (default)
    - walking: Pedestrian routing
    - cycling: Bicycle routing
    """
    return await calculate_route(start_lat, start_lon, end_lat, end_lon, profile)


@mcp.tool()
async def isochrone(
    lat: Annotated[float, Field(description="Center point latitude")],
    lon: Annotated[float, Field(description="Center point longitude")],
    time_minutes: Annotated[int, Field(description="Travel time in minutes")],
    profile: Annotated[str, Field(description="Profile: driving/walking/cycling")] = "driving"
) -> dict:
    """Calculate an isochrone (area reachable within a time limit).

    Returns a polygon representing the area that can be reached from the
    center point within the specified time limit.

    Note: This uses OSRM table queries to approximate the isochrone.
    For production use, consider Valhalla which has native isochrone support.
    """
    return await calculate_isochrone(lat, lon, time_minutes, profile)


# =============================================================================
# FILE TOOLS
# =============================================================================

@mcp.tool()
async def read_file(
    file_path: Annotated[str, Field(description="Path to geospatial file")],
    layer: Annotated[str | None, Field(description="Layer name")] = None,
    limit: Annotated[int | None, Field(description="Max features to return")] = None
) -> dict:
    """Read a geospatial file and return its features.

    Supported formats:
    - GeoJSON (.geojson, .json)
    - Shapefile (.shp)
    - GeoPackage (.gpkg)
    - And 200+ other formats via GDAL

    Returns features as GeoJSON FeatureCollection with metadata.
    """
    return await read_geo_file(file_path, layer, limit)


@mcp.tool()
async def write_file(
    features: Annotated[dict, Field(description="GeoJSON FeatureCollection")],
    file_path: Annotated[str, Field(description="Output file path")],
    driver: Annotated[str, Field(description="Format: GeoJSON/Shapefile/GPKG")] = "GeoJSON"
) -> dict:
    """Write features to a geospatial file.

    Supported output formats:
    - GeoJSON: Universal JSON format
    - ESRI Shapefile: Legacy format for ArcGIS compatibility
    - GPKG (GeoPackage): Modern SQLite-based format

    Returns path to created file and feature count.
    """
    return await write_geo_file(features, file_path, driver)


def main():
    """Run the MCP server."""
    logger.info("Starting GIS MCP Server...")
    config = get_config()
    logger.info(f"Nominatim URL: {config.nominatim.base_url}")
    logger.info(f"OSRM URL: {config.osrm.base_url}")
    mcp.run()


if __name__ == "__main__":
    main()
