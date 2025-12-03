"""Geometry tools for GIS MCP Server."""

import logging
import math
from typing import Any

from pyproj import CRS, Transformer
from shapely.geometry import mapping, shape
from shapely.ops import transform

from gis_mcp.utils import (
    format_distance,
    make_error_response,
    make_success_response,
    validate_coordinates,
)

logger = logging.getLogger(__name__)


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the Haversine distance between two points.

    Args:
        lat1: Latitude of first point.
        lon1: Longitude of first point.
        lat2: Latitude of second point.
        lon2: Longitude of second point.

    Returns:
        Distance in meters.
    """
    earth_radius = 6371000  # Earth's radius in meters

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return earth_radius * c


def _geodesic_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the geodesic distance between two points using pyproj.

    Args:
        lat1: Latitude of first point.
        lon1: Longitude of first point.
        lat2: Latitude of second point.
        lon2: Longitude of second point.

    Returns:
        Distance in meters.
    """
    from pyproj import Geod

    geod = Geod(ellps="WGS84")
    _, _, distance = geod.inv(lon1, lat1, lon2, lat2)
    return abs(distance)


async def calculate_distance(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    method: str = "geodesic"
) -> dict[str, Any]:
    """Calculate the distance between two points.

    Args:
        lat1: Latitude of first point.
        lon1: Longitude of first point.
        lat2: Latitude of second point.
        lon2: Longitude of second point.
        method: 'haversine' or 'geodesic'.

    Returns:
        GIS response with distance in various units.
    """
    # Validate coordinates
    for lat, lon, name in [(lat1, lon1, "first"), (lat2, lon2, "second")]:
        is_valid, error = validate_coordinates(lat, lon)
        if not is_valid:
            return make_error_response(f"Invalid {name} point: {error}")

    method = method.lower()
    if method not in ("haversine", "geodesic"):
        return make_error_response(
            f"Invalid method '{method}'. Use 'haversine' or 'geodesic'."
        )

    try:
        if method == "haversine":
            distance_meters = _haversine_distance(lat1, lon1, lat2, lon2)
        else:
            distance_meters = _geodesic_distance(lat1, lon1, lat2, lon2)

        data = {
            "distance": format_distance(distance_meters),
            "from": {"lat": lat1, "lon": lon1},
            "to": {"lat": lat2, "lon": lon2},
        }

        metadata = {
            "method": method,
            "ellipsoid": "WGS84" if method == "geodesic" else "sphere",
        }

        return make_success_response(data, metadata)

    except Exception as e:
        logger.exception(f"Error calculating distance: {e}")
        return make_error_response(f"Distance calculation failed: {str(e)}")


def _get_utm_crs(lon: float, lat: float) -> CRS:
    """Get the appropriate UTM CRS for a given point.

    Args:
        lon: Longitude.
        lat: Latitude.

    Returns:
        pyproj CRS object for the appropriate UTM zone.
    """
    zone = int((lon + 180) / 6) + 1
    hemisphere = "north" if lat >= 0 else "south"
    epsg = 32600 + zone if hemisphere == "north" else 32700 + zone
    return CRS.from_epsg(epsg)


async def calculate_buffer(
    geometry: dict[str, Any],
    distance_meters: float,
    resolution: int = 16
) -> dict[str, Any]:
    """Create a buffer around a geometry.

    Args:
        geometry: GeoJSON geometry.
        distance_meters: Buffer distance in meters.
        resolution: Number of segments for curves.

    Returns:
        GIS response with buffered geometry.
    """
    if distance_meters <= 0:
        return make_error_response("Buffer distance must be positive")

    if resolution < 1 or resolution > 64:
        return make_error_response("Resolution must be between 1 and 64")

    try:
        # Parse GeoJSON geometry
        geom = shape(geometry)

        if geom.is_empty:
            return make_error_response("Input geometry is empty")

        # Get centroid for UTM projection
        centroid = geom.centroid
        utm_crs = _get_utm_crs(centroid.x, centroid.y)
        wgs84 = CRS.from_epsg(4326)

        # Create transformers
        to_utm = Transformer.from_crs(wgs84, utm_crs, always_xy=True)
        to_wgs84 = Transformer.from_crs(utm_crs, wgs84, always_xy=True)

        # Transform to UTM, buffer, transform back
        geom_utm = transform(to_utm.transform, geom)
        buffered_utm = geom_utm.buffer(distance_meters, quad_segs=resolution)
        buffered_wgs84 = transform(to_wgs84.transform, buffered_utm)

        data = {
            "geometry": mapping(buffered_wgs84),
            "area_km2": round(buffered_utm.area / 1_000_000, 4),
            "perimeter_km": round(buffered_utm.length / 1000, 4),
        }

        metadata = {
            "buffer_distance_m": distance_meters,
            "resolution": resolution,
            "utm_zone": utm_crs.to_epsg(),
            "input_type": geometry.get("type"),
        }

        return make_success_response(data, metadata)

    except Exception as e:
        logger.exception(f"Error creating buffer: {e}")
        return make_error_response(f"Buffer creation failed: {str(e)}")


async def perform_spatial_query(
    geometry1: dict[str, Any],
    geometry2: dict[str, Any],
    operation: str
) -> dict[str, Any]:
    """Perform a spatial operation between two geometries.

    Args:
        geometry1: First GeoJSON geometry.
        geometry2: Second GeoJSON geometry.
        operation: Spatial operation to perform.

    Returns:
        GIS response with result geometry or boolean.
    """
    valid_operations = {
        "intersection", "union", "difference",
        "contains", "within", "intersects", "overlaps"
    }

    operation = operation.lower()
    if operation not in valid_operations:
        valid_ops = ", ".join(sorted(valid_operations))
        return make_error_response(
            f"Invalid operation '{operation}'. Valid operations: {valid_ops}"
        )

    try:
        geom1 = shape(geometry1)
        geom2 = shape(geometry2)

        if geom1.is_empty:
            return make_error_response("First geometry is empty")
        if geom2.is_empty:
            return make_error_response("Second geometry is empty")

        # Predicate operations (return boolean)
        if operation == "contains":
            result = geom1.contains(geom2)
            data = {"result": result, "operation": operation}
        elif operation == "within":
            result = geom1.within(geom2)
            data = {"result": result, "operation": operation}
        elif operation == "intersects":
            result = geom1.intersects(geom2)
            data = {"result": result, "operation": operation}
        elif operation == "overlaps":
            result = geom1.overlaps(geom2)
            data = {"result": result, "operation": operation}
        # Geometry operations
        elif operation == "intersection":
            result_geom = geom1.intersection(geom2)
            data = {
                "geometry": mapping(result_geom) if not result_geom.is_empty else None,
                "is_empty": result_geom.is_empty,
                "operation": operation,
            }
        elif operation == "union":
            result_geom = geom1.union(geom2)
            data = {
                "geometry": mapping(result_geom),
                "operation": operation,
            }
        elif operation == "difference":
            result_geom = geom1.difference(geom2)
            data = {
                "geometry": mapping(result_geom) if not result_geom.is_empty else None,
                "is_empty": result_geom.is_empty,
                "operation": operation,
            }

        metadata = {
            "geometry1_type": geometry1.get("type"),
            "geometry2_type": geometry2.get("type"),
        }

        return make_success_response(data, metadata)

    except Exception as e:
        logger.exception(f"Error in spatial query: {e}")
        return make_error_response(f"Spatial query failed: {str(e)}")


async def transform_coordinates(
    geometry: dict[str, Any],
    source_crs: str,
    target_crs: str
) -> dict[str, Any]:
    """Transform geometry coordinates between CRS.

    Args:
        geometry: GeoJSON geometry.
        source_crs: Source CRS (e.g., 'EPSG:4326').
        target_crs: Target CRS (e.g., 'EPSG:3857').

    Returns:
        GIS response with transformed geometry.
    """
    try:
        source = CRS.from_string(source_crs)
    except Exception as e:
        return make_error_response(f"Invalid source CRS '{source_crs}': {str(e)}")

    try:
        target = CRS.from_string(target_crs)
    except Exception as e:
        return make_error_response(f"Invalid target CRS '{target_crs}': {str(e)}")

    try:
        geom = shape(geometry)

        if geom.is_empty:
            return make_error_response("Input geometry is empty")

        transformer = Transformer.from_crs(source, target, always_xy=True)
        transformed_geom = transform(transformer.transform, geom)

        data = {
            "geometry": mapping(transformed_geom),
            "source_crs": source_crs,
            "target_crs": target_crs,
        }

        metadata = {
            "source_crs_name": source.name,
            "target_crs_name": target.name,
            "source_is_geographic": source.is_geographic,
            "target_is_geographic": target.is_geographic,
        }

        return make_success_response(data, metadata)

    except Exception as e:
        logger.exception(f"Error transforming coordinates: {e}")
        return make_error_response(f"CRS transformation failed: {str(e)}")
