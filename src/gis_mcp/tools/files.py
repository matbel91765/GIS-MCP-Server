"""File I/O tools for GIS MCP Server."""

import logging
from pathlib import Path
from typing import Any

import geopandas as gpd

from gis_mcp.config import get_config
from gis_mcp.utils import make_error_response, make_success_response

logger = logging.getLogger(__name__)


# Supported file extensions and their drivers
EXTENSION_DRIVERS = {
    ".geojson": "GeoJSON",
    ".json": "GeoJSON",
    ".shp": "ESRI Shapefile",
    ".gpkg": "GPKG",
    ".gdb": "OpenFileGDB",
    ".kml": "KML",
    ".gml": "GML",
}


def _get_driver_for_path(file_path: str) -> str | None:
    """Get the appropriate driver for a file path.

    Args:
        file_path: Path to the file.

    Returns:
        Driver name or None if unsupported.
    """
    ext = Path(file_path).suffix.lower()
    return EXTENSION_DRIVERS.get(ext)


async def read_geo_file(
    file_path: str,
    layer: str | None = None,
    limit: int | None = None
) -> dict[str, Any]:
    """Read a geospatial file and return its features.

    Args:
        file_path: Path to the file.
        layer: Layer name for multi-layer files.
        limit: Maximum number of features to return.

    Returns:
        GIS response with features as GeoJSON.
    """
    # Validate file exists
    path = Path(file_path)
    if not path.exists():
        return make_error_response(f"File not found: {file_path}")

    # Check file size
    config = get_config()
    file_size_mb = path.stat().st_size / (1024 * 1024)
    if file_size_mb > config.max_file_size_mb:
        return make_error_response(
            f"File too large ({file_size_mb:.1f} MB). Maximum: {config.max_file_size_mb} MB"
        )

    # Check extension
    driver = _get_driver_for_path(file_path)
    if not driver:
        supported = ", ".join(EXTENSION_DRIVERS.keys())
        return make_error_response(
            f"Unsupported file format. Supported extensions: {supported}"
        )

    try:
        # Read with geopandas
        read_kwargs: dict[str, Any] = {}
        if layer:
            read_kwargs["layer"] = layer
        if limit:
            read_kwargs["rows"] = limit

        gdf = gpd.read_file(file_path, **read_kwargs)

        if gdf.empty:
            return make_error_response("File contains no features")

        # Convert to GeoJSON
        geojson = gdf.__geo_interface__

        # Get layer info for multi-layer files
        layers = None
        try:
            import fiona
            layers = fiona.listlayers(file_path)
        except Exception:
            pass

        data = {
            "type": "FeatureCollection",
            "features": geojson.get("features", []),
            "feature_count": len(gdf),
        }

        # Add CRS info
        crs_info = None
        if gdf.crs:
            crs_info = {
                "epsg": gdf.crs.to_epsg(),
                "wkt": gdf.crs.to_wkt(),
                "proj4": gdf.crs.to_proj4() if hasattr(gdf.crs, "to_proj4") else None,
            }

        # Get column info
        columns = [
            {"name": col, "dtype": str(gdf[col].dtype)}
            for col in gdf.columns if col != "geometry"
        ]

        # Get geometry types
        geom_types = gdf.geometry.geom_type.unique().tolist()

        metadata = {
            "file_path": str(path.absolute()),
            "file_size_mb": round(file_size_mb, 2),
            "driver": driver,
            "crs": crs_info,
            "columns": columns,
            "geometry_types": geom_types,
            "layers": layers,
            "bounds": list(gdf.total_bounds) if not gdf.empty else None,
        }

        return make_success_response(data, metadata)

    except Exception as e:
        logger.exception(f"Error reading file: {e}")
        return make_error_response(f"Failed to read file: {str(e)}")


async def write_geo_file(
    features: dict[str, Any],
    file_path: str,
    driver: str = "GeoJSON"
) -> dict[str, Any]:
    """Write features to a geospatial file.

    Args:
        features: GeoJSON FeatureCollection.
        file_path: Output file path.
        driver: Output format driver.

    Returns:
        GIS response with file info.
    """
    # Validate driver
    valid_drivers = {"GeoJSON", "ESRI Shapefile", "GPKG"}
    if driver not in valid_drivers:
        return make_error_response(
            f"Invalid driver '{driver}'. Valid options: {', '.join(valid_drivers)}"
        )

    # Validate features structure
    if not isinstance(features, dict):
        return make_error_response("Features must be a GeoJSON object")

    if features.get("type") != "FeatureCollection":
        return make_error_response("Features must be a FeatureCollection")

    feature_list = features.get("features", [])
    if not feature_list:
        return make_error_response("FeatureCollection contains no features")

    try:
        # Create GeoDataFrame from GeoJSON
        gdf = gpd.GeoDataFrame.from_features(feature_list)

        # Set CRS if not present (default to WGS84)
        if gdf.crs is None:
            crs = features.get("crs", {}).get("properties", {}).get("name")
            if crs:
                gdf.set_crs(crs, inplace=True)
            else:
                gdf.set_crs("EPSG:4326", inplace=True)

        # Ensure parent directory exists
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        gdf.to_file(file_path, driver=driver)

        # Get file info
        file_size_mb = path.stat().st_size / (1024 * 1024)

        data = {
            "file_path": str(path.absolute()),
            "feature_count": len(gdf),
            "driver": driver,
        }

        metadata = {
            "file_size_mb": round(file_size_mb, 4),
            "crs": str(gdf.crs) if gdf.crs else None,
            "geometry_types": gdf.geometry.geom_type.unique().tolist(),
            "columns": list(gdf.columns),
        }

        return make_success_response(data, metadata)

    except Exception as e:
        logger.exception(f"Error writing file: {e}")
        return make_error_response(f"Failed to write file: {str(e)}")
