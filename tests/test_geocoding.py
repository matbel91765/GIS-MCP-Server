"""Tests for geocoding tools.

Note: These tests require network access to Nominatim.
For CI/CD, consider mocking the HTTP requests.
"""

import pytest
from unittest.mock import AsyncMock, patch

from gis_mcp.tools.geocoding import geocode_address, reverse_geocode_coords


class TestGeocode:
    """Tests for the geocode tool."""

    @pytest.mark.asyncio
    async def test_geocode_empty_address(self):
        """Test geocoding with empty address."""
        result = await geocode_address("")

        assert result["success"] is False
        assert "empty" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_geocode_whitespace_address(self):
        """Test geocoding with whitespace-only address."""
        result = await geocode_address("   ")

        assert result["success"] is False
        assert "empty" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_geocode_response_structure(self):
        """Test that geocode returns correct structure (mocked)."""
        mock_response = [{
            "lat": "48.8566",
            "lon": "2.3522",
            "display_name": "Paris, Île-de-France, France",
            "type": "city",
            "class": "place",
            "importance": 0.9,
            "osm_type": "relation",
            "osm_id": 7444,
            "boundingbox": ["48.815", "48.902", "2.224", "2.469"],
            "address": {
                "city": "Paris",
                "state": "Île-de-France",
                "country": "France"
            }
        }]

        with patch("gis_mcp.tools.geocoding._nominatim_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response

            result = await geocode_address("Paris")

            assert result["success"] is True
            assert result["data"]["lat"] == 48.8566
            assert result["data"]["lon"] == 2.3522
            assert "Paris" in result["data"]["display_name"]
            assert result["metadata"]["source"] == "nominatim"
            assert "confidence" in result["metadata"]

    @pytest.mark.asyncio
    async def test_geocode_no_results(self):
        """Test geocoding when no results found (mocked)."""
        with patch("gis_mcp.tools.geocoding._nominatim_request", new_callable=AsyncMock) as mock:
            mock.return_value = []

            result = await geocode_address("xyznonexistentplace123")

            assert result["success"] is False
            assert "no results" in result["error"].lower()


class TestReverseGeocode:
    """Tests for the reverse geocode tool."""

    @pytest.mark.asyncio
    async def test_reverse_geocode_invalid_lat(self):
        """Test reverse geocoding with invalid latitude."""
        result = await reverse_geocode_coords(100, 2.3522)

        assert result["success"] is False
        assert "latitude" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_reverse_geocode_invalid_lon(self):
        """Test reverse geocoding with invalid longitude."""
        result = await reverse_geocode_coords(48.8566, 200)

        assert result["success"] is False
        assert "longitude" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_reverse_geocode_response_structure(self):
        """Test that reverse geocode returns correct structure (mocked)."""
        mock_response = {
            "display_name": "Eiffel Tower, Paris, France",
            "type": "attraction",
            "class": "tourism",
            "osm_type": "way",
            "osm_id": 123456,
            "boundingbox": ["48.857", "48.859", "2.293", "2.296"],
            "address": {
                "tourism": "Eiffel Tower",
                "road": "Avenue Gustave Eiffel",
                "city": "Paris",
                "state": "Île-de-France",
                "postcode": "75007",
                "country": "France",
                "country_code": "fr"
            }
        }

        with patch("gis_mcp.tools.geocoding._nominatim_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response

            result = await reverse_geocode_coords(48.8584, 2.2945)

            assert result["success"] is True
            assert "Eiffel Tower" in result["data"]["display_name"]
            assert result["data"]["structured"]["city"] == "Paris"
            assert result["metadata"]["source"] == "nominatim"

    @pytest.mark.asyncio
    async def test_reverse_geocode_error_response(self):
        """Test reverse geocoding when API returns error (mocked)."""
        mock_response = {
            "error": "Unable to geocode"
        }

        with patch("gis_mcp.tools.geocoding._nominatim_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response

            result = await reverse_geocode_coords(0, 0)  # Middle of ocean

            assert result["success"] is False


class TestValidation:
    """Tests for coordinate validation."""

    @pytest.mark.asyncio
    async def test_lat_boundary_min(self):
        """Test latitude at minimum boundary."""
        result = await reverse_geocode_coords(-90, 0)
        # Should not fail validation (may fail for other reasons)
        assert "latitude" not in (result.get("error") or "").lower()

    @pytest.mark.asyncio
    async def test_lat_boundary_max(self):
        """Test latitude at maximum boundary."""
        result = await reverse_geocode_coords(90, 0)
        assert "latitude" not in (result.get("error") or "").lower()

    @pytest.mark.asyncio
    async def test_lon_boundary_min(self):
        """Test longitude at minimum boundary."""
        result = await reverse_geocode_coords(0, -180)
        assert "longitude" not in (result.get("error") or "").lower()

    @pytest.mark.asyncio
    async def test_lon_boundary_max(self):
        """Test longitude at maximum boundary."""
        result = await reverse_geocode_coords(0, 180)
        assert "longitude" not in (result.get("error") or "").lower()
