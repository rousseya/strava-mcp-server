#!/usr/bin/env python3
"""
Integration tests for the Strava MCP server tools.
These tests make real API calls and require valid credentials.
Run with: uv run pytest tests/test_integration.py -v
"""

import os
import sys

import pytest

# Add src to path so we can import the package
sys.path.append(os.path.join(os.getcwd(), "src"))

from strava_mcp_server.main import get_activities, get_activity, get_stats

# Skip integration tests if no real credentials
pytestmark = pytest.mark.skipif(
    os.getenv("STRAVA_CLIENT_ID") == "test",
    reason="Skipping integration tests in CI (no real credentials)",
)


def test_get_activities():
    """Test fetching activities from Strava API."""
    activities = get_activities(limit=5)
    assert isinstance(activities, list)
    if activities:
        assert "id" in activities[0]
        assert "name" in activities[0]
        assert "type" in activities[0]


def test_get_stats():
    """Test fetching athlete stats from Strava API."""
    stats = get_stats()
    assert isinstance(stats, dict)
    assert "all_run_totals" in stats or "all_ride_totals" in stats


def test_get_activity():
    """Test fetching a specific activity from Strava API."""
    # First get some activities to get an ID
    activities = get_activities(limit=1)
    if not activities:
        pytest.skip("No activities found")

    activity_id = activities[0]["id"]
    activity = get_activity(activity_id)

    assert isinstance(activity, dict)
    assert activity["id"] == activity_id
    assert "name" in activity
    assert "distance" in activity


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
