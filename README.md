# ⚡ Utilities Tracker

A professional desktop application for tracking home utility bills (Electric, Gas, Water) and correlating usage with weather data.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![PyQt6](https://img.shields.io/badge/PyQt6-6.5+-green.svg)
![SQLite](https://img.shields.io/badge/SQLite-3-orange.svg)

## Features

### 📊 Dashboard
- **Command Center Layout** - Ribbon-style toolbar with grouped metrics
- **Interactive Qt Charts** - Monthly trends, cost breakdown, weather demand
- **Real-time Statistics** - Current month costs, usage per day, YTD totals

### 💰 Bill Management
- **Multi-utility Support** - Electric (kWh), Gas (Therms), Water (Gallons)
- **Slide-out Entry Panel** - Quick data entry with auto-calculations
- **Historical Tracking** - View and analyze bills over time

### 🌤️ Weather Integration
- **Weather Underground API** - Personal weather station support
- **Demand Analysis** - Heating/cooling demand calculations
- **Historical Data** - 7+ years of weather correlation

## Quick Start

### Option 1: Run from Source
```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python run.py
```

### Option 2: Build Standalone EXE (Windows)
```bash
# Double-click build.bat, or run:
pip install pyinstaller
pyinstaller build.spec

# Your EXE will be in: dist/Utilities Tracker.exe
```

## Building the EXE

### Requirements
- Windows 10/11
- Python 3.10 or higher
- ~500MB disk space for build

### Steps
1. Open Command Prompt in the project folder
2. Run `build.bat`
3. Wait 2-5 minutes for compilation
4. Find your EXE in `dist/Utilities Tracker.exe`

### What Gets Built
- Single ~100MB executable
- No Python installation required to run
- Database created automatically on first launch
- Portable - copy anywhere and run

## Project Structure

```
utilities-tracker/
├── run.py              # Application launcher
├── build.bat           # Windows build script
├── build.spec          # PyInstaller configuration
├── requirements.txt    # Python dependencies
├── data/
│   └── utilities.db    # SQLite database
├── resources/
│   └── icon.svg        # Application icon
└── src/
    ├── main.py         # Main UI (PyQt6)
    ├── charts.py       # Qt Charts components
    ├── database.py     # Database layer
    ├── weather_api.py  # Weather Underground API
    └── migrate_data.py # Excel import tool
```

## Data Migration

Import from existing Excel workbook:
```bash
python src/migrate_data.py /path/to/Utilities.xlsm --db data/utilities.db
```

## Charts Included

| Chart | Type | Shows |
|-------|------|-------|
| Monthly Cost Trend | Spline | Electric/Gas/Water over time |
| Cost Breakdown | Donut | Annual % by utility |
| Weather Demand | Combo | Costs vs heating/cooling demand |
| Year Comparison | Grouped Bar | Last 4 years side by side |

## License

MIT License - Free for personal use.

---
*Built with PyQt6 and Qt Charts*
