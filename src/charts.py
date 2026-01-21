"""
Utilities Tracker - Charts Module
Professional Qt Charts for utility data visualization.
"""

from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSizePolicy
from PyQt6.QtCore import Qt, QPointF, QMargins
from PyQt6.QtGui import QColor, QPainter, QFont, QLinearGradient, QPen, QBrush
from PyQt6.QtCharts import (
    QChart, QChartView, QLineSeries, QBarSeries, QBarSet, QPieSeries,
    QAreaSeries, QBarCategoryAxis, QValueAxis, QDateTimeAxis,
    QPieSlice, QStackedBarSeries, QLegend, QSplineSeries
)


class ChartColors:
    """Color palette for charts - matches the Carbon Sage dark theme."""
    
    # Utility colors - Excel-style warm tones
    ELECTRIC = QColor("#f39c12")  # Orange/Amber
    GAS = QColor("#e74c3c")       # Red
    WATER = QColor("#3498db")     # Blue
    TOTAL = QColor("#86efac")     # Sage Green (accent)
    
    # Temperature colors
    TEMP_HIGH = QColor("#e74c3c")  # Red
    TEMP_LOW = QColor("#3498db")   # Blue
    
    # Demand colors
    HEATING = QColor("#e74c3c")    # Red
    COOLING = QColor("#3498db")    # Blue
    ECONOMY = QColor("#27ae60")    # Green
    
    # Chart background - Carbon Sage
    BACKGROUND = QColor("#121212")
    GRID = QColor("#2e2e2e")
    TEXT = QColor("#a3a3a3")
    TITLE = QColor("#fafafa")
    
    @classmethod
    def gradient(cls, color: QColor, vertical: bool = True) -> QLinearGradient:
        """Create a gradient from a base color."""
        grad = QLinearGradient(0, 0, 0 if vertical else 1, 1 if vertical else 0)
        grad.setColorAt(0, color)
        grad.setColorAt(1, color.darker(150))
        return grad


class BaseChart(QChartView):
    """Base class for all charts with common styling."""
    
    def __init__(self, title: str = ""):
        self.chart = QChart()
        super().__init__(self.chart)
        
        # Configure chart
        self.chart.setTitle(title)
        self.chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        self.chart.setBackgroundBrush(QBrush(ChartColors.BACKGROUND))
        self.chart.setBackgroundRoundness(12)
        self.chart.setMargins(QMargins(10, 10, 10, 10))
        
        # Title font
        title_font = QFont("Segoe UI", 12, QFont.Weight.DemiBold)
        self.chart.setTitleFont(title_font)
        self.chart.setTitleBrush(QBrush(ChartColors.TITLE))
        
        # Legend styling
        legend = self.chart.legend()
        legend.setVisible(True)
        legend.setAlignment(Qt.AlignmentFlag.AlignBottom)
        legend.setLabelColor(ChartColors.TEXT)
        legend.setFont(QFont("Segoe UI", 9))
        
        # View settings
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setStyleSheet("background: transparent; border: none;")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    
    def _style_axis(self, axis, is_x: bool = True):
        """Apply consistent styling to an axis."""
        axis.setLabelsColor(ChartColors.TEXT)
        axis.setGridLineColor(ChartColors.GRID)
        axis.setLinePen(QPen(ChartColors.GRID))
        axis.setLabelsFont(QFont("Segoe UI", 9))
        
        if hasattr(axis, 'setTitleBrush'):
            axis.setTitleBrush(QBrush(ChartColors.TEXT))
            axis.setTitleFont(QFont("Segoe UI", 10))


class MonthlyCostChart(BaseChart):
    """Line chart showing monthly costs over time."""
    
    def __init__(self):
        super().__init__("Monthly Utility Costs")
        self._setup_chart()
    
    def _setup_chart(self):
        # Create series for each utility
        self.electric_series = QSplineSeries()
        self.electric_series.setName("Electric")
        self.electric_series.setColor(ChartColors.ELECTRIC)
        self.electric_series.setPen(QPen(ChartColors.ELECTRIC, 3))
        
        self.gas_series = QSplineSeries()
        self.gas_series.setName("Gas")
        self.gas_series.setColor(ChartColors.GAS)
        self.gas_series.setPen(QPen(ChartColors.GAS, 3))
        
        self.water_series = QSplineSeries()
        self.water_series.setName("Water")
        self.water_series.setColor(ChartColors.WATER)
        self.water_series.setPen(QPen(ChartColors.WATER, 3))
        
        self.chart.addSeries(self.electric_series)
        self.chart.addSeries(self.gas_series)
        self.chart.addSeries(self.water_series)
        
        # X-axis (categories for months)
        self.axis_x = QBarCategoryAxis()
        self._style_axis(self.axis_x, True)
        self.chart.addAxis(self.axis_x, Qt.AlignmentFlag.AlignBottom)
        
        # Y-axis (cost in dollars)
        self.axis_y = QValueAxis()
        self.axis_y.setTitleText("Cost ($)")
        self.axis_y.setLabelFormat("$%.0f")
        self._style_axis(self.axis_y, False)
        self.chart.addAxis(self.axis_y, Qt.AlignmentFlag.AlignLeft)
        
        # Attach series to axes
        self.electric_series.attachAxis(self.axis_x)
        self.electric_series.attachAxis(self.axis_y)
        self.gas_series.attachAxis(self.axis_x)
        self.gas_series.attachAxis(self.axis_y)
        self.water_series.attachAxis(self.axis_x)
        self.water_series.attachAxis(self.axis_y)
    
    def update_data(self, monthly_data: List[Dict]):
        """
        Update chart with monthly cost data.
        
        Args:
            monthly_data: List of dicts with keys: month, year, electric, gas, water
        """
        self.electric_series.clear()
        self.gas_series.clear()
        self.water_series.clear()
        
        categories = []
        max_val = 0
        
        for i, data in enumerate(monthly_data):
            month_label = f"{data.get('month', i+1)}/{str(data.get('year', 2025))[-2:]}"
            categories.append(month_label)
            
            elec = data.get('electric_cost', 0) or 0
            gas = data.get('gas_cost', 0) or 0
            water = data.get('water_cost', 0) or 0
            
            self.electric_series.append(i, elec)
            self.gas_series.append(i, gas)
            self.water_series.append(i, water)
            
            max_val = max(max_val, elec, gas, water)
        
        self.axis_x.clear()
        self.axis_x.append(categories)
        self.axis_y.setRange(0, max_val * 1.1)


class CostBreakdownChart(BaseChart):
    """Donut/Pie chart showing cost breakdown by utility type."""
    
    def __init__(self):
        super().__init__("Annual Cost Breakdown")
        self._setup_chart()
    
    def _setup_chart(self):
        self.series = QPieSeries()
        self.series.setHoleSize(0.45)  # Donut style
        
        self.chart.addSeries(self.series)
        self.chart.legend().setAlignment(Qt.AlignmentFlag.AlignRight)
    
    def update_data(self, electric: float, gas: float, water: float):
        """Update chart with cost breakdown."""
        self.series.clear()
        
        total = electric + gas + water
        if total == 0:
            return
        
        # Electric slice
        elec_slice = self.series.append(f"Electric ${electric:,.0f}", electric)
        elec_slice.setColor(ChartColors.ELECTRIC)
        elec_slice.setLabelVisible(True)
        elec_slice.setLabelColor(ChartColors.TEXT)
        elec_slice.setLabelPosition(QPieSlice.LabelPosition.LabelOutside)
        elec_slice.setLabel(f"Electric\n{electric/total*100:.0f}%")
        
        # Gas slice
        gas_slice = self.series.append(f"Gas ${gas:,.0f}", gas)
        gas_slice.setColor(ChartColors.GAS)
        gas_slice.setLabelVisible(True)
        gas_slice.setLabelColor(ChartColors.TEXT)
        gas_slice.setLabelPosition(QPieSlice.LabelPosition.LabelOutside)
        gas_slice.setLabel(f"Gas\n{gas/total*100:.0f}%")
        
        # Water slice
        water_slice = self.series.append(f"Water ${water:,.0f}", water)
        water_slice.setColor(ChartColors.WATER)
        water_slice.setLabelVisible(True)
        water_slice.setLabelColor(ChartColors.TEXT)
        water_slice.setLabelPosition(QPieSlice.LabelPosition.LabelOutside)
        water_slice.setLabel(f"Water\n{water/total*100:.0f}%")


class WeatherDemandChart(BaseChart):
    """Combined bar and line chart showing weather demand vs costs."""
    
    def __init__(self):
        super().__init__("Weather Demand vs. Utility Costs")
        self._setup_chart()
    
    def _setup_chart(self):
        # Bar series for costs
        self.cost_set = QBarSet("Total Cost")
        self.cost_set.setColor(ChartColors.TOTAL)
        
        self.bar_series = QBarSeries()
        self.bar_series.append(self.cost_set)
        self.bar_series.setBarWidth(0.6)
        
        # Line series for heating demand
        self.heating_series = QSplineSeries()
        self.heating_series.setName("Heating Demand")
        self.heating_series.setColor(ChartColors.HEATING)
        self.heating_series.setPen(QPen(ChartColors.HEATING, 3))
        
        # Line series for cooling demand
        self.cooling_series = QSplineSeries()
        self.cooling_series.setName("Cooling Demand")
        self.cooling_series.setColor(ChartColors.COOLING)
        self.cooling_series.setPen(QPen(ChartColors.COOLING, 3))
        
        self.chart.addSeries(self.bar_series)
        self.chart.addSeries(self.heating_series)
        self.chart.addSeries(self.cooling_series)
        
        # X-axis (months)
        self.axis_x = QBarCategoryAxis()
        self._style_axis(self.axis_x, True)
        self.chart.addAxis(self.axis_x, Qt.AlignmentFlag.AlignBottom)
        
        # Y-axis left (cost)
        self.axis_y_cost = QValueAxis()
        self.axis_y_cost.setTitleText("Cost ($)")
        self.axis_y_cost.setLabelFormat("$%.0f")
        self._style_axis(self.axis_y_cost, False)
        self.chart.addAxis(self.axis_y_cost, Qt.AlignmentFlag.AlignLeft)
        
        # Y-axis right (demand %)
        self.axis_y_demand = QValueAxis()
        self.axis_y_demand.setTitleText("Demand %")
        self.axis_y_demand.setLabelFormat("%.0f%")
        self.axis_y_demand.setRange(0, 100)
        self._style_axis(self.axis_y_demand, False)
        self.chart.addAxis(self.axis_y_demand, Qt.AlignmentFlag.AlignRight)
        
        # Attach axes
        self.bar_series.attachAxis(self.axis_x)
        self.bar_series.attachAxis(self.axis_y_cost)
        self.heating_series.attachAxis(self.axis_x)
        self.heating_series.attachAxis(self.axis_y_demand)
        self.cooling_series.attachAxis(self.axis_x)
        self.cooling_series.attachAxis(self.axis_y_demand)
    
    def update_data(self, data: List[Dict]):
        """
        Update chart with monthly demand and cost data.
        
        Args:
            data: List of dicts with keys: month, total_cost, heating_demand, cooling_demand
        """
        self.cost_set.remove(0, self.cost_set.count())
        self.heating_series.clear()
        self.cooling_series.clear()
        
        categories = []
        max_cost = 0
        
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        for i, d in enumerate(data):
            month_idx = d.get('month', i+1) - 1
            categories.append(months[month_idx])
            
            cost = d.get('total_cost', 0) or 0
            heating = abs(d.get('heating_demand', 0) or 0) * 100
            cooling = (d.get('cooling_demand', 0) or 0) * 100
            
            self.cost_set.append(cost)
            self.heating_series.append(i, heating)
            self.cooling_series.append(i, cooling)
            
            max_cost = max(max_cost, cost)
        
        self.axis_x.clear()
        self.axis_x.append(categories)
        self.axis_y_cost.setRange(0, max_cost * 1.15)


class YearComparisonChart(BaseChart):
    """Grouped bar chart comparing costs across years."""
    
    def __init__(self):
        super().__init__("Year-over-Year Comparison")
        self._setup_chart()
    
    def _setup_chart(self):
        self.bar_series = QBarSeries()
        self.bar_series.setBarWidth(0.7)
        
        self.chart.addSeries(self.bar_series)
        
        # X-axis (months)
        self.axis_x = QBarCategoryAxis()
        self._style_axis(self.axis_x, True)
        self.chart.addAxis(self.axis_x, Qt.AlignmentFlag.AlignBottom)
        
        # Y-axis (cost)
        self.axis_y = QValueAxis()
        self.axis_y.setTitleText("Total Cost ($)")
        self.axis_y.setLabelFormat("$%.0f")
        self._style_axis(self.axis_y, False)
        self.chart.addAxis(self.axis_y, Qt.AlignmentFlag.AlignLeft)
        
        self.bar_series.attachAxis(self.axis_x)
        self.bar_series.attachAxis(self.axis_y)
    
    def update_data(self, yearly_data: Dict[int, List[float]]):
        """
        Update chart with yearly comparison data.
        
        Args:
            yearly_data: Dict mapping year to list of 12 monthly totals
        """
        # Clear existing bar sets
        self.bar_series.clear()
        
        # Color gradient for years (most recent = brightest)
        colors = [
            QColor("#6366f1"),  # Indigo
            QColor("#8b5cf6"),  # Purple
            QColor("#86efac"),  # Violet
            QColor("#c084fc"),  # Light purple
        ]
        
        max_val = 0
        years = sorted(yearly_data.keys(), reverse=True)[:4]  # Last 4 years
        
        for i, year in enumerate(reversed(years)):
            bar_set = QBarSet(str(year))
            bar_set.setColor(colors[i % len(colors)])
            
            monthly = yearly_data[year]
            for val in monthly:
                bar_set.append(val or 0)
                max_val = max(max_val, val or 0)
            
            self.bar_series.append(bar_set)
        
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        self.axis_x.clear()
        self.axis_x.append(months)
        self.axis_y.setRange(0, max_val * 1.15)


class UsageTrendChart(BaseChart):
    """Area chart showing usage trends over time."""
    
    def __init__(self, utility_type: str = "Electric"):
        super().__init__(f"{utility_type} Usage Trend")
        self.utility_type = utility_type
        self._setup_chart()
    
    def _setup_chart(self):
        # Get color based on utility type
        colors = {
            "Electric": ChartColors.ELECTRIC,
            "Gas": ChartColors.GAS,
            "Water": ChartColors.WATER
        }
        color = colors.get(self.utility_type, ChartColors.ELECTRIC)
        
        # Create area series
        self.upper_series = QSplineSeries()
        self.lower_series = QSplineSeries()
        
        self.area_series = QAreaSeries(self.upper_series, self.lower_series)
        self.area_series.setName(self.utility_type)
        
        # Create gradient fill
        gradient = QLinearGradient(0, 0, 0, 1)
        gradient.setColorAt(0, color)
        gradient.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 50))
        gradient.setCoordinateMode(QLinearGradient.CoordinateMode.ObjectBoundingMode)
        
        self.area_series.setBrush(QBrush(gradient))
        self.area_series.setPen(QPen(color, 2))
        
        self.chart.addSeries(self.area_series)
        
        # X-axis
        self.axis_x = QBarCategoryAxis()
        self._style_axis(self.axis_x, True)
        self.chart.addAxis(self.axis_x, Qt.AlignmentFlag.AlignBottom)
        
        # Y-axis
        self.axis_y = QValueAxis()
        units = {"Electric": "kWh", "Gas": "Therms", "Water": "Gallons"}
        self.axis_y.setTitleText(units.get(self.utility_type, "Usage"))
        self._style_axis(self.axis_y, False)
        self.chart.addAxis(self.axis_y, Qt.AlignmentFlag.AlignLeft)
        
        self.area_series.attachAxis(self.axis_x)
        self.area_series.attachAxis(self.axis_y)
        
        # Hide legend for single series
        self.chart.legend().hide()
    
    def update_data(self, data: List[Tuple[str, float]]):
        """
        Update chart with usage data.
        
        Args:
            data: List of (label, value) tuples
        """
        self.upper_series.clear()
        self.lower_series.clear()
        
        categories = []
        max_val = 0
        
        for i, (label, value) in enumerate(data):
            categories.append(label)
            self.upper_series.append(i, value)
            self.lower_series.append(i, 0)
            max_val = max(max_val, value)
        
        self.axis_x.clear()
        self.axis_x.append(categories)
        self.axis_y.setRange(0, max_val * 1.1)


class TemperatureRangeChart(BaseChart):
    """Area chart showing temperature ranges with high/low bands."""
    
    def __init__(self):
        super().__init__("Temperature Range")
        self._setup_chart()
    
    def _setup_chart(self):
        # High temperature line
        self.high_series = QSplineSeries()
        self.high_series.setName("High")
        self.high_series.setPen(QPen(ChartColors.TEMP_HIGH, 2))
        
        # Low temperature line
        self.low_series = QSplineSeries()
        self.low_series.setName("Low")
        self.low_series.setPen(QPen(ChartColors.TEMP_LOW, 2))
        
        # Area between high and low
        self.range_area = QAreaSeries(self.high_series, self.low_series)
        self.range_area.setName("Range")
        
        # Gradient fill
        gradient = QLinearGradient(0, 0, 0, 1)
        gradient.setColorAt(0, QColor(239, 68, 68, 100))  # Red with alpha
        gradient.setColorAt(1, QColor(59, 130, 246, 100))  # Blue with alpha
        gradient.setCoordinateMode(QLinearGradient.CoordinateMode.ObjectBoundingMode)
        self.range_area.setBrush(QBrush(gradient))
        self.range_area.setPen(QPen(Qt.PenStyle.NoPen))
        
        self.chart.addSeries(self.range_area)
        self.chart.addSeries(self.high_series)
        self.chart.addSeries(self.low_series)
        
        # X-axis
        self.axis_x = QBarCategoryAxis()
        self._style_axis(self.axis_x, True)
        self.chart.addAxis(self.axis_x, Qt.AlignmentFlag.AlignBottom)
        
        # Y-axis
        self.axis_y = QValueAxis()
        self.axis_y.setTitleText("Temperature (°F)")
        self.axis_y.setLabelFormat("%.0f°")
        self._style_axis(self.axis_y, False)
        self.chart.addAxis(self.axis_y, Qt.AlignmentFlag.AlignLeft)
        
        self.range_area.attachAxis(self.axis_x)
        self.range_area.attachAxis(self.axis_y)
        self.high_series.attachAxis(self.axis_x)
        self.high_series.attachAxis(self.axis_y)
        self.low_series.attachAxis(self.axis_x)
        self.low_series.attachAxis(self.axis_y)
    
    def update_data(self, data: List[Dict]):
        """
        Update chart with temperature data.
        
        Args:
            data: List of dicts with keys: label, high, low
        """
        self.high_series.clear()
        self.low_series.clear()
        
        categories = []
        max_temp = 0
        min_temp = 100
        
        for i, d in enumerate(data):
            categories.append(d.get('label', str(i)))
            high = d.get('high', 0) or 0
            low = d.get('low', 0) or 0
            
            self.high_series.append(i, high)
            self.low_series.append(i, low)
            
            max_temp = max(max_temp, high)
            min_temp = min(min_temp, low)
        
        self.axis_x.clear()
        self.axis_x.append(categories)
        self.axis_y.setRange(min_temp - 10, max_temp + 10)


class QuickStatsWidget(QFrame):
    """Compact widget showing quick statistics."""
    
    def __init__(self):
        super().__init__()
        self.setObjectName("chartPanel")
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)
        
        # Title
        title = QLabel("Quick Statistics")
        title.setStyleSheet("color: white; font-size: 14px; font-weight: 600;")
        layout.addWidget(title)
        
        # Stats
        self.stats = {}
        stat_items = [
            ("avg_monthly", "Avg Monthly", "$0"),
            ("cost_per_day", "Cost/Day", "$0"),
            ("cost_per_sqft", "Cost/SqFt", "$0"),
            ("ytd_total", "YTD Total", "$0"),
            ("vs_last_year", "vs Last Year", "—"),
        ]
        
        for key, label, default in stat_items:
            row = QHBoxLayout()
            
            name_label = QLabel(label)
            name_label.setStyleSheet("color: #8b8ba7; font-size: 12px;")
            row.addWidget(name_label)
            
            row.addStretch()
            
            value_label = QLabel(default)
            value_label.setStyleSheet("color: white; font-weight: 600; font-size: 14px;")
            row.addWidget(value_label)
            
            self.stats[key] = value_label
            layout.addLayout(row)
        
        layout.addStretch()
    
    def update_stats(self, data: Dict):
        """Update displayed statistics."""
        if 'avg_monthly' in data:
            self.stats['avg_monthly'].setText(f"${data['avg_monthly']:,.0f}")
        if 'cost_per_day' in data:
            self.stats['cost_per_day'].setText(f"${data['cost_per_day']:.2f}")
        if 'cost_per_sqft' in data:
            self.stats['cost_per_sqft'].setText(f"${data['cost_per_sqft']:.2f}")
        if 'ytd_total' in data:
            self.stats['ytd_total'].setText(f"${data['ytd_total']:,.0f}")
        if 'vs_last_year' in data:
            pct = data['vs_last_year']
            color = "#4ade80" if pct <= 0 else "#f87171"
            sign = "+" if pct > 0 else ""
            self.stats['vs_last_year'].setText(f"{sign}{pct:.1f}%")
            self.stats['vs_last_year'].setStyleSheet(f"color: {color}; font-weight: 600; font-size: 14px;")
