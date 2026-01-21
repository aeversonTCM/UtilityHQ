"""
Utilities Tracker - Data Migration
Imports existing data from the Excel workbook into the SQLite database.
"""

import pandas as pd
from pathlib import Path
from datetime import datetime, date
from typing import Optional
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from database import (
    DatabaseManager, ElectricBill, GasBill, WaterBill, WeatherDay
)


class ExcelMigrator:
    """Migrates data from the Utilities Excel workbook to SQLite."""
    
    def __init__(self, excel_path: str, db_path: str = "utilities.db"):
        self.excel_path = Path(excel_path)
        self.db = DatabaseManager(db_path)
        
        if not self.excel_path.exists():
            raise FileNotFoundError(f"Excel file not found: {excel_path}")
    
    def migrate_all(self):
        """Run full migration of all data."""
        print("=" * 60)
        print("UTILITIES TRACKER - DATA MIGRATION")
        print("=" * 60)
        
        print(f"\nSource: {self.excel_path}")
        print(f"Target: {self.db.db_path}")
        
        # Migrate each data type
        self.migrate_electric_bills()
        self.migrate_gas_bills()
        self.migrate_water_bills()
        self.migrate_weather_data()
        self.migrate_config()
        
        # Update summary tables
        print("\n📊 Updating yearly cost summaries...")
        self.db.update_yearly_costs()
        
        print("\n" + "=" * 60)
        print("✅ MIGRATION COMPLETE!")
        print("=" * 60)
        
        # Print summary
        self._print_summary()
    
    def _safe_float(self, value) -> Optional[float]:
        """Safely convert value to float."""
        if pd.isna(value) or value == '' or value == '-':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    def _safe_int(self, value) -> Optional[int]:
        """Safely convert value to int."""
        if pd.isna(value) or value == '' or value == '-':
            return None
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None
    
    def _safe_date(self, value) -> Optional[date]:
        """Safely convert value to date."""
        if pd.isna(value) or value == '' or value == '-':
            return None
        try:
            if isinstance(value, datetime):
                return value.date()
            elif isinstance(value, date):
                return value
            elif isinstance(value, str):
                return datetime.strptime(value, '%Y-%m-%d').date()
            return None
        except (ValueError, TypeError):
            return None
    
    def migrate_electric_bills(self):
        """Migrate electric bill data."""
        print("\n⚡ Migrating Electric Bills...")
        
        try:
            df = pd.read_excel(self.excel_path, sheet_name='ElecBill')
            
            # Skip header row if present, find the data
            # The data starts after the header row
            success_count = 0
            error_count = 0
            
            for idx, row in df.iterrows():
                try:
                    # Skip rows without valid dates
                    bill_date = self._safe_date(row.iloc[0])
                    if not bill_date:
                        continue
                    
                    # Skip if no usage data
                    usage = self._safe_float(row.iloc[2])
                    if usage is None:
                        continue
                    
                    total_cost = self._safe_float(row.iloc[7])
                    if total_cost is None:
                        continue
                    
                    bill = ElectricBill(
                        id=None,
                        bill_date=bill_date,
                        meter_reading=self._safe_float(row.iloc[1]),
                        usage_kwh=usage,
                        days=self._safe_int(row.iloc[3]) or 30,
                        kwh_per_day=self._safe_float(row.iloc[4]),
                        electric_cost=self._safe_float(row.iloc[5]),
                        taxes=self._safe_float(row.iloc[6]),
                        total_cost=total_cost,
                        cost_per_kwh=self._safe_float(row.iloc[8]),
                        last_read_date=None
                    )
                    
                    self.db.add_electric_bill(bill)
                    success_count += 1
                    
                except Exception as e:
                    error_count += 1
                    if error_count <= 3:
                        print(f"   ⚠️  Row {idx}: {e}")
            
            print(f"   ✅ Imported {success_count} electric bills")
            if error_count > 0:
                print(f"   ⚠️  {error_count} rows skipped")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    def migrate_gas_bills(self):
        """Migrate gas bill data."""
        print("\n🔥 Migrating Gas Bills...")
        
        try:
            df = pd.read_excel(self.excel_path, sheet_name='GasBill')
            
            success_count = 0
            error_count = 0
            
            for idx, row in df.iterrows():
                try:
                    bill_date = self._safe_date(row.iloc[0])
                    if not bill_date:
                        continue
                    
                    usage_ccf = self._safe_float(row.iloc[2])
                    if usage_ccf is None:
                        continue
                    
                    total_cost = self._safe_float(row.iloc[11])
                    if total_cost is None:
                        continue
                    
                    bill = GasBill(
                        id=None,
                        bill_date=bill_date,
                        meter_reading=self._safe_float(row.iloc[1]),
                        usage_ccf=usage_ccf,
                        btu_factor=self._safe_float(row.iloc[3]),
                        days=self._safe_int(row.iloc[4]) or 30,
                        therms=self._safe_float(row.iloc[5]),
                        therms_per_day=self._safe_float(row.iloc[6]),
                        cost_per_therm=self._safe_float(row.iloc[7]),
                        therm_cost=self._safe_float(row.iloc[8]),
                        service_charge=self._safe_float(row.iloc[9]),
                        taxes=self._safe_float(row.iloc[10]),
                        total_cost=total_cost,
                        last_read_date=None
                    )
                    
                    self.db.add_gas_bill(bill)
                    success_count += 1
                    
                except Exception as e:
                    error_count += 1
                    if error_count <= 3:
                        print(f"   ⚠️  Row {idx}: {e}")
            
            print(f"   ✅ Imported {success_count} gas bills")
            if error_count > 0:
                print(f"   ⚠️  {error_count} rows skipped")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    def migrate_water_bills(self):
        """Migrate water bill data."""
        print("\n💧 Migrating Water Bills...")
        
        try:
            df = pd.read_excel(self.excel_path, sheet_name='WaterBill')
            
            success_count = 0
            error_count = 0
            
            for idx, row in df.iterrows():
                try:
                    bill_date = self._safe_date(row.iloc[0])
                    if not bill_date:
                        continue
                    
                    # Water usage is in hundreds of gallons (Gal/100)
                    usage_hundreds = self._safe_float(row.iloc[2])
                    if usage_hundreds is None:
                        continue
                    
                    total_cost = self._safe_float(row.iloc[7])
                    if total_cost is None:
                        continue
                    
                    bill = WaterBill(
                        id=None,
                        bill_date=bill_date,
                        meter_reading=self._safe_float(row.iloc[1]),
                        usage_gallons=usage_hundreds * 100 if usage_hundreds else 0,  # Convert to gallons
                        gallons_per_day=self._safe_float(row.iloc[3]),
                        water_cost=self._safe_float(row.iloc[4]),
                        service_charge=self._safe_float(row.iloc[5]),
                        cost_per_kgal=self._safe_float(row.iloc[6]),
                        total_cost=total_cost
                    )
                    
                    self.db.add_water_bill(bill)
                    success_count += 1
                    
                except Exception as e:
                    error_count += 1
                    if error_count <= 3:
                        print(f"   ⚠️  Row {idx}: {e}")
            
            print(f"   ✅ Imported {success_count} water bills")
            if error_count > 0:
                print(f"   ⚠️  {error_count} rows skipped")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    def migrate_weather_data(self):
        """Migrate weather data."""
        print("\n🌤️  Migrating Weather Data...")
        
        try:
            df = pd.read_excel(self.excel_path, sheet_name='Weather', header=1)
            
            success_count = 0
            error_count = 0
            
            for idx, row in df.iterrows():
                try:
                    weather_date = self._safe_date(row.iloc[0])
                    if not weather_date:
                        continue
                    
                    # Skip placeholder rows (like Feb 29 in non-leap years marked with '-')
                    if str(row.iloc[0]) == '-':
                        continue
                    
                    weather = WeatherDay(
                        id=None,
                        date=weather_date,
                        temp_high=self._safe_float(row.iloc[1]),
                        temp_avg=self._safe_float(row.iloc[2]),
                        temp_low=self._safe_float(row.iloc[3]),
                        dewpoint_high=self._safe_float(row.iloc[4]),
                        dewpoint_avg=self._safe_float(row.iloc[5]),
                        dewpoint_low=self._safe_float(row.iloc[6]),
                        humidity_high=self._safe_float(row.iloc[7]),
                        humidity_avg=self._safe_float(row.iloc[8]),
                        humidity_low=self._safe_float(row.iloc[9]),
                        wind_max=self._safe_float(row.iloc[10]),
                        wind_avg=self._safe_float(row.iloc[11]),
                        wind_gust=self._safe_float(row.iloc[12]),
                        pressure_max=self._safe_float(row.iloc[13]),
                        pressure_min=self._safe_float(row.iloc[14]),
                        rain_total=self._safe_float(row.iloc[15]) or 0,
                        cooling_demand=self._safe_float(row.iloc[16]),
                        heating_demand=self._safe_float(row.iloc[17]),
                        max_demand=self._safe_float(row.iloc[18])
                    )
                    
                    self.db.add_weather_day(weather)
                    success_count += 1
                    
                except Exception as e:
                    error_count += 1
                    if error_count <= 5:
                        print(f"   ⚠️  Row {idx}: {e}")
            
            print(f"   ✅ Imported {success_count} weather days")
            if error_count > 0:
                print(f"   ⚠️  {error_count} rows skipped")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    def migrate_config(self):
        """Migrate configuration settings."""
        print("\n⚙️  Migrating Configuration...")
        
        try:
            df = pd.read_excel(self.excel_path, sheet_name='Config')
            
            # Station ID is typically in cell B7 (row 5 in 0-indexed after header)
            # Temperature setpoints are in rows 2-3
            
            # Try to extract station ID
            for idx, row in df.iterrows():
                try:
                    # Look for station ID pattern
                    for col_idx, val in enumerate(row):
                        if isinstance(val, str) and val.startswith('KNCH'):
                            self.db.set_config('station_id', val)
                            print(f"   ✅ Station ID: {val}")
                            break
                except:
                    pass
            
            # Temperature thresholds from row 2 (heating/cooling limits)
            try:
                # Based on the Excel structure:
                # Row 2 has: Min(15), Max(54) for heating, Min(78), Max(96) for cooling
                config_row = df.iloc[2]
                
                heating_min = self._safe_float(config_row.iloc[1])
                heating_max = self._safe_float(config_row.iloc[2])
                cooling_min = self._safe_float(config_row.iloc[5])
                cooling_max = self._safe_float(config_row.iloc[6])
                
                if heating_min:
                    self.db.set_config('heating_min_temp', str(int(heating_min)))
                if heating_max:
                    self.db.set_config('heating_max_temp', str(int(heating_max)))
                if cooling_min:
                    self.db.set_config('cooling_min_temp', str(int(cooling_min)))
                if cooling_max:
                    self.db.set_config('cooling_max_temp', str(int(cooling_max)))
                
                print(f"   ✅ Temperature thresholds configured")
                
            except Exception as e:
                print(f"   ⚠️  Could not extract temperature thresholds: {e}")
            
            print(f"   ✅ Configuration migrated")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    def _print_summary(self):
        """Print migration summary."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) as count FROM electric_bills')
            elec_count = cursor.fetchone()['count']
            
            cursor.execute('SELECT COUNT(*) as count FROM gas_bills')
            gas_count = cursor.fetchone()['count']
            
            cursor.execute('SELECT COUNT(*) as count FROM water_bills')
            water_count = cursor.fetchone()['count']
            
            cursor.execute('SELECT COUNT(*) as count FROM weather_daily')
            weather_count = cursor.fetchone()['count']
            
            cursor.execute('SELECT MIN(bill_date) as min_date, MAX(bill_date) as max_date FROM electric_bills')
            elec_dates = cursor.fetchone()
            
            cursor.execute('SELECT MIN(date) as min_date, MAX(date) as max_date FROM weather_daily')
            weather_dates = cursor.fetchone()
        
        print("\n📊 DATABASE SUMMARY")
        print("-" * 40)
        print(f"Electric Bills:  {elec_count:,} records")
        print(f"Gas Bills:       {gas_count:,} records")
        print(f"Water Bills:     {water_count:,} records")
        print(f"Weather Days:    {weather_count:,} records")
        
        if elec_dates['min_date']:
            print(f"\nBill Date Range: {elec_dates['min_date']} to {elec_dates['max_date']}")
        if weather_dates['min_date']:
            print(f"Weather Range:   {weather_dates['min_date']} to {weather_dates['max_date']}")


def main():
    """Main entry point for migration."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate Excel utilities data to SQLite')
    parser.add_argument('excel_file', help='Path to the Excel workbook (.xlsm)')
    parser.add_argument('--db', default='utilities.db', help='Output database path')
    
    args = parser.parse_args()
    
    migrator = ExcelMigrator(args.excel_file, args.db)
    migrator.migrate_all()


if __name__ == '__main__':
    main()
