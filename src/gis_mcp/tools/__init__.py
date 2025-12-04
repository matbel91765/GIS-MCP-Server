"""GIS MCP Tools - Comprehensive geospatial operations."""

# Elevation tools
from gis_mcp.tools.elevation import get_elevation, get_elevation_profile

# File I/O tools
from gis_mcp.tools.files import (
    read_geo_file,
    write_geo_file,
    spatial_join,
    clip_features,
    dissolve_features,
    overlay_features,
    merge_features,
)

# Geocoding tools
from gis_mcp.tools.geocoding import geocode_address, reverse_geocode_coords

# Geometry tools (Shapely + PyProj)
from gis_mcp.tools.geometry import (
    calculate_buffer,
    calculate_distance,
    perform_spatial_query,
    transform_coordinates,
    get_centroid,
    simplify_geometry,
    get_convex_hull,
    get_envelope,
    validate_geometry,
    calculate_area,
    calculate_length,
    get_utm_zone,
    get_crs_info,
)

# Routing tools
from gis_mcp.tools.routing import calculate_isochrone, calculate_route

# Raster tools
from gis_mcp.tools.raster import (
    read_raster,
    calculate_ndvi,
    calculate_hillshade,
    calculate_slope,
    zonal_statistics,
    reproject_raster,
    raster_calculator,
)

# Visualization tools
from gis_mcp.tools.visualization import (
    create_static_map,
    create_web_map,
    create_choropleth_map,
)

# Spatial statistics tools
from gis_mcp.tools.statistics import (
    calculate_moran_i,
    calculate_local_moran,
    calculate_getis_ord,
    create_spatial_weights,
)

__all__ = [
    # Geocoding
    "geocode_address",
    "reverse_geocode_coords",
    # Geometry (basic)
    "calculate_buffer",
    "calculate_distance",
    "perform_spatial_query",
    "transform_coordinates",
    # Geometry (advanced Shapely)
    "get_centroid",
    "simplify_geometry",
    "get_convex_hull",
    "get_envelope",
    "validate_geometry",
    "calculate_area",
    "calculate_length",
    # PyProj
    "get_utm_zone",
    "get_crs_info",
    # Routing
    "calculate_route",
    "calculate_isochrone",
    # Files (basic)
    "read_geo_file",
    "write_geo_file",
    # Files (GeoPandas operations)
    "spatial_join",
    "clip_features",
    "dissolve_features",
    "overlay_features",
    "merge_features",
    # Elevation
    "get_elevation",
    "get_elevation_profile",
    # Raster
    "read_raster",
    "calculate_ndvi",
    "calculate_hillshade",
    "calculate_slope",
    "zonal_statistics",
    "reproject_raster",
    "raster_calculator",
    # Visualization
    "create_static_map",
    "create_web_map",
    "create_choropleth_map",
    # Statistics
    "calculate_moran_i",
    "calculate_local_moran",
    "calculate_getis_ord",
    "create_spatial_weights",
]
