"""
ApexCharts integration for UtilityHQ
Embeds ApexCharts (JavaScript) in PyQt6 using QWebEngineView for 3D cylinder-style charts.

Note: Requires PyQt6-WebEngine to be installed:
    pip install PyQt6-WebEngine
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy, QLabel
from PyQt6.QtCore import QUrl
from typing import List, Dict, Any
import json

# Try to import WebEngine, set flag if not available
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False
    QWebEngineView = QWidget  # Fallback to basic widget


class ApexChartWidget(QWebEngineView if WEBENGINE_AVAILABLE else QWidget):
    """Base widget for embedding ApexCharts in PyQt6."""
    
    # Carbon Sage theme colors
    COLORS = {
        'electric': '#f39c12',
        'electric_light': '#f1c40f',
        'gas': '#c0392b',
        'gas_light': '#e74c3c',
        'water': '#2980b9',
        'water_light': '#3498db',
        'heating': '#c0392b',
        'heating_light': '#e74c3c',
        'cooling': '#2980b9',
        'cooling_light': '#3498db',
        'economy': '#27ae60',
        'economy_light': '#2ecc71',
        'accent': '#86efac',
        'text': '#a3a3a3',
        'muted': '#737373',
        'grid': '#2e2e2e',
        'background': '#1e1e1e',
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(250)
        
        if WEBENGINE_AVAILABLE:
            # Set dark background color to match theme (prevents white flash)
            from PyQt6.QtGui import QColor
            self.page().setBackgroundColor(QColor("#1e1e1e"))
        else:
            # Show fallback message
            layout = QVBoxLayout(self)
            label = QLabel("PyQt6-WebEngine not installed.\nInstall with: pip install PyQt6-WebEngine")
            label.setStyleSheet("color: #737373; font-size: 11px;")
            layout.addWidget(label)
        
    def _get_base_html(self, chart_div_id: str, chart_config: str) -> str:
        """Generate the HTML template with ApexCharts."""
        return f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <script src="https://cdn.jsdelivr.net/npm/apexcharts"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            background: {self.COLORS['background']}; 
            font-family: 'Segoe UI', sans-serif;
            overflow: hidden;
        }}
        #{chart_div_id} {{
            width: 100%;
            height: 100vh;
        }}
        .apexcharts-tooltip {{
            background: #242424 !important;
            border: 1px solid #3a3a3a !important;
            color: #fafafa !important;
        }}
        .apexcharts-tooltip-title {{
            background: #1a1a1a !important;
            border-bottom: 1px solid #3a3a3a !important;
        }}
    </style>
</head>
<body>
    <div id="{chart_div_id}"></div>
    <script>
        const textColor = '{self.COLORS["text"]}';
        const mutedColor = '{self.COLORS["muted"]}';
        const gridColor = '{self.COLORS["grid"]}';
        
        {chart_config}
    </script>
</body>
</html>
'''

    def render_chart(self, chart_div_id: str, chart_config: str):
        """Render the chart with the given configuration."""
        if not WEBENGINE_AVAILABLE:
            return  # Skip rendering if WebEngine not available
        html = self._get_base_html(chart_div_id, chart_config)
        self.setHtml(html)


class MonthlyCostChart(ApexChartWidget):
    """Monthly utility costs - 3D cylinder bar chart."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(280)
        
    def update_data(self, electric_data: List[float], gas_data: List[float], 
                    water_data: List[float], months: List[str] = None):
        """Update chart with monthly cost data for each utility."""
        if months is None:
            months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        config = f'''
        new ApexCharts(document.getElementById('costChart'), {{
            series: [
                {{ name: 'Electric', data: {json.dumps(electric_data)} }},
                {{ name: 'Gas', data: {json.dumps(gas_data)} }},
                {{ name: 'Water', data: {json.dumps(water_data)} }}
            ],
            chart: {{ 
                type: 'bar', 
                height: '100%',
                toolbar: {{ show: false }}, 
                background: 'transparent',
                animations: {{
                    enabled: true,
                    easing: 'easeinout',
                    speed: 800
                }}
            }},
            colors: ['{self.COLORS["electric"]}', '{self.COLORS["gas"]}', '{self.COLORS["water"]}'],
            fill: {{
                type: 'gradient',
                gradient: {{
                    shade: 'light',
                    type: 'horizontal',
                    shadeIntensity: 0.8,
                    gradientToColors: ['{self.COLORS["electric_light"]}', '{self.COLORS["gas_light"]}', '{self.COLORS["water_light"]}'],
                    inverseColors: false,
                    opacityFrom: 1,
                    opacityTo: 0.85,
                    stops: [0, 50, 100]
                }}
            }},
            plotOptions: {{ 
                bar: {{ 
                    horizontal: false,
                    columnWidth: '70%',
                    borderRadius: 2,
                    borderRadiusApplication: 'end'
                }}
            }},
            stroke: {{
                show: true,
                width: 1,
                colors: ['rgba(0,0,0,0.3)']
            }},
            dataLabels: {{ enabled: false }},
            xaxis: {{ 
                categories: {json.dumps(months)},
                labels: {{ style: {{ colors: mutedColor, fontSize: '10px' }} }},
                axisBorder: {{ show: false }},
                axisTicks: {{ show: false }}
            }},
            yaxis: {{ 
                labels: {{ 
                    style: {{ colors: mutedColor, fontSize: '10px' }},
                    formatter: function(val) {{ return '$' + val.toFixed(0); }}
                }}
            }},
            grid: {{ borderColor: gridColor, strokeDashArray: 0 }},
            legend: {{ 
                position: 'top',
                horizontalAlign: 'right',
                labels: {{ colors: textColor }}, 
                fontSize: '11px'
            }},
            tooltip: {{ theme: 'dark' }}
        }}).render();
        '''
        
        self.render_chart('costChart', config)


class DemandCostChart(ApexChartWidget):
    """Weather demand with cost/day line - mixed bar/line chart."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(280)
        
    def update_data(self, matrix_data: List[Dict] = None, heating_data: List[float] = None, 
                    cooling_data: List[float] = None, cost_per_day: List[float] = None, 
                    categories: List[str] = None):
        """
        Update chart with demand data.
        
        Accepts either:
        - matrix_data: List of dicts with 'year', 'avg_heating', 'avg_cooling', 'cost_per_day'
        - Or individual arrays: heating_data, cooling_data, cost_per_day, categories
        """
        # Handle matrix_data format (from V80)
        if matrix_data is not None:
            categories = [str(d['year']) for d in matrix_data]
            heating_data = [d.get('avg_heating', 0) * 100 for d in matrix_data]
            cooling_data = [d.get('avg_cooling', 0) * 100 for d in matrix_data]
            cost_per_day = [d.get('cost_per_day', 0) for d in matrix_data]
        
        if categories is None:
            categories = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                          'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        # Calculate max for y-axis
        max_demand = max(max(heating_data or [0]), max(cooling_data or [0]), 40)
        max_cpd = max(cost_per_day or [0]) if cost_per_day else 10
        
        config = f'''
        new ApexCharts(document.getElementById('demandChart'), {{
            series: [
                {{ name: 'Heating', type: 'bar', data: {json.dumps(heating_data)} }},
                {{ name: 'Cooling', type: 'bar', data: {json.dumps(cooling_data)} }},
                {{ name: '$/Day', type: 'line', data: {json.dumps(cost_per_day)} }}
            ],
            chart: {{ 
                type: 'line', 
                height: '100%',
                toolbar: {{ show: false }}, 
                background: 'transparent'
            }},
            colors: ['{self.COLORS["heating"]}', '{self.COLORS["cooling"]}', '{self.COLORS["accent"]}'],
            fill: {{
                type: ['gradient', 'gradient', 'solid'],
                gradient: {{
                    shade: 'light',
                    type: 'horizontal',
                    shadeIntensity: 0.8,
                    gradientToColors: ['{self.COLORS["heating_light"]}', '{self.COLORS["cooling_light"]}'],
                    inverseColors: false,
                    opacityFrom: 1,
                    opacityTo: 0.85,
                    stops: [0, 50, 100]
                }}
            }},
            stroke: {{ 
                width: [1, 1, 3], 
                curve: 'smooth',
                colors: ['rgba(0,0,0,0.3)', 'rgba(0,0,0,0.3)', '{self.COLORS["accent"]}']
            }},
            plotOptions: {{ 
                bar: {{ 
                    columnWidth: '65%',
                    borderRadius: 2,
                    borderRadiusApplication: 'end'
                }}
            }},
            dataLabels: {{ enabled: false }},
            xaxis: {{ 
                categories: {json.dumps(categories)},
                labels: {{ style: {{ colors: mutedColor, fontSize: '10px' }} }},
                axisBorder: {{ show: false }},
                axisTicks: {{ show: false }}
            }},
            yaxis: [
                {{ 
                    labels: {{ 
                        style: {{ colors: mutedColor, fontSize: '10px' }},
                        formatter: function(val) {{ return val.toFixed(0) + '%'; }}
                    }},
                    max: {max_demand * 1.1:.0f}
                }},
                {{ 
                    opposite: true,
                    labels: {{ 
                        style: {{ colors: mutedColor, fontSize: '10px' }},
                        formatter: function(val) {{ return '$' + val.toFixed(2); }}
                    }},
                    max: {max_cpd * 1.3:.2f}
                }}
            ],
            grid: {{ borderColor: gridColor, strokeDashArray: 0 }},
            legend: {{ 
                position: 'top',
                horizontalAlign: 'right',
                labels: {{ colors: textColor }}, 
                fontSize: '11px'
            }},
            tooltip: {{ theme: 'dark' }},
            title: {{
                text: 'Weather Demand vs Cost Per Day',
                align: 'left',
                style: {{
                    fontSize: '13px',
                    fontWeight: 600,
                    color: '#fafafa'
                }}
            }}
        }}).render();
        '''
        
        self.render_chart('demandChart', config)


class DegreeDaysChart(ApexChartWidget):
    """Degree days by year - 3D cylinder grouped bar chart."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(260)
        
    def update_data(self, degree_days_data: List[Dict] = None, heating_days: List[float] = None, 
                    cooling_days: List[float] = None, economy_days: List[float] = None, 
                    years: List[str] = None):
        """
        Update chart with degree day data.
        
        Accepts either:
        - degree_days_data: List of dicts with 'year', 'heating_days', 'cooling_days', 'economy_days'
        - Or individual arrays
        """
        # Handle degree_days_data format (from V80)
        if degree_days_data is not None:
            years = [str(d['year']) for d in degree_days_data]
            heating_days = [d.get('heating_days', 0) for d in degree_days_data]
            cooling_days = [d.get('cooling_days', 0) for d in degree_days_data]
            economy_days = [d.get('economy_days', 0) for d in degree_days_data]
        
        if not years:
            years = []
        if not heating_days:
            heating_days = []
        if not cooling_days:
            cooling_days = []
        if not economy_days:
            economy_days = []
            
        max_val = max(max(heating_days or [0]), max(cooling_days or [0]), max(economy_days or [0]), 100)
        
        config = f'''
        new ApexCharts(document.getElementById('degreeDaysChart'), {{
            series: [
                {{ name: 'Heating', data: {json.dumps(heating_days)} }},
                {{ name: 'Cooling', data: {json.dumps(cooling_days)} }},
                {{ name: 'Economy', data: {json.dumps(economy_days)} }}
            ],
            chart: {{ 
                type: 'bar', 
                height: '100%',
                toolbar: {{ show: false }}, 
                background: 'transparent'
            }},
            colors: ['{self.COLORS["heating"]}', '{self.COLORS["cooling"]}', '{self.COLORS["economy"]}'],
            fill: {{
                type: 'gradient',
                gradient: {{
                    shade: 'light',
                    type: 'horizontal',
                    shadeIntensity: 0.8,
                    gradientToColors: ['{self.COLORS["heating_light"]}', '{self.COLORS["cooling_light"]}', '{self.COLORS["economy_light"]}'],
                    inverseColors: false,
                    opacityFrom: 1,
                    opacityTo: 0.85,
                    stops: [0, 50, 100]
                }}
            }},
            plotOptions: {{ 
                bar: {{ 
                    horizontal: false,
                    columnWidth: '75%',
                    borderRadius: 2,
                    borderRadiusApplication: 'end'
                }}
            }},
            stroke: {{
                show: true,
                width: 1,
                colors: ['rgba(0,0,0,0.3)']
            }},
            dataLabels: {{ enabled: false }},
            xaxis: {{ 
                categories: {json.dumps(years)},
                labels: {{ style: {{ colors: mutedColor, fontSize: '10px' }} }},
                axisBorder: {{ show: false }},
                axisTicks: {{ show: false }}
            }},
            yaxis: {{ 
                labels: {{ style: {{ colors: mutedColor, fontSize: '10px' }} }},
                max: {max_val * 1.15:.0f}
            }},
            grid: {{ borderColor: gridColor, strokeDashArray: 0 }},
            legend: {{ 
                position: 'top',
                horizontalAlign: 'center',
                labels: {{ colors: textColor }}, 
                fontSize: '11px'
            }},
            tooltip: {{ theme: 'dark' }},
            title: {{
                text: 'Degree Days by Year',
                align: 'left',
                style: {{
                    fontSize: '13px',
                    fontWeight: 600,
                    color: '#fafafa'
                }}
            }}
        }}).render();
        '''
        
        self.render_chart('degreeDaysChart', config)


class MonthlyDemandChart(ApexChartWidget):
    """Monthly demand percentage by year - 3D cylinder grouped bar chart with average line."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(280)
        
    def update_data(self, monthly_data: Dict):
        """
        Update chart with monthly demand data.
        
        Args:
            monthly_data: Dict with keys: 
                'years': list of years available
                'data': dict of year -> [12 monthly values]
                'averages': list of 12 monthly average values
        """
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        # Get last 5 years
        all_years = sorted(monthly_data.get('years', []), reverse=True)
        years_to_show = sorted(all_years[:5])
        
        # Color palette for years (oldest to newest)
        year_colors = ['#6366f1', '#8b5cf6', '#a855f7', '#3498db', '#27ae60']
        year_colors_light = ['#818cf8', '#a78bfa', '#c084fc', '#5dade2', '#2ecc71']
        
        # Build series
        series = []
        colors = []
        gradient_colors = []
        year_data = monthly_data.get('data', {})
        
        for i, year in enumerate(years_to_show):
            if year in year_data:
                data = [(v or 0) * 100 for v in year_data[year]]  # Convert to percentage
                series.append({'name': str(year), 'type': 'bar', 'data': data})
                color_idx = min(i, len(year_colors) - 1)
                colors.append(year_colors[color_idx])
                gradient_colors.append(year_colors_light[color_idx])
        
        # Add average line
        averages = monthly_data.get('averages', [])
        if averages:
            avg_data = [(v or 0) * 100 for v in averages]
            series.append({'name': 'Average', 'type': 'line', 'data': avg_data})
            colors.append(self.COLORS['accent'])
            gradient_colors.append(self.COLORS['accent'])
        
        # Calculate max
        all_values = []
        for s in series:
            all_values.extend(s['data'])
        max_val = max(all_values) if all_values else 100
        
        # Build stroke widths (1 for bars, 3 for line)
        stroke_widths = [1] * (len(series) - 1) + [3] if averages else [1] * len(series)
        
        config = f'''
        new ApexCharts(document.getElementById('monthlyDemandChart'), {{
            series: {json.dumps(series)},
            chart: {{ 
                type: 'line', 
                height: '100%',
                toolbar: {{ show: false }}, 
                background: 'transparent'
            }},
            colors: {json.dumps(colors)},
            fill: {{
                type: {json.dumps(['gradient'] * (len(series) - 1) + ['solid'] if averages else ['gradient'] * len(series))},
                gradient: {{
                    shade: 'light',
                    type: 'horizontal',
                    shadeIntensity: 0.8,
                    gradientToColors: {json.dumps(gradient_colors)},
                    inverseColors: false,
                    opacityFrom: 1,
                    opacityTo: 0.85,
                    stops: [0, 50, 100]
                }}
            }},
            stroke: {{ 
                width: {json.dumps(stroke_widths)}, 
                curve: 'smooth'
            }},
            plotOptions: {{ 
                bar: {{ 
                    columnWidth: '70%',
                    borderRadius: 2,
                    borderRadiusApplication: 'end'
                }}
            }},
            dataLabels: {{ enabled: false }},
            xaxis: {{ 
                categories: {json.dumps(months)},
                labels: {{ style: {{ colors: mutedColor, fontSize: '10px' }} }},
                axisBorder: {{ show: false }},
                axisTicks: {{ show: false }}
            }},
            yaxis: {{ 
                labels: {{ 
                    style: {{ colors: mutedColor, fontSize: '10px' }},
                    formatter: function(val) {{ return val.toFixed(0) + '%'; }}
                }},
                max: {min(100, max_val * 1.15):.0f}
            }},
            grid: {{ borderColor: gridColor, strokeDashArray: 0 }},
            legend: {{ 
                position: 'top',
                horizontalAlign: 'right',
                labels: {{ colors: textColor }}, 
                fontSize: '10px'
            }},
            tooltip: {{ theme: 'dark' }}
        }}).render();
        '''
        
        self.render_chart('monthlyDemandChart', config)


class CPDIndexChart(ApexChartWidget):
    """Cost Per Degree day index - Stacked bar with line overlay."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(280)
        
    def update_data(self, matrix_data: List[Dict] = None, heating_cpd: List[float] = None, 
                    cooling_cpd: List[float] = None, cpd_line: List[float] = None, 
                    years: List[str] = None):
        """
        Update chart with CPD index data.
        
        Accepts either:
        - matrix_data: List of dicts with 'year', 'cpd_index', 'pct_avg_cost', etc.
        - Or individual arrays
        """
        # Handle matrix_data format (from V80) 
        if matrix_data is not None:
            years = [str(d['year']) for d in matrix_data]
            # Extract CPD-related values
            heating_cpd = [d.get('avg_heating', 0) * 100 for d in matrix_data]  # Heating %
            cooling_cpd = [d.get('avg_cooling', 0) * 100 for d in matrix_data]  # Cooling %
            cpd_line = [d.get('pct_avg_cost', 0) * 100 for d in matrix_data]  # % of average as line
        
        if not years:
            years = []
        if not heating_cpd:
            heating_cpd = []
        if not cooling_cpd:
            cooling_cpd = []
        if not cpd_line:
            cpd_line = []
            
        max_bar = max(
            max([h + c for h, c in zip(heating_cpd, cooling_cpd)]) if heating_cpd and cooling_cpd else 0,
            100
        )
        max_line = max(cpd_line) if cpd_line else 100
        
        config = f'''
        new ApexCharts(document.getElementById('cpdChart'), {{
            series: [
                {{ name: 'Heating %', type: 'bar', data: {json.dumps(heating_cpd)} }},
                {{ name: 'Cooling %', type: 'bar', data: {json.dumps(cooling_cpd)} }},
                {{ name: '% Avg Cost', type: 'line', data: {json.dumps(cpd_line)} }}
            ],
            chart: {{ 
                type: 'line',
                stacked: false,
                height: '100%',
                toolbar: {{ show: false }}, 
                background: 'transparent'
            }},
            colors: ['{self.COLORS["heating"]}', '{self.COLORS["cooling"]}', '{self.COLORS["accent"]}'],
            fill: {{
                type: ['gradient', 'gradient', 'solid'],
                gradient: {{
                    shade: 'light',
                    type: 'horizontal',
                    shadeIntensity: 0.8,
                    gradientToColors: ['{self.COLORS["heating_light"]}', '{self.COLORS["cooling_light"]}'],
                    inverseColors: false,
                    opacityFrom: 1,
                    opacityTo: 0.85,
                    stops: [0, 50, 100]
                }}
            }},
            stroke: {{ 
                width: [1, 1, 3], 
                curve: 'smooth',
                colors: ['rgba(0,0,0,0.3)', 'rgba(0,0,0,0.3)', '{self.COLORS["accent"]}']
            }},
            plotOptions: {{ 
                bar: {{ 
                    columnWidth: '60%',
                    borderRadius: 2
                }}
            }},
            dataLabels: {{ enabled: false }},
            xaxis: {{ 
                categories: {json.dumps(years)},
                labels: {{ style: {{ colors: mutedColor, fontSize: '10px' }} }},
                axisBorder: {{ show: false }},
                axisTicks: {{ show: false }}
            }},
            yaxis: [
                {{ 
                    labels: {{ 
                        style: {{ colors: mutedColor, fontSize: '10px' }},
                        formatter: function(val) {{ return val.toFixed(0) + '%'; }}
                    }},
                    max: {max_bar * 1.2:.0f}
                }},
                {{ 
                    opposite: true,
                    labels: {{ 
                        style: {{ colors: mutedColor, fontSize: '10px' }},
                        formatter: function(val) {{ return val.toFixed(0) + '%'; }}
                    }},
                    max: {max(max_line * 1.2, 150):.0f}
                }}
            ],
            grid: {{ borderColor: gridColor, strokeDashArray: 0 }},
            legend: {{ 
                position: 'top',
                horizontalAlign: 'right',
                labels: {{ colors: textColor }}, 
                fontSize: '10px'
            }},
            tooltip: {{ theme: 'dark' }},
            title: {{
                text: 'CPD Index by Year',
                align: 'left',
                style: {{
                    fontSize: '13px',
                    fontWeight: 600,
                    color: '#fafafa'
                }}
            }}
        }}).render();
        '''
        
        self.render_chart('cpdChart', config)


class UtilityLineChart(ApexChartWidget):
    """Utility cost/usage line chart - Average, Previous Year, Current Year."""
    
    UTILITY_COLORS = {
        'electric': ('#f39c12', '#f1c40f', '#7a530a'),  # current, previous, average
        'gas': ('#e74c3c', '#c0392b', '#6e211a'),
        'water': ('#3498db', '#2980b9', '#185270'),
    }
    
    def __init__(self, title: str, utility_type: str, y_label: str = "$", parent=None):
        super().__init__(parent)
        self.title = title
        self.utility_type = utility_type
        self.y_label = y_label
        self.setMinimumHeight(260)
        
    def update_data(self, average: List[float], previous_year: List[float], current_year: List[float],
                    prev_year_label: int = None, curr_year_label: int = None):
        """Update chart with yearly data. Each list has 12 values (one per month)."""
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        colors = self.UTILITY_COLORS.get(self.utility_type, self.UTILITY_COLORS['electric'])
        
        prev_label = str(prev_year_label) if prev_year_label else 'Previous'
        curr_label = str(curr_year_label) if curr_year_label else 'Current'
        
        # Calculate max for y-axis
        all_vals = [v for v in average + previous_year + current_year if v and v > 0]
        max_val = max(all_vals) * 1.1 if all_vals else 100
        
        is_currency = '$' in self.y_label
        formatter = "function(val) { return '$' + val.toFixed(0); }" if is_currency else "function(val) { return val.toFixed(0); }"
        
        config = f'''
        new ApexCharts(document.getElementById('utilityChart'), {{
            series: [
                {{ name: 'Average', data: {json.dumps(average)} }},
                {{ name: '{prev_label}', data: {json.dumps(previous_year)} }},
                {{ name: '{curr_label}', data: {json.dumps(current_year)} }}
            ],
            chart: {{ 
                type: 'line', 
                height: '100%',
                toolbar: {{ show: false }}, 
                background: 'transparent'
            }},
            colors: ['{colors[2]}', '{colors[1]}', '{colors[0]}'],
            stroke: {{ 
                width: [2, 2, 3], 
                curve: 'smooth',
                dashArray: [5, 0, 0]
            }},
            markers: {{
                size: [0, 4, 5],
                strokeWidth: 0
            }},
            dataLabels: {{ enabled: false }},
            xaxis: {{ 
                categories: {json.dumps(months)},
                labels: {{ style: {{ colors: mutedColor, fontSize: '10px' }} }},
                axisBorder: {{ show: false }},
                axisTicks: {{ show: false }}
            }},
            yaxis: {{ 
                labels: {{ 
                    style: {{ colors: mutedColor, fontSize: '10px' }},
                    formatter: {formatter}
                }},
                max: {max_val:.0f}
            }},
            grid: {{ borderColor: gridColor, strokeDashArray: 0 }},
            legend: {{ 
                position: 'top',
                horizontalAlign: 'right',
                labels: {{ colors: textColor }}, 
                fontSize: '11px'
            }},
            tooltip: {{ theme: 'dark' }},
            title: {{
                text: '{self.title}',
                align: 'left',
                style: {{
                    fontSize: '13px',
                    fontWeight: 600,
                    color: '#fafafa'
                }}
            }}
        }}).render();
        '''
        
        self.render_chart('utilityChart', config)


class DonutChart(ApexChartWidget):
    """Cost distribution donut chart."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(220)
        
    def update_data(self, electric: float, gas: float, water: float):
        """Update chart with cost distribution."""
        total = electric + gas + water
        
        config = f'''
        new ApexCharts(document.getElementById('donutChart'), {{
            series: [{electric:.0f}, {gas:.0f}, {water:.0f}],
            chart: {{ 
                type: 'donut', 
                height: '100%',
                background: 'transparent',
                dropShadow: {{
                    enabled: true,
                    top: 3,
                    left: 0,
                    blur: 8,
                    opacity: 0.35
                }}
            }},
            colors: ['{self.COLORS["electric"]}', '{self.COLORS["gas"]}', '{self.COLORS["water"]}'],
            labels: ['Electric', 'Gas', 'Water'],
            fill: {{
                type: 'gradient',
                gradient: {{
                    shade: 'dark',
                    type: 'diagonal1',
                    shadeIntensity: 0.5,
                    gradientToColors: ['{self.COLORS["electric_light"]}', '{self.COLORS["gas_light"]}', '{self.COLORS["water_light"]}'],
                    opacityFrom: 1,
                    opacityTo: 0.85
                }}
            }},
            plotOptions: {{
                pie: {{
                    donut: {{
                        size: '60%',
                        labels: {{
                            show: true,
                            total: {{
                                show: true,
                                label: 'Total',
                                color: textColor,
                                fontSize: '11px',
                                formatter: function() {{ return '${total:.0f}'; }}
                            }}
                        }}
                    }},
                    expandOnClick: true
                }}
            }},
            stroke: {{ width: 2, colors: ['#1e1e1e'] }},
            dataLabels: {{ enabled: false }},
            legend: {{ 
                position: 'bottom',
                labels: {{ colors: textColor }}, 
                fontSize: '10px'
            }},
            tooltip: {{ theme: 'dark' }}
        }}).render();
        '''
        
        self.render_chart('donutChart', config)


class DailyDemandScatterChart(ApexChartWidget):
    """Daily weather demand scatter chart with trend lines."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(350)
        
    def update_data(self, daily_data: Dict):
        """
        Update chart with daily demand data.
        
        Args:
            daily_data: Dict with keys:
                'current_year': int
                'previous_year': int  
                'data': dict of year -> [366 daily values]
        """
        current_year = daily_data.get('current_year', 2025)
        previous_year = daily_data.get('previous_year', 2024)
        year_data = daily_data.get('data', {})
        
        # Build scatter data points
        prev_points = []
        curr_points = []
        
        if previous_year in year_data:
            for day, val in enumerate(year_data[previous_year], 1):
                if val is not None and val > 0:
                    prev_points.append({'x': day, 'y': round(val * 100, 1)})
        
        if current_year in year_data:
            for day, val in enumerate(year_data[current_year], 1):
                if val is not None and val > 0:
                    curr_points.append({'x': day, 'y': round(val * 100, 1)})
        
        max_demand = 100
        if prev_points:
            max_demand = max(max_demand, max(p['y'] for p in prev_points))
        if curr_points:
            max_demand = max(max_demand, max(p['y'] for p in curr_points))
        
        config = f'''
        new ApexCharts(document.getElementById('scatterChart'), {{
            series: [
                {{ name: '{previous_year}', data: {json.dumps(prev_points)} }},
                {{ name: '{current_year}', data: {json.dumps(curr_points)} }}
            ],
            chart: {{ 
                type: 'scatter', 
                height: '100%',
                toolbar: {{ show: false }}, 
                background: 'transparent',
                zoom: {{ enabled: false }}
            }},
            colors: ['#6366f1', '#27ae60'],
            markers: {{
                size: 4,
                strokeWidth: 0
            }},
            xaxis: {{ 
                type: 'numeric',
                min: 1,
                max: 366,
                tickAmount: 12,
                labels: {{ 
                    style: {{ colors: mutedColor, fontSize: '10px' }},
                    formatter: function(val) {{ return Math.round(val); }}
                }},
                title: {{
                    text: 'Day of Year',
                    style: {{ color: mutedColor, fontSize: '10px' }}
                }},
                axisBorder: {{ show: false }},
                axisTicks: {{ show: false }}
            }},
            yaxis: {{ 
                min: 0,
                max: {min(120, max_demand * 1.15):.0f},
                labels: {{ 
                    style: {{ colors: mutedColor, fontSize: '10px' }},
                    formatter: function(val) {{ return val.toFixed(0) + '%'; }}
                }},
                title: {{
                    text: 'Demand %',
                    style: {{ color: mutedColor, fontSize: '10px' }}
                }}
            }},
            grid: {{ borderColor: gridColor, strokeDashArray: 0 }},
            legend: {{ 
                position: 'top',
                horizontalAlign: 'right',
                labels: {{ colors: textColor }}, 
                fontSize: '11px'
            }},
            tooltip: {{ theme: 'dark' }},
            title: {{
                text: 'Daily Weather Demand',
                align: 'left',
                style: {{
                    fontSize: '13px',
                    fontWeight: 600,
                    color: '#fafafa'
                }}
            }}
        }}).render();
        '''
        
        self.render_chart('scatterChart', config)


class RainGaugeChart(ApexChartWidget):
    """Monthly rainfall bar chart by year."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(280)
        
    def update_data(self, rainfall_data: Dict):
        """
        Update chart with monthly rainfall data.
        
        Args:
            rainfall_data: Dict with 'years' list and 'data' dict of year -> [12 monthly values]
        """
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        years = sorted(rainfall_data.get('years', []), reverse=True)[:5]
        years = sorted(years)
        
        # Color palette
        year_colors = ['#3498db', '#2980b9', '#1abc9c', '#16a085', '#27ae60']
        year_colors_light = ['#5dade2', '#5499c7', '#48c9b0', '#1abc9c', '#2ecc71']
        
        series = []
        colors = []
        gradient_colors = []
        year_data = rainfall_data.get('data', {})
        
        for i, year in enumerate(years):
            if year in year_data:
                series.append({'name': str(year), 'data': year_data[year]})
                color_idx = min(i, len(year_colors) - 1)
                colors.append(year_colors[color_idx])
                gradient_colors.append(year_colors_light[color_idx])
        
        # Calculate max
        all_vals = []
        for s in series:
            all_vals.extend(s['data'])
        max_val = max(all_vals) if all_vals else 10
        
        config = f'''
        new ApexCharts(document.getElementById('rainChart'), {{
            series: {json.dumps(series)},
            chart: {{ 
                type: 'bar', 
                height: '100%',
                toolbar: {{ show: false }}, 
                background: 'transparent'
            }},
            colors: {json.dumps(colors)},
            fill: {{
                type: 'gradient',
                gradient: {{
                    shade: 'light',
                    type: 'horizontal',
                    shadeIntensity: 0.8,
                    gradientToColors: {json.dumps(gradient_colors)},
                    inverseColors: false,
                    opacityFrom: 1,
                    opacityTo: 0.85,
                    stops: [0, 50, 100]
                }}
            }},
            plotOptions: {{ 
                bar: {{ 
                    columnWidth: '70%',
                    borderRadius: 2,
                    borderRadiusApplication: 'end'
                }}
            }},
            stroke: {{
                show: true,
                width: 1,
                colors: ['rgba(0,0,0,0.3)']
            }},
            dataLabels: {{ enabled: false }},
            xaxis: {{ 
                categories: {json.dumps(months)},
                labels: {{ style: {{ colors: mutedColor, fontSize: '10px' }} }},
                axisBorder: {{ show: false }},
                axisTicks: {{ show: false }}
            }},
            yaxis: {{ 
                labels: {{ 
                    style: {{ colors: mutedColor, fontSize: '10px' }},
                    formatter: function(val) {{ return val.toFixed(1) + '"'; }}
                }},
                max: {max_val * 1.2:.1f}
            }},
            grid: {{ borderColor: gridColor, strokeDashArray: 0 }},
            legend: {{ 
                position: 'top',
                horizontalAlign: 'right',
                labels: {{ colors: textColor }}, 
                fontSize: '10px'
            }},
            tooltip: {{ theme: 'dark' }},
            title: {{
                text: 'Monthly Rainfall',
                align: 'left',
                style: {{
                    fontSize: '13px',
                    fontWeight: 600,
                    color: '#fafafa'
                }}
            }}
        }}).render();
        '''
        
        self.render_chart('rainChart', config)
