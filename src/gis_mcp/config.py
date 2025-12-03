"""Configuration management for GIS MCP Server."""

import os
from dataclasses import dataclass, field


@dataclass
class NominatimConfig:
    """Configuration for Nominatim geocoding service."""

    base_url: str = "https://nominatim.openstreetmap.org"
    user_agent: str = "gis-mcp-server/0.1.0"
    timeout: float = 10.0
    rate_limit_delay: float = 1.0  # Nominatim requires 1 req/sec max


@dataclass
class OSRMConfig:
    """Configuration for OSRM routing service."""

    base_url: str = "https://router.project-osrm.org"
    timeout: float = 30.0
    profile: str = "driving"  # driving, walking, cycling


@dataclass
class ValhallaConfig:
    """Configuration for Valhalla routing service (alternative)."""

    base_url: str = ""  # No public demo, must be self-hosted
    timeout: float = 30.0
    api_key: str = ""


@dataclass
class Config:
    """Main configuration for GIS MCP Server."""

    nominatim: NominatimConfig = field(default_factory=NominatimConfig)
    osrm: OSRMConfig = field(default_factory=OSRMConfig)
    valhalla: ValhallaConfig = field(default_factory=ValhallaConfig)

    # General settings
    default_crs: str = "EPSG:4326"  # WGS84
    max_file_size_mb: int = 100
    temp_dir: str = "/tmp/gis-mcp"

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        config = cls()

        # Nominatim overrides
        if url := os.getenv("NOMINATIM_URL"):
            config.nominatim.base_url = url
        if user_agent := os.getenv("NOMINATIM_USER_AGENT"):
            config.nominatim.user_agent = user_agent

        # OSRM overrides
        if url := os.getenv("OSRM_URL"):
            config.osrm.base_url = url
        if profile := os.getenv("OSRM_PROFILE"):
            config.osrm.profile = profile

        # Valhalla overrides
        if url := os.getenv("VALHALLA_URL"):
            config.valhalla.base_url = url
        if api_key := os.getenv("VALHALLA_API_KEY"):
            config.valhalla.api_key = api_key

        # General overrides
        if crs := os.getenv("GIS_DEFAULT_CRS"):
            config.default_crs = crs
        if temp_dir := os.getenv("GIS_TEMP_DIR"):
            config.temp_dir = temp_dir

        return config


# Global config instance
_config: Config | None = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config


def set_config(config: Config) -> None:
    """Set the global configuration instance."""
    global _config
    _config = config
