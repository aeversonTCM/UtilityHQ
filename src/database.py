"""
Utilities Tracker - Database Module
SQLite database schema and operations for utility bills, weather data, and configuration.
"""

import sqlite3
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from contextlib import contextmanager


# Data Classes for type safety
@dataclass
class ElectricBill:
    id: Optional[int]
    bill_date: date
    meter_reading: float
    usage_kwh: float
    days: int
    kwh_per_day: float
    electric_cost: float
    taxes: float
    total_cost: float
    cost_per_kwh: float
    last_read_date: Optional[date] = None

@dataclass
class GasBill:
    id: Optional[int]
    bill_date: date
    meter_reading: float
    usage_ccf: float
    btu_factor: float
    days: int
    therms: float
    therms_per_day: float
    cost_per_therm: float
    therm_cost: float
    service_charge: float
    taxes: float
    total_cost: float
    last_read_date: Optional[date] = None

@dataclass
class WaterBill:
    id: Optional[int]
    bill_date: date
    meter_reading: float
    usage_gallons: float
    gallons_per_day: float
    water_cost: float
    service_charge: float
    cost_per_kgal: float
    total_cost: float

@dataclass
@dataclass
class WeatherDay:
    date: date
    temp_high: Optional[float] = None
    temp_avg: Optional[float] = None
    temp_low: Optional[float] = None
    dewpoint_high: Optional[float] = None
    dewpoint_avg: Optional[float] = None
    dewpoint_low: Optional[float] = None
    humidity_high: Optional[float] = None
    humidity_avg: Optional[float] = None
    humidity_low: Optional[float] = None
    wind_max: Optional[float] = None
    wind_avg: Optional[float] = None
    wind_gust: Optional[float] = None
    pressure_max: Optional[float] = None
    pressure_min: Optional[float] = None
    rain_total: Optional[float] = None
    cooling_demand: Optional[float] = None
    heating_demand: Optional[float] = None
    max_demand: Optional[float] = None
    id: Optional[int] = None


class DatabaseManager:
    """Manages SQLite database operations for the Utilities Tracker."""
    
    def __init__(self, db_path: str = "utilities.db"):
        self.db_path = Path(db_path)
        self._init_database()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def _init_database(self):
        """Initialize database with schema."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Electric Bills Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS electric_bills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bill_date DATE NOT NULL UNIQUE,
                    meter_reading REAL,
                    usage_kwh REAL NOT NULL,
                    days INTEGER NOT NULL,
                    kwh_per_day REAL,
                    electric_cost REAL,
                    taxes REAL,
                    total_cost REAL NOT NULL,
                    cost_per_kwh REAL,
                    last_read_date DATE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Gas Bills Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS gas_bills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bill_date DATE NOT NULL UNIQUE,
                    meter_reading REAL,
                    usage_ccf REAL NOT NULL,
                    btu_factor REAL,
                    days INTEGER NOT NULL,
                    therms REAL,
                    therms_per_day REAL,
                    cost_per_therm REAL,
                    therm_cost REAL,
                    service_charge REAL,
                    taxes REAL,
                    total_cost REAL NOT NULL,
                    last_read_date DATE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Water Bills Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS water_bills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bill_date DATE NOT NULL UNIQUE,
                    meter_reading REAL,
                    usage_gallons REAL NOT NULL,
                    gallons_per_day REAL,
                    water_cost REAL,
                    service_charge REAL,
                    cost_per_kgal REAL,
                    total_cost REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Weather Data Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS weather_daily (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE NOT NULL UNIQUE,
                    temp_high REAL,
                    temp_avg REAL,
                    temp_low REAL,
                    dewpoint_high REAL,
                    dewpoint_avg REAL,
                    dewpoint_low REAL,
                    humidity_high REAL,
                    humidity_avg REAL,
                    humidity_low REAL,
                    wind_max REAL,
                    wind_avg REAL,
                    wind_gust REAL,
                    pressure_max REAL,
                    pressure_min REAL,
                    rain_total REAL DEFAULT 0,
                    cooling_demand REAL,
                    heating_demand REAL,
                    max_demand REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Configuration Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    description TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Yearly Summary View (materialized as table for performance)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS yearly_costs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    year INTEGER NOT NULL,
                    month INTEGER NOT NULL,
                    electric_cost REAL DEFAULT 0,
                    gas_cost REAL DEFAULT 0,
                    water_cost REAL DEFAULT 0,
                    total_cost REAL DEFAULT 0,
                    electric_usage REAL DEFAULT 0,
                    gas_usage REAL DEFAULT 0,
                    water_usage REAL DEFAULT 0,
                    UNIQUE(year, month)
                )
            ''')
            
            # Create indexes for performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_electric_date ON electric_bills(bill_date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_gas_date ON gas_bills(bill_date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_water_date ON water_bills(bill_date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_weather_date ON weather_daily(date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_yearly_costs ON yearly_costs(year, month)')
            
            # Meter Readings Table (for tracking current readings separate from bills)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS meter_readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    utility_type TEXT NOT NULL,
                    reading_date DATE NOT NULL,
                    reading_value REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_meter_readings ON meter_readings(utility_type, reading_date)')
            
            # PDF Templates Table (for storing field mappings for PDF import)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pdf_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    utility_type TEXT NOT NULL UNIQUE,
                    field_mappings TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Insert default configuration
            default_config = [
                ('station_id', 'KNCHENDE440', 'Weather Underground Station ID'),
                ('heating_min_temp', '15', 'Minimum temperature for heating demand calculation'),
                ('heating_max_temp', '54', 'Maximum temperature for heating demand calculation'),
                ('cooling_min_temp', '78', 'Minimum temperature for cooling demand calculation'),
                ('cooling_max_temp', '96', 'Maximum temperature for cooling demand calculation'),
                ('home_sqft', '1730', 'Home square footage for cost per sqft calculations'),
                ('wu_api_key', 'ccd2cced77eb4b3d92cced77ebab3d69', 'Weather Underground API Key'),
                ('weather_source', 'open-meteo', 'Weather data source: open-meteo or wu'),
                ('location_latitude', '35.3187', 'Location latitude for Open-Meteo'),
                ('location_longitude', '-82.4612', 'Location longitude for Open-Meteo'),
                ('location_name', 'Hendersonville, North Carolina', 'Location display name'),
            ]
            
            cursor.executemany('''
                INSERT OR IGNORE INTO config (key, value, description) VALUES (?, ?, ?)
            ''', default_config)
    
    # ==================== Electric Bill Operations ====================
    
    def add_electric_bill(self, bill: ElectricBill) -> int:
        """Add a new electric bill."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO electric_bills 
                (bill_date, meter_reading, usage_kwh, days, kwh_per_day, 
                 electric_cost, taxes, total_cost, cost_per_kwh, last_read_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (bill.bill_date, bill.meter_reading, bill.usage_kwh, bill.days,
                  bill.kwh_per_day, bill.electric_cost, bill.taxes, bill.total_cost,
                  bill.cost_per_kwh, bill.last_read_date))
            return cursor.lastrowid
    
    def get_electric_bills(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Get electric bills with pagination."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM electric_bills 
                ORDER BY bill_date DESC 
                LIMIT ? OFFSET ?
            ''', (limit, offset))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_latest_electric_bill(self) -> Optional[Dict]:
        """Get the most recent electric bill."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM electric_bills ORDER BY bill_date DESC LIMIT 1')
            row = cursor.fetchone()
            return dict(row) if row else None
    
    # ==================== Gas Bill Operations ====================
    
    def add_gas_bill(self, bill: GasBill) -> int:
        """Add a new gas bill."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO gas_bills 
                (bill_date, meter_reading, usage_ccf, btu_factor, days, therms,
                 therms_per_day, cost_per_therm, therm_cost, service_charge, 
                 taxes, total_cost, last_read_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (bill.bill_date, bill.meter_reading, bill.usage_ccf, bill.btu_factor,
                  bill.days, bill.therms, bill.therms_per_day, bill.cost_per_therm,
                  bill.therm_cost, bill.service_charge, bill.taxes, bill.total_cost,
                  bill.last_read_date))
            return cursor.lastrowid
    
    def get_gas_bills(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Get gas bills with pagination."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM gas_bills 
                ORDER BY bill_date DESC 
                LIMIT ? OFFSET ?
            ''', (limit, offset))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_latest_gas_bill(self) -> Optional[Dict]:
        """Get the most recent gas bill."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM gas_bills ORDER BY bill_date DESC LIMIT 1')
            row = cursor.fetchone()
            return dict(row) if row else None
    
    # ==================== Water Bill Operations ====================
    
    def add_water_bill(self, bill: WaterBill) -> int:
        """Add a new water bill."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO water_bills 
                (bill_date, meter_reading, usage_gallons, gallons_per_day,
                 water_cost, service_charge, cost_per_kgal, total_cost)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (bill.bill_date, bill.meter_reading, bill.usage_gallons,
                  bill.gallons_per_day, bill.water_cost, bill.service_charge,
                  bill.cost_per_kgal, bill.total_cost))
            return cursor.lastrowid
    
    def get_water_bills(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Get water bills with pagination."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM water_bills 
                ORDER BY bill_date DESC 
                LIMIT ? OFFSET ?
            ''', (limit, offset))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_latest_water_bill(self) -> Optional[Dict]:
        """Get the most recent water bill."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM water_bills ORDER BY bill_date DESC LIMIT 1')
            row = cursor.fetchone()
            return dict(row) if row else None
    
    # ==================== Weather Operations ====================
    
    def add_weather_day(self, weather: WeatherDay) -> int:
        """Add or update weather data for a day."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO weather_daily 
                (date, temp_high, temp_avg, temp_low, dewpoint_high, dewpoint_avg,
                 dewpoint_low, humidity_high, humidity_avg, humidity_low, wind_max,
                 wind_avg, wind_gust, pressure_max, pressure_min, rain_total,
                 cooling_demand, heating_demand, max_demand)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (weather.date, weather.temp_high, weather.temp_avg, weather.temp_low,
                  weather.dewpoint_high, weather.dewpoint_avg, weather.dewpoint_low,
                  weather.humidity_high, weather.humidity_avg, weather.humidity_low,
                  weather.wind_max, weather.wind_avg, weather.wind_gust,
                  weather.pressure_max, weather.pressure_min, weather.rain_total,
                  weather.cooling_demand, weather.heating_demand, weather.max_demand))
            return cursor.lastrowid
    
    def get_weather_range(self, start_date: date, end_date: date) -> List[Dict]:
        """Get weather data for a date range."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM weather_daily 
                WHERE date BETWEEN ? AND ?
                ORDER BY date
            ''', (start_date, end_date))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_latest_weather_date(self) -> Optional[date]:
        """Get the most recent weather data date."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT MAX(date) as max_date FROM weather_daily')
            row = cursor.fetchone()
            if row and row['max_date']:
                return datetime.strptime(row['max_date'], '%Y-%m-%d').date()
            return None
    
    # ==================== Configuration Operations ====================
    
    def get_config(self, key: str) -> Optional[str]:
        """Get a configuration value."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT value FROM config WHERE key = ?', (key,))
            row = cursor.fetchone()
            return row['value'] if row else None
    
    def set_config(self, key: str, value: str, description: str = None):
        """Set a configuration value (insert or update)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Always use INSERT OR REPLACE to handle both new and existing keys
            cursor.execute('''
                INSERT OR REPLACE INTO config (key, value, description, updated_at)
                VALUES (?, ?, COALESCE(?, (SELECT description FROM config WHERE key = ?)), CURRENT_TIMESTAMP)
            ''', (key, value, description, key))
    
    def get_all_config(self) -> Dict[str, str]:
        """Get all configuration values."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT key, value FROM config')
            return {row['key']: row['value'] for row in cursor.fetchall()}
    
    # ==================== Analytics Queries ====================
    
    def get_monthly_totals(self, year: int) -> List[Dict]:
        """Get monthly cost totals for a year."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM yearly_costs
                WHERE year = ?
                ORDER BY month
            ''', (year,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_monthly_cost_forecast(self) -> Dict:
        """Get cost forecast for previous, current, and next month."""
        from calendar import monthrange
        today = date.today()
        
        # Calculate the three months
        prev_month = today.month - 1 if today.month > 1 else 12
        prev_year = today.year if today.month > 1 else today.year - 1
        
        curr_month = today.month
        curr_year = today.year
        
        next_month = today.month + 1 if today.month < 12 else 1
        next_year = today.year if today.month < 12 else today.year + 1
        
        month_names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                       'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        def get_month_stats(month: int) -> Dict:
            """Get historical stats for a specific month across all years."""
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT total_cost, year
                    FROM yearly_costs
                    WHERE month = ?
                    ORDER BY year
                ''', (month,))
                rows = cursor.fetchall()
                
                if not rows:
                    return {'last_yr': 0, 'min': 0, 'max': 0, 'avg': 0}
                
                costs = [r['total_cost'] for r in rows if r['total_cost']]
                years = [r['year'] for r in rows]
                
                last_yr_cost = 0
                if len(rows) >= 2:
                    last_yr_cost = rows[-2]['total_cost'] or 0  # Second to last year
                elif len(rows) == 1:
                    last_yr_cost = rows[-1]['total_cost'] or 0
                
                return {
                    'last_yr': last_yr_cost,
                    'min': min(costs) if costs else 0,
                    'max': max(costs) if costs else 0,
                    'avg': sum(costs) / len(costs) if costs else 0,
                }
        
        def get_actual_cost(year: int, month: int) -> float:
            """Get actual cost for a specific month/year."""
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT total_cost FROM yearly_costs
                    WHERE year = ? AND month = ?
                ''', (year, month))
                row = cursor.fetchone()
                return row['total_cost'] if row and row['total_cost'] else 0
        
        def get_forecast_cost(month: int) -> float:
            """Calculate forecast cost using demand monthly averages."""
            # Get demand monthly data
            demand_data = self.get_demand_monthly()
            
            # Get the average demand for this month
            month_demand = demand_data['averages'][month - 1] if demand_data['averages'] else 0
            
            if month_demand == 0:
                # Fall back to historical average cost for this month
                stats = get_month_stats(month)
                return stats['avg']
            
            # Calculate cost per demand unit from historical data
            # Use the demand matrix to get total cost and total demand
            matrix = self.get_demand_matrix()
            if not matrix:
                stats = get_month_stats(month)
                return stats['avg']
            
            # Calculate average cost per demand unit
            total_cost = sum(y['total_cost'] for y in matrix if y['total_cost'])
            total_demand = sum(y['demand_index_total'] for y in matrix if y['demand_index_total'])
            
            if total_demand == 0:
                stats = get_month_stats(month)
                return stats['avg']
            
            cost_per_demand = total_cost / total_demand
            
            # Estimate: demand * cost_per_demand * scaling factor
            # The monthly demand is an average daily value, multiply by days in month
            days_in_month = monthrange(curr_year, month)[1]
            forecast = month_demand * cost_per_demand * days_in_month / 30  # Normalize
            
            # Sanity check - if forecast is wildly different from avg, blend it
            stats = get_month_stats(month)
            if stats['avg'] > 0:
                # Blend 70% forecast, 30% historical average
                forecast = forecast * 0.7 + stats['avg'] * 0.3
            
            return forecast
        
        # Build result
        prev_stats = get_month_stats(prev_month)
        curr_stats = get_month_stats(curr_month)
        next_stats = get_month_stats(next_month)
        
        return {
            'previous_month': {
                'month': prev_month,
                'year': prev_year,
                'label': f"{month_names[prev_month]} {prev_year}",
                'value': get_actual_cost(prev_year, prev_month),
                'is_actual': True,
                **prev_stats
            },
            'this_month': {
                'month': curr_month,
                'year': curr_year,
                'label': f"{month_names[curr_month]} {curr_year}",
                'value': get_forecast_cost(curr_month),
                'is_actual': False,
                **curr_stats
            },
            'next_month': {
                'month': next_month,
                'year': next_year,
                'label': f"{month_names[next_month]} {next_year}",
                'value': get_forecast_cost(next_month),
                'is_actual': False,
                **next_stats
            },
        }
    
    def get_weather_stats(self) -> Dict:
        """Get weather statistics for dashboard display with tooltip data."""
        today = date.today()
        current_year = today.year
        last_year = current_year - 1
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get current year stats
            cursor.execute('''
                SELECT 
                    MAX(temp_high) as max_temp,
                    MIN(temp_low) as min_temp,
                    SUM(rain_total) as total_rain
                FROM weather_daily
                WHERE strftime('%Y', date) = ?
            ''', (str(current_year),))
            current = cursor.fetchone()
            
            # Get last year stats
            cursor.execute('''
                SELECT 
                    MAX(temp_high) as max_temp,
                    MIN(temp_low) as min_temp,
                    SUM(rain_total) as total_rain
                FROM weather_daily
                WHERE strftime('%Y', date) = ?
            ''', (str(last_year),))
            last_yr = cursor.fetchone()
            
            # Get all-time stats
            cursor.execute('''
                SELECT 
                    MAX(temp_high) as max_temp,
                    MIN(temp_low) as min_temp
                FROM weather_daily
            ''')
            all_time = cursor.fetchone()
            
            # Get yearly max temps for average calculation
            cursor.execute('''
                SELECT strftime('%Y', date) as year, MAX(temp_high) as max_temp
                FROM weather_daily
                GROUP BY strftime('%Y', date)
            ''')
            yearly_maxes = [r['max_temp'] for r in cursor.fetchall() if r['max_temp']]
            avg_max = sum(yearly_maxes) / len(yearly_maxes) if yearly_maxes else 0
            
            # Get yearly min temps for average calculation
            cursor.execute('''
                SELECT strftime('%Y', date) as year, MIN(temp_low) as min_temp
                FROM weather_daily
                GROUP BY strftime('%Y', date)
            ''')
            yearly_mins = [r['min_temp'] for r in cursor.fetchall() if r['min_temp']]
            avg_min = sum(yearly_mins) / len(yearly_mins) if yearly_mins else 0
            
            # Get yearly rainfall totals for stats
            cursor.execute('''
                SELECT strftime('%Y', date) as year, SUM(rain_total) as total_rain
                FROM weather_daily
                GROUP BY strftime('%Y', date)
            ''')
            yearly_rain = [r['total_rain'] for r in cursor.fetchall() if r['total_rain']]
            avg_rain = sum(yearly_rain) / len(yearly_rain) if yearly_rain else 0
            all_time_rain = max(yearly_rain) if yearly_rain else 0
            
            return {
                'max_temp': {
                    'current': current['max_temp'] if current and current['max_temp'] else 0,
                    'last_year': last_yr['max_temp'] if last_yr and last_yr['max_temp'] else 0,
                    'all_time': all_time['max_temp'] if all_time and all_time['max_temp'] else 0,
                    'average': avg_max,
                },
                'min_temp': {
                    'current': current['min_temp'] if current and current['min_temp'] else 0,
                    'last_year': last_yr['min_temp'] if last_yr and last_yr['min_temp'] else 0,
                    'all_time': all_time['min_temp'] if all_time and all_time['min_temp'] else 0,
                    'average': avg_min,
                },
                'rainfall': {
                    'current': current['total_rain'] if current and current['total_rain'] else 0,
                    'last_year': last_yr['total_rain'] if last_yr and last_yr['total_rain'] else 0,
                    'all_time': all_time_rain,
                    'average': avg_rain,
                },
            }
    
    def get_yearly_summary(self) -> List[Dict]:
        """Get yearly summary statistics."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    year,
                    SUM(electric_cost) as total_electric,
                    SUM(gas_cost) as total_gas,
                    SUM(water_cost) as total_water,
                    SUM(total_cost) as grand_total,
                    AVG(total_cost) as avg_monthly,
                    SUM(electric_usage) as total_kwh,
                    SUM(gas_usage) as total_therms,
                    SUM(water_usage) as total_gallons
                FROM yearly_costs
                GROUP BY year
                ORDER BY year DESC
            ''')
            return [dict(row) for row in cursor.fetchall()]
    
    def get_current_month_stats(self) -> Dict:
        """Get statistics for the current billing period."""
        today = date.today()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get latest bills
            cursor.execute('SELECT total_cost, usage_kwh, days FROM electric_bills ORDER BY bill_date DESC LIMIT 1')
            elec = cursor.fetchone()
            
            cursor.execute('SELECT total_cost, therms, days FROM gas_bills ORDER BY bill_date DESC LIMIT 1')
            gas = cursor.fetchone()
            
            cursor.execute('SELECT total_cost, usage_gallons, gallons_per_day FROM water_bills ORDER BY bill_date DESC LIMIT 1')
            water = cursor.fetchone()
            
            # Get weather stats for current year
            cursor.execute('''
                SELECT 
                    MAX(temp_high) as max_temp,
                    MIN(temp_low) as min_temp,
                    SUM(rain_total) as total_rain
                FROM weather_daily
                WHERE strftime('%Y', date) = ?
            ''', (str(today.year),))
            weather = cursor.fetchone()
            
            return {
                'electric': dict(elec) if elec else {},
                'gas': dict(gas) if gas else {},
                'water': dict(water) if water else {},
                'weather': dict(weather) if weather else {},
                'total_cost': (
                    (elec['total_cost'] if elec else 0) +
                    (gas['total_cost'] if gas else 0) +
                    (water['total_cost'] if water else 0)
                )
            }
    
    def update_yearly_costs(self):
        """Rebuild the yearly_costs summary table from bill data."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Clear existing data
            cursor.execute('DELETE FROM yearly_costs')
            
            # Get all unique year/month combinations from all bills
            cursor.execute('''
                SELECT DISTINCT year, month FROM (
                    SELECT 
                        CAST(strftime('%Y', bill_date) AS INTEGER) as year,
                        CAST(strftime('%m', bill_date) AS INTEGER) as month
                    FROM electric_bills
                    UNION
                    SELECT 
                        CAST(strftime('%Y', bill_date) AS INTEGER) as year,
                        CAST(strftime('%m', bill_date) AS INTEGER) as month
                    FROM gas_bills
                    UNION
                    SELECT 
                        CAST(strftime('%Y', bill_date) AS INTEGER) as year,
                        CAST(strftime('%m', bill_date) AS INTEGER) as month
                    FROM water_bills
                )
                ORDER BY year, month
            ''')
            
            year_months = cursor.fetchall()
            
            for row in year_months:
                year, month = row['year'], row['month']
                
                # Get electric data for this month
                cursor.execute('''
                    SELECT total_cost, usage_kwh FROM electric_bills
                    WHERE CAST(strftime('%Y', bill_date) AS INTEGER) = ?
                    AND CAST(strftime('%m', bill_date) AS INTEGER) = ?
                ''', (year, month))
                elec = cursor.fetchone()
                elec_cost = elec['total_cost'] if elec else 0
                elec_usage = elec['usage_kwh'] if elec else 0
                
                # Get gas data for this month
                cursor.execute('''
                    SELECT total_cost, therms FROM gas_bills
                    WHERE CAST(strftime('%Y', bill_date) AS INTEGER) = ?
                    AND CAST(strftime('%m', bill_date) AS INTEGER) = ?
                ''', (year, month))
                gas = cursor.fetchone()
                gas_cost = gas['total_cost'] if gas else 0
                gas_usage = gas['therms'] if gas else 0
                
                # Get water data for this month
                cursor.execute('''
                    SELECT total_cost, usage_gallons FROM water_bills
                    WHERE CAST(strftime('%Y', bill_date) AS INTEGER) = ?
                    AND CAST(strftime('%m', bill_date) AS INTEGER) = ?
                ''', (year, month))
                water = cursor.fetchone()
                water_cost = water['total_cost'] if water else 0
                water_usage = water['usage_gallons'] if water else 0
                
                # Insert combined record
                total = (elec_cost or 0) + (gas_cost or 0) + (water_cost or 0)
                cursor.execute('''
                    INSERT INTO yearly_costs 
                    (year, month, electric_cost, gas_cost, water_cost, total_cost,
                     electric_usage, gas_usage, water_usage)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (year, month, elec_cost, gas_cost, water_cost, total,
                      elec_usage, gas_usage, water_usage))

    # ==================== Meter Reading Operations ====================
    
    def add_meter_reading(self, utility_type: str, reading_value: float, reading_date: date = None) -> int:
        """Add a new meter reading."""
        if reading_date is None:
            reading_date = date.today()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO meter_readings (utility_type, reading_date, reading_value)
                VALUES (?, ?, ?)
            ''', (utility_type, reading_date, reading_value))
            return cursor.lastrowid
    
    def get_last_meter_reading(self, utility_type: str) -> Optional[Dict]:
        """Get the most recent meter reading for a utility type."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM meter_readings 
                WHERE utility_type = ?
                ORDER BY reading_date DESC, id DESC
                LIMIT 1
            ''', (utility_type,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_meter_readings(self, utility_type: str, limit: int = 10) -> List[Dict]:
        """Get recent meter readings for a utility type."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM meter_readings 
                WHERE utility_type = ?
                ORDER BY reading_date DESC, id DESC
                LIMIT ?
            ''', (utility_type, limit))
            return [dict(row) for row in cursor.fetchall()]

    # ==================== Weather Statistics ====================
    
    def get_performance_stats(self) -> Dict:
        """Get performance statistics for dashboard."""
        from datetime import datetime
        
        stats = {
            'ytd': 0,
            'last_year': 0,
            'average': 0,
            'cost_per_sqft': 0,
            'cost_per_day': 0,
        }
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Find the most recent year with utility data
            cursor.execute('''
                SELECT DISTINCT year FROM (
                    SELECT strftime('%Y', bill_date) as year FROM electric_bills
                    UNION
                    SELECT strftime('%Y', bill_date) as year FROM gas_bills
                    UNION
                    SELECT strftime('%Y', bill_date) as year FROM water_bills
                )
                ORDER BY year DESC LIMIT 2
            ''')
            years = [row['year'] for row in cursor.fetchall()]
            current_year = years[0] if years else str(datetime.now().year)
            last_year = years[1] if len(years) > 1 else str(int(current_year) - 1)
            
            # Get the last date in the current year to calculate days elapsed
            cursor.execute('''
                SELECT MAX(bill_date) as last_date FROM (
                    SELECT bill_date FROM electric_bills WHERE strftime('%Y', bill_date) = ?
                    UNION
                    SELECT bill_date FROM gas_bills WHERE strftime('%Y', bill_date) = ?
                    UNION
                    SELECT bill_date FROM water_bills WHERE strftime('%Y', bill_date) = ?
                )
            ''', (current_year, current_year, current_year))
            row = cursor.fetchone()
            last_date_str = row['last_date'] if row else None
            
            if last_date_str:
                try:
                    last_date = datetime.strptime(last_date_str, '%Y-%m-%d').date()
                    first_of_year = date(int(current_year), 1, 1)
                    days_elapsed = (last_date - first_of_year).days + 1
                except:
                    days_elapsed = datetime.now().timetuple().tm_yday
            else:
                days_elapsed = datetime.now().timetuple().tm_yday
            
            # YTD total (current year)
            cursor.execute('''
                SELECT 
                    COALESCE((SELECT SUM(total_cost) FROM electric_bills WHERE strftime('%Y', bill_date) = ?), 0) +
                    COALESCE((SELECT SUM(total_cost) FROM gas_bills WHERE strftime('%Y', bill_date) = ?), 0) +
                    COALESCE((SELECT SUM(total_cost) FROM water_bills WHERE strftime('%Y', bill_date) = ?), 0) as total
            ''', (current_year, current_year, current_year))
            row = cursor.fetchone()
            stats['ytd'] = row['total'] if row else 0
            
            # Last year total
            cursor.execute('''
                SELECT 
                    COALESCE((SELECT SUM(total_cost) FROM electric_bills WHERE strftime('%Y', bill_date) = ?), 0) +
                    COALESCE((SELECT SUM(total_cost) FROM gas_bills WHERE strftime('%Y', bill_date) = ?), 0) +
                    COALESCE((SELECT SUM(total_cost) FROM water_bills WHERE strftime('%Y', bill_date) = ?), 0) as total
            ''', (last_year, last_year, last_year))
            row = cursor.fetchone()
            stats['last_year'] = row['total'] if row else 0
            
            # Average annual total
            cursor.execute('''
                SELECT AVG(yearly_total) as avg FROM (
                    SELECT strftime('%Y', bill_date) as year, SUM(total_cost) as yearly_total 
                    FROM (
                        SELECT bill_date, total_cost FROM electric_bills
                        UNION ALL
                        SELECT bill_date, total_cost FROM gas_bills
                        UNION ALL
                        SELECT bill_date, total_cost FROM water_bills
                    )
                    GROUP BY year
                )
            ''')
            row = cursor.fetchone()
            stats['average'] = row['avg'] if row and row['avg'] else 0
            
            # Get home sqft for cost per sqft calc
            sqft = float(self.get_config('home_sqft') or 1730)
            stats['cost_per_sqft'] = stats['ytd'] / sqft if sqft > 0 else 0
            
            # Cost per day (YTD / days elapsed)
            stats['cost_per_day'] = stats['ytd'] / days_elapsed if days_elapsed > 0 else 0
        
        return stats
    
    def get_cpd_sqft_tooltip_stats(self) -> Dict:
        """Get $/Day and $/SqFt statistics for tooltips: min, max, avg."""
        sqft = float(self.get_config('home_sqft') or 1730)
        
        result = {
            'cpd': {'min': 0, 'max': 0, 'avg': 0},
            'sqft': {'min': 0, 'max': 0, 'avg': 0},
        }
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get yearly totals and days for each year
            cursor.execute('''
                SELECT 
                    year,
                    SUM(total_cost) as total,
                    COUNT(*) * 30 as approx_days
                FROM yearly_costs
                GROUP BY year
                HAVING SUM(total_cost) > 0
            ''')
            rows = cursor.fetchall()
            
            if rows:
                cpd_values = []
                sqft_values = []
                
                for row in rows:
                    yearly_total = row['total'] or 0
                    # Use approximate days (months * 30) or actual days in year
                    days = row['approx_days'] or 365
                    
                    if days > 0 and yearly_total > 0:
                        cpd = yearly_total / days
                        cpd_values.append(cpd)
                        
                        if sqft > 0:
                            sqft_values.append(yearly_total / sqft)
                
                if cpd_values:
                    result['cpd']['min'] = min(cpd_values)
                    result['cpd']['max'] = max(cpd_values)
                    result['cpd']['avg'] = sum(cpd_values) / len(cpd_values)
                
                if sqft_values:
                    result['sqft']['min'] = min(sqft_values)
                    result['sqft']['max'] = max(sqft_values)
                    result['sqft']['avg'] = sum(sqft_values) / len(sqft_values)
        
        return result

    def get_current_utility_costs(self) -> Dict:
        """Get most recent bill costs for each utility."""
        costs = {
            'electric': 0,
            'gas': 0,
            'water': 0,
            'total': 0,
        }
        
        elec = self.get_latest_electric_bill()
        if elec:
            costs['electric'] = elec.get('total_cost', 0) or 0
        
        gas = self.get_latest_gas_bill()
        if gas:
            costs['gas'] = gas.get('total_cost', 0) or 0
        
        water = self.get_latest_water_bill()
        if water:
            costs['water'] = water.get('total_cost', 0) or 0
        
        costs['total'] = costs['electric'] + costs['gas'] + costs['water']
        return costs

    # ==================== Performance Stats for Dashboard ====================
    
    def get_usage_per_day_stats(self, utility_type: str) -> Dict:
        """Get usage per day stats: last_month, average, min, max."""
        # Electric and gas have usage/days columns, water has gallons_per_day directly
        table_map = {
            'kwh_day': ('electric_bills', 'usage_kwh', 'days', 'kWh'),
            'thm_day': ('gas_bills', 'therms', 'days', 'thm'),
            'gal_day': ('water_bills', 'gallons_per_day', None, 'gal'),  # Direct column
        }
        
        if utility_type not in table_map:
            return {'last_month': 0, 'average': 0, 'min': 0, 'max': 0, 'unit': '', 'current': 0}
        
        table, usage_col, days_col, unit = table_map[utility_type]
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get all usage per day values
            if days_col:
                # Calculate per day from usage/days
                cursor.execute(f'''
                    SELECT {usage_col} * 1.0 / {days_col} as per_day
                    FROM {table}
                    WHERE {days_col} > 0
                    ORDER BY bill_date DESC
                ''')
            else:
                # Use direct per_day column
                cursor.execute(f'''
                    SELECT {usage_col} as per_day
                    FROM {table}
                    WHERE {usage_col} IS NOT NULL AND {usage_col} > 0
                    ORDER BY bill_date DESC
                ''')
            rows = cursor.fetchall()
            
            if not rows:
                return {'last_month': 0, 'average': 0, 'min': 0, 'max': 0, 'unit': unit, 'current': 0}
            
            values = [r['per_day'] for r in rows if r['per_day']]
            
            # Current month (most recent)
            current = values[0] if values else 0
            
            # Last month (second most recent)
            last_month = values[1] if len(values) > 1 else current
            
            # Stats
            avg = sum(values) / len(values) if values else 0
            min_val = min(values) if values else 0
            max_val = max(values) if values else 0
            
            return {
                'current': current,
                'last_month': last_month,
                'average': avg,
                'min': min_val,
                'max': max_val,
                'unit': unit,
            }
    
    def get_cost_stats(self, stat_type: str) -> Dict:
        """Get cost stats: last_year, average, min, max for cost/day, $/sqft, ytd."""
        current_year = date.today().year
        last_year = current_year - 1
        sqft = float(self.get_config('home_sqft') or 1730)
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get yearly totals from electric and gas (which have days column)
            # Water is excluded from days calculation since it doesn't have that column
            cursor.execute('''
                SELECT 
                    year,
                    SUM(total) as total,
                    SUM(days) as days
                FROM (
                    SELECT strftime('%Y', bill_date) as year, total_cost as total, days FROM electric_bills
                    UNION ALL
                    SELECT strftime('%Y', bill_date) as year, total_cost as total, days FROM gas_bills
                )
                GROUP BY year
                ORDER BY year DESC
            ''')
            elec_gas_rows = cursor.fetchall()
            
            # Get water yearly totals separately
            cursor.execute('''
                SELECT strftime('%Y', bill_date) as year, SUM(total_cost) as total
                FROM water_bills
                GROUP BY year
            ''')
            water_rows = cursor.fetchall()
            water_by_year = {r['year']: r['total'] or 0 for r in water_rows}
            
            if not elec_gas_rows:
                return {'current': 0, 'last_year': 0, 'average': 0, 'min': 0, 'max': 0, 'unit': ''}
            
            # Combine data - add water totals to combined totals
            yearly_data = {}
            for r in elec_gas_rows:
                year = r['year']
                yearly_data[year] = {
                    'total': (r['total'] or 0) + water_by_year.get(year, 0),
                    'days': r['days'] or 365
                }
            
            if stat_type == 'cost_day':
                # Cost per day
                values = [(d['total'] / d['days']) if d['days'] > 0 else 0 for d in yearly_data.values()]
                current_data = yearly_data.get(str(current_year), {'total': 0, 'days': 1})
                current = current_data['total'] / current_data['days'] if current_data['days'] > 0 else 0
                last_data = yearly_data.get(str(last_year), {'total': 0, 'days': 1})
                last_yr = last_data['total'] / last_data['days'] if last_data['days'] > 0 else 0
                unit = '$/day'
                
            elif stat_type == 'cost_sqft':
                # Cost per sqft (based on YTD total)
                values = [(d['total'] / sqft) if sqft > 0 else 0 for d in yearly_data.values()]
                current = yearly_data.get(str(current_year), {'total': 0})['total'] / sqft if sqft > 0 else 0
                last_yr = yearly_data.get(str(last_year), {'total': 0})['total'] / sqft if sqft > 0 else 0
                unit = '$/sqft'
                
            elif stat_type == 'ytd_total':
                # YTD totals by year
                values = [d['total'] for d in yearly_data.values()]
                current = yearly_data.get(str(current_year), {'total': 0})['total']
                last_yr = yearly_data.get(str(last_year), {'total': 0})['total']
                unit = '$'
                
            else:
                return {'current': 0, 'last_year': 0, 'average': 0, 'min': 0, 'max': 0, 'unit': ''}
            
            avg = sum(values) / len(values) if values else 0
            min_val = min(values) if values else 0
            max_val = max(values) if values else 0
            
            return {
                'current': current,
                'last_year': last_yr,
                'average': avg,
                'min': min_val,
                'max': max_val,
                'unit': unit,
            }
    
    def get_blended_demand(self, year: int = None) -> Dict:
        """
        Calculate blended demand projection combining YTD actuals with historical averages.
        
        Formula: Blended = M² × YTD + (1 - M) × Historical_Avg
        
        Where M = current_month / 12
        
        This gives more weight to historical data early in the year when YTD
        data is sparse, then transitions to actual data as the year progresses.
        If YTD has no data (YTD=0), the formula naturally weights toward historical.
        
        Args:
            year: Year to calculate for (defaults to current year)
        
        Returns:
            Dict with blended cooling, heating, total demand, and weights used
        """
        from datetime import date
        
        if year is None:
            year = date.today().year
        
        current_month = date.today().month
        m = current_month / 12  # Month fraction
        m_squared = m * m  # Weight for YTD
        hist_weight = 1 - m  # Weight for historical
        
        # Get historical averages from demand matrix (all previous years)
        matrix = self.get_demand_matrix()
        
        # Calculate historical averages (excluding current year)
        hist_cooling = []
        hist_heating = []
        hist_total = []
        
        for row in matrix:
            if row['year'] < year:
                hist_cooling.append(row['avg_cooling'])
                hist_heating.append(row['avg_heating'])
                hist_total.append(row['total_demand'])
        
        avg_cooling = sum(hist_cooling) / len(hist_cooling) if hist_cooling else 0
        avg_heating = sum(hist_heating) / len(hist_heating) if hist_heating else 0
        avg_total = sum(hist_total) / len(hist_total) if hist_total else 0
        
        # Get YTD actuals for the current year (will be 0 if no data yet)
        ytd_cooling = 0
        ytd_heating = 0
        ytd_total = 0
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get YTD averages from weather_daily for current year
            cursor.execute('''
                SELECT 
                    AVG(cooling_demand) as avg_cooling,
                    AVG(heating_demand) as avg_heating,
                    COUNT(*) as days
                FROM weather_daily
                WHERE strftime('%Y', date) = ?
            ''', (str(year),))
            
            row = cursor.fetchone()
            if row and row['days'] > 0:
                ytd_cooling = row['avg_cooling'] or 0
                ytd_heating = row['avg_heating'] or 0
                ytd_total = ytd_cooling + abs(ytd_heating)
        
        # Apply blended formula: M² × YTD + (1 - M) × Avg
        # If YTD is 0 (no data), this naturally gives ~(1-M) weight to historical
        blended_cooling = m_squared * ytd_cooling + hist_weight * avg_cooling
        blended_heating = m_squared * ytd_heating + hist_weight * avg_heating
        blended_total = m_squared * ytd_total + hist_weight * avg_total
        
        return {
            'year': year,
            'blended_cooling': blended_cooling,
            'blended_heating': blended_heating,
            'blended_total': blended_total,
            'ytd_cooling': ytd_cooling,
            'ytd_heating': ytd_heating,
            'ytd_total': ytd_total,
            'avg_cooling': avg_cooling,
            'avg_heating': avg_heating,
            'avg_total': avg_total,
            'month': current_month,
            'month_fraction': m,
            'ytd_weight': m_squared,
            'hist_weight': hist_weight,
        }

    def get_current_demand_stats(self) -> Dict:
        """Get current year demand stats for dashboard using blended projection."""
        current_year = date.today().year
        matrix = self.get_demand_matrix()
        k_factor = float(self.get_config('k_factor') or 2.25)
        
        # Get blended demand projection
        blended = self.get_blended_demand(current_year)
        
        # Get the historical average total demand for comparison
        avg_total_demand = blended['avg_total']
        
        # Calculate demand % using blended total vs historical average
        if avg_total_demand > 0:
            demand_pct = (blended['blended_total'] - avg_total_demand) / avg_total_demand
        else:
            demand_pct = 0
        
        # Calculate Expected CPD% using K-th root transformation on blended demand
        expected_cpd_pct = self._calc_expected_cpd_pct(demand_pct, k_factor)
        
        # Get actual CPD% - use current year if bills exist, otherwise use previous year
        actual_cpd_pct = 0
        current_year_has_bills = False
        
        # Check if current year has any bills
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) as count FROM (
                    SELECT 1 FROM electric_bills WHERE strftime('%Y', bill_date) = ?
                    UNION ALL
                    SELECT 1 FROM gas_bills WHERE strftime('%Y', bill_date) = ?
                    UNION ALL
                    SELECT 1 FROM water_bills WHERE strftime('%Y', bill_date) = ?
                )
            ''', (str(current_year), str(current_year), str(current_year)))
            row = cursor.fetchone()
            current_year_has_bills = row['count'] > 0 if row else False
        
        # Find actual CPD% from current year or fall back to previous year
        for row in sorted(matrix, key=lambda x: x['year'], reverse=True):
            if row['year'] == current_year and current_year_has_bills:
                actual_cpd_pct = row['pct_avg_cost']
                break
            elif row['year'] < current_year:
                # Use most recent previous year with data
                actual_cpd_pct = row['pct_avg_cost']
                break
        
        return {
            'actual_cpd': actual_cpd_pct * 100,  # % above/below avg cost
            'expected_cpd': expected_cpd_pct * 100,  # K-root transformed expected %
            'demand_pct': blended['blended_total'] * 100,  # Blended total demand %
            'ytd_weight': blended['ytd_weight'] * 100,  # YTD weight %
            'hist_weight': blended['hist_weight'] * 100,  # Historical weight %
        }
    
    def _calc_expected_cpd_pct(self, demand_pct: float, k_factor: float) -> float:
        """
        Calculate Expected CPD% using K-th root transformation.
        
        Formula: sign(diff) × (|diff × 100|^(1/K)) / 100
        
        This non-linear transformation compresses large deviations:
        - Small demand changes have relatively larger expected cost impact
        - Large demand swings are dampened
        
        Args:
            demand_pct: Linear demand % as decimal (e.g., 0.05 for 5%)
            k_factor: K factor for root transformation (default 2.25)
        
        Returns:
            Expected CPD% as decimal
        """
        import math
        
        if demand_pct == 0 or k_factor == 0:
            return 0
        
        sign = 1 if demand_pct > 0 else -1
        abs_pct = abs(demand_pct) * 100  # Convert to whole number %
        power_result = math.pow(abs_pct, 1 / k_factor)  # K-th root
        return sign * power_result / 100  # Convert back to decimal

    def get_current_performance(self) -> Dict:
        """Get current performance stats for dashboard display."""
        current_year = date.today().year
        
        # Get usage per day stats
        kwh_stats = self.get_usage_per_day_stats('kwh_day')
        thm_stats = self.get_usage_per_day_stats('thm_day')
        gal_stats = self.get_usage_per_day_stats('gal_day')
        
        # Get cost stats
        cpd_stats = self.get_cost_stats('cost_day')
        sqft_stats = self.get_cost_stats('cost_sqft')
        ytd_stats = self.get_cost_stats('ytd_total')
        
        # Get demand stats
        demand_stats = self.get_current_demand_stats()
        
        return {
            'kwh_day': kwh_stats['current'],
            'thm_day': thm_stats['current'],
            'gal_day': gal_stats['current'],
            'cost_day': cpd_stats['current'],
            'cost_sqft': sqft_stats['current'],
            'ytd_total': ytd_stats['current'],
            'actual_cpd_pct': demand_stats['actual_cpd'],
            'expected_cpd_pct': demand_stats['expected_cpd'],
            'demand_pct': demand_stats['demand_pct'],
        }

    # ==================== Demand Matrix Calculations ====================
    
    def get_demand_matrix(self) -> List[Dict]:
        """Calculate demand matrix data for all years with data."""
        # Get temperature range settings
        heating_min = float(self.get_config('heating_min_temp') or 15)
        heating_max = float(self.get_config('heating_max_temp') or 54)
        cooling_min = float(self.get_config('cooling_min_temp') or 78)
        cooling_max = float(self.get_config('cooling_max_temp') or 96)
        
        results = []
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get all years with weather data
            cursor.execute('''
                SELECT DISTINCT strftime('%Y', date) as year 
                FROM weather_daily 
                ORDER BY year
            ''')
            years = [row['year'] for row in cursor.fetchall()]
            
            # Calculate for each year
            all_cpd = []  # Collect all CPD values for average
            all_demand = []  # Collect all demand values for average
            
            for year in years:
                # Get weather data for this year
                cursor.execute('''
                    SELECT date, temp_high, temp_low, cooling_demand, heating_demand
                    FROM weather_daily
                    WHERE strftime('%Y', date) = ?
                ''', (year,))
                weather_days = cursor.fetchall()
                
                if not weather_days:
                    continue
                
                # Calculate demand stats
                cooling_days = 0
                heating_days = 0
                econ_days = 0
                total_cooling = 0
                total_heating = 0
                
                for day in weather_days:
                    cool = day['cooling_demand'] or 0
                    heat = day['heating_demand'] or 0
                    
                    if cool > 0:
                        cooling_days += 1
                        total_cooling += cool
                    elif heat < 0:
                        heating_days += 1
                        total_heating += heat
                    else:
                        econ_days += 1
                
                num_days = len(weather_days)
                avg_cooling = total_cooling / num_days if num_days > 0 else 0
                avg_heating = total_heating / num_days if num_days > 0 else 0
                total_demand = abs(avg_heating) + avg_cooling
                
                # Calculate demand index
                demand_index_clg = avg_cooling * cooling_days
                demand_index_htg = abs(avg_heating) * heating_days
                demand_index_total = demand_index_clg + demand_index_htg
                
                # Get total costs for this year
                cursor.execute('''
                    SELECT 
                        COALESCE((SELECT SUM(total_cost) FROM electric_bills WHERE strftime('%Y', bill_date) = ?), 0) +
                        COALESCE((SELECT SUM(total_cost) FROM gas_bills WHERE strftime('%Y', bill_date) = ?), 0) +
                        COALESCE((SELECT SUM(total_cost) FROM water_bills WHERE strftime('%Y', bill_date) = ?), 0) as total
                ''', (year, year, year))
                row = cursor.fetchone()
                total_cost = row['total'] if row else 0
                
                # Cost per day
                cpd = total_cost / num_days if num_days > 0 else 0
                
                # Get rainfall for the year
                cursor.execute('''
                    SELECT SUM(rain_total) as total_rain
                    FROM weather_daily
                    WHERE strftime('%Y', date) = ?
                ''', (year,))
                row = cursor.fetchone()
                rainfall = row['total_rain'] if row and row['total_rain'] else 0
                
                results.append({
                    'year': int(year),
                    'avg_cooling': avg_cooling,
                    'avg_heating': avg_heating,
                    'total_demand': total_demand,
                    'cooling_days': cooling_days,
                    'heating_days': heating_days,
                    'econ_days': econ_days,
                    'num_days': num_days,
                    'demand_index_clg': demand_index_clg,
                    'demand_index_htg': demand_index_htg,
                    'demand_index_total': demand_index_total,
                    'total_cost': total_cost,
                    'cost_per_day': cpd,
                    'rainfall': rainfall,
                })
                
                if cpd > 0:
                    all_cpd.append(cpd)
                if total_demand > 0:
                    all_demand.append(total_demand)
            
            # Calculate averages
            avg_cpd = sum(all_cpd) / len(all_cpd) if all_cpd else 0
            avg_demand = sum(all_demand) / len(all_demand) if all_demand else 0
            k_factor = float(self.get_config('k_factor') or 2.25)
            
            # Add percentage of average calculations
            for r in results:
                if avg_cpd > 0:
                    r['pct_avg_cost'] = (r['cost_per_day'] - avg_cpd) / avg_cpd
                else:
                    r['pct_avg_cost'] = 0
                    
                if avg_demand > 0:
                    r['pct_avg_demand'] = (r['total_demand'] - avg_demand) / avg_demand
                else:
                    r['pct_avg_demand'] = 0
                
                # Calculate Expected CPD% using K-th root transformation
                r['expected_cpd_pct'] = self._calc_expected_cpd_pct(r['pct_avg_demand'], k_factor)
            
            # Store averages in results
            for r in results:
                r['avg_cpd'] = avg_cpd
                r['avg_total_demand'] = avg_demand
                r['k_factor'] = k_factor
        
        return results
    
    def get_demand_settings(self) -> Dict:
        """Get demand calculation settings."""
        return {
            'heating_min_temp': float(self.get_config('heating_min_temp') or 15),
            'heating_max_temp': float(self.get_config('heating_max_temp') or 54),
            'cooling_min_temp': float(self.get_config('cooling_min_temp') or 78),
            'cooling_max_temp': float(self.get_config('cooling_max_temp') or 96),
            'k_factor': float(self.get_config('k_factor') or 2.25),
        }
    
    def set_demand_settings(self, settings: Dict):
        """Save demand calculation settings."""
        self.set_config('heating_min_temp', str(settings.get('heating_min_temp', 15)))
        self.set_config('heating_max_temp', str(settings.get('heating_max_temp', 54)))
        self.set_config('cooling_min_temp', str(settings.get('cooling_min_temp', 78)))
        self.set_config('cooling_max_temp', str(settings.get('cooling_max_temp', 96)))
        self.set_config('k_factor', str(settings.get('k_factor', 2.25)))

    def get_demand_monthly(self) -> Dict:
        """Calculate monthly demand averages for each year."""
        results = {
            'years': [],
            'months': list(range(1, 13)),
            'data': {},  # year -> [12 monthly values]
            'averages': [0] * 12,  # Average for each month across all years
        }
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get all years with weather data
            cursor.execute('''
                SELECT DISTINCT strftime('%Y', date) as year 
                FROM weather_daily 
                ORDER BY year
            ''')
            years = [row['year'] for row in cursor.fetchall()]
            results['years'] = [int(y) for y in years]
            
            # For each year, calculate monthly demand
            monthly_totals = [[] for _ in range(12)]  # Collect values for averaging
            
            for year in years:
                year_data = [0] * 12
                
                for month in range(1, 13):
                    cursor.execute('''
                        SELECT AVG(max_demand) as avg_demand
                        FROM weather_daily
                        WHERE strftime('%Y', date) = ?
                        AND strftime('%m', date) = ?
                    ''', (year, f'{month:02d}'))
                    row = cursor.fetchone()
                    
                    if row and row['avg_demand'] is not None:
                        demand = row['avg_demand']
                        year_data[month - 1] = demand
                        monthly_totals[month - 1].append(demand)
                
                results['data'][int(year)] = year_data
            
            # Calculate averages
            for i in range(12):
                if monthly_totals[i]:
                    results['averages'][i] = sum(monthly_totals[i]) / len(monthly_totals[i])
        
        return results

    def get_demand_daily(self) -> Dict:
        """Calculate daily demand for each day of year by year."""
        results = {
            'years': [],
            'days': list(range(1, 367)),  # Day of year 1-366
            'data': {},  # year -> [366 daily values]
            'averages': [0] * 366,  # Average for each day across all years
        }
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get all years with weather data
            cursor.execute('''
                SELECT DISTINCT strftime('%Y', date) as year 
                FROM weather_daily 
                ORDER BY year
            ''')
            years = [row['year'] for row in cursor.fetchall()]
            results['years'] = [int(y) for y in years]
            
            # For each year, get daily demand by day of year
            daily_totals = [[] for _ in range(366)]  # Collect values for averaging
            
            for year in years:
                year_data = [None] * 366  # Use None for missing days
                
                cursor.execute('''
                    SELECT 
                        CAST(strftime('%j', date) AS INTEGER) as day_of_year,
                        max_demand
                    FROM weather_daily
                    WHERE strftime('%Y', date) = ?
                    ORDER BY date
                ''', (year,))
                
                for row in cursor.fetchall():
                    doy = row['day_of_year'] - 1  # 0-indexed
                    demand = row['max_demand'] or 0
                    if 0 <= doy < 366:
                        year_data[doy] = demand
                        daily_totals[doy].append(demand)
                
                results['data'][int(year)] = year_data
            
            # Calculate averages
            for i in range(366):
                if daily_totals[i]:
                    results['averages'][i] = sum(daily_totals[i]) / len(daily_totals[i])
        
        return results

    def get_monthly_rainfall(self) -> Dict:
        """Get monthly rainfall data by year."""
        results = {
            'years': [],
            'months': list(range(1, 13)),
            'data': {},  # year -> [12 monthly values]
            'averages': [0] * 12,  # Average for each month across all years
        }
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get all years with weather data
            cursor.execute('''
                SELECT DISTINCT strftime('%Y', date) as year 
                FROM weather_daily 
                WHERE rain_total IS NOT NULL
                ORDER BY year
            ''')
            years = [row['year'] for row in cursor.fetchall()]
            results['years'] = [int(y) for y in years]
            
            # For each year, calculate monthly rainfall totals
            monthly_totals = [[] for _ in range(12)]  # Collect values for averaging
            
            for year in years:
                year_data = [0] * 12
                
                for month in range(1, 13):
                    cursor.execute('''
                        SELECT SUM(rain_total) as total_rain
                        FROM weather_daily
                        WHERE strftime('%Y', date) = ?
                        AND strftime('%m', date) = ?
                    ''', (year, f'{month:02d}'))
                    row = cursor.fetchone()
                    
                    if row and row['total_rain'] is not None:
                        rain = row['total_rain']
                        year_data[month - 1] = rain
                        monthly_totals[month - 1].append(rain)
                
                results['data'][int(year)] = year_data
            
            # Calculate averages
            for i in range(12):
                if monthly_totals[i]:
                    results['averages'][i] = sum(monthly_totals[i]) / len(monthly_totals[i])
        
        return results

    def get_usage_stats(self, utility_type: str) -> Dict:
        """Get usage statistics for a utility: last month, average, min, max."""
        stats = {
            'last_month': 0,
            'average': 0,
            'min': 0,
            'max': 0,
            'unit': '',
        }
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            if utility_type == 'electric':
                stats['unit'] = 'kWh'
                cursor.execute('''
                    SELECT usage_kwh, bill_date FROM electric_bills 
                    ORDER BY bill_date DESC
                ''')
                rows = cursor.fetchall()
                if rows:
                    usages = [r['usage_kwh'] for r in rows if r['usage_kwh']]
                    if usages:
                        stats['last_month'] = usages[0] if len(usages) > 0 else 0
                        stats['average'] = sum(usages) / len(usages)
                        stats['min'] = min(usages)
                        stats['max'] = max(usages)
                        
            elif utility_type == 'gas':
                stats['unit'] = 'thm'
                cursor.execute('''
                    SELECT therms, bill_date FROM gas_bills 
                    ORDER BY bill_date DESC
                ''')
                rows = cursor.fetchall()
                if rows:
                    usages = [r['therms'] for r in rows if r['therms']]
                    if usages:
                        stats['last_month'] = usages[0] if len(usages) > 0 else 0
                        stats['average'] = sum(usages) / len(usages)
                        stats['min'] = min(usages)
                        stats['max'] = max(usages)
                        
            elif utility_type == 'water':
                stats['unit'] = 'gal'
                cursor.execute('''
                    SELECT usage_gallons, bill_date FROM water_bills 
                    ORDER BY bill_date DESC
                ''')
                rows = cursor.fetchall()
                if rows:
                    usages = [r['usage_gallons'] for r in rows if r['usage_gallons']]
                    if usages:
                        stats['last_month'] = usages[0] if len(usages) > 0 else 0
                        stats['average'] = sum(usages) / len(usages)
                        stats['min'] = min(usages)
                        stats['max'] = max(usages)
        
        return stats

    def get_performance_tooltip_stats(self, stat_type: str) -> Dict:
        """Get performance statistics for tooltips: last year, average, min, max."""
        stats = {
            'last_year': 0,
            'average': 0,
            'min': 0,
            'max': 0,
            'unit': '',
        }
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            current_year = datetime.now().year
            last_year = current_year - 1
            
            if stat_type == 'kwh_day':
                stats['unit'] = 'kWh'
                # Get kWh per day for each year
                cursor.execute('''
                    SELECT strftime('%Y', bill_date) as year,
                           SUM(usage_kwh) as total_kwh,
                           SUM(days) as total_days
                    FROM electric_bills
                    GROUP BY strftime('%Y', bill_date)
                    ORDER BY year
                ''')
                rows = cursor.fetchall()
                values = []
                for r in rows:
                    if r['total_days'] and r['total_days'] > 0:
                        kwh_day = r['total_kwh'] / r['total_days']
                        values.append(kwh_day)
                        if int(r['year']) == last_year:
                            stats['last_year'] = kwh_day
                if values:
                    stats['average'] = sum(values) / len(values)
                    stats['min'] = min(values)
                    stats['max'] = max(values)
                    
            elif stat_type == 'thm_day':
                stats['unit'] = 'thm'
                cursor.execute('''
                    SELECT strftime('%Y', bill_date) as year,
                           SUM(therms) as total_therms,
                           SUM(days) as total_days
                    FROM gas_bills
                    GROUP BY strftime('%Y', bill_date)
                    ORDER BY year
                ''')
                rows = cursor.fetchall()
                values = []
                for r in rows:
                    if r['total_days'] and r['total_days'] > 0:
                        thm_day = r['total_therms'] / r['total_days']
                        values.append(thm_day)
                        if int(r['year']) == last_year:
                            stats['last_year'] = thm_day
                if values:
                    stats['average'] = sum(values) / len(values)
                    stats['min'] = min(values)
                    stats['max'] = max(values)
                    
            elif stat_type == 'gal_day':
                stats['unit'] = 'gal'
                cursor.execute('''
                    SELECT strftime('%Y', bill_date) as year,
                           AVG(gallons_per_day) as avg_gpd
                    FROM water_bills
                    GROUP BY strftime('%Y', bill_date)
                    ORDER BY year
                ''')
                rows = cursor.fetchall()
                values = []
                for r in rows:
                    if r['avg_gpd'] and r['avg_gpd'] > 0:
                        values.append(r['avg_gpd'])
                        if int(r['year']) == last_year:
                            stats['last_year'] = r['avg_gpd']
                if values:
                    stats['average'] = sum(values) / len(values)
                    stats['min'] = min(values)
                    stats['max'] = max(values)
                    
            elif stat_type == 'cost_day':
                stats['unit'] = '$'
                # Get from demand matrix which already has CPD by year
                matrix = self.get_demand_matrix()
                values = [r['cost_per_day'] for r in matrix if r['cost_per_day'] > 0]
                for r in matrix:
                    if r['year'] == last_year:
                        stats['last_year'] = r['cost_per_day']
                if values:
                    stats['average'] = sum(values) / len(values)
                    stats['min'] = min(values)
                    stats['max'] = max(values)
                    
            elif stat_type == 'cost_sqft':
                stats['unit'] = '$'
                sqft = float(self.get_config('square_footage') or 1800)
                cursor.execute('''
                    SELECT strftime('%Y', bill_date) as year, SUM(total_cost) as total
                    FROM (
                        SELECT bill_date, total_cost FROM electric_bills
                        UNION ALL SELECT bill_date, total_cost FROM gas_bills
                        UNION ALL SELECT bill_date, total_cost FROM water_bills
                    )
                    GROUP BY strftime('%Y', bill_date)
                    ORDER BY year
                ''')
                rows = cursor.fetchall()
                values = []
                for r in rows:
                    if r['total']:
                        cost_sqft = r['total'] / sqft
                        values.append(cost_sqft)
                        if int(r['year']) == last_year:
                            stats['last_year'] = cost_sqft
                if values:
                    stats['average'] = sum(values) / len(values)
                    stats['min'] = min(values)
                    stats['max'] = max(values)
                    
            elif stat_type == 'ytd_total':
                stats['unit'] = '$'
                cursor.execute('''
                    SELECT strftime('%Y', bill_date) as year, SUM(total_cost) as total
                    FROM (
                        SELECT bill_date, total_cost FROM electric_bills
                        UNION ALL SELECT bill_date, total_cost FROM gas_bills
                        UNION ALL SELECT bill_date, total_cost FROM water_bills
                    )
                    GROUP BY strftime('%Y', bill_date)
                    ORDER BY year
                ''')
                rows = cursor.fetchall()
                values = []
                for r in rows:
                    if r['total']:
                        values.append(r['total'])
                        if int(r['year']) == last_year:
                            stats['last_year'] = r['total']
                if values:
                    stats['average'] = sum(values) / len(values)
                    stats['min'] = min(values)
                    stats['max'] = max(values)
        
        return stats

    def get_current_performance(self) -> Dict:
        """Get current year performance metrics for dashboard."""
        current_year = datetime.now().year
        sqft = float(self.get_config('square_footage') or 1800)
        
        result = {
            'kwh_day': 0,
            'thm_day': 0,
            'gal_day': 0,
            'cost_day': 0,
            'cost_sqft': 0,
            'ytd_total': 0,
            'actual_cpd_pct': 0,
            'expected_cpd_pct': 0,
            'demand_pct': 0,
        }
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Try current year first, fall back to most recent year with data
            for year in [current_year, current_year - 1]:
                cursor.execute('''
                    SELECT SUM(usage_kwh) as total, SUM(days) as days
                    FROM electric_bills WHERE strftime('%Y', bill_date) = ?
                ''', (str(year),))
                r = cursor.fetchone()
                if r and r['days'] and r['days'] > 0:
                    result['kwh_day'] = r['total'] / r['days']
                    break
            
            for year in [current_year, current_year - 1]:
                cursor.execute('''
                    SELECT SUM(therms) as total, SUM(days) as days
                    FROM gas_bills WHERE strftime('%Y', bill_date) = ?
                ''', (str(year),))
                r = cursor.fetchone()
                if r and r['days'] and r['days'] > 0:
                    result['thm_day'] = r['total'] / r['days']
                    break
            
            for year in [current_year, current_year - 1]:
                cursor.execute('''
                    SELECT AVG(gallons_per_day) as avg_gpd
                    FROM water_bills WHERE strftime('%Y', bill_date) = ?
                ''', (str(year),))
                r = cursor.fetchone()
                if r and r['avg_gpd']:
                    result['gal_day'] = r['avg_gpd']
                    break
            
            # YTD total - use current year first, then fall back
            for year in [current_year, current_year - 1]:
                cursor.execute('''
                    SELECT SUM(total_cost) as total FROM (
                        SELECT total_cost FROM electric_bills WHERE strftime('%Y', bill_date) = ?
                        UNION ALL SELECT total_cost FROM gas_bills WHERE strftime('%Y', bill_date) = ?
                        UNION ALL SELECT total_cost FROM water_bills WHERE strftime('%Y', bill_date) = ?
                    )
                ''', (str(year), str(year), str(year)))
                r = cursor.fetchone()
                if r and r['total']:
                    result['ytd_total'] = r['total']
                    result['cost_sqft'] = r['total'] / sqft
                    break
        
        # Get demand metrics using blended projection
        demand_stats = self.get_current_demand_stats()
        result['actual_cpd_pct'] = demand_stats['actual_cpd']
        result['expected_cpd_pct'] = demand_stats['expected_cpd']
        result['demand_pct'] = demand_stats['demand_pct']
        
        # Get cost_day from most recent year with data
        matrix = self.get_demand_matrix()
        for year in [current_year, current_year - 1]:
            for r in matrix:
                if r['year'] == year and r['cost_per_day'] > 0:
                    result['cost_day'] = r['cost_per_day']
                    return result
        
        return result

    # ==================== PDF Template Methods ====================
    
    def get_pdf_template(self, utility_type: str) -> Optional[Dict]:
        """Get PDF field mappings for a utility type."""
        import json
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT field_mappings FROM pdf_templates WHERE utility_type = ?',
                (utility_type,)
            )
            row = cursor.fetchone()
            if row:
                return json.loads(row['field_mappings'])
            return None
    
    def save_pdf_template(self, utility_type: str, field_mappings: Dict):
        """Save PDF field mappings for a utility type."""
        import json
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO pdf_templates (utility_type, field_mappings, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (utility_type, json.dumps(field_mappings)))
            conn.commit()
    
    def delete_pdf_template(self, utility_type: str):
        """Delete PDF template for a utility type."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM pdf_templates WHERE utility_type = ?', (utility_type,))
            conn.commit()
    
    def get_previous_month_costs(self) -> Dict:
        """Get costs from the previous month for comparison."""
        from datetime import datetime
        from dateutil.relativedelta import relativedelta
        
        now = datetime.now()
        prev_month = now - relativedelta(months=1)
        prev_year = prev_month.year
        prev_mo = prev_month.month
        
        result = {'electric': 0, 'gas': 0, 'water': 0}
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get previous month electric cost
            cursor.execute('''
                SELECT total_cost FROM electric_bills 
                WHERE strftime('%Y', bill_date) = ? AND strftime('%m', bill_date) = ?
                ORDER BY bill_date DESC LIMIT 1
            ''', (str(prev_year), f'{prev_mo:02d}'))
            r = cursor.fetchone()
            if r and r['total_cost']:
                result['electric'] = r['total_cost']
            
            # Get previous month gas cost
            cursor.execute('''
                SELECT total_cost FROM gas_bills 
                WHERE strftime('%Y', bill_date) = ? AND strftime('%m', bill_date) = ?
                ORDER BY bill_date DESC LIMIT 1
            ''', (str(prev_year), f'{prev_mo:02d}'))
            r = cursor.fetchone()
            if r and r['total_cost']:
                result['gas'] = r['total_cost']
            
            # Get previous month water cost
            cursor.execute('''
                SELECT total_cost FROM water_bills 
                WHERE strftime('%Y', bill_date) = ? AND strftime('%m', bill_date) = ?
                ORDER BY bill_date DESC LIMIT 1
            ''', (str(prev_year), f'{prev_mo:02d}'))
            r = cursor.fetchone()
            if r and r['total_cost']:
                result['water'] = r['total_cost']
        
        return result
    
    def get_ytd_previous_year(self) -> float:
        """Get YTD total from same period last year for comparison."""
        from datetime import datetime
        
        now = datetime.now()
        prev_year = now.year - 1
        current_month = now.month
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get YTD total from previous year through current month
            cursor.execute('''
                SELECT SUM(total_cost) as total FROM (
                    SELECT total_cost FROM electric_bills 
                    WHERE strftime('%Y', bill_date) = ? AND CAST(strftime('%m', bill_date) AS INTEGER) <= ?
                    UNION ALL 
                    SELECT total_cost FROM gas_bills 
                    WHERE strftime('%Y', bill_date) = ? AND CAST(strftime('%m', bill_date) AS INTEGER) <= ?
                    UNION ALL 
                    SELECT total_cost FROM water_bills 
                    WHERE strftime('%Y', bill_date) = ? AND CAST(strftime('%m', bill_date) AS INTEGER) <= ?
                )
            ''', (str(prev_year), current_month, str(prev_year), current_month, str(prev_year), current_month))
            r = cursor.fetchone()
            if r and r['total']:
                return r['total']
        
        return 0.0


# Quick test
if __name__ == '__main__':
    db = DatabaseManager('test_utilities.db')
    print("Database initialized successfully!")
    print(f"Config: {db.get_all_config()}")
