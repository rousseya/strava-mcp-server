"""Unit tests for Strava MCP server tools with mocked API responses."""

from unittest.mock import MagicMock, patch

import pytest

# Mock activity data
MOCK_ACTIVITY = MagicMock()
MOCK_ACTIVITY.id = 12345678
MOCK_ACTIVITY.name = "Morning Run"
MOCK_ACTIVITY.type = "Run"
MOCK_ACTIVITY.distance = 10000.0
MOCK_ACTIVITY.moving_time = 3600
MOCK_ACTIVITY.elapsed_time = 3700
MOCK_ACTIVITY.total_elevation_gain = 150.0
MOCK_ACTIVITY.start_date_local = MagicMock()
MOCK_ACTIVITY.start_date_local.isoformat.return_value = "2025-12-10T08:00:00"
MOCK_ACTIVITY.average_speed = 2.78
MOCK_ACTIVITY.max_speed = 4.0
MOCK_ACTIVITY.average_heartrate = 145.0
MOCK_ACTIVITY.max_heartrate = 175.0
MOCK_ACTIVITY.suffer_score = 50
MOCK_ACTIVITY.kudos_count = 10


# Mock stats data
def create_mock_totals(count, distance, moving_time, elapsed_time, elevation_gain):
    totals = MagicMock()
    totals.count = count
    totals.distance = distance
    totals.moving_time = moving_time
    totals.elapsed_time = elapsed_time
    totals.elevation_gain = elevation_gain
    return totals


MOCK_STATS = MagicMock()
MOCK_STATS.recent_ride_totals = create_mock_totals(5, 100000, 10000, 11000, 500)
MOCK_STATS.recent_run_totals = create_mock_totals(10, 80000, 8000, 8500, 300)
MOCK_STATS.ytd_ride_totals = create_mock_totals(50, 1000000, 100000, 110000, 5000)
MOCK_STATS.ytd_run_totals = create_mock_totals(100, 800000, 80000, 85000, 3000)
MOCK_STATS.all_ride_totals = create_mock_totals(200, 4000000, 400000, 440000, 20000)
MOCK_STATS.all_run_totals = create_mock_totals(500, 6000000, 600000, 650000, 30000)


class TestGetActivities:
    """Tests for get_activities tool."""

    @patch("strava_mcp_server.main.StravaClient")
    def test_get_activities_returns_list(self, mock_client_class):
        """Test that get_activities returns a list of activity dicts."""
        from strava_mcp_server.main import get_activities

        mock_client = MagicMock()
        mock_client.get_activities.return_value = [MOCK_ACTIVITY]
        mock_client_class.return_value = mock_client

        result = get_activities(limit=5)

        assert isinstance(result, list)
        assert len(result) == 1
        mock_client.get_activities.assert_called_once_with(limit=5)

    @patch("strava_mcp_server.main.StravaClient")
    def test_get_activities_data_format(self, mock_client_class):
        """Test that activity data is correctly formatted."""
        from strava_mcp_server.main import get_activities

        mock_client = MagicMock()
        mock_client.get_activities.return_value = [MOCK_ACTIVITY]
        mock_client_class.return_value = mock_client

        result = get_activities(limit=1)
        activity = result[0]

        assert activity["id"] == 12345678
        assert activity["name"] == "Morning Run"
        assert activity["type"] == "Run"
        assert activity["distance"] == 10000.0
        assert activity["moving_time"] == 3600
        assert activity["elevation_gain"] == 150.0
        assert activity["start_date_local"] == "2025-12-10T08:00:00"

    @patch("strava_mcp_server.main.StravaClient")
    def test_get_activities_empty_list(self, mock_client_class):
        """Test that empty activity list is handled."""
        from strava_mcp_server.main import get_activities

        mock_client = MagicMock()
        mock_client.get_activities.return_value = []
        mock_client_class.return_value = mock_client

        result = get_activities()

        assert result == []


class TestGetActivity:
    """Tests for get_activity tool."""

    @patch("strava_mcp_server.main.StravaClient")
    def test_get_activity_returns_dict(self, mock_client_class):
        """Test that get_activity returns an activity dict."""
        from strava_mcp_server.main import get_activity

        mock_client = MagicMock()
        mock_client.get_activity.return_value = MOCK_ACTIVITY
        mock_client_class.return_value = mock_client

        result = get_activity(activity_id=12345678)

        assert isinstance(result, dict)
        mock_client.get_activity.assert_called_once_with(12345678)

    @patch("strava_mcp_server.main.StravaClient")
    def test_get_activity_includes_detailed_fields(self, mock_client_class):
        """Test that detailed fields are included."""
        from strava_mcp_server.main import get_activity

        mock_client = MagicMock()
        mock_client.get_activity.return_value = MOCK_ACTIVITY
        mock_client_class.return_value = mock_client

        result = get_activity(activity_id=12345678)

        assert result["average_speed"] == 2.78
        assert result["max_speed"] == 4.0
        assert result["average_heartrate"] == 145.0
        assert result["max_heartrate"] == 175.0
        assert result["suffer_score"] == 50
        assert result["kudos_count"] == 10


class TestGetStats:
    """Tests for get_stats tool."""

    @patch("strava_mcp_server.main.StravaClient")
    def test_get_stats_returns_dict(self, mock_client_class):
        """Test that get_stats returns a stats dict."""
        from strava_mcp_server.main import get_stats

        mock_client = MagicMock()
        mock_client.get_stats.return_value = MOCK_STATS
        mock_client_class.return_value = mock_client

        result = get_stats()

        assert isinstance(result, dict)
        mock_client.get_stats.assert_called_once()

    @patch("strava_mcp_server.main.StravaClient")
    def test_get_stats_includes_all_totals(self, mock_client_class):
        """Test that all totals categories are included."""
        from strava_mcp_server.main import get_stats

        mock_client = MagicMock()
        mock_client.get_stats.return_value = MOCK_STATS
        mock_client_class.return_value = mock_client

        result = get_stats()

        assert "recent_ride_totals" in result
        assert "recent_run_totals" in result
        assert "ytd_ride_totals" in result
        assert "ytd_run_totals" in result
        assert "all_ride_totals" in result
        assert "all_run_totals" in result

    @patch("strava_mcp_server.main.StravaClient")
    def test_get_stats_totals_format(self, mock_client_class):
        """Test that totals have correct format."""
        from strava_mcp_server.main import get_stats

        mock_client = MagicMock()
        mock_client.get_stats.return_value = MOCK_STATS
        mock_client_class.return_value = mock_client

        result = get_stats()
        run_totals = result["all_run_totals"]

        assert run_totals["count"] == 500
        assert run_totals["distance"] == 6000000
        assert run_totals["moving_time"] == 600000
        assert run_totals["elevation_gain"] == 30000

    @patch("strava_mcp_server.main.StravaClient")
    def test_get_stats_handles_none(self, mock_client_class):
        """Test that None stats returns empty dict."""
        from strava_mcp_server.main import get_stats

        mock_client = MagicMock()
        mock_client.get_stats.return_value = None
        mock_client_class.return_value = mock_client

        result = get_stats()

        assert result == {}


class TestStravaClient:
    """Tests for StravaClient wrapper."""

    @patch.dict(
        "os.environ",
        {
            "STRAVA_CLIENT_ID": "12345",
            "STRAVA_CLIENT_SECRET": "secret",
            "STRAVA_ACCESS_TOKEN": "access",
            "STRAVA_REFRESH_TOKEN": "refresh",
        },
    )
    @patch("strava_mcp_server.strava_client.Client")
    def test_client_initializes_with_credentials(self, mock_stravalib_client):
        """Test that client initializes with env credentials."""
        from strava_mcp_server.strava_client import StravaClient

        client = StravaClient()

        assert client.client_id == "12345"
        assert client.client_secret == "secret"

    @patch("strava_mcp_server.strava_client.Client")
    def test_client_raises_on_missing_credentials(self, mock_stravalib_client):
        """Test that missing credentials raises RuntimeError."""
        import os

        from strava_mcp_server.strava_client import StravaClient

        # Save and clear env vars
        saved = {}
        env_keys = [
            "STRAVA_CLIENT_ID",
            "STRAVA_CLIENT_SECRET",
            "STRAVA_ACCESS_TOKEN",
            "STRAVA_REFRESH_TOKEN",
        ]
        for key in env_keys:
            saved[key] = os.environ.pop(key, None)

        try:
            with pytest.raises(RuntimeError, match="Missing Strava credentials"):
                StravaClient()
        finally:
            # Restore env vars
            for key, value in saved.items():
                if value is not None:
                    os.environ[key] = value
