# GIS MCP Server

A Model Context Protocol (MCP) server providing geospatial tools for AI agents. Enables Claude, GPT, and other LLMs to perform geocoding, routing, spatial analysis, and file operations.

## Features

- **Geocoding**: Convert addresses to coordinates and vice versa (via Nominatim/OSM)
- **Routing**: Calculate routes between points with distance, duration, and geometry (via OSRM)
- **Spatial Analysis**: Buffer, intersection, union, distance calculations
- **File I/O**: Read/write Shapefiles, GeoJSON, GeoPackage
- **CRS Transformation**: Convert between coordinate reference systems

## Installation

```bash
# From PyPI (when published)
pip install gis-mcp-server

# From source
git clone https://github.com/your-org/gis-mcp-server.git
cd gis-mcp-server
pip install -e .
```

## Quick Start

### With Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "gis": {
      "command": "uvx",
      "args": ["gis-mcp-server"]
    }
  }
}
```

### Direct Usage

```bash
# Run the server
gis-mcp-server
```

## Available Tools

### Geocoding

#### `geocode`
Convert an address to coordinates.

```
Input: "1600 Pennsylvania Avenue, Washington DC"
Output: {lat: 38.8977, lon: -77.0365, display_name: "White House..."}
```

#### `reverse_geocode`
Convert coordinates to an address.

```
Input: lat=48.8566, lon=2.3522
Output: {display_name: "Paris, Île-de-France, France", ...}
```

### Geometry

#### `distance`
Calculate distance between two points.

```
Input: lat1=48.8566, lon1=2.3522, lat2=51.5074, lon2=-0.1278
Output: {distance: {meters: 343556, kilometers: 343.56, miles: 213.47}}
```

#### `buffer`
Create a buffer zone around a geometry.

```
Input: geometry={type: "Point", coordinates: [2.3522, 48.8566]}, distance_meters=1000
Output: {geometry: {type: "Polygon", ...}, area_km2: 3.14}
```

#### `spatial_query`
Perform spatial operations (intersection, union, contains, within, etc.).

```
Input: geometry1={...}, geometry2={...}, operation="intersection"
Output: {geometry: {...}}
```

#### `transform_crs`
Transform coordinates between CRS.

```
Input: geometry={...}, source_crs="EPSG:4326", target_crs="EPSG:3857"
Output: {geometry: {...}}
```

### Routing

#### `route`
Calculate route between two points.

```
Input: start_lat=48.8566, start_lon=2.3522, end_lat=48.8606, end_lon=2.3376
Output: {distance: {...}, duration: {...}, geometry: {...}, steps: [...]}
```

#### `isochrone`
Calculate area reachable within a time limit.

```
Input: lat=48.8566, lon=2.3522, time_minutes=15, profile="driving"
Output: {geometry: {type: "Polygon", ...}}
```

### Files

#### `read_file`
Read geospatial files (Shapefile, GeoJSON, GeoPackage).

```
Input: file_path="data/cities.shp"
Output: {type: "FeatureCollection", features: [...]}
```

#### `write_file`
Write features to geospatial files.

```
Input: features={...}, file_path="output.geojson", driver="GeoJSON"
Output: {file_path: "...", feature_count: 10}
```

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `NOMINATIM_URL` | `https://nominatim.openstreetmap.org` | Nominatim API URL |
| `NOMINATIM_USER_AGENT` | `gis-mcp-server/0.1.0` | User agent for Nominatim |
| `OSRM_URL` | `https://router.project-osrm.org` | OSRM API URL |
| `OSRM_PROFILE` | `driving` | Default routing profile |
| `GIS_DEFAULT_CRS` | `EPSG:4326` | Default CRS |
| `GIS_TEMP_DIR` | `/tmp/gis-mcp` | Temporary directory |

## Response Format

All tools return a consistent JSON structure:

```json
{
  "success": true,
  "data": { ... },
  "metadata": {
    "source": "nominatim",
    "confidence": 0.95
  },
  "error": null
}
```

## Rate Limits

- **Nominatim**: 1 request/second (enforced automatically)
- **OSRM Demo**: Best effort, consider self-hosting for production

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=src/gis_mcp --cov-report=html

# Type checking
mypy src/gis_mcp

# Linting
ruff check src/gis_mcp
```

## Architecture

```
src/gis_mcp/
├── server.py      # MCP server entry point
├── config.py      # Configuration management
├── utils.py       # Common utilities
└── tools/
    ├── geocoding.py   # geocode, reverse_geocode
    ├── routing.py     # route, isochrone
    ├── geometry.py    # buffer, distance, spatial_query, transform_crs
    └── files.py       # read_file, write_file
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions welcome! Please read the contributing guidelines before submitting PRs.

## Roadmap

- [ ] Pelias geocoding support (higher accuracy)
- [ ] Valhalla routing integration (native isochrones)
- [ ] PostGIS spatial queries
- [ ] Elevation/terrain data
- [ ] Real-time traffic data
- [ ] Batch geocoding
- [ ] ESRI FileGDB full support
