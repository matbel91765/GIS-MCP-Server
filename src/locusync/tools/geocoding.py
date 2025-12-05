"""Geocoding tools for GIS MCP Server."""

import logging
from typing import Any, cast

import aiohttp

from locusync.config import get_config
from locusync.utils import (
    get_nominatim_limiter,
    make_error_response,
    make_success_response,
    retry_async,
    validate_coordinates,
)

logger = logging.getLogger(__name__)


async def _nominatim_request(
    endpoint: str,
    params: dict[str, Any]
) -> dict[str, Any]:
    """Make a rate-limited request to Nominatim API.

    Args:
        endpoint: API endpoint ('search' or 'reverse').
        params: Query parameters.

    Returns:
        JSON response from Nominatim.

    Raises:
        aiohttp.ClientError: On network errors.
        ValueError: On invalid response.
    """
    config = get_config()
    limiter = get_nominatim_limiter()

    # Wait for rate limit
    await limiter.acquire()

    url = f"{config.nominatim.base_url}/{endpoint}"
    params["format"] = "json"

    headers = {
        "User-Agent": config.nominatim.user_agent,
        "Accept": "application/json",
    }

    async with aiohttp.ClientSession() as session, session.get(
        url,
        params=params,
        headers=headers,
        timeout=aiohttp.ClientTimeout(total=config.nominatim.timeout)
    ) as response:
        response.raise_for_status()
        return cast(dict[str, Any], await response.json())


async def _pelias_geocode(address: str) -> dict[str, Any]:
    """Internal helper to geocode an address using Pelias.

    Args:
        address: Address string to geocode.

    Returns:
        Pelias API response.

    Raises:
        aiohttp.ClientError: On network errors.
        ValueError: On invalid configuration or response.
    """
    config = get_config()

    if not config.pelias.base_url:
        raise ValueError("Pelias base_url not configured")

    url = f"{config.pelias.base_url}/v1/search"
    params = {"text": address}

    # Add API key if configured
    if config.pelias.api_key:
        params["api_key"] = config.pelias.api_key

    headers = {"Accept": "application/json"}

    async with aiohttp.ClientSession() as session, session.get(
        url,
        params=params,
        headers=headers,
        timeout=aiohttp.ClientTimeout(total=config.pelias.timeout)
    ) as response:
        response.raise_for_status()
        return cast(dict[str, Any], await response.json())


async def _pelias_reverse(lat: float, lon: float) -> dict[str, Any]:
    """Internal helper to reverse geocode coordinates using Pelias.

    Args:
        lat: Latitude.
        lon: Longitude.

    Returns:
        Pelias API response.

    Raises:
        aiohttp.ClientError: On network errors.
        ValueError: On invalid configuration or response.
    """
    config = get_config()

    if not config.pelias.base_url:
        raise ValueError("Pelias base_url not configured")

    url = f"{config.pelias.base_url}/v1/reverse"
    params: dict[str, Any] = {
        "point.lat": lat,
        "point.lon": lon,
    }

    # Add API key if configured
    if config.pelias.api_key:
        params["api_key"] = config.pelias.api_key

    headers = {"Accept": "application/json"}

    async with aiohttp.ClientSession() as session, session.get(
        url,
        params=params,
        headers=headers,
        timeout=aiohttp.ClientTimeout(total=config.pelias.timeout)
    ) as response:
        response.raise_for_status()
        return cast(dict[str, Any], await response.json())


async def geocode_address(address: str, provider: str = "nominatim") -> dict[str, Any]:
    """Geocode an address to coordinates.

    Args:
        address: Address string to geocode.
        provider: Geocoding provider to use ("nominatim" or "pelias").

    Returns:
        GIS response with coordinates and metadata.
    """
    if not address or not address.strip():
        return make_error_response("Address cannot be empty")

    # Validate provider
    if provider not in ("nominatim", "pelias"):
        return make_error_response(f"Invalid provider: {provider}. Must be 'nominatim' or 'pelias'")

    # Check if Pelias is configured when requested
    if provider == "pelias":
        config = get_config()
        if not config.pelias.base_url:
            logger.warning(
                "Pelias provider requested but not configured, falling back to Nominatim"
            )
            provider = "nominatim"

    try:
        if provider == "pelias":
            # Use Pelias
            async def do_pelias_request() -> dict[str, Any]:
                return await _pelias_geocode(address.strip())

            response = await retry_async(do_pelias_request, max_retries=3)

            # Parse Pelias response
            features = response.get("features", [])
            if not features:
                return make_error_response(
                    f"No results found for address: {address}",
                    metadata={"source": "pelias", "query": address}
                )

            feature = features[0]
            properties = feature.get("properties", {})
            geometry = feature.get("geometry", {})
            coordinates = geometry.get("coordinates", [])

            if len(coordinates) < 2:
                return make_error_response(
                    "Invalid coordinates in Pelias response",
                    metadata={"source": "pelias"}
                )

            lon, lat = coordinates[0], coordinates[1]

            # Build response data
            data = {
                "lat": lat,
                "lon": lon,
                "display_name": properties.get("label", ""),
                "type": properties.get("layer", "unknown"),
                "class": properties.get("source", "unknown"),
            }

            # Extract address components if available
            if any(k in properties for k in ["name", "street", "locality", "region", "country"]):
                data["address"] = {
                    "name": properties.get("name"),
                    "street": properties.get("street"),
                    "locality": properties.get("locality"),
                    "region": properties.get("region"),
                    "country": properties.get("country"),
                }

            # Build metadata
            metadata = {
                "source": "pelias",
                "confidence": round(properties.get("confidence", 0.5), 2),
                "gid": properties.get("gid"),
                "layer": properties.get("layer"),
            }

            return make_success_response(data, metadata)

        else:
            # Use Nominatim (default)
            params = {
                "q": address.strip(),
                "addressdetails": 1,
                "limit": 1,
            }

            async def do_nominatim_request() -> Any:
                return await _nominatim_request("search", params)

            results = await retry_async(do_nominatim_request, max_retries=3)

            if not results:
                return make_error_response(
                    f"No results found for address: {address}",
                    metadata={"source": "nominatim", "query": address}
                )

            result = results[0]

            # Extract coordinates
            lat = float(result["lat"])
            lon = float(result["lon"])

            # Calculate confidence based on importance score
            importance_val = result.get("importance", 0.5)
            importance = float(importance_val) if importance_val is not None else 0.5
            confidence = min(importance * 1.2, 1.0)  # Scale to 0-1

            # Build response data
            data = {
                "lat": lat,
                "lon": lon,
                "display_name": result.get("display_name", ""),
                "type": result.get("type", "unknown"),
                "class": result.get("class", "unknown"),
            }

            # Extract address components if available
            if "address" in result:
                data["address"] = result["address"]

            # Build metadata
            metadata = {
                "source": "nominatim",
                "confidence": round(confidence, 2),
                "osm_type": result.get("osm_type"),
                "osm_id": result.get("osm_id"),
                "place_rank": result.get("place_rank"),
            }

            # Add bounding box if available
            if "boundingbox" in result:
                bbox = result["boundingbox"]
                metadata["bbox"] = {
                    "south": float(bbox[0]),
                    "north": float(bbox[1]),
                    "west": float(bbox[2]),
                    "east": float(bbox[3]),
                }

            return make_success_response(data, metadata)

    except aiohttp.ClientError as e:
        logger.error(f"Network error during geocoding: {e}")
        return make_error_response(
            f"Network error: Unable to reach geocoding service. {str(e)}",
            metadata={"source": provider}
        )
    except Exception as e:
        logger.exception(f"Unexpected error during geocoding: {e}")
        return make_error_response(
            f"Geocoding failed: {str(e)}",
            metadata={"source": provider}
        )


async def batch_geocode(addresses: list[str]) -> dict[str, Any]:
    """Batch geocode multiple addresses with rate limiting.

    Args:
        addresses: List of address strings to geocode (max 10).

    Returns:
        GIS response with results for all addresses.
    """
    # Validate input
    if not addresses:
        return make_error_response("Address list cannot be empty")

    if not isinstance(addresses, list):
        return make_error_response("Addresses must be provided as a list")

    if len(addresses) > 10:
        return make_error_response(
            f"Too many addresses: {len(addresses)}. Maximum is 10 to respect rate limits."
        )

    results = []
    success_count = 0
    failure_count = 0

    # Process each address with rate limiting
    for idx, address in enumerate(addresses):
        try:
            result = await geocode_address(address)

            # Track success/failure
            if result["success"]:
                success_count += 1
            else:
                failure_count += 1

            # Add the result with the original address
            results.append({
                "index": idx,
                "address": address,
                "result": result
            })

        except Exception as e:
            logger.exception(f"Unexpected error processing address '{address}': {e}")
            failure_count += 1
            results.append({
                "index": idx,
                "address": address,
                "result": make_error_response(f"Processing failed: {str(e)}")
            })

    # Build response
    data = {
        "results": results,
        "summary": {
            "total": len(addresses),
            "successful": success_count,
            "failed": failure_count
        }
    }

    metadata = {
        "source": "nominatim",
        "batch_size": len(addresses),
        "rate_limited": True  # Indicates rate limiting was applied
    }

    # Overall success if at least one address succeeded
    if success_count > 0:
        return make_success_response(data, metadata)
    else:
        return make_error_response(
            "All addresses failed to geocode",
            metadata={**metadata, "results": results}
        )


async def reverse_geocode_coords(
    lat: float, lon: float, provider: str = "nominatim"
) -> dict[str, Any]:
    """Reverse geocode coordinates to an address.

    Args:
        lat: Latitude.
        lon: Longitude.
        provider: Geocoding provider to use ("nominatim" or "pelias").

    Returns:
        GIS response with address and metadata.
    """
    # Validate coordinates
    is_valid, error = validate_coordinates(lat, lon)
    if not is_valid:
        return make_error_response(error)  # type: ignore

    # Validate provider
    if provider not in ("nominatim", "pelias"):
        return make_error_response(f"Invalid provider: {provider}. Must be 'nominatim' or 'pelias'")

    # Check if Pelias is configured when requested
    if provider == "pelias":
        config = get_config()
        if not config.pelias.base_url:
            logger.warning(
                "Pelias provider requested but not configured, falling back to Nominatim"
            )
            provider = "nominatim"

    try:
        if provider == "pelias":
            # Use Pelias
            async def do_pelias_reverse() -> dict[str, Any]:
                return await _pelias_reverse(lat, lon)

            response = await retry_async(do_pelias_reverse, max_retries=3)

            # Parse Pelias response
            features = response.get("features", [])
            if not features:
                return make_error_response(
                    f"No address found for coordinates ({lat}, {lon})",
                    metadata={"source": "pelias", "lat": lat, "lon": lon}
                )

            feature = features[0]
            properties = feature.get("properties", {})

            # Build response data
            data = {
                "display_name": properties.get("label", ""),
                "type": properties.get("layer", "unknown"),
                "class": properties.get("source", "unknown"),
            }

            # Extract address components
            if any(k in properties for k in ["name", "street", "locality", "region", "country"]):
                data["address"] = {
                    "name": properties.get("name"),
                    "street": properties.get("street"),
                    "locality": properties.get("locality"),
                    "region": properties.get("region"),
                    "country": properties.get("country"),
                }

                # Provide structured address fields
                data["structured"] = {
                    "road": properties.get("street"),
                    "neighbourhood": properties.get("neighbourhood"),
                    "city": properties.get("locality"),
                    "county": properties.get("county"),
                    "state": properties.get("region"),
                    "postcode": properties.get("postalcode"),
                    "country": properties.get("country"),
                }
                # Remove None values
                data["structured"] = {k: v for k, v in data["structured"].items() if v is not None}

            # Build metadata
            metadata = {
                "source": "pelias",
                "lat": lat,
                "lon": lon,
                "gid": properties.get("gid"),
                "layer": properties.get("layer"),
            }

            return make_success_response(data, metadata)

        else:
            # Use Nominatim (default)
            params = {
                "lat": lat,
                "lon": lon,
                "addressdetails": 1,
                "zoom": 18,  # Building level detail
            }

            async def do_nominatim_reverse() -> Any:
                return await _nominatim_request("reverse", params)

            result = await retry_async(do_nominatim_reverse, max_retries=3)

            if not result or "error" in result:
                error_msg = result.get("error", "Unknown error") if result else "No result"
                return make_error_response(
                    f"No address found for coordinates ({lat}, {lon}): {error_msg}",
                    metadata={"source": "nominatim", "lat": lat, "lon": lon}
                )

            # Build response data
            data = {
                "display_name": result.get("display_name", ""),
                "type": result.get("type", "unknown"),
                "class": result.get("class", "unknown"),
            }

            # Extract address components
            if "address" in result:
                address = result["address"]
                data["address"] = address

                # Provide structured address fields
                data["structured"] = {
                    "house_number": address.get("house_number"),
                    "road": address.get("road"),
                    "neighbourhood": address.get("neighbourhood"),
                    "suburb": address.get("suburb"),
                    "city": address.get("city") or address.get("town") or address.get("village"),
                    "county": address.get("county"),
                    "state": address.get("state"),
                    "postcode": address.get("postcode"),
                    "country": address.get("country"),
                    "country_code": address.get("country_code"),
                }
                # Remove None values
                data["structured"] = {k: v for k, v in data["structured"].items() if v is not None}

            # Build metadata
            metadata = {
                "source": "nominatim",
                "lat": lat,
                "lon": lon,
                "osm_type": result.get("osm_type"),
                "osm_id": result.get("osm_id"),
                "place_rank": result.get("place_rank"),
            }

            # Add bounding box if available
            if "boundingbox" in result:
                bbox = result["boundingbox"]
                metadata["bbox"] = {
                    "south": float(bbox[0]),
                    "north": float(bbox[1]),
                    "west": float(bbox[2]),
                    "east": float(bbox[3]),
                }

            return make_success_response(data, metadata)

    except aiohttp.ClientError as e:
        logger.error(f"Network error during reverse geocoding: {e}")
        return make_error_response(
            f"Network error: Unable to reach geocoding service. {str(e)}",
            metadata={"source": provider}
        )
    except Exception as e:
        logger.exception(f"Unexpected error during reverse geocoding: {e}")
        return make_error_response(
            f"Reverse geocoding failed: {str(e)}",
            metadata={"source": provider}
        )
