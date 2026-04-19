"""Tests for MELCloud Home API client - Parameter validation.

These tests verify client-side parameter validation without making API calls.
They run fast (no VCR, no network) and document expected validation behavior.
"""

import pytest

from custom_components.melcloudhome.api.client import MELCloudHomeClient
from custom_components.melcloudhome.api.exceptions import AuthenticationError


class TestTemperatureValidation:
    """Test temperature parameter validation."""

    @pytest.mark.asyncio
    async def test_temperature_below_minimum(self) -> None:
        """Temperature below 10°C should raise ValueError."""
        client = MELCloudHomeClient()

        with pytest.raises(ValueError, match=r"must be between 10\.0 and 31\.0"):
            await client.ata.set_temperature("unit-id", 9.5)

    @pytest.mark.asyncio
    async def test_temperature_above_maximum(self) -> None:
        """Temperature above 31°C should raise ValueError."""
        client = MELCloudHomeClient()

        with pytest.raises(ValueError, match=r"must be between 10\.0 and 31\.0"):
            await client.ata.set_temperature("unit-id", 31.5)

    @pytest.mark.asyncio
    async def test_temperature_way_below_minimum(self) -> None:
        """Temperature far below minimum should raise ValueError."""
        client = MELCloudHomeClient()

        with pytest.raises(ValueError, match=r"must be between 10\.0 and 31\.0"):
            await client.ata.set_temperature("unit-id", 0.0)

    @pytest.mark.asyncio
    async def test_temperature_way_above_maximum(self) -> None:
        """Temperature far above maximum should raise ValueError."""
        client = MELCloudHomeClient()

        with pytest.raises(ValueError, match=r"must be between 10\.0 and 31\.0"):
            await client.ata.set_temperature("unit-id", 50.0)

    @pytest.mark.asyncio
    async def test_temperature_valid_minimum(self) -> None:
        """Minimum temperature (10.0°C) should pass validation."""
        client = MELCloudHomeClient()

        # Should raise AuthenticationError (not ValueError) since validation passes
        with pytest.raises(AuthenticationError, match="Not authenticated"):
            await client.ata.set_temperature("unit-id", 10.0)

    @pytest.mark.asyncio
    async def test_temperature_valid_maximum(self) -> None:
        """Maximum temperature (31.0°C) should pass validation."""
        client = MELCloudHomeClient()

        # Should raise AuthenticationError (not ValueError) since validation passes
        with pytest.raises(AuthenticationError, match="Not authenticated"):
            await client.ata.set_temperature("unit-id", 31.0)

    @pytest.mark.asyncio
    async def test_temperature_valid_half_degree(self) -> None:
        """Half degree increment (20.5°C) should pass validation."""
        client = MELCloudHomeClient()

        # Should raise AuthenticationError (not ValueError) since validation passes
        with pytest.raises(AuthenticationError, match="Not authenticated"):
            await client.ata.set_temperature("unit-id", 20.5)

    @pytest.mark.asyncio
    async def test_temperature_valid_whole_number(self) -> None:
        """Whole number temperature (21.0°C) should pass validation."""
        client = MELCloudHomeClient()

        # Should raise AuthenticationError (not ValueError) since validation passes
        with pytest.raises(AuthenticationError, match="Not authenticated"):
            await client.ata.set_temperature("unit-id", 21.0)


class TestModeValidation:
    """Test operation mode parameter validation."""

    @pytest.mark.asyncio
    async def test_invalid_mode_string(self) -> None:
        """Invalid mode string should raise ValueError."""
        client = MELCloudHomeClient()

        with pytest.raises(ValueError, match=r"Invalid mode.*Must be one of"):
            await client.ata.set_mode("unit-id", "InvalidMode")

    @pytest.mark.asyncio
    async def test_mode_case_sensitive_lowercase(self) -> None:
        """Lowercase mode should raise ValueError (case-sensitive)."""
        client = MELCloudHomeClient()

        with pytest.raises(ValueError, match="Invalid mode"):
            await client.ata.set_mode("unit-id", "heat")

    @pytest.mark.asyncio
    async def test_mode_case_sensitive_uppercase(self) -> None:
        """Uppercase mode should raise ValueError (case-sensitive)."""
        client = MELCloudHomeClient()

        with pytest.raises(ValueError, match="Invalid mode"):
            await client.ata.set_mode("unit-id", "HEAT")

    @pytest.mark.asyncio
    async def test_mode_common_typo_auto(self) -> None:
        """Common typo 'Auto' instead of 'Automatic' should raise ValueError."""
        client = MELCloudHomeClient()

        with pytest.raises(ValueError, match="Invalid mode"):
            await client.ata.set_mode("unit-id", "Auto")

    @pytest.mark.asyncio
    async def test_mode_empty_string(self) -> None:
        """Empty string mode should raise ValueError."""
        client = MELCloudHomeClient()

        with pytest.raises(ValueError, match="Invalid mode"):
            await client.ata.set_mode("unit-id", "")

    @pytest.mark.asyncio
    async def test_mode_valid_heat(self) -> None:
        """Valid mode 'Heat' should pass validation."""
        client = MELCloudHomeClient()

        # Should raise AuthenticationError (not ValueError) since validation passes
        with pytest.raises(AuthenticationError, match="Not authenticated"):
            await client.ata.set_mode("unit-id", "Heat")

    @pytest.mark.asyncio
    async def test_mode_valid_cool(self) -> None:
        """Valid mode 'Cool' should pass validation."""
        client = MELCloudHomeClient()

        with pytest.raises(AuthenticationError, match="Not authenticated"):
            await client.ata.set_mode("unit-id", "Cool")

    @pytest.mark.asyncio
    async def test_mode_valid_automatic(self) -> None:
        """Valid mode 'Automatic' should pass validation."""
        client = MELCloudHomeClient()

        with pytest.raises(AuthenticationError, match="Not authenticated"):
            await client.ata.set_mode("unit-id", "Automatic")

    @pytest.mark.asyncio
    async def test_mode_valid_dry(self) -> None:
        """Valid mode 'Dry' should pass validation."""
        client = MELCloudHomeClient()

        with pytest.raises(AuthenticationError, match="Not authenticated"):
            await client.ata.set_mode("unit-id", "Dry")

    @pytest.mark.asyncio
    async def test_mode_valid_fan(self) -> None:
        """Valid mode 'Fan' should pass validation."""
        client = MELCloudHomeClient()

        with pytest.raises(AuthenticationError, match="Not authenticated"):
            await client.ata.set_mode("unit-id", "Fan")


class TestFanSpeedValidation:
    """Test fan speed parameter validation."""

    @pytest.mark.asyncio
    async def test_numeric_string_zero(self) -> None:
        """Numeric string '0' should be rejected (use 'Auto')."""
        client = MELCloudHomeClient()

        with pytest.raises(ValueError, match="Invalid fan speed"):
            await client.ata.set_fan_speed("unit-id", "0")

    @pytest.mark.asyncio
    async def test_numeric_string_one(self) -> None:
        """Numeric string '1' should be rejected (use 'One')."""
        client = MELCloudHomeClient()

        with pytest.raises(ValueError, match="Invalid fan speed"):
            await client.ata.set_fan_speed("unit-id", "1")

    @pytest.mark.asyncio
    async def test_numeric_string_three(self) -> None:
        """Numeric string '3' should be rejected (use 'Three')."""
        client = MELCloudHomeClient()

        with pytest.raises(ValueError, match="Invalid fan speed"):
            await client.ata.set_fan_speed("unit-id", "3")

    @pytest.mark.asyncio
    async def test_out_of_range_six(self) -> None:
        """Fan speed 'Six' should be rejected (max is 'Five')."""
        client = MELCloudHomeClient()

        with pytest.raises(ValueError, match="Invalid fan speed"):
            await client.ata.set_fan_speed("unit-id", "Six")

    @pytest.mark.asyncio
    async def test_invalid_string(self) -> None:
        """Invalid string should be rejected."""
        client = MELCloudHomeClient()

        with pytest.raises(ValueError, match="Invalid fan speed"):
            await client.ata.set_fan_speed("unit-id", "Invalid")

    @pytest.mark.asyncio
    async def test_case_sensitive_lowercase(self) -> None:
        """Lowercase 'auto' should be rejected (case-sensitive)."""
        client = MELCloudHomeClient()

        with pytest.raises(ValueError, match="Invalid fan speed"):
            await client.ata.set_fan_speed("unit-id", "auto")

    @pytest.mark.asyncio
    async def test_valid_auto(self) -> None:
        """Valid fan speed 'Auto' should pass validation."""
        client = MELCloudHomeClient()

        with pytest.raises(AuthenticationError, match="Not authenticated"):
            await client.ata.set_fan_speed("unit-id", "Auto")

    @pytest.mark.asyncio
    async def test_valid_one(self) -> None:
        """Valid fan speed 'One' should pass validation."""
        client = MELCloudHomeClient()

        with pytest.raises(AuthenticationError, match="Not authenticated"):
            await client.ata.set_fan_speed("unit-id", "One")

    @pytest.mark.asyncio
    async def test_valid_five(self) -> None:
        """Valid fan speed 'Five' should pass validation."""
        client = MELCloudHomeClient()

        with pytest.raises(AuthenticationError, match="Not authenticated"):
            await client.ata.set_fan_speed("unit-id", "Five")


class TestVaneVerticalValidation:
    """Test vertical vane direction parameter validation."""

    @pytest.mark.asyncio
    async def test_invalid_vertical_direction(self) -> None:
        """Invalid vertical direction should raise ValueError."""
        client = MELCloudHomeClient()

        with pytest.raises(ValueError, match="Invalid vertical direction"):
            await client.ata.set_vane_vertical("unit-id", "Up")

    @pytest.mark.asyncio
    async def test_vertical_numeric_string(self) -> None:
        """Numeric string for vertical should be rejected (we expose words)."""
        client = MELCloudHomeClient()

        with pytest.raises(ValueError, match="Invalid vertical direction"):
            await client.ata.set_vane_vertical("unit-id", "1")

    @pytest.mark.asyncio
    async def test_valid_vertical_auto(self) -> None:
        """Valid 'Auto' should pass validation."""
        client = MELCloudHomeClient()

        with pytest.raises(AuthenticationError, match="Not authenticated"):
            await client.ata.set_vane_vertical("unit-id", "Auto")

    @pytest.mark.asyncio
    async def test_valid_vertical_swing(self) -> None:
        """Valid 'Swing' should pass validation."""
        client = MELCloudHomeClient()

        with pytest.raises(AuthenticationError, match="Not authenticated"):
            await client.ata.set_vane_vertical("unit-id", "Swing")

    @pytest.mark.asyncio
    async def test_valid_vertical_position(self) -> None:
        """Valid position 'Three' should pass validation."""
        client = MELCloudHomeClient()

        with pytest.raises(AuthenticationError, match="Not authenticated"):
            await client.ata.set_vane_vertical("unit-id", "Three")


class TestVaneHorizontalValidation:
    """Test horizontal vane direction parameter validation."""

    @pytest.mark.asyncio
    async def test_invalid_horizontal_direction(self) -> None:
        """Invalid horizontal direction should raise ValueError."""
        client = MELCloudHomeClient()

        with pytest.raises(ValueError, match="Invalid horizontal direction"):
            await client.ata.set_vane_horizontal("unit-id", "Invalid")

    @pytest.mark.asyncio
    async def test_horizontal_numeric_string(self) -> None:
        """Numeric string for horizontal should be rejected."""
        client = MELCloudHomeClient()

        with pytest.raises(ValueError, match="Invalid horizontal direction"):
            await client.ata.set_vane_horizontal("unit-id", "1")

    @pytest.mark.asyncio
    async def test_valid_horizontal_auto(self) -> None:
        """Valid 'Auto' should pass validation."""
        client = MELCloudHomeClient()

        with pytest.raises(AuthenticationError, match="Not authenticated"):
            await client.ata.set_vane_horizontal("unit-id", "Auto")

    @pytest.mark.asyncio
    async def test_valid_horizontal_swing(self) -> None:
        """Valid 'Swing' should pass validation."""
        client = MELCloudHomeClient()

        with pytest.raises(AuthenticationError, match="Not authenticated"):
            await client.ata.set_vane_horizontal("unit-id", "Swing")

    @pytest.mark.asyncio
    async def test_valid_horizontal_centre(self) -> None:
        """Valid 'Centre' (British spelling) should pass validation."""
        client = MELCloudHomeClient()

        with pytest.raises(AuthenticationError, match="Not authenticated"):
            await client.ata.set_vane_horizontal("unit-id", "Centre")


class TestPowerValidation:
    """Test power parameter validation (via type hints)."""

    @pytest.mark.asyncio
    async def test_power_requires_auth(self) -> None:
        """set_power should require authentication."""
        client = MELCloudHomeClient()

        with pytest.raises(AuthenticationError, match="Not authenticated"):
            await client.ata.set_power("unit-id", True)


class TestAuthenticationRequired:
    """Test that API methods require authentication."""

    @pytest.mark.asyncio
    async def test_get_user_context_requires_auth(self) -> None:
        """get_user_context should raise AuthenticationError when not logged in."""
        client = MELCloudHomeClient()

        with pytest.raises(AuthenticationError, match="Not authenticated"):
            await client.get_user_context()

    @pytest.mark.asyncio
    async def test_set_temperature_requires_auth(self) -> None:
        """set_temperature should raise AuthenticationError when not logged in."""
        client = MELCloudHomeClient()

        with pytest.raises(AuthenticationError, match="Not authenticated"):
            await client.ata.set_temperature("unit-id", 20.0)

    @pytest.mark.asyncio
    async def test_set_mode_requires_auth(self) -> None:
        """set_mode should raise AuthenticationError when not logged in."""
        client = MELCloudHomeClient()

        with pytest.raises(AuthenticationError, match="Not authenticated"):
            await client.ata.set_mode("unit-id", "Heat")

    @pytest.mark.asyncio
    async def test_set_fan_speed_requires_auth(self) -> None:
        """set_fan_speed should raise AuthenticationError when not logged in."""
        client = MELCloudHomeClient()

        with pytest.raises(AuthenticationError, match="Not authenticated"):
            await client.ata.set_fan_speed("unit-id", "Auto")

    @pytest.mark.asyncio
    async def test_set_vane_vertical_requires_auth(self) -> None:
        """set_vane_vertical should raise AuthenticationError when not logged in."""
        client = MELCloudHomeClient()

        with pytest.raises(AuthenticationError, match="Not authenticated"):
            await client.ata.set_vane_vertical("unit-id", "Auto")

    @pytest.mark.asyncio
    async def test_set_vane_horizontal_requires_auth(self) -> None:
        """set_vane_horizontal should raise AuthenticationError when not logged in."""
        client = MELCloudHomeClient()

        with pytest.raises(AuthenticationError, match="Not authenticated"):
            await client.ata.set_vane_horizontal("unit-id", "Auto")
