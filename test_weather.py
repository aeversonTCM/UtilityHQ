#!/usr/bin/env python3
"""
Weather API Test Script
Run this to test your Weather Underground API connection and see what data is returned.

Usage:
    python test_weather.py YOUR_API_KEY YOUR_STATION_ID
    
Example:
    python test_weather.py abc123def456 KNCHENDE440
"""

import sys
import json
from datetime import date, timedelta

# Add src to path
sys.path.insert(0, 'src')

from weather_api import WeatherUndergroundAPI

def main():
    if len(sys.argv) < 3:
        print("Usage: python test_weather.py API_KEY STATION_ID")
        print("Example: python test_weather.py abc123def456 KNCHENDE440")
        sys.exit(1)
    
    api_key = sys.argv[1]
    station_id = sys.argv[2]
    
    print("=" * 60)
    print("Weather Underground API Test")
    print("=" * 60)
    print(f"Station ID: {station_id}")
    print(f"API Key: {api_key[:8]}...{api_key[-4:]}")
    print()
    
    api = WeatherUndergroundAPI(api_key, station_id)
    
    # Test 1: Current conditions
    print("-" * 60)
    print("TEST 1: Current Conditions")
    print("-" * 60)
    current = api.get_current_conditions()
    if current:
        print("✅ SUCCESS!")
        print(f"   Temperature: {current.get('temp')}°F")
        print(f"   Humidity: {current.get('humidity')}%")
        print(f"   Wind: {current.get('wind_speed')} mph")
    else:
        print("❌ FAILED - Could not get current conditions")
    print()
    
    # Test 2: Yesterday's history
    print("-" * 60)
    print("TEST 2: Yesterday's History (history/all endpoint)")
    print("-" * 60)
    yesterday = date.today() - timedelta(days=1)
    obs = api.get_historical_daily(yesterday)
    if obs:
        print("✅ SUCCESS!")
        print(f"   Date: {obs.date}")
        print(f"   High: {obs.temp_high}°F")
        print(f"   Low: {obs.temp_low}°F")
        print(f"   Rain: {obs.rain_total}\"")
    else:
        print("❌ FAILED - Could not get yesterday's data")
    print()
    
    # Test 3: Monthly summary
    print("-" * 60)
    print("TEST 3: Monthly Summary (history/daily endpoint)")
    print("-" * 60)
    today = date.today()
    monthly = api.get_monthly_summary(today.year, today.month)
    if monthly:
        print(f"✅ SUCCESS! Got {len(monthly)} days")
        for obs in monthly[:3]:  # Show first 3
            print(f"   {obs.date}: High {obs.temp_high}°F, Low {obs.temp_low}°F")
        if len(monthly) > 3:
            print(f"   ... and {len(monthly) - 3} more days")
    else:
        print("❌ FAILED - Could not get monthly data")
    print()
    
    # Test 4: 7-day summary
    print("-" * 60)
    print("TEST 4: 7-Day Summary (dailysummary/7day endpoint)")
    print("-" * 60)
    summary = api.get_daily_summary(yesterday)
    if summary:
        print("✅ SUCCESS!")
        print(f"   Date: {summary.date}")
        print(f"   High: {summary.temp_high}°F")
        print(f"   Low: {summary.temp_low}°F")
    else:
        print("❌ FAILED - Could not get 7-day summary")
    print()
    
    print("=" * 60)
    print("Test complete!")
    print("=" * 60)

if __name__ == '__main__':
    main()
