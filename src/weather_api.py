"""
Utilities Tracker - Weather API Integration
Supports multiple weather data sources:
- Open-Meteo (free, no API key, historical data back to 1940)
- Weather Underground (Personal Weather Stations)
"""

import requests
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import time


@dataclass
class WeatherObservation:
    """Single weather observation from any weather source."""
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


class OpenMeteoAPI:
    """
    Open-Meteo API client - Free weather data, no API key required.
    
    Features:
    - Historical data back to 1940
    - No API key or registration needed
    - 10,000 requests/day free limit
    - ~9km resolution for historical, ~1km for recent
    
    API Documentation: https://open-meteo.com/en/docs
    """
    
    FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
    HISTORICAL_URL = "https://archive-api.open-meteo.com/v1/archive"
    
    def __init__(self, latitude: float, longitude: float):
        """
        Initialize the Open-Meteo API client.
        
        Args:
            latitude: Location latitude (e.g., 35.9606)
            longitude: Location longitude (e.g., -83.9207)
        """
        self.latitude = latitude
        self.longitude = longitude
        self.session = requests.Session()
    
    def _make_request(self, url: str, params: Dict[str, Any]) -> Optional[Dict]:
        """Make an API request with error handling."""
        params['latitude'] = self.latitude
        params['longitude'] = self.longitude
        
        try:
            print(f"🌐 Open-Meteo request: {url}")
            response = self.session.get(url, params=params, timeout=30)
            
            if response.status_code != 200:
                print(f"   ⚠️ HTTP {response.status_code}")
                return None
            
            data = response.json()
            
            if 'error' in data and data['error']:
                print(f"   ⚠️ API Error: {data.get('reason', 'Unknown')}")
                return None
            
            return data
            
        except requests.exceptions.Timeout:
            print(f"   ⚠️ Request timeout")
            return None
        except requests.exceptions.RequestException as e:
            print(f"   ⚠️ Request error: {e}")
            return None
        except ValueError as e:
            print(f"   ⚠️ JSON decode error: {e}")
            return None
    
    def get_daily_weather(self, target_date: date) -> Optional[WeatherObservation]:
        """
        Get daily weather for a specific date.
        
        Args:
            target_date: The date to fetch data for
            
        Returns:
            WeatherObservation or None on error
        """
        # Use historical API for dates more than 5 days ago
        days_ago = (date.today() - target_date).days
        
        if days_ago > 5:
            return self._get_historical_daily(target_date)
        else:
            return self._get_forecast_daily(target_date)
    
    def _get_forecast_daily(self, target_date: date) -> Optional[WeatherObservation]:
        """Get daily weather from forecast API (recent days)."""
        params = {
            'daily': 'temperature_2m_max,temperature_2m_min,temperature_2m_mean,'
                     'precipitation_sum,rain_sum,wind_speed_10m_max,'
                     'relative_humidity_2m_max,relative_humidity_2m_min,relative_humidity_2m_mean,'
                     'dew_point_2m_max,dew_point_2m_min,dew_point_2m_mean,'
                     'pressure_msl_max,pressure_msl_min',
            'temperature_unit': 'fahrenheit',
            'wind_speed_unit': 'mph',
            'precipitation_unit': 'inch',
            'timezone': 'America/New_York',
            'past_days': 7,
            'forecast_days': 1,
        }
        
        data = self._make_request(self.FORECAST_URL, params)
        return self._parse_daily_response(data, target_date)
    
    def _get_historical_daily(self, target_date: date) -> Optional[WeatherObservation]:
        """Get daily weather from historical/archive API."""
        params = {
            'start_date': target_date.strftime('%Y-%m-%d'),
            'end_date': target_date.strftime('%Y-%m-%d'),
            'daily': 'temperature_2m_max,temperature_2m_min,temperature_2m_mean,'
                     'precipitation_sum,rain_sum,wind_speed_10m_max,'
                     'relative_humidity_2m_max,relative_humidity_2m_min,relative_humidity_2m_mean,'
                     'dew_point_2m_max,dew_point_2m_min,dew_point_2m_mean,'
                     'pressure_msl_max,pressure_msl_min',
            'temperature_unit': 'fahrenheit',
            'wind_speed_unit': 'mph',
            'precipitation_unit': 'inch',
            'timezone': 'America/New_York',
        }
        
        data = self._make_request(self.HISTORICAL_URL, params)
        return self._parse_daily_response(data, target_date)
    
    def _parse_daily_response(self, data: Optional[Dict], target_date: date) -> Optional[WeatherObservation]:
        """Parse daily weather response into WeatherObservation."""
        if not data or 'daily' not in data:
            return None
        
        daily = data['daily']
        times = daily.get('time', [])
        
        # Find the index for our target date
        target_str = target_date.strftime('%Y-%m-%d')
        try:
            idx = times.index(target_str)
        except ValueError:
            print(f"   ⚠️ Date {target_str} not found in response")
            return None
        
        def get_val(key: str) -> Optional[float]:
            arr = daily.get(key, [])
            if idx < len(arr) and arr[idx] is not None:
                return float(arr[idx])
            return None
        
        obs = WeatherObservation(
            date=target_date,
            temp_high=get_val('temperature_2m_max'),
            temp_low=get_val('temperature_2m_min'),
            temp_avg=get_val('temperature_2m_mean'),
            dewpoint_high=get_val('dew_point_2m_max'),
            dewpoint_low=get_val('dew_point_2m_min'),
            dewpoint_avg=get_val('dew_point_2m_mean'),
            humidity_high=get_val('relative_humidity_2m_max'),
            humidity_low=get_val('relative_humidity_2m_min'),
            humidity_avg=get_val('relative_humidity_2m_mean'),
            wind_max=get_val('wind_speed_10m_max'),
            pressure_max=get_val('pressure_msl_max'),
            pressure_min=get_val('pressure_msl_min'),
            rain_total=get_val('precipitation_sum') or get_val('rain_sum') or 0,
        )
        
        print(f"   ✅ {target_date}: High {obs.temp_high}°F, Low {obs.temp_low}°F, Rain {obs.rain_total}\"")
        return obs
    
    def get_date_range(self, start_date: date, end_date: date,
                       progress_callback=None) -> List[WeatherObservation]:
        """
        Get weather data for a date range (efficient batch request).
        
        Args:
            start_date: Start of date range
            end_date: End of date range
            progress_callback: Optional callback function(current, total) for progress
            
        Returns:
            List of WeatherObservation objects
        """
        # Historical API can fetch entire range in one request
        params = {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'daily': 'temperature_2m_max,temperature_2m_min,temperature_2m_mean,'
                     'precipitation_sum,rain_sum,wind_speed_10m_max,'
                     'relative_humidity_2m_max,relative_humidity_2m_min,relative_humidity_2m_mean,'
                     'dew_point_2m_max,dew_point_2m_min,dew_point_2m_mean,'
                     'pressure_msl_max,pressure_msl_min',
            'temperature_unit': 'fahrenheit',
            'wind_speed_unit': 'mph',
            'precipitation_unit': 'inch',
            'timezone': 'America/New_York',
        }
        
        # Use historical API for older data, forecast for recent
        days_ago = (date.today() - end_date).days
        url = self.HISTORICAL_URL if days_ago > 5 else self.FORECAST_URL
        
        if url == self.FORECAST_URL:
            # Forecast API uses past_days instead of date range
            params = {
                'daily': params['daily'],
                'temperature_unit': 'fahrenheit',
                'wind_speed_unit': 'mph',
                'precipitation_unit': 'inch',
                'timezone': 'America/New_York',
                'past_days': min((date.today() - start_date).days + 1, 92),
                'forecast_days': 1,
            }
        
        data = self._make_request(url, params)
        
        if not data or 'daily' not in data:
            return []
        
        observations = []
        daily = data['daily']
        times = daily.get('time', [])
        total_days = len(times)
        
        for i, time_str in enumerate(times):
            try:
                obs_date = datetime.strptime(time_str, '%Y-%m-%d').date()
            except ValueError:
                continue
            
            # Filter to requested range
            if obs_date < start_date or obs_date > end_date:
                continue
            
            if progress_callback:
                progress_callback(i + 1, total_days)
            
            def get_val(key: str) -> Optional[float]:
                arr = daily.get(key, [])
                if i < len(arr) and arr[i] is not None:
                    return float(arr[i])
                return None
            
            obs = WeatherObservation(
                date=obs_date,
                temp_high=get_val('temperature_2m_max'),
                temp_low=get_val('temperature_2m_min'),
                temp_avg=get_val('temperature_2m_mean'),
                dewpoint_high=get_val('dew_point_2m_max'),
                dewpoint_low=get_val('dew_point_2m_min'),
                dewpoint_avg=get_val('dew_point_2m_mean'),
                humidity_high=get_val('relative_humidity_2m_max'),
                humidity_low=get_val('relative_humidity_2m_min'),
                humidity_avg=get_val('relative_humidity_2m_mean'),
                wind_max=get_val('wind_speed_10m_max'),
                pressure_max=get_val('pressure_msl_max'),
                pressure_min=get_val('pressure_msl_min'),
                rain_total=get_val('precipitation_sum') or get_val('rain_sum') or 0,
            )
            observations.append(obs)
        
        print(f"   ✅ Retrieved {len(observations)} days of weather data")
        return observations
    
    def test_connection(self) -> bool:
        """
        Test the API connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        params = {
            'current': 'temperature_2m',
            'temperature_unit': 'fahrenheit',
        }
        
        data = self._make_request(self.FORECAST_URL, params)
        if data and 'current' in data:
            temp = data['current'].get('temperature_2m')
            print(f"   ✅ Connection OK - Current temp: {temp}°F")
            return True
        return False


class WeatherUndergroundAPI:
    """
    Weather Underground API client for Personal Weather Stations.
    
    API Documentation: https://docs.google.com/document/d/1eKCnKXI9xnoMGRRzOL1xPCBihNV2rOet08qpE_gArAY
    """
    
    BASE_URL = "https://api.weather.com/v2/pws"
    
    def __init__(self, api_key: str, station_id: str):
        """
        Initialize the Weather Underground API client.
        
        Args:
            api_key: Your Weather Underground API key
            station_id: Your PWS station ID (e.g., 'KNCHENDE440')
        """
        self.api_key = api_key
        self.station_id = station_id
        self.session = requests.Session()
    
    def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Optional[Dict]:
        """Make an API request with error handling."""
        params['apiKey'] = self.api_key
        params['format'] = 'json'
        
        url = f"{self.BASE_URL}/{endpoint}"
        
        try:
            print(f"🌐 Requesting: {url}")
            print(f"   Params: {', '.join(f'{k}={v}' for k, v in params.items() if k != 'apiKey')}")
            
            response = self.session.get(url, params=params, timeout=30)
            
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 204:
                print("   ⚠️ No data available for this date")
                return None
            
            response.raise_for_status()
            data = response.json()
            
            # Debug: show what we got
            if 'observations' in data:
                print(f"   ✅ Got {len(data['observations'])} observations")
            elif 'summaries' in data:
                print(f"   ✅ Got {len(data['summaries'])} summaries")
            else:
                print(f"   ⚠️ Unexpected response format: {list(data.keys())}")
            
            return data
            
        except requests.exceptions.Timeout:
            print(f"   ⚠️ Request timeout")
            return None
        except requests.exceptions.HTTPError as e:
            print(f"   ⚠️ HTTP error {e.response.status_code}")
            try:
                error_data = e.response.json()
                print(f"   Error: {error_data}")
            except:
                print(f"   Response: {e.response.text[:200]}")
            return None
        except requests.exceptions.RequestException as e:
            print(f"   ⚠️ Request error: {e}")
            return None
        except ValueError as e:
            print(f"   ⚠️ JSON decode error: {e}")
            return None
    
    def get_current_conditions(self) -> Optional[Dict]:
        """
        Get current weather conditions from the PWS.
        
        Returns:
            Dictionary with current conditions or None on error
        """
        params = {
            'stationId': self.station_id,
            'units': 'e',  # Imperial units
            'numericPrecision': 'decimal'
        }
        
        data = self._make_request('observations/current', params)
        
        if data and 'observations' in data and len(data['observations']) > 0:
            obs = data['observations'][0]
            return {
                'station_id': obs.get('stationID'),
                'observation_time': obs.get('obsTimeLocal'),
                'temp': obs.get('imperial', {}).get('temp'),
                'humidity': obs.get('humidity'),
                'dewpoint': obs.get('imperial', {}).get('dewpt'),
                'wind_speed': obs.get('imperial', {}).get('windSpeed'),
                'wind_gust': obs.get('imperial', {}).get('windGust'),
                'wind_dir': obs.get('winddir'),
                'pressure': obs.get('imperial', {}).get('pressure'),
                'precip_rate': obs.get('imperial', {}).get('precipRate'),
                'precip_total': obs.get('imperial', {}).get('precipTotal'),
                'uv': obs.get('uv'),
                'solar_radiation': obs.get('solarRadiation'),
            }
        
        return None
    
    def get_daily_summary(self, target_date: date) -> Optional[WeatherObservation]:
        """
        Get daily summary for a specific date.
        
        Args:
            target_date: The date to fetch data for
            
        Returns:
            WeatherObservation or None on error
        """
        date_str = target_date.strftime('%Y%m%d')
        
        params = {
            'stationId': self.station_id,
            'units': 'e',
            'numericPrecision': 'decimal'
        }
        
        data = self._make_request(f'dailysummary/7day', params)
        
        if data and 'summaries' in data:
            for summary in data['summaries']:
                # Check if this is the date we're looking for
                obs_date_str = summary.get('obsTimeLocal', '')[:10].replace('-', '')
                if obs_date_str == date_str:
                    imperial = summary.get('imperial', {})
                    metric = summary.get('metric', {})
                    
                    return WeatherObservation(
                        date=target_date,
                        temp_high=imperial.get('tempHigh'),
                        temp_avg=imperial.get('tempAvg'),
                        temp_low=imperial.get('tempLow'),
                        dewpoint_high=imperial.get('dewptHigh'),
                        dewpoint_avg=imperial.get('dewptAvg'),
                        dewpoint_low=imperial.get('dewptLow'),
                        humidity_high=summary.get('humidityHigh'),
                        humidity_avg=summary.get('humidityAvg'),
                        humidity_low=summary.get('humidityLow'),
                        wind_max=imperial.get('windspeedHigh'),
                        wind_avg=imperial.get('windspeedAvg'),
                        wind_gust=imperial.get('windgustHigh'),
                        pressure_max=imperial.get('pressureMax'),
                        pressure_min=imperial.get('pressureMin'),
                        rain_total=imperial.get('precipTotal'),
                    )
        
        return None
    
    def get_historical_daily(self, target_date: date) -> Optional[WeatherObservation]:
        """
        Get historical daily data for a specific date.
        
        API Endpoint: /history/daily
        Required params: stationId, format, units, date (YYYYMMDD), apiKey
        
        Args:
            target_date: The date to fetch data for
            
        Returns:
            WeatherObservation or None on error
        """
        date_str = target_date.strftime('%Y%m%d')
        
        # According to WU API docs, use history/daily with date param
        params = {
            'stationId': self.station_id,
            'units': 'e',
            'numericPrecision': 'decimal',
            'date': date_str
        }
        
        # history/daily returns raw observations for that day
        data = self._make_request('history/daily', params)
        
        if not data:
            print(f"   ❌ No data returned for {target_date}")
            return None
        
        # Check for observations in the response
        observations = data.get('observations', [])
        if not observations:
            print(f"   ❌ No observations in response for {target_date}")
            print(f"   Response keys: {list(data.keys())}")
            return None
        
        print(f"   📊 Processing {len(observations)} observations for {target_date}")
        
        # Look at first observation to understand structure
        first_obs = observations[0]
        print(f"   First obs keys: {list(first_obs.keys())}")
        
        # The API can return data in different formats - check for 'metric' or 'imperial'
        # or direct values
        temps = []
        dewpoints = []
        humidities = []
        winds = []
        gusts = []
        pressures = []
        precips = []
        
        for obs in observations:
            # Try imperial first (requested with units=e)
            imperial = obs.get('imperial', {})
            metric = obs.get('metric', {})
            
            # Temperature - try multiple possible keys
            temp = imperial.get('temp') or imperial.get('tempAvg') or obs.get('tempAvg') or obs.get('temp')
            if temp is not None:
                temps.append(float(temp))
            
            # Dewpoint
            dewpt = imperial.get('dewpt') or imperial.get('dewptAvg') or obs.get('dewptAvg')
            if dewpt is not None:
                dewpoints.append(float(dewpt))
            
            # Humidity
            hum = obs.get('humidity') or obs.get('humidityAvg')
            if hum is not None:
                humidities.append(float(hum))
            
            # Wind
            ws = imperial.get('windSpeed') or imperial.get('windspeedAvg') or obs.get('windspeedAvg')
            if ws is not None:
                winds.append(float(ws))
            
            wg = imperial.get('windGust') or imperial.get('windgustHigh') or obs.get('windgustHigh')
            if wg is not None:
                gusts.append(float(wg))
            
            # Pressure
            pres = imperial.get('pressure') or imperial.get('pressureMax') or obs.get('pressureMax')
            if pres is not None:
                pressures.append(float(pres))
            
            # Precipitation
            precip = imperial.get('precipTotal') or obs.get('precipTotal')
            if precip is not None:
                precips.append(float(precip))
        
        print(f"   Temps found: {len(temps)}, range: {min(temps) if temps else 'N/A'} - {max(temps) if temps else 'N/A'}")
        
        if not temps:
            print(f"   ⚠️ No temperature data found!")
            # Print sample observation for debugging
            print(f"   Sample obs: {first_obs}")
            return None
        
        return WeatherObservation(
            date=target_date,
            temp_high=max(temps) if temps else None,
            temp_avg=sum(temps) / len(temps) if temps else None,
            temp_low=min(temps) if temps else None,
            dewpoint_high=max(dewpoints) if dewpoints else None,
            dewpoint_avg=sum(dewpoints) / len(dewpoints) if dewpoints else None,
            dewpoint_low=min(dewpoints) if dewpoints else None,
            humidity_high=max(humidities) if humidities else None,
            humidity_avg=sum(humidities) / len(humidities) if humidities else None,
            humidity_low=min(humidities) if humidities else None,
            wind_max=max(winds) if winds else None,
            wind_avg=sum(winds) / len(winds) if winds else None,
            wind_gust=max(gusts) if gusts else None,
            pressure_max=max(pressures) if pressures else None,
            pressure_min=min(pressures) if pressures else None,
            rain_total=max(precips) if precips else 0,
        )
    
    def get_date_range(self, start_date: date, end_date: date, 
                       progress_callback=None) -> List[WeatherObservation]:
        """
        Get weather data for a date range.
        
        Args:
            start_date: Start of date range
            end_date: End of date range
            progress_callback: Optional callback function(current, total) for progress
            
        Returns:
            List of WeatherObservation objects
        """
        observations = []
        current = start_date
        total_days = (end_date - start_date).days + 1
        day_count = 0
        
        while current <= end_date:
            day_count += 1
            
            if progress_callback:
                progress_callback(day_count, total_days)
            
            obs = self.get_historical_daily(current)
            if obs:
                observations.append(obs)
            
            # Rate limiting - WU allows 30 calls/minute, 1500/day
            # Using 2.5 second delay = 24 calls/minute (safe margin)
            time.sleep(2.5)
            
            current += timedelta(days=1)
        
        return observations
    
    def get_monthly_summary(self, year: int, month: int) -> List[WeatherObservation]:
        """
        Get daily summaries for a whole month in one API call.
        This is more efficient than fetching day by day.
        
        Args:
            year: Year (e.g., 2024)
            month: Month (1-12)
            
        Returns:
            List of WeatherObservation objects for each day
        """
        # Calculate start and end dates for the month
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)
        
        params = {
            'stationId': self.station_id,
            'units': 'e',
            'numericPrecision': 'decimal',
            'startDate': start_date.strftime('%Y%m%d'),
            'endDate': end_date.strftime('%Y%m%d')
        }
        
        data = self._make_request('history/daily', params)
        observations = []
        
        if data and 'observations' in data:
            for obs in data['observations']:
                # Parse the date from obsTimeLocal
                obs_date_str = obs.get('obsTimeLocal', '')[:10]
                try:
                    obs_date = datetime.strptime(obs_date_str, '%Y-%m-%d').date()
                except:
                    continue
                
                imperial = obs.get('imperial', {})
                
                observations.append(WeatherObservation(
                    date=obs_date,
                    temp_high=imperial.get('tempHigh'),
                    temp_avg=imperial.get('tempAvg'),
                    temp_low=imperial.get('tempLow'),
                    dewpoint_high=imperial.get('dewptHigh'),
                    dewpoint_avg=imperial.get('dewptAvg'),
                    dewpoint_low=imperial.get('dewptLow'),
                    humidity_high=obs.get('humidityHigh'),
                    humidity_avg=obs.get('humidityAvg'),
                    humidity_low=obs.get('humidityLow'),
                    wind_max=imperial.get('windspeedHigh'),
                    wind_avg=imperial.get('windspeedAvg'),
                    wind_gust=imperial.get('windgustHigh'),
                    pressure_max=imperial.get('pressureMax'),
                    pressure_min=imperial.get('pressureMin'),
                    rain_total=imperial.get('precipTotal') or 0,
                ))
        
        return observations
    
    def test_connection(self) -> bool:
        """
        Test the API connection and credentials.
        
        Returns:
            True if connection successful, False otherwise
        """
        result = self.get_current_conditions()
        return result is not None


class WeatherDemandCalculator:
    """
    Calculates heating and cooling demand based on temperature.
    Uses degree-day methodology.
    """
    
    def __init__(self, 
                 heating_min: float = 15, 
                 heating_max: float = 54,
                 cooling_min: float = 78, 
                 cooling_max: float = 96):
        """
        Initialize the demand calculator.
        
        Args:
            heating_min: Minimum temp for max heating demand
            heating_max: Maximum temp where heating demand starts
            cooling_min: Minimum temp where cooling demand starts
            cooling_max: Maximum temp for max cooling demand
        """
        self.heating_min = heating_min
        self.heating_max = heating_max
        self.cooling_min = cooling_min
        self.cooling_max = cooling_max
    
    def calculate_cooling_demand(self, temp_high: float) -> float:
        """
        Calculate cooling demand percentage (0 to 1).
        
        Args:
            temp_high: Daily high temperature
            
        Returns:
            Cooling demand as fraction (0-1)
        """
        if temp_high is None or temp_high <= self.cooling_min:
            return 0.0
        
        if temp_high >= self.cooling_max:
            return 1.0
        
        return (temp_high - self.cooling_min) / (self.cooling_max - self.cooling_min)
    
    def calculate_heating_demand(self, temp_low: float) -> float:
        """
        Calculate heating demand percentage (0 to -1).
        
        Args:
            temp_low: Daily low temperature
            
        Returns:
            Heating demand as negative fraction (0 to -1)
        """
        if temp_low is None or temp_low >= self.heating_max:
            return 0.0
        
        if temp_low <= self.heating_min:
            return -1.0
        
        return -1 * (self.heating_max - temp_low) / (self.heating_max - self.heating_min)
    
    def calculate_demands(self, temp_high: float, temp_low: float) -> Dict[str, float]:
        """
        Calculate all demand metrics.
        
        Args:
            temp_high: Daily high temperature
            temp_low: Daily low temperature
            
        Returns:
            Dictionary with cooling_demand, heating_demand, and max_demand
        """
        cooling = self.calculate_cooling_demand(temp_high)
        heating = self.calculate_heating_demand(temp_low)
        max_demand = max(cooling, abs(heating))
        
        return {
            'cooling_demand': cooling,
            'heating_demand': heating,
            'max_demand': max_demand
        }


# Simple test
if __name__ == '__main__':
    # Test demand calculator
    calc = WeatherDemandCalculator()
    
    test_cases = [
        (95, 75),  # Hot day
        (75, 55),  # Mild day
        (45, 25),  # Cold day
        (85, 40),  # Variable day
    ]
    
    print("Demand Calculator Test")
    print("-" * 50)
    for high, low in test_cases:
        demands = calc.calculate_demands(high, low)
        print(f"High: {high}°F, Low: {low}°F")
        print(f"  Cooling: {demands['cooling_demand']:.2%}")
        print(f"  Heating: {demands['heating_demand']:.2%}")
        print(f"  Max:     {demands['max_demand']:.2%}")
        print()


class MyAcuriteScraper:
    """
    API client for MyAcurite.com to fetch weather data from Acurite weather stations.
    
    Uses the marapi.myacurite.com API endpoint for authentication and data retrieval.
    This is for personal use with your own account data.
    """
    
    API_BASE = "https://marapi.myacurite.com"
    WEB_BASE = "https://www.myacurite.com"
    
    def __init__(self, email: str, password: str):
        """
        Initialize the MyAcurite API client.
        
        Args:
            email: Your MyAcurite account email
            password: Your MyAcurite account password
        """
        self.email = email
        self.password = password
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.5',
            'Content-Type': 'application/json;charset=UTF-8',
            'Origin': 'https://www.myacurite.com',
            'Referer': 'https://www.myacurite.com/',
        })
        self._token = None
        self._account_id = None
        self._hub_id = None
        self._logged_in = False
    
    def login(self) -> bool:
        """
        Log into MyAcurite via the API.
        
        Returns:
            True if login successful, False otherwise
        """
        try:
            print("🔐 Logging into MyAcurite API...")
            
            login_data = {
                "email": self.email,
                "password": self.password,
                "remember": True
            }
            
            response = self.session.post(
                f"{self.API_BASE}/users/login",
                json=login_data,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                self._token = data.get('token_id')
                
                if self._token:
                    # Set the token header for subsequent requests
                    self.session.headers['x-one-vue-token'] = self._token
                    print("   ✅ Login successful!")
                    self._logged_in = True
                    
                    # Try to get account info
                    self._fetch_account_info()
                    return True
                else:
                    print("   ⚠️ Login response missing token")
                    return False
            elif response.status_code == 401:
                print("   ⚠️ Login failed - invalid credentials")
                return False
            else:
                print(f"   ⚠️ Login failed - HTTP {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                except:
                    pass
                return False
                
        except requests.exceptions.Timeout:
            print("   ⚠️ Login request timeout")
            return False
        except requests.exceptions.RequestException as e:
            print(f"   ⚠️ Login error: {e}")
            return False
        except Exception as e:
            print(f"   ⚠️ Unexpected error during login: {e}")
            return False
    
    def _fetch_account_info(self):
        """Fetch account and hub information after login."""
        try:
            # Get user account info
            response = self.session.get(
                f"{self.API_BASE}/users/me",
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                # Account ID might be in various places
                self._account_id = data.get('account_id') or data.get('id')
                print(f"   Account ID: {self._account_id}")
                
                # Try to get hubs
                if self._account_id:
                    self._fetch_hubs()
        except Exception as e:
            print(f"   ⚠️ Could not fetch account info: {e}")
    
    def _fetch_hubs(self):
        """Fetch hub/device information."""
        try:
            response = self.session.get(
                f"{self.API_BASE}/accounts/{self._account_id}/hubs",
                timeout=30
            )
            
            if response.status_code == 200:
                hubs = response.json()
                if isinstance(hubs, list) and hubs:
                    self._hub_id = hubs[0].get('id')
                    hub_name = hubs[0].get('name', 'Unknown')
                    print(f"   Hub: {hub_name} (ID: {self._hub_id})")
                elif isinstance(hubs, dict):
                    # Might be wrapped in a response object
                    hub_list = hubs.get('hubs', [])
                    if hub_list:
                        self._hub_id = hub_list[0].get('id')
                        print(f"   Hub ID: {self._hub_id}")
        except Exception as e:
            print(f"   ⚠️ Could not fetch hubs: {e}")
    
    def get_current_conditions(self) -> Optional[Dict[str, Any]]:
        """
        Get current weather conditions from all sensors.
        
        Returns:
            Dictionary with current conditions or None on error
        """
        if not self._logged_in:
            if not self.login():
                return None
        
        if not self._account_id or not self._hub_id:
            print("   ⚠️ Missing account or hub ID")
            return None
        
        try:
            print("📊 Fetching current conditions...")
            
            response = self.session.get(
                f"{self.API_BASE}/accounts/{self._account_id}/dashboard/hubs/{self._hub_id}",
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"   ⚠️ Dashboard request failed: HTTP {response.status_code}")
                return None
            
            data = response.json()
            
            # Parse the response to extract sensor readings
            conditions = {
                'raw_data': data,
                'devices': []
            }
            
            devices = data.get('devices', [])
            for device in devices:
                device_info = {
                    'name': device.get('name', 'Unknown'),
                    'model': device.get('model_code', ''),
                    'battery': device.get('battery_level', ''),
                    'signal': device.get('signal_strength', 0),
                    'last_check_in': device.get('last_check_in_at', ''),
                    'sensors': {}
                }
                
                # Extract high/low temps if available
                if device.get('temp_high_value'):
                    device_info['temp_high'] = float(device['temp_high_value'])
                if device.get('temp_low_value'):
                    device_info['temp_low'] = float(device['temp_low_value'])
                
                # Extract individual sensor readings
                sensors = device.get('sensors', [])
                for sensor in sensors:
                    sensor_name = sensor.get('sensor_code', sensor.get('sensor_name', 'Unknown'))
                    value = sensor.get('last_reading_value')
                    unit = sensor.get('chart_unit', sensor.get('display_unit', ''))
                    
                    if value is not None:
                        try:
                            device_info['sensors'][sensor_name] = {
                                'value': float(value),
                                'unit': unit
                            }
                        except ValueError:
                            device_info['sensors'][sensor_name] = {
                                'value': value,
                                'unit': unit
                            }
                
                conditions['devices'].append(device_info)
            
            # Extract key values for easy access
            for device in conditions['devices']:
                sensors = device.get('sensors', {})
                if 'Temperature' in sensors:
                    conditions['temperature'] = sensors['Temperature']['value']
                if 'Humidity' in sensors:
                    conditions['humidity'] = sensors['Humidity']['value']
                if 'Wind Speed' in sensors:
                    conditions['wind_speed'] = sensors['Wind Speed']['value']
                if 'Rain' in sensors:
                    conditions['rain'] = sensors['Rain']['value']
                if 'Barometric Pressure' in sensors:
                    conditions['pressure'] = sensors['Barometric Pressure']['value']
                if 'Dew Point' in sensors:
                    conditions['dewpoint'] = sensors['Dew Point']['value']
                    
                # Also check for temp high/low
                if 'temp_high' in device and 'temp_high' not in conditions:
                    conditions['temp_high'] = device['temp_high']
                if 'temp_low' in device and 'temp_low' not in conditions:
                    conditions['temp_low'] = device['temp_low']
            
            print(f"   ✅ Found {len(conditions['devices'])} device(s)")
            return conditions
            
        except Exception as e:
            print(f"   ⚠️ Error fetching conditions: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_daily_summary(self, target_date: date) -> Optional[WeatherObservation]:
        """
        Get daily weather summary for a specific date.
        
        Note: MyAcurite only stores 31 days of history.
        
        Args:
            target_date: The date to fetch data for
            
        Returns:
            WeatherObservation or None on error
        """
        if not self._logged_in:
            if not self.login():
                return None
        
        # MyAcurite's historical data access is limited
        # This would require accessing chart data or CSV export
        print(f"   ⚠️ Historical data for {target_date} requires CSV export")
        return None
    
    def test_connection(self) -> bool:
        """
        Test the connection to MyAcurite.
        
        Returns:
            True if connection and login successful
        """
        return self.login()
    
    def logout(self):
        """Log out and clear session."""
        self._token = None
        self._account_id = None
        self._hub_id = None
        self.session.headers.pop('x-one-vue-token', None)
        self.session.cookies.clear()
        self._logged_in = False
        print("🔓 Logged out of MyAcurite")
