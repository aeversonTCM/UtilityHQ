"""
Test script for the UtilityHQ updater
Run this to test each component of the update system
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from updater import (
    get_current_version,
    parse_version,
    is_newer_version,
    check_for_updates,
    GITHUB_API_URL
)


def test_version_parsing():
    """Test version string parsing."""
    print("=" * 50)
    print("TEST 1: Version Parsing")
    print("=" * 50)
    
    test_cases = [
        ("1.0.0", (1, 0, 0)),
        ("v1.0.0", (1, 0, 0)),
        ("0.92.0", (0, 92, 0)),
        ("v2.1.3", (2, 1, 3)),
        ("1.0.0-beta", (1, 0, 0)),
    ]
    
    all_passed = True
    for version_str, expected in test_cases:
        result = parse_version(version_str)
        status = "✓" if result == expected else "✗"
        if result != expected:
            all_passed = False
        print(f"  {status} parse_version('{version_str}') = {result} (expected {expected})")
    
    return all_passed


def test_version_comparison():
    """Test version comparison logic."""
    print("\n" + "=" * 50)
    print("TEST 2: Version Comparison")
    print("=" * 50)
    
    test_cases = [
        ("1.0.1", "1.0.0", True),
        ("1.1.0", "1.0.0", True),
        ("2.0.0", "1.9.9", True),
        ("1.0.0", "1.0.0", False),
        ("1.0.0", "1.0.1", False),
        ("0.93.0", "0.92.0", True),
    ]
    
    all_passed = True
    for remote, local, expected in test_cases:
        result = is_newer_version(remote, local)
        status = "✓" if result == expected else "✗"
        if result != expected:
            all_passed = False
        print(f"  {status} is_newer_version('{remote}', '{local}') = {result} (expected {expected})")
    
    return all_passed


def test_github_api():
    """Test GitHub API connection."""
    print("\n" + "=" * 50)
    print("TEST 3: GitHub API Connection")
    print("=" * 50)
    
    print(f"  Current version: {get_current_version()}")
    print(f"  API URL: {GITHUB_API_URL}")
    print(f"  Checking for updates...")
    
    try:
        result = check_for_updates()
        
        if result is None:
            print(f"  ✓ Connected successfully!")
            print(f"  ℹ No update available (you're on latest or no releases exist)")
            return True
        else:
            print(f"  ✓ Connected successfully!")
            print(f"  ℹ Update available: {result['version']}")
            print(f"  ℹ Download URL: {result.get('download_url', 'N/A')}")
            print(f"  ℹ Release page: {result.get('html_url', 'N/A')}")
            return True
            
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def main():
    print("\n" + "=" * 50)
    print("  UtilityHQ Updater Test Suite")
    print("=" * 50)
    
    results = []
    results.append(("Version Parsing", test_version_parsing()))
    results.append(("Version Comparison", test_version_comparison()))
    results.append(("GitHub API", test_github_api()))
    
    print("\n" + "=" * 50)
    print("  SUMMARY")
    print("=" * 50)
    
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {name}")


if __name__ == "__main__":
    main()
