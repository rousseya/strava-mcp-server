#!/usr/bin/env python3
"""
Test script for the Strava MCP server tools.
This script directly calls the MCP tools to verify they work correctly.
"""

import sys
import os

# Add src to path so we can import the package
sys.path.append(os.path.join(os.getcwd(), "src"))

from strava_mcp_server.main import get_activities, get_activity, get_stats

def test_get_activities():
    print("Testing get_activities...")
    try:
        activities = get_activities(limit=5)
        print(f"✓ Got {len(activities)} activities")
        if activities:
            print(f"  First activity: {activities[0]['name']} ({activities[0]['type']})")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_get_stats():
    print("Testing get_stats...")
    try:
        stats = get_stats()
        print("✓ Got athlete stats")
        if stats.get('all_run_totals'):
            print(f"  All-time runs: {stats['all_run_totals']['count']}")
        if stats.get('all_ride_totals'):
            print(f"  All-time rides: {stats['all_ride_totals']['count']}")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_get_activity():
    print("Testing get_activity...")
    try:
        # First get some activities to get an ID
        activities = get_activities(limit=1)
        if not activities:
            print("✗ No activities found to test get_activity")
            return False

        activity_id = activities[0]['id']
        print(f"  Testing with activity ID: {activity_id}")

        activity = get_activity(activity_id)
        print(f"✓ Got activity details: {activity['name']}")
        print(f"  Distance: {activity['distance']:.2f} meters")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

if __name__ == "__main__":
    print("Testing Strava MCP Server Tools")
    print("=" * 40)

    tests = [
        test_get_activities,
        test_get_stats,
        test_get_activity,
    ]

    passed = 0
    for test in tests:
        if test():
            passed += 1
        print()

    print(f"Results: {passed}/{len(tests)} tests passed")
    if passed == len(tests):
        print("🎉 All tests passed!")
    else:
        print("❌ Some tests failed")
        sys.exit(1)