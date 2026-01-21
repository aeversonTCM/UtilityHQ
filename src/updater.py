"""
UtilityHQ Auto-Updater
Checks GitHub releases for updates and handles download/install
"""

import os
import sys
import json
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Tuple
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# Version - use 0.x.x until production ready, then 1.0.0
__version__ = "0.92.0"

# GitHub repository info
GITHUB_OWNER = "aeversonTCM"
GITHUB_REPO = "utilityHQ"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"


def get_current_version() -> str:
    """Return the current application version."""
    return __version__


def parse_version(version_str: str) -> Tuple[int, int, int]:
    """Parse version string into tuple for comparison."""
    # Remove 'v' prefix if present
    version_str = version_str.lstrip('vV')
    
    try:
        parts = version_str.split('.')
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2].split('-')[0]) if len(parts) > 2 else 0  # Handle v1.0.0-beta
        return (major, minor, patch)
    except (ValueError, IndexError):
        return (0, 0, 0)


def is_newer_version(remote: str, local: str) -> bool:
    """Check if remote version is newer than local version."""
    remote_tuple = parse_version(remote)
    local_tuple = parse_version(local)
    return remote_tuple > local_tuple


def check_for_updates() -> Optional[dict]:
    """
    Check GitHub for the latest release.
    
    Returns:
        dict with keys: version, download_url, release_notes, html_url
        None if no update available or error occurred
    """
    try:
        request = Request(
            GITHUB_API_URL,
            headers={
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': f'UtilityHQ-Updater/{__version__}'
            }
        )
        
        with urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
        
        remote_version = data.get('tag_name', '0.0.0')
        
        if not is_newer_version(remote_version, __version__):
            return None  # No update available
        
        # Find the exe asset
        download_url = None
        asset_name = None
        for asset in data.get('assets', []):
            name = asset.get('name', '')
            if name.endswith('.exe'):
                download_url = asset.get('browser_download_url')
                asset_name = name
                break
        
        if not download_url:
            # No exe found, return the release page URL
            return {
                'version': remote_version,
                'download_url': None,
                'html_url': data.get('html_url'),
                'release_notes': data.get('body', 'No release notes available.'),
                'asset_name': None
            }
        
        return {
            'version': remote_version,
            'download_url': download_url,
            'html_url': data.get('html_url'),
            'release_notes': data.get('body', 'No release notes available.'),
            'asset_name': asset_name
        }
        
    except HTTPError as e:
        print(f"HTTP Error checking for updates: {e.code}")
        return None
    except URLError as e:
        print(f"URL Error checking for updates: {e.reason}")
        return None
    except Exception as e:
        print(f"Error checking for updates: {e}")
        return None


def download_update(download_url: str, progress_callback=None) -> Optional[str]:
    """
    Download the update file to a temp directory.
    
    Args:
        download_url: URL to download the update from
        progress_callback: Optional callback function(bytes_downloaded, total_bytes)
    
    Returns:
        Path to downloaded file, or None if failed
    """
    try:
        request = Request(
            download_url,
            headers={'User-Agent': f'UtilityHQ-Updater/{__version__}'}
        )
        
        with urlopen(request, timeout=60) as response:
            total_size = int(response.headers.get('content-length', 0))
            
            # Create temp file
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, 'UtilityHQ_update.exe')
            
            downloaded = 0
            chunk_size = 8192
            
            with open(temp_path, 'wb') as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    if progress_callback and total_size > 0:
                        progress_callback(downloaded, total_size)
        
        return temp_path
        
    except Exception as e:
        print(f"Error downloading update: {e}")
        return None


def create_update_script(new_exe_path: str, current_exe_path: str) -> str:
    """
    Create a batch script that will:
    1. Wait for the current app to close
    2. Replace the old exe with the new one
    3. Restart the app
    
    Returns:
        Path to the batch script
    """
    temp_dir = tempfile.gettempdir()
    script_path = os.path.join(temp_dir, 'utilityhq_update.bat')
    
    # Batch script content
    script = f'''@echo off
echo Updating UtilityHQ...
echo.

:: Wait for the application to close (up to 30 seconds)
set /a count=0
:waitloop
tasklist /FI "IMAGENAME eq {os.path.basename(current_exe_path)}" 2>NUL | find /I "{os.path.basename(current_exe_path)}" >NUL
if "%ERRORLEVEL%"=="0" (
    set /a count+=1
    if %count% GEQ 30 (
        echo Timeout waiting for application to close.
        pause
        exit /b 1
    )
    timeout /t 1 /nobreak >NUL
    goto waitloop
)

:: Small delay to ensure file handles are released
timeout /t 2 /nobreak >NUL

:: Backup old exe
if exist "{current_exe_path}" (
    move /Y "{current_exe_path}" "{current_exe_path}.backup" >NUL 2>&1
)

:: Copy new exe
copy /Y "{new_exe_path}" "{current_exe_path}" >NUL 2>&1

if "%ERRORLEVEL%"=="0" (
    echo Update successful!
    :: Clean up backup
    del "{current_exe_path}.backup" >NUL 2>&1
    :: Start the updated application
    start "" "{current_exe_path}"
) else (
    echo Update failed! Restoring backup...
    move /Y "{current_exe_path}.backup" "{current_exe_path}" >NUL 2>&1
    pause
)

:: Clean up
del "{new_exe_path}" >NUL 2>&1
del "%~f0" >NUL 2>&1
'''
    
    with open(script_path, 'w') as f:
        f.write(script)
    
    return script_path


def apply_update(new_exe_path: str) -> bool:
    """
    Apply the update by running the update script and closing the app.
    
    Args:
        new_exe_path: Path to the downloaded update exe
    
    Returns:
        True if update script was launched successfully
    """
    try:
        # Get current executable path
        if getattr(sys, 'frozen', False):
            # Running as compiled exe
            current_exe = sys.executable
        else:
            # Running as script - for testing, use a dummy path
            current_exe = os.path.join(os.path.dirname(__file__), '..', 'UtilityHQ.exe')
        
        # Create the update script
        script_path = create_update_script(new_exe_path, current_exe)
        
        # Launch the update script (hidden window)
        subprocess.Popen(
            ['cmd', '/c', script_path],
            creationflags=subprocess.CREATE_NO_WINDOW,
            cwd=tempfile.gettempdir()
        )
        
        return True
        
    except Exception as e:
        print(f"Error applying update: {e}")
        return False


# For testing
if __name__ == "__main__":
    print(f"Current version: {get_current_version()}")
    print("Checking for updates...")
    
    update = check_for_updates()
    if update:
        print(f"Update available: {update['version']}")
        print(f"Download URL: {update['download_url']}")
        print(f"Release notes: {update['release_notes'][:200]}...")
    else:
        print("No updates available (or you're already on the latest version)")
