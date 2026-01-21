"""
UtilityHQ - Home Utilities Tracker
Separate pages for Electric, Gas, Water with Cost/Usage charts
"""

import sys
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Optional, Dict, List, Tuple

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QGridLayout, QScrollArea, QLineEdit,
    QDateEdit, QDoubleSpinBox, QSpinBox, QComboBox, QGroupBox,
    QFormLayout, QMessageBox, QProgressDialog, QTableWidget,
    QTableWidgetItem, QHeaderView, QDialog, QDialogButtonBox,
    QMenuBar, QMenu, QStackedWidget, QSplitter, QFileDialog,
    QTextEdit, QCheckBox, QSizePolicy, QTabWidget, QToolTip
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal, QThread, QMargins, QTimer, QEvent, QPoint
from PyQt6.QtGui import QFont, QColor, QIcon, QPixmap, QAction, QPainter, QBrush, QPen
from PyQt6.QtCharts import (
    QChart, QChartView, QLineSeries, QValueAxis, QSplineSeries, QLegend,
    QStackedBarSeries, QScatterSeries
)

sys.path.insert(0, str(Path(__file__).parent))

from database import DatabaseManager, WeatherDay
from weather_api import WeatherUndergroundAPI, WeatherDemandCalculator
from updater import get_current_version, check_for_updates, download_update, apply_update

# Try to import ApexCharts (requires PyQt6-WebEngine)
# Falls back to QtCharts if not available
try:
    from apex_charts import (
        MonthlyCostChart as ApexMonthlyCostChart,
        DemandCostChart as ApexDemandCostChart,
        DegreeDaysChart as ApexDegreeDaysChart,
        MonthlyDemandChart as ApexMonthlyDemandChart,
        CPDIndexChart as ApexCPDIndexChart,
        UtilityLineChart as ApexUtilityLineChart,
        DailyDemandScatterChart as ApexDailyDemandChart,
        RainGaugeChart as ApexRainGaugeChart,
        DonutChart as ApexDonutChart,
        WEBENGINE_AVAILABLE,
    )
    USE_APEX_CHARTS = WEBENGINE_AVAILABLE
except ImportError:
    USE_APEX_CHARTS = False


# ============== INSTANT TOOLTIP FRAME ==============

class InstantTooltipFrame(QFrame):
    """Frame that shows tooltip instantly on mouse enter."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._tooltip_text = ""
        self._tooltip_showing = False
        self.setMouseTracking(True)
    
    def setInstantTooltip(self, text: str):
        """Set the tooltip text."""
        self._tooltip_text = text
    
    def enterEvent(self, event):
        """Show tooltip immediately on mouse enter."""
        if self._tooltip_text and not self._tooltip_showing:
            self._tooltip_showing = True
            # Show tooltip at widget's top-left, offset slightly
            global_pos = self.mapToGlobal(QPoint(10, -60))
            QToolTip.showText(global_pos, self._tooltip_text, self, self.rect(), 10000)
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Hide tooltip on mouse leave."""
        self._tooltip_showing = False
        QToolTip.hideText()
        super().leaveEvent(event)


# ============== HOVER LABEL ==============

class HoverLabel(QLabel):
    """Label that shows a popup on hover."""
    
    # Utility types use get_usage_stats, performance types use get_performance_tooltip_stats
    UTILITY_TYPES = ['electric', 'gas', 'water']
    PERFORMANCE_TYPES = ['kwh_day', 'thm_day', 'gal_day', 'cost_day', 'cost_sqft', 'ytd_total']
    FORECAST_TYPES = ['forecast_prev', 'forecast_curr', 'forecast_next']
    WEATHER_TYPES = ['weather_max', 'weather_min', 'weather_rain']
    
    def __init__(self, text: str, stat_type: str, main_window, tooltip_data: dict = None):
        super().__init__(text)
        self.stat_type = stat_type
        self.main_window = main_window
        self.tooltip_data = tooltip_data  # For forecast and weather tooltips
        self.popup = None
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
    def enterEvent(self, event):
        """Show popup when mouse enters."""
        if self.stat_type in self.FORECAST_TYPES and self.tooltip_data:
            self.popup = self.main_window._create_forecast_popup(self.tooltip_data)
        elif self.stat_type in self.WEATHER_TYPES and self.tooltip_data:
            self.popup = self.main_window._create_weather_popup(self.stat_type, self.tooltip_data)
        else:
            self.popup = self.main_window._create_performance_popup(self.stat_type)
        # Position popup below the label
        pos = self.mapToGlobal(self.rect().bottomLeft())
        self.popup.move(pos.x(), pos.y() + 4)
        self.popup.show()
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        """Hide popup when mouse leaves."""
        if self.popup:
            self.popup.close()
            self.popup = None
        super().leaveEvent(event)


# ============== THEME ==============

# Carbon Sage Theme - Dark grey with sage green accent
CARBON_SAGE_THEME = """
QMainWindow, QDialog { background-color: #121212; }
QWidget { color: #fafafa; font-family: 'Segoe UI', sans-serif; font-size: 13px; }

QMenuBar { background-color: #1a1a1a; border-bottom: 1px solid #2e2e2e; padding: 4px; }
QMenuBar::item { padding: 6px 12px; border-radius: 4px; }
QMenuBar::item:selected { background-color: #86efac; color: #121212; }
QMenu { background-color: #1a1a1a; border: 1px solid #2e2e2e; }
QMenu::item { padding: 8px 24px; }
QMenu::item:selected { background-color: #86efac; color: #121212; }

QFrame#sidebar { background-color: #1a1a1a; border-right: 1px solid #2e2e2e; }
QFrame#topBar { background-color: #1a1a1a; border-bottom: 1px solid #2e2e2e; }
QFrame#titleBar { background-color: #1a1a1a; border-bottom: 1px solid #2e2e2e; }
QFrame#statsBar { background-color: #1e1e1e; border: 1px solid #2e2e2e; border-radius: 12px; }
QFrame#statusBar { background-color: #0a0a0a; border-top: 1px solid #2e2e2e; }
QFrame#statCard { background: #1e1e1e; border: 1px solid #2e2e2e; border-radius: 8px; padding: 8px; }
QFrame#statCardElectric { background: rgba(243, 156, 18, 0.1); border: 1px solid rgba(243, 156, 18, 0.3); border-radius: 8px; }
QFrame#statCardGas { background: rgba(231, 76, 60, 0.1); border: 1px solid rgba(231, 76, 60, 0.3); border-radius: 8px; }
QFrame#statCardWater { background: rgba(52, 152, 219, 0.1); border: 1px solid rgba(52, 152, 219, 0.3); border-radius: 8px; }
QFrame#chartPanel { background: #1e1e1e; border: 1px solid #2e2e2e; border-radius: 12px; }
QFrame#formSection { background: rgba(30, 30, 30, 0.5); border: 1px solid #2e2e2e; border-radius: 8px; }

QPushButton { background-color: #242424; border: 1px solid #3a3a3a; border-radius: 6px; padding: 8px 16px; color: #fafafa; font-weight: 500; }
QPushButton:hover { background-color: #3a3a3a; border-color: #86efac; }
QPushButton:checked { background-color: rgba(134, 239, 172, 0.15); border-color: #86efac; color: #86efac; }
QPushButton#addButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #86efac, stop:1 #4ade80); border: none; color: #121212; }
QPushButton#navButton { background: transparent; border: none; padding: 9px 10px; text-align: left; color: #a3a3a3; border-radius: 6px; }
QPushButton#navButton:hover { background-color: #242424; color: #fafafa; }
QPushButton#navButton:checked { background-color: rgba(134, 239, 172, 0.1); color: #86efac; }

QLineEdit, QSpinBox, QDoubleSpinBox, QDateEdit, QComboBox { background-color: #0a0a0a; border: 1px solid #2e2e2e; border-radius: 6px; padding: 8px 12px; color: #ffffff; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus, QComboBox:focus { border-color: #86efac; }
QComboBox QAbstractItemView { background-color: #1a1a1a; border: 1px solid #2e2e2e; selection-background-color: #86efac; selection-color: #121212; }

QLabel#statValue { font-size: 24px; font-weight: 700; }
QLabel#statValueElectric { font-size: 24px; font-weight: 700; color: #f39c12; }
QLabel#statValueGas { font-size: 24px; font-weight: 700; color: #e74c3c; }
QLabel#statValueWater { font-size: 24px; font-weight: 700; color: #3498db; }
QLabel#statLabel { color: #737373; font-size: 11px; }
QLabel#pageTitle { font-size: 20px; font-weight: 700; color: white; }

QGroupBox { font-weight: bold; color: #a3a3a3; font-size: 13px; border: 1px solid #2e2e2e; border-radius: 8px; margin-top: 12px; padding-top: 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }

QTableWidget { background-color: #0a0a0a; border: 1px solid #2e2e2e; border-radius: 8px; gridline-color: #2e2e2e; }
QTableWidget::item { padding: 8px; }
QTableWidget::item:selected { background-color: #86efac; color: #121212; }
QHeaderView::section { background-color: #1a1a1a; color: #a3a3a3; padding: 8px; border: none; font-weight: 600; }
QScrollBar:vertical { background: #0a0a0a; width: 10px; }
QScrollBar::handle:vertical { background: #2e2e2e; border-radius: 5px; }
QScrollBar::handle:vertical:hover { background: #3a3a3a; }
QProgressDialog { background-color: #121212; }

QTabWidget::pane { border: 1px solid #2e2e2e; background: #121212; border-radius: 8px; }
QTabBar::tab { background: #1a1a1a; color: #a3a3a3; padding: 8px 16px; margin-right: 4px; border-top-left-radius: 8px; border-top-right-radius: 8px; }
QTabBar::tab:selected { background: #242424; color: #86efac; }
QTabBar::tab:hover { background: #242424; }

QToolTip { background-color: #121212; color: #a3a3a3; border: 1px solid #3a3a3a; border-radius: 6px; padding: 8px; font-size: 12px; }
"""

# Utility-specific tooltip styles (applied per-card)
TOOLTIP_STYLES = {
    'electric': "QToolTip { background-color: #121212; color: #a3a3a3; border: 1px solid #f39c12; border-radius: 6px; padding: 8px; font-size: 12px; }",
    'gas': "QToolTip { background-color: #121212; color: #a3a3a3; border: 1px solid #e74c3c; border-radius: 6px; padding: 8px; font-size: 12px; }",
    'water': "QToolTip { background-color: #121212; color: #a3a3a3; border: 1px solid #3498db; border-radius: 6px; padding: 8px; font-size: 12px; }",
}


# ============== CHART CLASSES ==============

class UtilityLineChart(QChartView):
    """Line chart showing Average, Previous Year, Current Year."""
    
    COLORS = {
        'electric': {'current': '#f39c12', 'previous': '#b47a0e', 'average': '#7a530a'},
        'gas': {'current': '#e74c3c', 'previous': '#a93226', 'average': '#6e211a'},
        'water': {'current': '#3498db', 'previous': '#2475a8', 'average': '#185270'},
    }
    
    def __init__(self, title: str, utility_type: str, y_label: str = "$"):
        self.chart = QChart()
        super().__init__(self.chart)
        
        self.utility_type = utility_type
        self.y_label = y_label
        
        # Configure chart
        self.chart.setTitle(title)
        self.chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        self.chart.setBackgroundBrush(QBrush(QColor("#121212")))
        self.chart.setBackgroundRoundness(12)
        self.chart.setMargins(QMargins(10, 10, 10, 10))
        
        # Title font
        title_font = QFont("Segoe UI", 11, QFont.Weight.DemiBold)
        self.chart.setTitleFont(title_font)
        self.chart.setTitleBrush(QBrush(QColor("#ffffff")))
        
        # Legend
        legend = self.chart.legend()
        legend.setVisible(True)
        legend.setAlignment(Qt.AlignmentFlag.AlignBottom)
        legend.setLabelColor(QColor("#a3a3a3"))
        legend.setFont(QFont("Segoe UI", 9))
        
        # View settings
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setStyleSheet("background: transparent; border: none;")
        self.setMinimumHeight(250)
        
        # Create axes
        self.axis_x = QValueAxis()
        self.axis_x.setRange(1, 12)
        self.axis_x.setTickCount(12)
        self.axis_x.setLabelFormat("%d")
        self.axis_x.setTitleText("Month")
        self.axis_x.setLabelsColor(QColor("#a3a3a3"))
        self.axis_x.setTitleBrush(QBrush(QColor("#a3a3a3")))
        self.axis_x.setGridLineColor(QColor("#2e2e2e"))
        
        self.axis_y = QValueAxis()
        self.axis_y.setTitleText(y_label)
        self.axis_y.setLabelsColor(QColor("#a3a3a3"))
        self.axis_y.setTitleBrush(QBrush(QColor("#a3a3a3")))
        self.axis_y.setGridLineColor(QColor("#2e2e2e"))
        
        self.chart.addAxis(self.axis_x, Qt.AlignmentFlag.AlignBottom)
        self.chart.addAxis(self.axis_y, Qt.AlignmentFlag.AlignLeft)
    
    def update_data(self, average: List[float], previous_year: List[float], current_year: List[float], 
                    prev_year_label: int = None, curr_year_label: int = None):
        """Update chart with new data. Each list has 12 values (one per month)."""
        # Clear existing series
        self.chart.removeAllSeries()
        
        colors = self.COLORS.get(self.utility_type, self.COLORS['electric'])
        
        # Find max value for Y axis
        all_values = [v for v in average + previous_year + current_year if v and v > 0]
        max_val = max(all_values) * 1.1 if all_values else 100
        self.axis_y.setRange(0, max_val)
        
        # Average line (dashed) - always show if there's data
        if any(v > 0 for v in average):
            avg_series = QLineSeries()
            avg_series.setName("Average")
            pen = QPen(QColor(colors['average']))
            pen.setWidth(2)
            pen.setStyle(Qt.PenStyle.DashLine)
            avg_series.setPen(pen)
            for month, val in enumerate(average, 1):
                if val and val > 0:
                    avg_series.append(month, val)
            self.chart.addSeries(avg_series)
            avg_series.attachAxis(self.axis_x)
            avg_series.attachAxis(self.axis_y)
        
        # Previous year line
        if any(v > 0 for v in previous_year):
            prev_series = QLineSeries()
            prev_name = f"{prev_year_label}" if prev_year_label else "Previous Year"
            prev_series.setName(prev_name)
            pen = QPen(QColor(colors['previous']))
            pen.setWidth(2)
            prev_series.setPen(pen)
            for month, val in enumerate(previous_year, 1):
                if val and val > 0:
                    prev_series.append(month, val)
            self.chart.addSeries(prev_series)
            prev_series.attachAxis(self.axis_x)
            prev_series.attachAxis(self.axis_y)
        
        # Current year line (bold)
        if any(v > 0 for v in current_year):
            curr_series = QLineSeries()
            curr_name = f"{curr_year_label}" if curr_year_label else "Current Year"
            curr_series.setName(curr_name)
            pen = QPen(QColor(colors['current']))
            pen.setWidth(3)
            curr_series.setPen(pen)
            for month, val in enumerate(current_year, 1):
                if val and val > 0:
                    curr_series.append(month, val)
            self.chart.addSeries(curr_series)
            curr_series.attachAxis(self.axis_x)
            curr_series.attachAxis(self.axis_y)


class DemandCostChart(QChartView):
    """Chart 1: Weather Demand vs Cost Per Day - Stacked bar chart with CPD line overlay.
    
    Heating demand shown as red bars below 0, Cooling demand as blue bars above 0.
    CPD shown as green line on right Y-axis.
    """
    
    def __init__(self):
        self.chart = QChart()
        super().__init__(self.chart)
        
        # Configure chart
        self.chart.setTitle("Weather Demand vs Cost Per Day")
        self.chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        self.chart.setBackgroundBrush(QBrush(QColor("#121212")))
        self.chart.setBackgroundRoundness(12)
        self.chart.setMargins(QMargins(10, 10, 10, 10))
        
        # Title font
        title_font = QFont("Segoe UI", 11, QFont.Weight.DemiBold)
        self.chart.setTitleFont(title_font)
        self.chart.setTitleBrush(QBrush(QColor("#ffffff")))
        
        # Legend
        legend = self.chart.legend()
        legend.setVisible(True)
        legend.setAlignment(Qt.AlignmentFlag.AlignBottom)
        legend.setLabelColor(QColor("#a3a3a3"))
        legend.setFont(QFont("Segoe UI", 9))
        
        # View settings
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setStyleSheet("background: transparent; border: none;")
        self.setMinimumHeight(280)
    
    def update_data(self, matrix_data: List[Dict]):
        """Update chart with demand matrix data."""
        from PyQt6.QtCharts import QBarSeries, QBarSet, QBarCategoryAxis
        
        self.chart.removeAllSeries()
        
        # Remove old axes
        for axis in self.chart.axes():
            self.chart.removeAxis(axis)
        
        if not matrix_data:
            return
        
        years = [str(d['year']) for d in matrix_data]
        cooling_demands = [d.get('avg_cooling', 0) * 100 for d in matrix_data]  # Positive %
        heating_demands = [d.get('avg_heating', 0) * 100 for d in matrix_data]  # Negative %
        cpds = [d['cost_per_day'] for d in matrix_data]
        avg_cpd = matrix_data[0].get('avg_cpd', 0) if matrix_data else 0
        
        # Create separate bar series for cooling (above 0) and heating (below 0)
        # We need two separate QBarSeries, not stacked, to show above/below zero
        
        cooling_set = QBarSet("Cooling")
        cooling_set.setColor(QColor("#86efac"))  # Blue
        
        heating_set = QBarSet("Heating")
        heating_set.setColor(QColor("#ef4444"))  # Red
        
        for i in range(len(matrix_data)):
            cooling_set.append(cooling_demands[i])
            heating_set.append(heating_demands[i])  # Negative values go below 0
        
        # Use stacked bar series - heating (negative) + cooling (positive) 
        bar_series = QStackedBarSeries()
        bar_series.append(heating_set)  # Add heating first (will be below zero)
        bar_series.append(cooling_set)  # Add cooling second (will be above zero)
        self.chart.addSeries(bar_series)
        
        # X axis (years)
        axis_x = QBarCategoryAxis()
        axis_x.append(years)
        axis_x.setLabelsColor(QColor("#a3a3a3"))
        axis_x.setGridLineColor(QColor("#2e2e2e"))
        self.chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        bar_series.attachAxis(axis_x)
        
        # Left Y axis (Demand %) - must span negative to positive
        max_cool = max(cooling_demands) if cooling_demands else 20
        min_heat = min(heating_demands) if heating_demands else -30
        y_max = max(abs(max_cool), abs(min_heat)) * 1.3
        
        axis_y_demand = QValueAxis()
        axis_y_demand.setRange(-y_max, y_max)
        axis_y_demand.setTitleText("Demand %")
        axis_y_demand.setLabelFormat("%.0f%%")
        axis_y_demand.setLabelsColor(QColor("#a3a3a3"))
        axis_y_demand.setTitleBrush(QBrush(QColor("#a3a3a3")))
        axis_y_demand.setGridLineColor(QColor("#2e2e2e"))
        self.chart.addAxis(axis_y_demand, Qt.AlignmentFlag.AlignLeft)
        bar_series.attachAxis(axis_y_demand)
        
        # Right Y axis (Cost Per Day $)
        max_cpd = max(cpds) if cpds else 10
        axis_y_cpd = QValueAxis()
        axis_y_cpd.setRange(0, max_cpd * 1.3)
        axis_y_cpd.setTitleText("$/Day")
        axis_y_cpd.setLabelFormat("$%.0f")
        axis_y_cpd.setLabelsColor(QColor("#22c55e"))
        axis_y_cpd.setTitleBrush(QBrush(QColor("#22c55e")))
        self.chart.addAxis(axis_y_cpd, Qt.AlignmentFlag.AlignRight)
        
        # Cost Per Day line (green)
        cpd_series = QLineSeries()
        cpd_series.setName("$/Day")
        pen = QPen(QColor("#22c55e"))
        pen.setWidth(3)
        cpd_series.setPen(pen)
        for i in range(len(years)):
            cpd_series.append(i, cpds[i])
        self.chart.addSeries(cpd_series)
        cpd_series.attachAxis(axis_x)
        cpd_series.attachAxis(axis_y_cpd)
        
        # Average CPD line (dashed gray)
        if avg_cpd > 0:
            avg_series = QLineSeries()
            avg_series.setName(f"Avg ${avg_cpd:.2f}")
            pen = QPen(QColor("#a3a3a3"))
            pen.setWidth(2)
            pen.setStyle(Qt.PenStyle.DashLine)
            avg_series.setPen(pen)
            avg_series.append(-0.5, avg_cpd)
            avg_series.append(len(years) - 0.5, avg_cpd)
            self.chart.addSeries(avg_series)
            avg_series.attachAxis(axis_x)
            avg_series.attachAxis(axis_y_cpd)


class CPDIndexChart(QChartView):
    """Chart 2: Cost Per Day Index vs Demand - Bar chart with line overlay."""
    
    def __init__(self):
        self.chart = QChart()
        super().__init__(self.chart)
        
        # Configure chart
        self.chart.setTitle("Cost Per Day Index vs Demand")
        self.chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        self.chart.setBackgroundBrush(QBrush(QColor("#121212")))
        self.chart.setBackgroundRoundness(12)
        self.chart.setMargins(QMargins(10, 10, 10, 10))
        
        # Title font
        title_font = QFont("Segoe UI", 11, QFont.Weight.DemiBold)
        self.chart.setTitleFont(title_font)
        self.chart.setTitleBrush(QBrush(QColor("#ffffff")))
        
        # Legend
        legend = self.chart.legend()
        legend.setVisible(True)
        legend.setAlignment(Qt.AlignmentFlag.AlignBottom)
        legend.setLabelColor(QColor("#a3a3a3"))
        legend.setFont(QFont("Segoe UI", 9))
        
        # View settings
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setStyleSheet("background: transparent; border: none;")
        self.setMinimumHeight(280)
    
    def update_data(self, matrix_data: List[Dict]):
        """Update chart with demand matrix data."""
        from PyQt6.QtCharts import QBarSeries, QBarSet, QBarCategoryAxis
        
        self.chart.removeAllSeries()
        
        # Remove old axes
        for axis in self.chart.axes():
            self.chart.removeAxis(axis)
        
        if not matrix_data:
            return
        
        years = [str(d['year']) for d in matrix_data]
        pct_costs = [d['pct_avg_cost'] * 100 for d in matrix_data]  # % above/below avg
        pct_demands = [d['pct_avg_demand'] * 100 for d in matrix_data]  # % of avg demand
        
        # Create bar sets for above and below average
        above_set = QBarSet("Above Avg (↑ cost)")
        above_set.setColor(QColor("#ef4444"))  # Red
        below_set = QBarSet("Below Avg (↓ cost)")
        below_set.setColor(QColor("#22c55e"))  # Green
        
        for pct in pct_costs:
            if pct >= 0:
                above_set.append(pct)
                below_set.append(0)
            else:
                above_set.append(0)
                below_set.append(pct)
        
        bar_series = QBarSeries()
        bar_series.append(above_set)
        bar_series.append(below_set)
        self.chart.addSeries(bar_series)
        
        # X axis (years)
        axis_x = QBarCategoryAxis()
        axis_x.append(years)
        axis_x.setLabelsColor(QColor("#a3a3a3"))
        axis_x.setGridLineColor(QColor("#2e2e2e"))
        self.chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        bar_series.attachAxis(axis_x)
        
        # Y axis (% of average)
        all_vals = pct_costs + pct_demands
        min_val = min(all_vals) if all_vals else -30
        max_val = max(all_vals) if all_vals else 30
        range_val = max(abs(min_val), abs(max_val)) * 1.2
        
        axis_y = QValueAxis()
        axis_y.setRange(-range_val, range_val)
        axis_y.setTitleText("% of Average")
        axis_y.setLabelsColor(QColor("#a3a3a3"))
        axis_y.setTitleBrush(QBrush(QColor("#a3a3a3")))
        axis_y.setGridLineColor(QColor("#2e2e2e"))
        self.chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        bar_series.attachAxis(axis_y)
        
        # Energy demand line overlay
        demand_series = QLineSeries()
        demand_series.setName("Energy Demand %")
        pen = QPen(QColor("#f39c12"))  # Yellow/amber
        pen.setWidth(3)
        demand_series.setPen(pen)
        
        for i, year in enumerate(years):
            # Position at center of bar (i + 0.5 doesn't work well, use index)
            demand_series.append(i, pct_demands[i])
        
        self.chart.addSeries(demand_series)
        demand_series.attachAxis(axis_x)
        demand_series.attachAxis(axis_y)


class DegreeDaysChart(QChartView):
    """Chart 3: Degree Days - Grouped bar chart showing heating/cooling/economy days per year."""
    
    def __init__(self):
        self.chart = QChart()
        super().__init__(self.chart)
        
        # Configure chart
        self.chart.setTitle("Degree Days by Year")
        self.chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        self.chart.setBackgroundBrush(QBrush(QColor("#121212")))
        self.chart.setBackgroundRoundness(12)
        self.chart.setMargins(QMargins(10, 10, 10, 10))
        
        # Title font
        title_font = QFont("Segoe UI", 11, QFont.Weight.DemiBold)
        self.chart.setTitleFont(title_font)
        self.chart.setTitleBrush(QBrush(QColor("#ffffff")))
        
        # Legend
        legend = self.chart.legend()
        legend.setVisible(True)
        legend.setAlignment(Qt.AlignmentFlag.AlignBottom)
        legend.setLabelColor(QColor("#a3a3a3"))
        legend.setFont(QFont("Segoe UI", 9))
        
        # View settings
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setStyleSheet("background: transparent; border: none;")
        self.setMinimumHeight(280)
    
    def update_data(self, degree_days_data: List[Dict]):
        """
        Update chart with degree days data.
        
        Args:
            degree_days_data: List of dicts with keys: year, cooling_days, heating_days, economy_days
        """
        from PyQt6.QtCharts import QBarSeries, QBarSet, QBarCategoryAxis
        
        self.chart.removeAllSeries()
        
        # Remove old axes
        for axis in self.chart.axes():
            self.chart.removeAxis(axis)
        
        if not degree_days_data:
            return
        
        years = [str(d['year']) for d in degree_days_data]
        
        # Create bar sets for grouped bars
        cooling_set = QBarSet("Cooling")
        cooling_set.setColor(QColor("#86efac"))  # Blue
        
        heating_set = QBarSet("Heating")
        heating_set.setColor(QColor("#ef4444"))  # Red
        
        economy_set = QBarSet("Economy")
        economy_set.setColor(QColor("#22c55e"))  # Green
        
        max_days = 0
        for d in degree_days_data:
            cool = d.get('cooling_days', 0)
            heat = d.get('heating_days', 0)
            econ = d.get('economy_days', 0)
            cooling_set.append(cool)
            heating_set.append(heat)
            economy_set.append(econ)
            max_days = max(max_days, cool, heat, econ)
        
        # Create grouped bar series (not stacked)
        bar_series = QBarSeries()
        bar_series.append(cooling_set)
        bar_series.append(heating_set)
        bar_series.append(economy_set)
        self.chart.addSeries(bar_series)
        
        # X axis (years)
        axis_x = QBarCategoryAxis()
        axis_x.append(years)
        axis_x.setLabelsColor(QColor("#a3a3a3"))
        axis_x.setGridLineColor(QColor("#2e2e2e"))
        self.chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        bar_series.attachAxis(axis_x)
        
        # Y axis (days)
        axis_y = QValueAxis()
        axis_y.setRange(0, max_days * 1.15 if max_days > 0 else 250)
        axis_y.setTitleText("Days")
        axis_y.setLabelsColor(QColor("#a3a3a3"))
        axis_y.setTitleBrush(QBrush(QColor("#a3a3a3")))
        axis_y.setGridLineColor(QColor("#2e2e2e"))
        self.chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        bar_series.attachAxis(axis_y)


class MonthlyDemandChart(QChartView):
    """Chart 4: Monthly Weather Demand - Bar chart showing 5 years with average line overlay."""
    
    def __init__(self):
        self.chart = QChart()
        super().__init__(self.chart)
        
        # Configure chart
        self.chart.setTitle("Monthly Weather Demand")
        self.chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        self.chart.setBackgroundBrush(QBrush(QColor("#121212")))
        self.chart.setBackgroundRoundness(12)
        self.chart.setMargins(QMargins(10, 10, 10, 10))
        
        # Title font
        title_font = QFont("Segoe UI", 11, QFont.Weight.DemiBold)
        self.chart.setTitleFont(title_font)
        self.chart.setTitleBrush(QBrush(QColor("#ffffff")))
        
        # Legend
        legend = self.chart.legend()
        legend.setVisible(True)
        legend.setAlignment(Qt.AlignmentFlag.AlignBottom)
        legend.setLabelColor(QColor("#a3a3a3"))
        legend.setFont(QFont("Segoe UI", 9))
        
        # View settings
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setStyleSheet("background: transparent; border: none;")
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
        from PyQt6.QtCharts import QBarSeries, QBarSet, QBarCategoryAxis
        
        self.chart.removeAllSeries()
        
        # Remove old axes
        for axis in self.chart.axes():
            self.chart.removeAxis(axis)
        
        if not monthly_data:
            return
        
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        # Get last 5 years of data
        all_years = sorted(monthly_data.get('years', []), reverse=True)
        years_to_show = all_years[:5]  # Last 5 years
        years_to_show = sorted(years_to_show)  # Show in chronological order
        
        # Color palette for years (oldest to newest)
        year_colors = [
            QColor("#6366f1"),  # Indigo (oldest)
            QColor("#8b5cf6"),  # Purple
            QColor("#a855f7"),  # Violet
            QColor("#86efac"),  # Blue
            QColor("#22c55e"),  # Green (newest/current)
        ]
        
        # Create bar sets for each year
        bar_series = QBarSeries()
        max_demand = 0
        
        year_data = monthly_data.get('data', {})
        for i, year in enumerate(years_to_show):
            if year in year_data:
                bar_set = QBarSet(str(year))
                color_idx = min(i, len(year_colors) - 1)
                bar_set.setColor(year_colors[color_idx])
                
                for month_val in year_data[year]:
                    val = (month_val or 0) * 100  # Convert to percentage
                    bar_set.append(val)
                    max_demand = max(max_demand, val)
                
                bar_series.append(bar_set)
        
        self.chart.addSeries(bar_series)
        
        # X axis (months)
        axis_x = QBarCategoryAxis()
        axis_x.append(months)
        axis_x.setLabelsColor(QColor("#a3a3a3"))
        axis_x.setGridLineColor(QColor("#2e2e2e"))
        self.chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        bar_series.attachAxis(axis_x)
        
        # Y axis (demand %)
        axis_y = QValueAxis()
        axis_y.setRange(0, min(100, max_demand * 1.15) if max_demand > 0 else 100)
        axis_y.setTitleText("Demand %")
        axis_y.setLabelsColor(QColor("#a3a3a3"))
        axis_y.setTitleBrush(QBrush(QColor("#a3a3a3")))
        axis_y.setGridLineColor(QColor("#2e2e2e"))
        self.chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        bar_series.attachAxis(axis_y)
        
        # Average line overlay
        averages = monthly_data.get('averages', [])
        if averages:
            avg_series = QLineSeries()
            avg_series.setName("Average")
            pen = QPen(QColor("#f39c12"))  # Amber/yellow
            pen.setWidth(3)
            avg_series.setPen(pen)
            
            for i, val in enumerate(averages):
                avg_pct = (val or 0) * 100
                avg_series.append(i, avg_pct)
                max_demand = max(max_demand, avg_pct)
            
            self.chart.addSeries(avg_series)
            avg_series.attachAxis(axis_x)
            avg_series.attachAxis(axis_y)
        
        # Readjust Y axis if needed
        axis_y.setRange(0, min(100, max_demand * 1.15) if max_demand > 0 else 100)


class DailyDemandChart(QChartView):
    """Daily Weather Demand - Scatter chart with trend lines for previous and current year."""
    
    def __init__(self):
        self.chart = QChart()
        super().__init__(self.chart)
        
        # Configure chart
        self.chart.setTitle("Daily Weather Demand")
        self.chart.setAnimationOptions(QChart.AnimationOption.NoAnimation)  # Scatter is slow with animation
        self.chart.setBackgroundBrush(QBrush(QColor("#121212")))
        self.chart.setBackgroundRoundness(12)
        self.chart.setMargins(QMargins(10, 10, 10, 10))
        
        # Title font
        title_font = QFont("Segoe UI", 11, QFont.Weight.DemiBold)
        self.chart.setTitleFont(title_font)
        self.chart.setTitleBrush(QBrush(QColor("#ffffff")))
        
        # Legend
        legend = self.chart.legend()
        legend.setVisible(True)
        legend.setAlignment(Qt.AlignmentFlag.AlignBottom)
        legend.setLabelColor(QColor("#a3a3a3"))
        legend.setFont(QFont("Segoe UI", 9))
        
        # View settings
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setStyleSheet("background: transparent; border: none;")
        self.setMinimumHeight(350)
    
    def update_data(self, daily_data: Dict):
        """
        Update chart with daily demand data.
        
        Args:
            daily_data: Dict with keys:
                'years': list of years
                'data': dict of year -> [366 daily values]
                'current_year': int
                'previous_year': int
        """
        self.chart.removeAllSeries()
        
        # Remove old axes
        for axis in self.chart.axes():
            self.chart.removeAxis(axis)
        
        if not daily_data or 'data' not in daily_data:
            return
        
        current_year = daily_data.get('current_year', 2025)
        previous_year = daily_data.get('previous_year', 2024)
        year_data = daily_data.get('data', {})
        
        # X axis (day of year)
        axis_x = QValueAxis()
        axis_x.setRange(1, 366)
        axis_x.setTitleText("Day of Year")
        axis_x.setLabelFormat("%d")
        axis_x.setTickCount(13)  # ~monthly
        axis_x.setLabelsColor(QColor("#a3a3a3"))
        axis_x.setTitleBrush(QBrush(QColor("#a3a3a3")))
        axis_x.setGridLineColor(QColor("#2e2e2e"))
        self.chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        
        # Y axis (demand %)
        axis_y = QValueAxis()
        axis_y.setRange(0, 100)
        axis_y.setTitleText("Demand %")
        axis_y.setLabelFormat("%.0f%%")
        axis_y.setLabelsColor(QColor("#a3a3a3"))
        axis_y.setTitleBrush(QBrush(QColor("#a3a3a3")))
        axis_y.setGridLineColor(QColor("#2e2e2e"))
        self.chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        
        max_demand = 0
        
        # Previous year scatter (blue)
        if previous_year in year_data:
            prev_scatter = QScatterSeries()
            prev_scatter.setName(f"{previous_year}")
            prev_scatter.setMarkerSize(6)
            prev_scatter.setColor(QColor("#6366f1"))  # Indigo
            prev_scatter.setBorderColor(QColor("#6366f1"))
            
            prev_points = []
            for day, val in enumerate(year_data[previous_year], 1):
                if val is not None and val > 0:
                    demand_pct = val * 100
                    prev_scatter.append(day, demand_pct)
                    prev_points.append((day, demand_pct))
                    max_demand = max(max_demand, demand_pct)
            
            self.chart.addSeries(prev_scatter)
            prev_scatter.attachAxis(axis_x)
            prev_scatter.attachAxis(axis_y)
            
            # Previous year trend line
            if len(prev_points) > 10:
                trend_line = self._calculate_trend_line(prev_points, f"{previous_year} Trend")
                trend_line.setColor(QColor("#6366f1"))
                pen = QPen(QColor("#6366f1"))
                pen.setWidth(2)
                pen.setStyle(Qt.PenStyle.DashLine)
                trend_line.setPen(pen)
                self.chart.addSeries(trend_line)
                trend_line.attachAxis(axis_x)
                trend_line.attachAxis(axis_y)
        
        # Current year scatter (green)
        if current_year in year_data:
            curr_scatter = QScatterSeries()
            curr_scatter.setName(f"{current_year}")
            curr_scatter.setMarkerSize(6)
            curr_scatter.setColor(QColor("#22c55e"))  # Green
            curr_scatter.setBorderColor(QColor("#22c55e"))
            
            curr_points = []
            for day, val in enumerate(year_data[current_year], 1):
                if val is not None and val > 0:
                    demand_pct = val * 100
                    curr_scatter.append(day, demand_pct)
                    curr_points.append((day, demand_pct))
                    max_demand = max(max_demand, demand_pct)
            
            self.chart.addSeries(curr_scatter)
            curr_scatter.attachAxis(axis_x)
            curr_scatter.attachAxis(axis_y)
            
            # Current year trend line
            if len(curr_points) > 10:
                trend_line = self._calculate_trend_line(curr_points, f"{current_year} Trend")
                trend_line.setColor(QColor("#22c55e"))
                pen = QPen(QColor("#22c55e"))
                pen.setWidth(2)
                pen.setStyle(Qt.PenStyle.DashLine)
                trend_line.setPen(pen)
                self.chart.addSeries(trend_line)
                trend_line.attachAxis(axis_x)
                trend_line.attachAxis(axis_y)
        
        # Adjust Y axis
        axis_y.setRange(0, min(120, max_demand * 1.15) if max_demand > 0 else 100)
    
    def _calculate_trend_line(self, points: List[tuple], name: str) -> QLineSeries:
        """Calculate linear regression trend line."""
        n = len(points)
        if n < 2:
            return QLineSeries()
        
        # Simple linear regression
        sum_x = sum(p[0] for p in points)
        sum_y = sum(p[1] for p in points)
        sum_xy = sum(p[0] * p[1] for p in points)
        sum_x2 = sum(p[0] ** 2 for p in points)
        
        # y = mx + b
        denom = n * sum_x2 - sum_x ** 2
        if denom == 0:
            return QLineSeries()
        
        m = (n * sum_xy - sum_x * sum_y) / denom
        b = (sum_y - m * sum_x) / n
        
        # Create trend line from day 1 to last day with data
        min_day = min(p[0] for p in points)
        max_day = max(p[0] for p in points)
        
        trend = QLineSeries()
        trend.setName(name)
        trend.append(min_day, m * min_day + b)
        trend.append(max_day, m * max_day + b)
        
        return trend


class RainGaugeChart(QChartView):
    """Rain Gauge - Bar chart showing monthly rainfall by year with average line."""
    
    def __init__(self):
        self.chart = QChart()
        super().__init__(self.chart)
        
        # Configure chart
        self.chart.setTitle("Monthly Rainfall")
        self.chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        self.chart.setBackgroundBrush(QBrush(QColor("#121212")))
        self.chart.setBackgroundRoundness(12)
        self.chart.setMargins(QMargins(10, 10, 10, 10))
        
        # Title font
        title_font = QFont("Segoe UI", 11, QFont.Weight.DemiBold)
        self.chart.setTitleFont(title_font)
        self.chart.setTitleBrush(QBrush(QColor("#ffffff")))
        
        # Legend
        legend = self.chart.legend()
        legend.setVisible(True)
        legend.setAlignment(Qt.AlignmentFlag.AlignBottom)
        legend.setLabelColor(QColor("#a3a3a3"))
        legend.setFont(QFont("Segoe UI", 9))
        
        # View settings
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setStyleSheet("background: transparent; border: none;")
        self.setMinimumHeight(280)
    
    def update_data(self, rain_data: Dict):
        """
        Update chart with monthly rainfall data.
        
        Args:
            rain_data: Dict with keys:
                'years': list of years
                'data': dict of year -> [12 monthly values in inches]
                'averages': list of 12 monthly average values
        """
        from PyQt6.QtCharts import QBarSeries, QBarSet, QBarCategoryAxis
        
        self.chart.removeAllSeries()
        
        # Remove old axes
        for axis in self.chart.axes():
            self.chart.removeAxis(axis)
        
        if not rain_data:
            return
        
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        # Get last 5 years of data
        all_years = sorted(rain_data.get('years', []), reverse=True)
        years_to_show = all_years[:5]  # Last 5 years
        years_to_show = sorted(years_to_show)  # Show in chronological order
        
        # Color palette for years - blues/cyans for rain
        year_colors = [
            QColor("#0ea5e9"),  # Sky blue (oldest)
            QColor("#3498db"),  # Cyan
            QColor("#14b8a6"),  # Teal
            QColor("#86efac"),  # Blue
            QColor("#6366f1"),  # Indigo (newest)
        ]
        
        # Create bar sets for each year
        bar_series = QBarSeries()
        max_rain = 0
        
        year_data = rain_data.get('data', {})
        for i, year in enumerate(years_to_show):
            if year in year_data:
                bar_set = QBarSet(str(year))
                color_idx = min(i, len(year_colors) - 1)
                bar_set.setColor(year_colors[color_idx])
                
                for month_val in year_data[year]:
                    val = month_val or 0
                    bar_set.append(val)
                    max_rain = max(max_rain, val)
                
                bar_series.append(bar_set)
        
        self.chart.addSeries(bar_series)
        
        # X axis (months)
        axis_x = QBarCategoryAxis()
        axis_x.append(months)
        axis_x.setLabelsColor(QColor("#a3a3a3"))
        axis_x.setGridLineColor(QColor("#2e2e2e"))
        self.chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        bar_series.attachAxis(axis_x)
        
        # Y axis (rainfall in inches)
        axis_y = QValueAxis()
        axis_y.setRange(0, max_rain * 1.2 if max_rain > 0 else 15)
        axis_y.setTitleText("Rain (in)")
        axis_y.setLabelFormat("%.1f\"")
        axis_y.setLabelsColor(QColor("#a3a3a3"))
        axis_y.setTitleBrush(QBrush(QColor("#a3a3a3")))
        axis_y.setGridLineColor(QColor("#2e2e2e"))
        self.chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        bar_series.attachAxis(axis_y)
        
        # Average line overlay
        averages = rain_data.get('averages', [])
        if averages:
            avg_series = QLineSeries()
            avg_series.setName("Average")
            pen = QPen(QColor("#f39c12"))  # Amber/yellow
            pen.setWidth(3)
            avg_series.setPen(pen)
            
            for i, val in enumerate(averages):
                avg_val = val or 0
                avg_series.append(i, avg_val)
                max_rain = max(max_rain, avg_val)
            
            self.chart.addSeries(avg_series)
            avg_series.attachAxis(axis_x)
            avg_series.attachAxis(axis_y)
        
        # Readjust Y axis if needed
        axis_y.setRange(0, max_rain * 1.2 if max_rain > 0 else 15)


# ============== STAT CARD ==============

class StatCard(QFrame):
    """Single stat card with value and label."""
    
    def __init__(self, label: str, value: str = "—", utility_type: str = ""):
        super().__init__()
        
        if utility_type == "electric":
            self.setObjectName("statCardElectric")
            value_style = "statValueElectric"
        elif utility_type == "gas":
            self.setObjectName("statCardGas")
            value_style = "statValueGas"
        elif utility_type == "water":
            self.setObjectName("statCardWater")
            value_style = "statValueWater"
        else:
            self.setObjectName("statCard")
            value_style = "statValue"
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)
        
        self.value_label = QLabel(value)
        self.value_label.setObjectName(value_style)
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.value_label)
        
        name_label = QLabel(label)
        name_label.setObjectName("statLabel")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name_label)
    
    def set_value(self, value: str):
        self.value_label.setText(value)


# ============== UTILITY PAGE ==============

class UtilityPage(QWidget):
    """Page for a single utility type with stats, charts, and bills table."""
    
    add_bill_requested = pyqtSignal(str)  # Signal to request adding a bill
    import_pdf_requested = pyqtSignal(str)  # Signal to request PDF import
    
    def __init__(self, utility_type: str, db: DatabaseManager):
        super().__init__()
        self.utility_type = utility_type  # 'electric', 'gas', or 'water'
        self.db = db
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # Header row with title and add button
        header = QHBoxLayout()
        
        icons = {'electric': '⚡', 'gas': '🔥', 'water': '💧'}
        titles = {'electric': 'Electric', 'gas': 'Gas', 'water': 'Water'}
        
        title = QLabel(f"{icons.get(self.utility_type, '')} {titles.get(self.utility_type, 'Utility')}")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch()
        
        # Import PDF button
        import_btn = QPushButton(f"📄 Import PDF")
        import_btn.setObjectName("importButton")
        import_btn.setToolTip(f"Import {titles.get(self.utility_type, '')} bill from PDF")
        import_btn.clicked.connect(lambda: self.import_pdf_requested.emit(self.utility_type))
        header.addWidget(import_btn)
        
        add_btn = QPushButton(f"+ Add {titles.get(self.utility_type, '')} Bill")
        add_btn.setObjectName("addButton")
        add_btn.clicked.connect(lambda: self.add_bill_requested.emit(self.utility_type))
        header.addWidget(add_btn)
        
        layout.addLayout(header)
        
        # Stats row
        stats_frame = QFrame()
        stats_frame.setObjectName("statsBar")
        stats_layout = QHBoxLayout(stats_frame)
        stats_layout.setContentsMargins(0, 8, 0, 8)
        stats_layout.setSpacing(16)
        
        self.stat_this_month = StatCard("This Month", "$0", self.utility_type)
        self.stat_last_month = StatCard("Last Month", "$0", self.utility_type)
        self.stat_avg_month = StatCard("Avg/Month", "$0", self.utility_type)
        self.stat_ytd = StatCard("YTD", "$0", self.utility_type)
        
        stats_layout.addWidget(self.stat_this_month)
        stats_layout.addWidget(self.stat_last_month)
        stats_layout.addWidget(self.stat_avg_month)
        stats_layout.addWidget(self.stat_ytd)
        stats_layout.addStretch()
        
        layout.addWidget(stats_frame)
        
        # Charts row - ApexCharts
        charts_layout = QHBoxLayout()
        charts_layout.setSpacing(16)
        
        units = {'electric': 'kWh', 'gas': 'Therms', 'water': 'Gallons'}
        
        # Wrap charts in card frames - use ApexCharts if available, else QtCharts
        cost_card = QFrame()
        cost_card.setObjectName("chartPanel")
        cost_card_layout = QVBoxLayout(cost_card)
        cost_card_layout.setContentsMargins(8, 8, 8, 8)
        if USE_APEX_CHARTS:
            self.cost_chart = ApexUtilityLineChart("Cost Over Time", self.utility_type, "$")
        else:
            self.cost_chart = UtilityLineChart("Cost Over Time", self.utility_type, "$")
        cost_card_layout.addWidget(self.cost_chart)
        charts_layout.addWidget(cost_card)
        
        usage_card = QFrame()
        usage_card.setObjectName("chartPanel")
        usage_card_layout = QVBoxLayout(usage_card)
        usage_card_layout.setContentsMargins(8, 8, 8, 8)
        if USE_APEX_CHARTS:
            self.usage_chart = ApexUtilityLineChart("Usage Over Time", self.utility_type, units.get(self.utility_type, ""))
        else:
            self.usage_chart = UtilityLineChart("Usage Over Time", self.utility_type, units.get(self.utility_type, ""))
        usage_card_layout.addWidget(self.usage_chart)
        charts_layout.addWidget(usage_card)
        
        layout.addLayout(charts_layout)
        
        # Bills table
        table_label = QLabel("Bills History")
        table_label.setStyleSheet("color: #a3a3a3; font-weight: 600; font-size: 12px;")
        layout.addWidget(table_label)
        
        self.bills_table = QTableWidget()
        self.bills_table.setColumnCount(6)
        
        if self.utility_type == "electric":
            self.bills_table.setHorizontalHeaderLabels(["Date", "kWh", "Days", "Total", "$/Day", "$/kWh"])
        elif self.utility_type == "gas":
            self.bills_table.setHorizontalHeaderLabels(["Date", "Therms", "Days", "Total", "$/Day", "$/Therm"])
        else:
            self.bills_table.setHorizontalHeaderLabels(["Date", "Gallons", "Days", "Total", "$/Day", "$/kGal"])
        
        self.bills_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.bills_table.verticalHeader().setVisible(False)
        self.bills_table.setMinimumHeight(200)
        
        layout.addWidget(self.bills_table)
    
    def refresh_data(self):
        """Refresh all data on this page."""
        year = datetime.now().year
        month = datetime.now().month
        last_month = month - 1 if month > 1 else 12
        last_month_year = year if month > 1 else year - 1
        
        # Get bills based on utility type
        if self.utility_type == "electric":
            bills = self.db.get_electric_bills(100)
            usage_key = 'usage_kwh'
            cost_key = 'total_cost'
        elif self.utility_type == "gas":
            bills = self.db.get_gas_bills(100)
            usage_key = 'therms'
            cost_key = 'total_cost'
        else:
            bills = self.db.get_water_bills(100)
            usage_key = 'usage_gallons'
            cost_key = 'total_cost'
        
        # Calculate stats
        this_month_cost = 0
        last_month_cost = 0
        ytd_cost = 0
        all_costs = []
        
        for bill in bills:
            bill_date = bill['bill_date']
            if isinstance(bill_date, str):
                bill_date = datetime.strptime(bill_date, '%Y-%m-%d').date()
            
            cost = bill.get(cost_key, 0) or 0
            all_costs.append(cost)
            
            if bill_date.year == year:
                ytd_cost += cost
                if bill_date.month == month:
                    this_month_cost += cost
            
            if bill_date.year == last_month_year and bill_date.month == last_month:
                last_month_cost += cost
        
        avg_cost = sum(all_costs) / len(all_costs) if all_costs else 0
        
        # Update stat cards
        self.stat_this_month.set_value(f"${this_month_cost:.0f}")
        self.stat_last_month.set_value(f"${last_month_cost:.0f}")
        self.stat_avg_month.set_value(f"${avg_cost:.0f}")
        self.stat_ytd.set_value(f"${ytd_cost:.0f}")
        
        # Build chart data
        self._update_charts(bills, usage_key, cost_key, year)
        
        # Update table
        self._update_table(bills, usage_key, cost_key)
    
    def _update_charts(self, bills, usage_key, cost_key, year):
        """Update the cost and usage charts."""
        # Organize data by year and month
        data_by_year = {}  # {year: {month: {'cost': x, 'usage': y}}}
        
        for bill in bills:
            bill_date = bill['bill_date']
            if isinstance(bill_date, str):
                bill_date = datetime.strptime(bill_date, '%Y-%m-%d').date()
            
            y = bill_date.year
            m = bill_date.month
            
            if y not in data_by_year:
                data_by_year[y] = {}
            if m not in data_by_year[y]:
                data_by_year[y][m] = {'cost': 0, 'usage': 0}
            
            data_by_year[y][m]['cost'] += bill.get(cost_key, 0) or 0
            data_by_year[y][m]['usage'] += bill.get(usage_key, 0) or 0
        
        # Calculate average across all years
        avg_cost = [0] * 12
        avg_usage = [0] * 12
        count_cost = [0] * 12
        count_usage = [0] * 12
        
        for y, months in data_by_year.items():
            for m, vals in months.items():
                if vals['cost'] > 0:
                    avg_cost[m-1] += vals['cost']
                    count_cost[m-1] += 1
                if vals['usage'] > 0:
                    avg_usage[m-1] += vals['usage']
                    count_usage[m-1] += 1
        
        avg_cost = [avg_cost[i] / count_cost[i] if count_cost[i] > 0 else 0 for i in range(12)]
        avg_usage = [avg_usage[i] / count_usage[i] if count_usage[i] > 0 else 0 for i in range(12)]
        
        # Find the most recent year with data for "current" and year before that for "previous"
        available_years = sorted(data_by_year.keys(), reverse=True)
        
        # Current year data (most recent year with data, or actual current year if it has data)
        curr_cost = [0] * 12
        curr_usage = [0] * 12
        curr_year_label = year
        
        if year in data_by_year:
            # Use actual current year
            curr_year_label = year
            for m, vals in data_by_year[year].items():
                curr_cost[m-1] = vals['cost']
                curr_usage[m-1] = vals['usage']
        elif available_years:
            # Use most recent year with data
            curr_year_label = available_years[0]
            for m, vals in data_by_year[curr_year_label].items():
                curr_cost[m-1] = vals['cost']
                curr_usage[m-1] = vals['usage']
        
        # Previous year data (year before the "current" year we're showing)
        prev_cost = [0] * 12
        prev_usage = [0] * 12
        prev_year = curr_year_label - 1
        
        if prev_year in data_by_year:
            for m, vals in data_by_year[prev_year].items():
                prev_cost[m-1] = vals['cost']
                prev_usage[m-1] = vals['usage']
        
        # Update charts with year labels
        self.cost_chart.update_data(avg_cost, prev_cost, curr_cost, prev_year, curr_year_label)
        self.usage_chart.update_data(avg_usage, prev_usage, curr_usage, prev_year, curr_year_label)
    
    def _update_table(self, bills, usage_key, cost_key):
        """Update the bills table."""
        self.bills_table.setRowCount(len(bills))
        
        for row, bill in enumerate(bills):
            bill_date = bill['bill_date']
            usage = bill.get(usage_key, 0) or 0
            days = bill.get('days', 30) or 30
            total = bill.get(cost_key, 0) or 0
            
            self.bills_table.setItem(row, 0, QTableWidgetItem(str(bill_date)))
            
            if self.utility_type == "electric":
                self.bills_table.setItem(row, 1, QTableWidgetItem(f"{usage:.0f}"))
                per_unit = total / usage if usage > 0 else 0
                self.bills_table.setItem(row, 5, QTableWidgetItem(f"${per_unit:.3f}"))
            elif self.utility_type == "gas":
                self.bills_table.setItem(row, 1, QTableWidgetItem(f"{usage:.1f}"))
                per_unit = total / usage if usage > 0 else 0
                self.bills_table.setItem(row, 5, QTableWidgetItem(f"${per_unit:.2f}"))
            else:
                self.bills_table.setItem(row, 1, QTableWidgetItem(f"{usage/1000:.1f}k"))
                per_unit = total / usage * 1000 if usage > 0 else 0
                self.bills_table.setItem(row, 5, QTableWidgetItem(f"${per_unit:.2f}"))
            
            self.bills_table.setItem(row, 2, QTableWidgetItem(str(days)))
            self.bills_table.setItem(row, 3, QTableWidgetItem(f"${total:.2f}"))
            self.bills_table.setItem(row, 4, QTableWidgetItem(f"${total/days:.2f}" if days > 0 else "—"))


# ============== DEMAND PAGE ==============

class DemandPage(QWidget):
    """Page showing demand data in three tabs: Matrix, Monthly, Daily."""
    
    def __init__(self, db: DatabaseManager):
        super().__init__()
        self.db = db
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # Header
        title = QLabel("📊 Energy Demand Analysis")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        
        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #2e2e2e; background: #121212; border-radius: 8px; }
            QTabBar::tab { background: #121212; color: #a3a3a3; padding: 8px 16px; margin-right: 4px; border-top-left-radius: 8px; border-top-right-radius: 8px; }
            QTabBar::tab:selected { background: #2e2e2e; color: #ffffff; }
            QTabBar::tab:hover { background: #242424; }
        """)
        
        # Tab 1: Matrix (Yearly Summary)
        self.matrix_tab = QWidget()
        self._setup_matrix_tab()
        self.tabs.addTab(self.matrix_tab, "Yearly Matrix")
        
        # Tab 2: Monthly
        self.monthly_tab = QWidget()
        self._setup_monthly_tab()
        self.tabs.addTab(self.monthly_tab, "Monthly Demand")
        
        # Tab 3: Daily
        self.daily_tab = QWidget()
        self._setup_daily_tab()
        self.tabs.addTab(self.daily_tab, "Daily Demand")
        
        layout.addWidget(self.tabs)
    
    def _setup_matrix_tab(self):
        """Setup the yearly demand matrix with 3 tables and formulas card."""
        layout = QVBoxLayout(self.matrix_tab)
        
        # Info label
        info = QLabel("Yearly energy demand summary showing cooling/heating days, cost per day, and demand index.")
        info.setStyleSheet("color: #737373; font-size: 12px; padding: 8px 0;")
        layout.addWidget(info)
        
        # Horizontal layout for all 3 tables + formulas card
        content_layout = QHBoxLayout()
        content_layout.setSpacing(12)
        
        # Common table style
        table_style = """
            QTableWidget { background-color: #121212; gridline-color: #2e2e2e; color: #fafafa; }
            QTableWidget::item { padding: 4px 6px; }
            QTableWidget::item:alternate { background-color: #121212; }
            QHeaderView::section { background-color: #2e2e2e; color: #ffffff; padding: 6px 4px; font-weight: bold; font-size: 11px; }
        """
        
        # === Table 1: Demand ===
        demand_container = QVBoxLayout()
        demand_label = QLabel("📊 Demand")
        demand_label.setStyleSheet("font-weight: bold; color: #ffffff; font-size: 12px;")
        demand_container.addWidget(demand_label)
        
        self.demand_table = QTableWidget()
        self.demand_table.setColumnCount(4)
        self.demand_table.setHorizontalHeaderLabels(["Year", "CLG\nDemand", "HTG\nDemand", "Total\nDemand"])
        self.demand_table.verticalHeader().setVisible(False)
        self.demand_table.setAlternatingRowColors(True)
        self.demand_table.setStyleSheet(table_style)
        
        header = self.demand_table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setMinimumSectionSize(50)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setFixedHeight(38)
        
        demand_container.addWidget(self.demand_table)
        content_layout.addLayout(demand_container, stretch=1)
        
        # === Table 2: Degree Days ===
        degree_container = QVBoxLayout()
        degree_label = QLabel("🌡️ Degree Days")
        degree_label.setStyleSheet("font-weight: bold; color: #ffffff; font-size: 12px;")
        degree_container.addWidget(degree_label)
        
        self.degree_days_table = QTableWidget()
        self.degree_days_table.setColumnCount(3)
        self.degree_days_table.setHorizontalHeaderLabels(["CLG\nDays", "HTG\nDays", "ECON\nDays"])
        self.degree_days_table.verticalHeader().setVisible(False)
        self.degree_days_table.setAlternatingRowColors(True)
        self.degree_days_table.setStyleSheet(table_style)
        
        header = self.degree_days_table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setMinimumSectionSize(50)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setFixedHeight(38)
        
        degree_container.addWidget(self.degree_days_table)
        content_layout.addLayout(degree_container, stretch=1)
        
        # === Table 3: Index ===
        index_container = QVBoxLayout()
        index_label = QLabel("📈 Cost & Index")
        index_label.setStyleSheet("font-weight: bold; color: #ffffff; font-size: 12px;")
        index_container.addWidget(index_label)
        
        self.index_table = QTableWidget()
        self.index_table.setColumnCount(4)
        self.index_table.setHorizontalHeaderLabels(["CPD", "% Avg\nCost", "Demand\nIdx", "% Avg\nDem"])
        self.index_table.verticalHeader().setVisible(False)
        self.index_table.setAlternatingRowColors(True)
        self.index_table.setStyleSheet(table_style)
        
        header = self.index_table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setMinimumSectionSize(50)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setFixedHeight(38)
        
        index_container.addWidget(self.index_table)
        content_layout.addLayout(index_container, stretch=1)
        
        # Formulas Card (right side - fixed width)
        self.formulas_card = self._create_formulas_card()
        content_layout.addWidget(self.formulas_card)
        
        layout.addLayout(content_layout)
    
    def _create_formulas_card(self) -> QFrame:
        """Create the formulas reference card."""
        card = QFrame()
        card.setObjectName("formulasCard")
        card.setStyleSheet("""
            #formulasCard {
                background-color: #121212;
                border: 1px solid #2e2e2e;
                border-radius: 12px;
                padding: 16px;
            }
            #formulasCard QLabel {
                color: #fafafa;
            }
        """)
        card.setMinimumWidth(300)
        card.setMaximumWidth(340)
        
        layout = QVBoxLayout(card)
        layout.setSpacing(8)
        
        # Title
        title = QLabel("📐 Demand Formulas")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        layout.addWidget(title)
        
        # Separator
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet("background-color: #2e2e2e;")
        layout.addWidget(sep1)
        
        # Cooling formula
        cool_title = QLabel("❄️ Cooling Demand")
        cool_title.setStyleSheet("font-weight: bold; color: #86efac;")
        layout.addWidget(cool_title)
        
        cool_formula = QLabel("(Temp High − Cool Min) / Cool Min")
        cool_formula.setStyleSheet("font-family: monospace; color: #a3a3a3; padding-left: 8px; font-size: 11px;")
        layout.addWidget(cool_formula)
        
        cool_condition = QLabel("When Temp High > Cool Min")
        cool_condition.setStyleSheet("font-size: 10px; color: #737373; padding-left: 8px;")
        layout.addWidget(cool_condition)
        
        # Heating formula
        heat_title = QLabel("🔥 Heating Demand")
        heat_title.setStyleSheet("font-weight: bold; color: #ef4444;")
        layout.addWidget(heat_title)
        
        heat_formula = QLabel("(Heat Max − Temp High) / Heat Max")
        heat_formula.setStyleSheet("font-family: monospace; color: #a3a3a3; padding-left: 8px; font-size: 11px;")
        layout.addWidget(heat_formula)
        
        heat_condition = QLabel("When Temp High < Heat Max")
        heat_condition.setStyleSheet("font-size: 10px; color: #737373; padding-left: 8px;")
        layout.addWidget(heat_condition)
        
        # Economy
        econ_title = QLabel("🌿 Economy Day")
        econ_title.setStyleSheet("font-weight: bold; color: #22c55e;")
        layout.addWidget(econ_title)
        
        econ_desc = QLabel("Heat Max ≤ Temp ≤ Cool Min")
        econ_desc.setStyleSheet("font-family: monospace; color: #a3a3a3; padding-left: 8px; font-size: 11px;")
        layout.addWidget(econ_desc)
        
        # Separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("background-color: #2e2e2e;")
        layout.addWidget(sep2)
        
        # Projected Demand formula (BLENDED)
        proj_title = QLabel("🎯 Projected Demand")
        proj_title.setStyleSheet("font-weight: bold; color: #3498db;")
        layout.addWidget(proj_title)
        
        proj_formula = QLabel("M² × YTD + (1 − M) × Avg")
        proj_formula.setStyleSheet("font-family: monospace; color: #a3a3a3; padding-left: 8px; font-size: 11px;")
        layout.addWidget(proj_formula)
        
        proj_where = QLabel("M = month / 12")
        proj_where.setStyleSheet("font-family: monospace; color: #737373; padding-left: 8px; font-size: 10px;")
        layout.addWidget(proj_where)
        
        proj_explain = QLabel("Blends YTD actuals with history.\nEarly year → more history weight.\nLate year → more actual weight.")
        proj_explain.setStyleSheet("font-size: 10px; color: #737373; padding-left: 8px;")
        proj_explain.setWordWrap(True)
        layout.addWidget(proj_explain)
        
        # Separator
        sep2b = QFrame()
        sep2b.setFrameShape(QFrame.Shape.HLine)
        sep2b.setStyleSheet("background-color: #2e2e2e;")
        layout.addWidget(sep2b)
        
        # Expected CPD% formula (KEY FORMULA)
        exp_title = QLabel("📈 Expected CPD %")
        exp_title.setStyleSheet("font-weight: bold; color: #f59e0b;")
        layout.addWidget(exp_title)
        
        exp_formula = QLabel("sign(d) × (|d × 100|^(1/K)) / 100")
        exp_formula.setStyleSheet("font-family: monospace; color: #a3a3a3; padding-left: 8px; font-size: 11px;")
        layout.addWidget(exp_formula)
        
        exp_where = QLabel("d = (Projected − Avg) / Avg")
        exp_where.setStyleSheet("font-family: monospace; color: #737373; padding-left: 8px; font-size: 10px;")
        layout.addWidget(exp_where)
        
        exp_explain = QLabel("K-th root compresses large swings:\nsmall Δ → bigger impact, large Δ → dampened")
        exp_explain.setStyleSheet("font-size: 10px; color: #737373; padding-left: 8px;")
        exp_explain.setWordWrap(True)
        layout.addWidget(exp_explain)
        
        # Separator
        sep3 = QFrame()
        sep3.setFrameShape(QFrame.Shape.HLine)
        sep3.setStyleSheet("background-color: #2e2e2e;")
        layout.addWidget(sep3)
        
        # Current Settings
        settings_title = QLabel("⚙️ Settings")
        settings_title.setStyleSheet("font-weight: bold; color: #f39c12;")
        layout.addWidget(settings_title)
        
        # Settings values (will be updated in refresh)
        self.settings_labels = {}
        
        settings_grid = QGridLayout()
        settings_grid.setSpacing(2)
        
        settings_items = [
            ("Heat Min:", "heating_min_temp", "°F"),
            ("Heat Max:", "heating_max_temp", "°F"),
            ("Cool Min:", "cooling_min_temp", "°F"),
            ("Cool Max:", "cooling_max_temp", "°F"),
            ("K Factor:", "k_factor", ""),
        ]
        
        for row, (label_text, key, unit) in enumerate(settings_items):
            label = QLabel(label_text)
            label.setStyleSheet("color: #a3a3a3; font-size: 11px;")
            settings_grid.addWidget(label, row, 0)
            
            value_label = QLabel("—")
            value_label.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 11px;")
            value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            self.settings_labels[key] = (value_label, unit)
            settings_grid.addWidget(value_label, row, 1)
        
        layout.addLayout(settings_grid)
        
        # Separator
        sep4 = QFrame()
        sep4.setFrameShape(QFrame.Shape.HLine)
        sep4.setStyleSheet("background-color: #2e2e2e;")
        layout.addWidget(sep4)
        
        # Other formulas
        other_title = QLabel("📊 Other")
        other_title.setStyleSheet("font-weight: bold; color: #a855f7;")
        layout.addWidget(other_title)
        
        cpd_label = QLabel("CPD = Total Cost / Days")
        cpd_label.setStyleSheet("font-family: monospace; color: #a3a3a3; font-size: 10px; padding-left: 8px;")
        layout.addWidget(cpd_label)
        
        idx_label = QLabel("Demand Idx = Avg Dem × Days")
        idx_label.setStyleSheet("font-family: monospace; color: #a3a3a3; font-size: 10px; padding-left: 8px;")
        layout.addWidget(idx_label)
        
        actual_label = QLabel("Actual CPD% = (CPD − Avg) / Avg")
        actual_label.setStyleSheet("font-family: monospace; color: #a3a3a3; font-size: 10px; padding-left: 8px;")
        layout.addWidget(actual_label)
        
        layout.addStretch()
        
        return card
    
    def _update_formulas_settings(self):
        """Update the settings values in the formulas card."""
        if not hasattr(self, 'settings_labels'):
            return
        
        settings = self.db.get_demand_settings()
        for key, (label, unit) in self.settings_labels.items():
            value = settings.get(key, 0)
            if key == 'k_factor':
                label.setText(f"{value:.2f}")
            else:
                label.setText(f"{value:.0f}{unit}")
    
    def _setup_monthly_tab(self):
        """Setup the monthly demand table."""
        layout = QVBoxLayout(self.monthly_tab)
        
        # Info label
        info = QLabel("Monthly demand averages by year. Values show % of max demand for each month.")
        info.setStyleSheet("color: #737373; font-size: 12px; padding: 8px 0;")
        layout.addWidget(info)
        
        # Table
        self.monthly_table = QTableWidget()
        self.monthly_table.setColumnCount(13)
        self.monthly_table.setHorizontalHeaderLabels([
            "Year", "Jan", "Feb", "Mar", "Apr", "May", "Jun", 
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
        ])
        self.monthly_table.verticalHeader().setVisible(False)
        self.monthly_table.setAlternatingRowColors(True)
        self.monthly_table.setStyleSheet("""
            QTableWidget { background-color: #121212; gridline-color: #2e2e2e; color: #fafafa; }
            QTableWidget::item { padding: 4px 8px; }
            QTableWidget::item:alternate { background-color: #121212; }
            QHeaderView::section { background-color: #2e2e2e; color: #ffffff; padding: 6px 4px; font-weight: bold; font-size: 11px; }
        """)
        
        # Auto-fit columns to content
        header = self.monthly_table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setMinimumSectionSize(50)
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        
        layout.addWidget(self.monthly_table)
    
    def _setup_daily_tab(self):
        """Setup the daily demand table."""
        layout = QVBoxLayout(self.daily_tab)
        
        # Info label
        info = QLabel("Daily demand data showing weather-based energy demand calculations.")
        info.setStyleSheet("color: #737373; font-size: 12px; padding: 8px 0;")
        layout.addWidget(info)
        
        # Table (full height since no chart)
        self.daily_table = QTableWidget()
        self.daily_table.verticalHeader().setVisible(False)
        self.daily_table.setAlternatingRowColors(True)
        self.daily_table.setStyleSheet("""
            QTableWidget { background-color: #121212; gridline-color: #2e2e2e; color: #fafafa; }
            QTableWidget::item { padding: 2px 6px; font-size: 11px; }
            QTableWidget::item:alternate { background-color: #121212; }
            QHeaderView::section { background-color: #2e2e2e; color: #ffffff; padding: 6px 4px; font-weight: bold; font-size: 11px; }
        """)
        
        # Auto-fit columns
        header = self.daily_table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setMinimumSectionSize(50)
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        
        layout.addWidget(self.daily_table)
    
    def refresh_data(self):
        """Refresh all demand tables."""
        self._refresh_matrix()
        self._refresh_monthly()
        self._refresh_daily()
        self._update_formulas_settings()
    
    def _refresh_matrix(self):
        """Refresh the yearly matrix tables."""
        from datetime import datetime
        
        matrix = self.db.get_demand_matrix()
        current_year = datetime.now().year
        
        # Get blended projection for current year
        blended = self.db.get_blended_demand(current_year)
        
        num_rows = len(matrix)
        
        # Set row counts for all 3 tables
        self.demand_table.setRowCount(num_rows)
        self.degree_days_table.setRowCount(num_rows)
        self.index_table.setRowCount(num_rows)
        
        for row, data in enumerate(matrix):
            year = data['year']
            year_str = str(year)
            is_current_year = (year == current_year)
            
            # For current year, use blended values
            if is_current_year:
                avg_cooling = blended['blended_cooling']
                avg_heating = blended['blended_heating']
                total_demand = blended['blended_total']
                
                # Raw values for tooltip
                raw_cooling = data['avg_cooling']
                raw_heating = data['avg_heating']
                raw_total = data['total_demand']
                
                # Historical averages for tooltip
                hist_cooling = blended['avg_cooling']
                hist_heating = blended['avg_heating']
                hist_total = blended['avg_total']
            else:
                avg_cooling = data['avg_cooling']
                avg_heating = data['avg_heating']
                total_demand = data['total_demand']
            
            # === Table 1: Demand (with Year) ===
            # Year
            item = QTableWidgetItem(year_str)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if is_current_year:
                item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            self.demand_table.setItem(row, 0, item)
            
            # CLG Demand (Blue)
            item = QTableWidgetItem(f"{avg_cooling*100:.1f}%")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setForeground(QColor("#86efac"))  # Blue for cooling
            if is_current_year:
                item.setToolTip(
                    f"Blended Projection: {avg_cooling*100:.1f}%\n"
                    f"─────────────────\n"
                    f"YTD Actual: {raw_cooling*100:.1f}%\n"
                    f"Historical Avg: {hist_cooling*100:.1f}%\n"
                    f"─────────────────\n"
                    f"Weight: {blended['ytd_weight']*100:.0f}% YTD / {blended['hist_weight']*100:.0f}% Hist"
                )
                item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            self.demand_table.setItem(row, 1, item)
            
            # HTG Demand (Red)
            item = QTableWidgetItem(f"{avg_heating*100:.1f}%")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setForeground(QColor("#ef4444"))  # Red for heating
            if is_current_year:
                item.setToolTip(
                    f"Blended Projection: {avg_heating*100:.1f}%\n"
                    f"─────────────────\n"
                    f"YTD Actual: {raw_heating*100:.1f}%\n"
                    f"Historical Avg: {hist_heating*100:.1f}%\n"
                    f"─────────────────\n"
                    f"Weight: {blended['ytd_weight']*100:.0f}% YTD / {blended['hist_weight']*100:.0f}% Hist"
                )
                item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            self.demand_table.setItem(row, 2, item)
            
            # Total Demand (Standard grey)
            item = QTableWidgetItem(f"{total_demand*100:.1f}%")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if is_current_year:
                item.setToolTip(
                    f"Blended Projection: {total_demand*100:.1f}%\n"
                    f"─────────────────\n"
                    f"YTD Actual: {raw_total*100:.1f}%\n"
                    f"Historical Avg: {hist_total*100:.1f}%"
                )
                item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            self.demand_table.setItem(row, 3, item)
            
            # === Table 2: Degree Days (no Year) ===
            # CLG Days
            item = QTableWidgetItem(str(data['cooling_days']))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.degree_days_table.setItem(row, 0, item)
            
            # HTG Days
            item = QTableWidgetItem(str(data['heating_days']))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.degree_days_table.setItem(row, 1, item)
            
            # ECON Days
            item = QTableWidgetItem(str(data['econ_days']))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.degree_days_table.setItem(row, 2, item)
            
            # === Table 3: Index (no Year) ===
            # CPD (Cost Per Day)
            item = QTableWidgetItem(f"${data['cost_per_day']:.2f}")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.index_table.setItem(row, 0, item)
            
            # % Avg Cost
            pct = data['pct_avg_cost'] * 100
            item = QTableWidgetItem(f"{pct:+.1f}%")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if pct > 0:
                item.setForeground(QColor("#ef4444"))  # Red = above avg (bad)
            else:
                item.setForeground(QColor("#22c55e"))  # Green = below avg (good)
            self.index_table.setItem(row, 1, item)
            
            # Demand Index
            item = QTableWidgetItem(f"{data['demand_index_total']:.1f}")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.index_table.setItem(row, 2, item)
            
            # % Avg Demand
            pct = data['pct_avg_demand'] * 100
            item = QTableWidgetItem(f"{pct:+.1f}%")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.index_table.setItem(row, 3, item)
    
    def _refresh_monthly(self):
        """Refresh the monthly demand table."""
        monthly = self.db.get_demand_monthly()
        
        years = monthly['years']
        num_rows = len(years) + 1  # +1 for average row
        
        self.monthly_table.setRowCount(num_rows)
        
        # Average row first
        item = QTableWidgetItem("Avg")
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.monthly_table.setItem(0, 0, item)
        
        for m in range(12):
            val = monthly['averages'][m] * 100
            item = QTableWidgetItem(f"{val:.1f}%")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            self._color_demand_cell(item, val)
            self.monthly_table.setItem(0, m + 1, item)
        
        # Year rows
        for row, year in enumerate(years, 1):
            # Year column
            item = QTableWidgetItem(str(year))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.monthly_table.setItem(row, 0, item)
            
            # Month columns
            year_data = monthly['data'].get(year, [0] * 12)
            for m in range(12):
                val = year_data[m] * 100
                item = QTableWidgetItem(f"{val:.1f}%")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._color_demand_cell(item, val)
                self.monthly_table.setItem(row, m + 1, item)
    
    def _refresh_daily(self):
        """Refresh the daily demand table."""
        daily = self.db.get_demand_daily()
        
        years = daily['years']
        current_year = datetime.now().year
        previous_year = current_year - 1
        
        # Setup columns: Day, Avg, then each year
        num_cols = 2 + len(years)
        self.daily_table.setColumnCount(num_cols)
        
        headers = ["Day", "Avg"] + [str(y) for y in years]
        self.daily_table.setHorizontalHeaderLabels(headers)
        
        # Fill data (366 rows for each day of year)
        self.daily_table.setRowCount(366)
        
        for day in range(366):
            # Day column (1-366)
            item = QTableWidgetItem(str(day + 1))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.daily_table.setItem(day, 0, item)
            
            # Average column
            val = daily['averages'][day] * 100
            item = QTableWidgetItem(f"{val:.0f}%")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            self._color_demand_cell(item, val)
            self.daily_table.setItem(day, 1, item)
            
            # Year columns
            for col, year in enumerate(years, 2):
                year_data = daily['data'].get(year, [None] * 366)
                val = year_data[day]
                
                if val is not None:
                    val_pct = val * 100
                    item = QTableWidgetItem(f"{val_pct:.0f}%")
                    self._color_demand_cell(item, val_pct)
                else:
                    item = QTableWidgetItem("—")
                    item.setForeground(QColor("#4a5568"))
                
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.daily_table.setItem(day, col, item)
    
    def _color_demand_cell(self, item: QTableWidgetItem, value: float):
        """Color code a demand cell based on value (0-100%)."""
        if value >= 70:
            item.setForeground(QColor("#ef4444"))  # Red - high demand
        elif value >= 40:
            item.setForeground(QColor("#e74c3c"))  # Orange - medium demand
        elif value >= 20:
            item.setForeground(QColor("#f39c12"))  # Yellow - low demand
        else:
            item.setForeground(QColor("#22c55e"))  # Green - minimal demand


# ============== WEATHER UPDATE THREAD ==============

class WeatherUpdateThread(QThread):
    progress = pyqtSignal(int, int, str)
    finished_update = pyqtSignal(int)
    error = pyqtSignal(str)
    
    def __init__(self, api, db, start_date, end_date):
        super().__init__()
        self.api = api
        self.db = db
        self.start_date = start_date
        self.end_date = end_date
        self.calculator = WeatherDemandCalculator()
        self._cancelled = False
    
    def cancel(self):
        self._cancelled = True
    
    def run(self):
        try:
            current = self.start_date
            total_days = (self.end_date - self.start_date).days + 1
            days_updated = 0
            
            while current <= self.end_date and not self._cancelled:
                day_num = (current - self.start_date).days + 1
                self.progress.emit(day_num, total_days, f"Fetching {current}...")
                
                obs = self.api.get_historical_daily(current)
                if obs and obs.temp_high is not None:
                    demands = self.calculator.calculate_demands(obs.temp_high, obs.temp_low or obs.temp_high)
                    weather_day = WeatherDay(
                        id=None, date=current,
                        temp_high=obs.temp_high, temp_avg=obs.temp_avg, temp_low=obs.temp_low,
                        dewpoint_high=obs.dewpoint_high, dewpoint_avg=obs.dewpoint_avg, dewpoint_low=obs.dewpoint_low,
                        humidity_high=obs.humidity_high, humidity_avg=obs.humidity_avg, humidity_low=obs.humidity_low,
                        wind_max=obs.wind_max, wind_avg=obs.wind_avg, wind_gust=obs.wind_gust,
                        pressure_max=obs.pressure_max, pressure_min=obs.pressure_min,
                        rain_total=obs.rain_total or 0,
                        cooling_demand=demands['cooling_demand'],
                        heating_demand=demands['heating_demand'],
                        max_demand=demands['max_demand']
                    )
                    self.db.add_weather_day(weather_day)
                    days_updated += 1
                
                current += timedelta(days=1)
            
            self.finished_update.emit(days_updated)
        except Exception as e:
            self.error.emit(str(e))


# ============== DIALOGS ==============

class SettingsDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Settings")
        self.setMinimumWidth(500)
        self._setup_ui()
        self._load_settings()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        
        # Weather Source Selection
        source_group = QGroupBox("Weather Data Source")
        source_layout = QFormLayout(source_group)
        
        self.weather_source = QComboBox()
        self.weather_source.addItems([
            "Open-Meteo (Free, No API Key)", 
            "MyAcurite (Direct from Acurite)",
            "Weather Underground (PWS)"
        ])
        self.weather_source.currentIndexChanged.connect(self._toggle_weather_source)
        source_layout.addRow("Source:", self.weather_source)
        
        # Auto-update checkbox
        self.auto_update_weather = QCheckBox("Auto-update weather on startup")
        self.auto_update_weather.setToolTip("Automatically fetch latest weather data when the app starts (10 second delay)")
        source_layout.addRow("", self.auto_update_weather)
        
        layout.addWidget(source_group)
        
        # Location Settings (Open-Meteo)
        self.openmeteo_group = QGroupBox("Location Settings")
        openmeteo_layout = QFormLayout(self.openmeteo_group)
        
        # Location search row
        location_row = QHBoxLayout()
        self.location_search = QLineEdit()
        self.location_search.setPlaceholderText("City name, ZIP code, or address...")
        self.location_search.returnPressed.connect(self._search_location)
        location_row.addWidget(self.location_search)
        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self._search_location)
        location_row.addWidget(search_btn)
        openmeteo_layout.addRow("Location:", location_row)
        
        # Results dropdown
        self.location_results = QComboBox()
        self.location_results.setMinimumWidth(300)
        self.location_results.currentIndexChanged.connect(self._select_location)
        openmeteo_layout.addRow("Select:", self.location_results)
        
        # Display selected coordinates (read-only)
        coord_row = QHBoxLayout()
        self.latitude_input = QDoubleSpinBox()
        self.latitude_input.setRange(-90, 90)
        self.latitude_input.setDecimals(4)
        self.latitude_input.setSuffix("°")
        coord_row.addWidget(QLabel("Lat:"))
        coord_row.addWidget(self.latitude_input)
        self.longitude_input = QDoubleSpinBox()
        self.longitude_input.setRange(-180, 180)
        self.longitude_input.setDecimals(4)
        self.longitude_input.setSuffix("°")
        coord_row.addWidget(QLabel("Lon:"))
        coord_row.addWidget(self.longitude_input)
        coord_row.addStretch()
        openmeteo_layout.addRow("Coordinates:", coord_row)
        
        # Selected location label
        self.selected_location_label = QLabel("")
        self.selected_location_label.setStyleSheet("color: #22c55e; font-weight: bold;")
        openmeteo_layout.addRow("Selected:", self.selected_location_label)
        
        test_om_btn = QPushButton("Test Connection")
        test_om_btn.clicked.connect(self._test_openmeteo)
        openmeteo_layout.addRow("", test_om_btn)
        layout.addWidget(self.openmeteo_group)
        
        # MyAcurite Settings
        self.acurite_group = QGroupBox("MyAcurite Account")
        acurite_layout = QFormLayout(self.acurite_group)
        
        self.acurite_email = QLineEdit()
        self.acurite_email.setPlaceholderText("your@email.com")
        acurite_layout.addRow("Email:", self.acurite_email)
        
        self.acurite_password = QLineEdit()
        self.acurite_password.setPlaceholderText("Your MyAcurite password")
        self.acurite_password.setEchoMode(QLineEdit.EchoMode.Password)
        acurite_layout.addRow("Password:", self.acurite_password)
        
        acurite_note = QLabel("Data scraped directly from myacurite.com")
        acurite_note.setStyleSheet("color: #737373; font-size: 11px;")
        acurite_layout.addRow("", acurite_note)
        
        test_acurite_btn = QPushButton("Test Connection")
        test_acurite_btn.clicked.connect(self._test_acurite)
        acurite_layout.addRow("", test_acurite_btn)
        layout.addWidget(self.acurite_group)
        
        # Weather Underground Settings
        self.wu_group = QGroupBox("Weather Underground API")
        wu_layout = QFormLayout(self.wu_group)
        self.station_input = QLineEdit()
        self.station_input.setPlaceholderText("e.g., KNCHENDE440")
        wu_layout.addRow("Station ID:", self.station_input)
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Your API key")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        wu_layout.addRow("API Key:", self.api_key_input)
        test_btn = QPushButton("Test Connection")
        test_btn.clicked.connect(self._test_connection)
        wu_layout.addRow("", test_btn)
        layout.addWidget(self.wu_group)
        
        home_group = QGroupBox("Home Information")
        home_layout = QFormLayout(home_group)
        self.home_sqft = QSpinBox()
        self.home_sqft.setRange(100, 20000)
        self.home_sqft.setSuffix(" sq ft")
        home_layout.addRow("Home Size:", self.home_sqft)
        layout.addWidget(home_group)
        
        # Demand Calculation Settings
        demand_group = QGroupBox("Demand Calculation Settings")
        demand_layout = QFormLayout(demand_group)
        
        # Heating range
        heating_row = QHBoxLayout()
        self.heating_min = QSpinBox()
        self.heating_min.setRange(-20, 50)
        self.heating_min.setSuffix("°F")
        heating_row.addWidget(self.heating_min)
        heating_row.addWidget(QLabel("to"))
        self.heating_max = QSpinBox()
        self.heating_max.setRange(30, 80)
        self.heating_max.setSuffix("°F")
        heating_row.addWidget(self.heating_max)
        heating_row.addStretch()
        demand_layout.addRow("Heating Range:", heating_row)
        
        # Cooling range
        cooling_row = QHBoxLayout()
        self.cooling_min = QSpinBox()
        self.cooling_min.setRange(60, 90)
        self.cooling_min.setSuffix("°F")
        cooling_row.addWidget(self.cooling_min)
        cooling_row.addWidget(QLabel("to"))
        self.cooling_max = QSpinBox()
        self.cooling_max.setRange(80, 120)
        self.cooling_max.setSuffix("°F")
        cooling_row.addWidget(self.cooling_max)
        cooling_row.addStretch()
        demand_layout.addRow("Cooling Range:", cooling_row)
        
        # K Factor
        self.k_factor = QDoubleSpinBox()
        self.k_factor.setRange(0.1, 10.0)
        self.k_factor.setDecimals(2)
        self.k_factor.setSingleStep(0.1)
        demand_layout.addRow("K Factor:", self.k_factor)
        
        layout.addWidget(demand_group)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save_settings)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def _load_settings(self):
        # Load weather source
        source = self.db.get_config('weather_source') or 'open-meteo'
        source_idx = {'open-meteo': 0, 'acurite': 1, 'wu': 2}.get(source, 0)
        self.weather_source.setCurrentIndex(source_idx)
        self._toggle_weather_source()
        
        # Load auto-update weather setting (default to disabled)
        auto_update = self.db.get_config('auto_update_weather')
        self.auto_update_weather.setChecked(auto_update == '1')
        
        # Load Open-Meteo settings
        lat = float(self.db.get_config('location_latitude') or 35.3187)
        lon = float(self.db.get_config('location_longitude') or -82.4612)
        self.latitude_input.setValue(lat)
        self.longitude_input.setValue(lon)
        
        # Load saved location name if available
        location_name = self.db.get_config('location_name') or ''
        if location_name:
            self.selected_location_label.setText(location_name)
        
        # Load MyAcurite settings
        self.acurite_email.setText(self.db.get_config('acurite_email') or '')
        self.acurite_password.setText(self.db.get_config('acurite_password') or '')
        
        # Load WU settings
        self.station_input.setText(self.db.get_config('station_id') or '')
        self.api_key_input.setText(self.db.get_config('wu_api_key') or '')
        self.home_sqft.setValue(int(self.db.get_config('home_sqft') or 1730))
        
        # Load demand settings
        demand = self.db.get_demand_settings()
        self.heating_min.setValue(int(demand['heating_min_temp']))
        self.heating_max.setValue(int(demand['heating_max_temp']))
        self.cooling_min.setValue(int(demand['cooling_min_temp']))
        self.cooling_max.setValue(int(demand['cooling_max_temp']))
        self.k_factor.setValue(demand['k_factor'])
        
        # Store location results for selection
        self._location_data = []
    
    def _toggle_weather_source(self):
        """Toggle visibility of weather source settings."""
        idx = self.weather_source.currentIndex()
        # 0 = Open-Meteo, 1 = MyAcurite, 2 = Weather Underground
        self.openmeteo_group.setVisible(idx == 0)
        self.acurite_group.setVisible(idx == 1)
        self.wu_group.setVisible(idx == 2)
    
    def _search_location(self):
        """Search for location using Open-Meteo Geocoding API."""
        query = self.location_search.text().strip()
        if not query:
            QMessageBox.warning(self, "Empty Search", "Please enter a city name, ZIP code, or address.")
            return
        
        try:
            import requests
            url = "https://geocoding-api.open-meteo.com/v1/search"
            params = {
                'name': query,
                'count': 10,
                'language': 'en',
                'format': 'json'
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code != 200:
                QMessageBox.warning(self, "Search Failed", f"API returned status {response.status_code}")
                return
            
            data = response.json()
            results = data.get('results', [])
            
            if not results:
                QMessageBox.information(self, "No Results", f"No locations found for '{query}'")
                return
            
            # Clear and populate dropdown
            self.location_results.clear()
            self._location_data = results
            
            for loc in results:
                name = loc.get('name', '')
                admin1 = loc.get('admin1', '')  # State/Province
                country = loc.get('country', '')
                
                # Format: "City, State, Country"
                parts = [name]
                if admin1:
                    parts.append(admin1)
                if country:
                    parts.append(country)
                display = ", ".join(parts)
                
                self.location_results.addItem(display)
            
            # Auto-select first result
            if results:
                self.location_results.setCurrentIndex(0)
                
        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "Connection Error", f"Could not connect to geocoding service:\n{e}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Search failed: {e}")
    
    def _select_location(self):
        """Handle location selection from dropdown."""
        idx = self.location_results.currentIndex()
        if idx < 0 or idx >= len(self._location_data):
            return
        
        loc = self._location_data[idx]
        lat = loc.get('latitude', 0)
        lon = loc.get('longitude', 0)
        
        self.latitude_input.setValue(lat)
        self.longitude_input.setValue(lon)
        
        # Build display name
        name = loc.get('name', '')
        admin1 = loc.get('admin1', '')
        country = loc.get('country', '')
        parts = [name]
        if admin1:
            parts.append(admin1)
        if country:
            parts.append(country)
        display = ", ".join(parts)
        
        self.selected_location_label.setText(display)
    
    def _test_openmeteo(self):
        """Test Open-Meteo API connection."""
        from weather_api import OpenMeteoAPI
        lat = self.latitude_input.value()
        lon = self.longitude_input.value()
        api = OpenMeteoAPI(latitude=lat, longitude=lon)
        if api.test_connection():
            QMessageBox.information(self, "Success", "Open-Meteo connection successful!")
        else:
            QMessageBox.warning(self, "Failed", "Could not connect to Open-Meteo API.")
    
    def _test_acurite(self):
        """Test MyAcurite connection."""
        email = self.acurite_email.text().strip()
        password = self.acurite_password.text()
        
        if not email or not password:
            QMessageBox.warning(self, "Missing Info", "Please enter your MyAcurite email and password.")
            return
        
        from weather_api import MyAcuriteScraper
        scraper = MyAcuriteScraper(email, password)
        if scraper.test_connection():
            QMessageBox.information(self, "Success", "✅ MyAcurite login successful!")
            scraper.logout()
        else:
            QMessageBox.critical(self, "Failed", "❌ Could not login to MyAcurite. Check your credentials.")
    
    def _save_settings(self):
        # Save weather source
        source_idx = self.weather_source.currentIndex()
        source = {0: 'open-meteo', 1: 'acurite', 2: 'wu'}.get(source_idx, 'open-meteo')
        self.db.set_config('weather_source', source)
        
        # Save auto-update weather setting
        self.db.set_config('auto_update_weather', '1' if self.auto_update_weather.isChecked() else '0')
        
        # Save Open-Meteo settings
        self.db.set_config('location_latitude', str(self.latitude_input.value()))
        self.db.set_config('location_longitude', str(self.longitude_input.value()))
        self.db.set_config('location_name', self.selected_location_label.text())
        
        # Save MyAcurite settings
        self.db.set_config('acurite_email', self.acurite_email.text())
        self.db.set_config('acurite_password', self.acurite_password.text())
        
        # Save WU settings
        self.db.set_config('station_id', self.station_input.text())
        self.db.set_config('wu_api_key', self.api_key_input.text())
        self.db.set_config('home_sqft', str(self.home_sqft.value()))
        
        # Save demand settings
        self.db.set_demand_settings({
            'heating_min_temp': self.heating_min.value(),
            'heating_max_temp': self.heating_max.value(),
            'cooling_min_temp': self.cooling_min.value(),
            'cooling_max_temp': self.cooling_max.value(),
            'k_factor': self.k_factor.value(),
        })
        self.accept()
    
    def _test_connection(self):
        station = self.station_input.text()
        api_key = self.api_key_input.text()
        if not station or not api_key:
            QMessageBox.warning(self, "Missing Info", "Please enter Station ID and API Key")
            return
        api = WeatherUndergroundAPI(api_key, station)
        if api.test_connection():
            QMessageBox.information(self, "Success", "✅ Connection successful!")
        else:
            QMessageBox.critical(self, "Failed", "❌ Could not connect. Check your credentials.")


class BillEntryDialog(QDialog):
    def __init__(self, db, bill_type="electric", parent=None):
        super().__init__(parent)
        self.db = db
        self.bill_type = bill_type
        self.setWindowTitle(f"Add {bill_type.title()} Bill")
        self.setMinimumWidth(400)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.date_input = QDateEdit(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        form.addRow("Bill Date:", self.date_input)
        
        if self.bill_type == "electric":
            self.usage_input = QDoubleSpinBox()
            self.usage_input.setRange(0, 99999)
            self.usage_input.setSuffix(" kWh")
            form.addRow("Usage:", self.usage_input)
        elif self.bill_type == "gas":
            self.usage_input = QDoubleSpinBox()
            self.usage_input.setRange(0, 9999)
            self.usage_input.setSuffix(" therms")
            form.addRow("Therms:", self.usage_input)
        else:
            self.usage_input = QDoubleSpinBox()
            self.usage_input.setRange(0, 999999)
            self.usage_input.setSuffix(" gal")
            form.addRow("Gallons:", self.usage_input)
        
        self.days_input = QSpinBox()
        self.days_input.setRange(1, 60)
        self.days_input.setValue(30)
        form.addRow("Days:", self.days_input)
        
        self.total_input = QDoubleSpinBox()
        self.total_input.setRange(0, 9999)
        self.total_input.setDecimals(2)
        self.total_input.setPrefix("$ ")
        form.addRow("Total:", self.total_input)
        
        layout.addLayout(form)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save_bill)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def _save_bill(self):
        try:
            from database import ElectricBill, GasBill, WaterBill
            
            usage = self.usage_input.value()
            days = self.days_input.value()
            total = self.total_input.value()
            bill_date = self.date_input.date().toPyDate()
            
            if self.bill_type == "electric":
                bill = ElectricBill(None, bill_date, 0, usage, days, usage/days if days else 0,
                    total*0.9, total*0.1, total, total/usage if usage else 0)
                self.db.add_electric_bill(bill)
            elif self.bill_type == "gas":
                bill = GasBill(None, bill_date, 0, 0, 1.0, days, usage, usage/days if days else 0,
                    total/usage if usage else 0, total*0.85, total*0.08, total*0.07, total)
                self.db.add_gas_bill(bill)
            else:
                bill = WaterBill(None, bill_date, 0, usage, usage/days if days else 0,
                    total*0.9, total*0.1, total/usage*1000 if usage else 0, total)
                self.db.add_water_bill(bill)
            
            self.db.update_yearly_costs()
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")


class WeatherImportDialog(QDialog):
    """Dialog for importing weather data from Excel or CSV files."""
    
    EXPECTED_COLUMNS = [
        'date', 'temp_high', 'temp_avg', 'temp_low',
        'dewpoint_high', 'dewpoint_avg', 'dewpoint_low',
        'humidity_high', 'humidity_avg', 'humidity_low',
        'wind_max', 'wind_avg', 'wind_gust',
        'pressure_max', 'pressure_min', 'rain_total'
    ]
    
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.file_path = None
        self.preview_data = []
        self.setWindowTitle("Import Weather Data")
        self.setMinimumSize(800, 600)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        
        # File selection
        file_group = QGroupBox("Select File")
        file_layout = QHBoxLayout(file_group)
        self.file_label = QLabel("No file selected")
        file_layout.addWidget(self.file_label, 1)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_file)
        file_layout.addWidget(browse_btn)
        layout.addWidget(file_group)
        
        # Expected format info
        format_group = QGroupBox("Expected Format")
        format_layout = QVBoxLayout(format_group)
        format_text = QLabel(
            "Your file should have these columns (order doesn't matter):\n\n"
            "• date - Date (YYYY-MM-DD or MM/DD/YYYY)\n"
            "• temp_high, temp_avg, temp_low - Temperature (°F)\n"
            "• dewpoint_high, dewpoint_avg, dewpoint_low - Dewpoint (°F)\n"
            "• humidity_high, humidity_avg, humidity_low - Humidity (%)\n"
            "• wind_max, wind_avg, wind_gust - Wind Speed (mph)\n"
            "• pressure_max, pressure_min - Barometric Pressure (inHg)\n"
            "• rain_total - Total Rainfall (inches)\n\n"
            "Heat%, Cool%, and Max Demand are auto-calculated from temperature."
        )
        format_text.setStyleSheet("color: #a3a3a3; font-size: 12px;")
        format_layout.addWidget(format_text)
        layout.addWidget(format_group)
        
        # Preview
        preview_group = QGroupBox("Preview (first 10 rows)")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_table = QTableWidget()
        self.preview_table.setMaximumHeight(200)
        preview_layout.addWidget(self.preview_table)
        layout.addWidget(preview_group)
        
        # Options
        options_group = QGroupBox("Import Options")
        options_layout = QVBoxLayout(options_group)
        self.skip_existing = QCheckBox("Skip dates that already have data (recommended)")
        self.skip_existing.setChecked(True)
        options_layout.addWidget(self.skip_existing)
        self.calc_demand = QCheckBox("Calculate heating/cooling demand")
        self.calc_demand.setChecked(True)
        options_layout.addWidget(self.calc_demand)
        layout.addWidget(options_group)
        
        # Status
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #86efac;")
        layout.addWidget(self.status_label)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._do_import)
        buttons.rejected.connect(self.reject)
        self.import_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.import_btn.setText("Import")
        self.import_btn.setEnabled(False)
        layout.addWidget(buttons)
    
    def _browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Weather Data File", "",
            "All Supported (*.xlsx *.xls *.csv);;Excel Files (*.xlsx *.xls);;CSV Files (*.csv)"
        )
        if file_path:
            self.file_path = file_path
            self.file_label.setText(file_path)
            self._load_preview()
    
    def _load_preview(self):
        try:
            import pandas as pd
            
            if self.file_path.endswith('.csv'):
                df = pd.read_csv(self.file_path)
            else:
                df = pd.read_excel(self.file_path)
            
            df.columns = [c.lower().strip().replace(' ', '_') for c in df.columns]
            
            if 'date' not in df.columns:
                self.status_label.setText("❌ Error: 'date' column not found")
                self.status_label.setStyleSheet("color: #ef4444;")
                return
            
            self.preview_table.setColumnCount(len(df.columns))
            self.preview_table.setHorizontalHeaderLabels(list(df.columns))
            preview_rows = min(10, len(df))
            self.preview_table.setRowCount(preview_rows)
            
            for row in range(preview_rows):
                for col, column in enumerate(df.columns):
                    val = df.iloc[row][column]
                    self.preview_table.setItem(row, col, QTableWidgetItem(str(val) if pd.notna(val) else ""))
            
            self.preview_data = df
            
            found_cols = [c for c in self.EXPECTED_COLUMNS if c in df.columns]
            missing_cols = [c for c in self.EXPECTED_COLUMNS if c not in df.columns and c != 'date']
            
            status = f"✅ Found {len(df)} rows, {len(found_cols)}/{len(self.EXPECTED_COLUMNS)} columns"
            if missing_cols:
                status += f"\n⚠️ Missing: {', '.join(missing_cols[:5])}"
                if len(missing_cols) > 5:
                    status += f" (+{len(missing_cols)-5} more)"
            
            self.status_label.setText(status)
            self.status_label.setStyleSheet("color: #86efac;")
            self.import_btn.setEnabled(True)
            
        except ImportError:
            self.status_label.setText("❌ Error: pandas/openpyxl not installed")
            self.status_label.setStyleSheet("color: #ef4444;")
        except Exception as e:
            self.status_label.setText(f"❌ Error reading file: {e}")
            self.status_label.setStyleSheet("color: #ef4444;")
    
    def _do_import(self):
        if self.preview_data is None or len(self.preview_data) == 0:
            return
        
        try:
            import pandas as pd
            
            df = self.preview_data
            calculator = WeatherDemandCalculator() if self.calc_demand.isChecked() else None
            
            existing_dates = set()
            if self.skip_existing.isChecked():
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT date FROM weather_daily")
                    for row in cursor.fetchall():
                        d = row['date']
                        existing_dates.add(d if isinstance(d, str) else str(d))
            
            imported = 0
            skipped = 0
            errors = 0
            
            for _, row in df.iterrows():
                try:
                    date_val = row['date']
                    if isinstance(date_val, str):
                        parsed = False
                        for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%m/%d/%y', '%d/%m/%Y', '%Y/%m/%d']:
                            try:
                                date_val = datetime.strptime(date_val, fmt).date()
                                parsed = True
                                break
                            except:
                                continue
                        if not parsed:
                            errors += 1
                            continue
                    elif hasattr(date_val, 'date'):
                        date_val = date_val.date()
                    elif hasattr(date_val, 'to_pydatetime'):
                        date_val = date_val.to_pydatetime().date()
                    
                    date_str = date_val.strftime('%Y-%m-%d')
                    if date_str in existing_dates:
                        skipped += 1
                        continue
                    
                    def get_val(col):
                        if col in df.columns:
                            v = row[col]
                            if pd.notna(v):
                                return float(v)
                        return None
                    
                    temp_high = get_val('temp_high')
                    temp_avg = get_val('temp_avg')
                    temp_low = get_val('temp_low')
                    
                    cooling_demand = None
                    heating_demand = None
                    max_demand = None
                    if calculator and temp_high is not None:
                        demands = calculator.calculate_demands(temp_high, temp_low or temp_high)
                        cooling_demand = demands['cooling_demand']
                        heating_demand = demands['heating_demand']
                        max_demand = demands['max_demand']
                    
                    weather_day = WeatherDay(
                        id=None, date=date_val,
                        temp_high=temp_high, temp_avg=temp_avg, temp_low=temp_low,
                        dewpoint_high=get_val('dewpoint_high'),
                        dewpoint_avg=get_val('dewpoint_avg'),
                        dewpoint_low=get_val('dewpoint_low'),
                        humidity_high=get_val('humidity_high'),
                        humidity_avg=get_val('humidity_avg'),
                        humidity_low=get_val('humidity_low'),
                        wind_max=get_val('wind_max'),
                        wind_avg=get_val('wind_avg'),
                        wind_gust=get_val('wind_gust'),
                        pressure_max=get_val('pressure_max'),
                        pressure_min=get_val('pressure_min'),
                        rain_total=get_val('rain_total') or 0,
                        cooling_demand=cooling_demand,
                        heating_demand=heating_demand,
                        max_demand=max_demand
                    )
                    
                    self.db.add_weather_day(weather_day)
                    imported += 1
                    
                except Exception as e:
                    errors += 1
            
            msg = f"Import complete!\n\n• Imported: {imported} days\n• Skipped (existing): {skipped}\n• Errors: {errors}"
            QMessageBox.information(self, "Import Complete", msg)
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import: {e}")


class PDFImportDialog(QDialog):
    """Dialog for importing bills from PDF files."""
    
    def __init__(self, db, utility_type: str, parent=None):
        super().__init__(parent)
        self.db = db
        self.utility_type = utility_type
        self.extracted_values = {}
        self.pdf_text = ""
        self.extractor = None
        self.file_path = None
        
        self.setWindowTitle(f"📄 Import {utility_type.title()} Bill from PDF")
        self.setMinimumWidth(500)
        self.setMinimumHeight(450)
        self.setAcceptDrops(True)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        
        # Drag and drop zone
        self.drop_zone = QLabel("📄 Drag & Drop PDF Here\n\nor click to browse")
        self.drop_zone.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_zone.setMinimumHeight(80)
        self.drop_zone.setStyleSheet("""
            QLabel {
                border: 2px dashed #86efac;
                border-radius: 8px;
                background-color: #1e293b;
                color: #a3a3a3;
                font-size: 13px;
                padding: 20px;
            }
            QLabel:hover {
                border-color: #60a5fa;
                background-color: #242424;
            }
        """)
        self.drop_zone.setCursor(Qt.CursorShape.PointingHandCursor)
        self.drop_zone.mousePressEvent = lambda e: self._browse_file()
        layout.addWidget(self.drop_zone)
        
        # Status/info label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #737373; font-size: 11px;")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        
        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #2e2e2e;")
        layout.addWidget(sep)
        
        # Field values form
        self.form_layout = QFormLayout()
        self.form_layout.setSpacing(8)
        self.field_inputs = {}
        
        # Create input fields based on utility type
        self._create_field_inputs()
        
        layout.addLayout(self.form_layout)
        
        # Spacer
        layout.addStretch()
        
        # Buttons: Cancel, Edit, Import
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        self.edit_btn = QPushButton("Edit")
        self.edit_btn.setToolTip("Edit field mappings for PDF extraction")
        self.edit_btn.clicked.connect(self._open_edit_dialog)
        self.edit_btn.setEnabled(False)
        button_layout.addWidget(self.edit_btn)
        
        self.import_btn = QPushButton("Import")
        self.import_btn.setDefault(True)
        self.import_btn.clicked.connect(self._do_import)
        self.import_btn.setEnabled(False)
        button_layout.addWidget(self.import_btn)
        
        layout.addLayout(button_layout)
    
    def _create_field_inputs(self):
        """Create input fields for the utility type."""
        from pdf_import import get_field_definitions
        
        fields = get_field_definitions(self.utility_type)
        
        # Fields that should be integers (no decimals)
        integer_fields = ['usage_kwh', 'usage_ccf', 'usage_gallons', 'meter_reading', 'therms']
        
        for field in fields:
            name = field['name']
            label = field['label']
            field_type = field['type']
            required = field['required']
            
            # Add asterisk for required fields
            display_label = f"{label}*:" if required else f"{label}:"
            
            if field_type == 'date':
                input_widget = QDateEdit()
                input_widget.setCalendarPopup(True)
                input_widget.setDate(QDate.currentDate())
            elif field_type == 'currency':
                input_widget = QDoubleSpinBox()
                input_widget.setRange(0, 99999.99)
                input_widget.setDecimals(2)
                input_widget.setPrefix("$ ")
            elif field_type == 'integer' or name in integer_fields:
                input_widget = QSpinBox()
                input_widget.setRange(0, 9999999)  # Allow large meter readings
            else:  # number (with decimals)
                input_widget = QDoubleSpinBox()
                input_widget.setRange(0, 999999.99)
                input_widget.setDecimals(2)
            
            self.field_inputs[name] = input_widget
            self.form_layout.addRow(display_label, input_widget)
        
        # For water bills: set up auto-calculation for service_charge and water_cost
        if self.utility_type == 'water':
            self._setup_water_auto_calc()
    
    def _setup_water_auto_calc(self):
        """Set up auto-calculation for water bill fields."""
        # Get last water bill's service charge
        last_bill = self.db.get_latest_water_bill()
        if last_bill and last_bill.get('service_charge'):
            service_charge = last_bill['service_charge']
            self.field_inputs['service_charge'].setValue(service_charge)
        
        # Connect signals for auto-calculation
        self.field_inputs['total_cost'].valueChanged.connect(self._update_water_cost)
        self.field_inputs['service_charge'].valueChanged.connect(self._update_water_cost)
        
        # Make water_cost read-only (calculated field)
        self.field_inputs['water_cost'].setReadOnly(True)
        self.field_inputs['water_cost'].setStyleSheet("background-color: #1e293b; color: #a3a3a3;")
        self.field_inputs['water_cost'].setToolTip("Auto-calculated: Total Cost - Service Charge")
    
    def _update_water_cost(self):
        """Update water_cost = total_cost - service_charge."""
        if self.utility_type != 'water':
            return
        
        total_cost = self.field_inputs['total_cost'].value()
        service_charge = self.field_inputs['service_charge'].value()
        water_cost = max(0, total_cost - service_charge)
        
        # Block signals to prevent recursion
        self.field_inputs['water_cost'].blockSignals(True)
        self.field_inputs['water_cost'].setValue(water_cost)
        self.field_inputs['water_cost'].blockSignals(False)
    
    def _browse_file(self):
        """Open file browser to select PDF."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Bill PDF", "",
            "PDF Files (*.pdf)"
        )
        if file_path:
            self._load_pdf(file_path)
    
    def _load_pdf(self, file_path: str):
        """Load a PDF file (from browse or drag-drop)."""
        self.file_path = file_path
        
        # Update drop zone to show file name
        file_name = file_path.split('/')[-1].split('\\')[-1]
        self.drop_zone.setText(f"📄 {file_name}")
        self.drop_zone.setStyleSheet("""
            QLabel {
                border: 2px solid #22c55e;
                border-radius: 8px;
                background-color: #1e3a2e;
                color: #22c55e;
                font-size: 13px;
                padding: 20px;
            }
        """)
        
        self._extract_from_pdf(file_path)
    
    def dragEnterEvent(self, event):
        """Handle drag enter - accept PDF files."""
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith('.pdf'):
                    event.acceptProposedAction()
                    self.drop_zone.setStyleSheet("""
                        QLabel {
                            border: 2px dashed #22c55e;
                            border-radius: 8px;
                            background-color: #1e3a2e;
                            color: #22c55e;
                            font-size: 13px;
                            padding: 20px;
                        }
                    """)
                    return
        event.ignore()
    
    def dragLeaveEvent(self, event):
        """Handle drag leave - reset style."""
        if not self.file_path:
            self.drop_zone.setStyleSheet("""
                QLabel {
                    border: 2px dashed #86efac;
                    border-radius: 8px;
                    background-color: #1e293b;
                    color: #a3a3a3;
                    font-size: 13px;
                    padding: 20px;
                }
            """)
    
    def dropEvent(self, event):
        """Handle drop - load the PDF."""
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.lower().endswith('.pdf'):
                self._load_pdf(file_path)
                return
    
    def _extract_from_pdf(self, file_path: str):
        """Extract data from the selected PDF."""
        try:
            from pdf_import import PDFExtractor, validate_extraction
            
            self.extractor = PDFExtractor()
            if not self.extractor.load_pdf(file_path):
                error_msg = self.extractor.error_message or "Failed to load PDF"
                raise Exception(error_msg)
            
            # Show any warning from loader
            if self.extractor.error_message:
                self.status_label.setText(f"⚠️ {self.extractor.error_message}")
                self.status_label.setStyleSheet("color: #f59e0b;")
            
            # Check if template exists
            template = self.db.get_pdf_template(self.utility_type)
            
            if template is None:
                # No template - open visual field mapping dialog
                self.status_label.setText("📝 No template found. Please map the fields...")
                self.status_label.setStyleSheet("color: #86efac;")
                
                # Open visual mapping dialog with PDF path
                dialog = PDFFieldMappingDialog(
                    self.db, self.utility_type, file_path, parent=self
                )
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    # Get extracted values directly from dialog
                    self.extracted_values = dialog.get_extracted_values()
                    # Also reload template for future use
                    template = self.db.get_pdf_template(self.utility_type)
                else:
                    # User cancelled - reset
                    self.status_label.setText("⚠️ Field mapping cancelled. Please try again.")
                    self.status_label.setStyleSheet("color: #f59e0b;")
                    return
            else:
                # Template exists - extract using it
                self.extracted_values = self.extractor.extract_with_template(template, 0)
            
            # Populate the form
            self._populate_form()
            
            # Validate extraction
            is_valid, issues = validate_extraction(self.extracted_values, self.utility_type)
            
            if is_valid:
                self.status_label.setText("✅ Fields extracted successfully. Please verify values before importing.")
                self.status_label.setStyleSheet("color: #22c55e;")
            else:
                issue_text = "\n".join(f"• {i}" for i in issues[:3])
                if len(issues) > 3:
                    issue_text += f"\n• ...and {len(issues) - 3} more issues"
                self.status_label.setText(f"⚠️ Some fields need attention:\n{issue_text}")
                self.status_label.setStyleSheet("color: #f59e0b;")
            
            self.edit_btn.setEnabled(True)
            self.import_btn.setEnabled(True)
            
        except ImportError as e:
            self.status_label.setText(f"❌ Missing dependency: {e}")
            self.status_label.setStyleSheet("color: #ef4444;")
        except Exception as e:
            self.status_label.setText(f"❌ Error reading PDF: {e}")
            self.status_label.setStyleSheet("color: #ef4444;")
    
    def _populate_form(self):
        """Populate form fields with extracted values."""
        from pdf_import import get_field_definitions, parse_value
        
        fields = get_field_definitions(self.utility_type)
        
        for field in fields:
            name = field['name']
            field_type = field['type']
            value = self.extracted_values.get(name, '')
            widget = self.field_inputs.get(name)
            
            if not widget or not value:
                continue
            
            parsed = parse_value(value, field_type)
            
            if parsed is not None:
                if field_type == 'date':
                    widget.setDate(QDate(parsed.year, parsed.month, parsed.day))
                elif isinstance(widget, QSpinBox):
                    widget.setValue(int(parsed))
                elif isinstance(widget, QDoubleSpinBox):
                    widget.setValue(float(parsed))
        
        # For water bills, trigger auto-calculation after populating
        if self.utility_type == 'water':
            self._update_water_cost()
    
    def _open_edit_dialog(self):
        """Open the visual field mapping editor."""
        if not hasattr(self, 'file_path') or not self.file_path:
            QMessageBox.warning(self, "No PDF", "Please select a PDF file first.")
            return
        
        dialog = PDFFieldMappingDialog(
            self.db, self.utility_type, self.file_path, parent=self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Get extracted values from dialog
            self.extracted_values = dialog.get_extracted_values()
            self._populate_form()
            self.status_label.setText("✅ Template updated. Please verify values.")
            self.status_label.setStyleSheet("color: #22c55e;")
    
    def _do_import(self):
        """Import the bill data."""
        try:
            from database import ElectricBill, GasBill, WaterBill
            from datetime import date as date_type
            
            # Get values from form
            def get_val(name, default=0):
                widget = self.field_inputs.get(name)
                if widget is None:
                    return default
                if isinstance(widget, QDateEdit):
                    return widget.date().toPyDate()
                return widget.value()
            
            bill_date = get_val('bill_date')
            total_cost = get_val('total_cost', 0)
            days = get_val('days', 30)
            
            if self.utility_type == 'electric':
                usage = get_val('usage_kwh', 0)
                meter = get_val('meter_reading', 0)
                electric_cost = get_val('electric_cost', total_cost * 0.9)
                taxes = get_val('taxes', total_cost * 0.1)
                
                bill = ElectricBill(
                    id=None,
                    bill_date=bill_date,
                    meter_reading=meter,
                    usage_kwh=usage,
                    days=days,
                    kwh_per_day=usage / days if days else 0,
                    electric_cost=electric_cost,
                    taxes=taxes,
                    total_cost=total_cost,
                    cost_per_kwh=total_cost / usage if usage else 0
                )
                self.db.add_electric_bill(bill)
                
            elif self.utility_type == 'gas':
                usage_ccf = get_val('usage_ccf', 0)
                therms = get_val('therms', usage_ccf)
                meter = get_val('meter_reading', 0)
                btu = get_val('btu_factor', 1.0)
                service = get_val('service_charge', 0)
                taxes = get_val('taxes', total_cost * 0.07)
                
                bill = GasBill(
                    id=None,
                    bill_date=bill_date,
                    meter_reading=meter,
                    usage_ccf=usage_ccf,
                    btu_factor=btu,
                    days=days,
                    therms=therms,
                    therms_per_day=therms / days if days else 0,
                    cost_per_therm=total_cost / therms if therms else 0,
                    therm_cost=total_cost - service - taxes,
                    service_charge=service,
                    taxes=taxes,
                    total_cost=total_cost
                )
                self.db.add_gas_bill(bill)
                
            else:  # water
                usage = get_val('usage_gallons', 0)
                meter = get_val('meter_reading', 0)
                water_cost = get_val('water_cost', total_cost * 0.9)
                service = get_val('service_charge', total_cost * 0.1)
                
                bill = WaterBill(
                    id=None,
                    bill_date=bill_date,
                    meter_reading=meter,
                    usage_gallons=usage,
                    gallons_per_day=usage / days if days else 0,
                    water_cost=water_cost,
                    service_charge=service,
                    cost_per_kgal=total_cost / usage * 1000 if usage else 0,
                    total_cost=total_cost
                )
                self.db.add_water_bill(bill)
            
            self.db.update_yearly_costs()
            QMessageBox.information(self, "Success", f"{self.utility_type.title()} bill imported successfully!")
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import bill: {e}")


class DraggableFieldBox(QLabel):
    """A draggable label that represents a field to be mapped."""
    
    positionChanged = pyqtSignal(str, float, float)  # field_name, x, y
    
    def __init__(self, field_name: str, label: str, required: bool = False, parent=None):
        super().__init__(parent)
        self.field_name = field_name
        self.field_label = label
        self.required = required
        self.mapped = False
        self.anchor_text = ""
        self.pattern = ""
        self.extracted_value = ""
        self.drop_callback = None  # Direct callback function
        
        self.setText(f"{'*' if required else ''}{label}")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedSize(120, 28)
        self._update_style()
        self.setCursor(Qt.CursorShape.OpenHandCursor)
    
    def _update_style(self):
        if self.mapped:
            self.setStyleSheet("""
                QLabel {
                    background-color: rgba(34, 197, 94, 180);
                    color: #000000;
                    border: 2px solid #16a34a;
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 11px;
                    padding: 2px 6px;
                }
            """)
        else:
            self.setStyleSheet("""
                QLabel {
                    background-color: rgba(59, 130, 246, 180);
                    color: #ffffff;
                    border: 2px solid #4ade80;
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 11px;
                    padding: 2px 6px;
                }
                QLabel:hover {
                    background-color: rgba(37, 99, 235, 200);
                }
            """)
    
    def set_mapped(self, mapped: bool, anchor: str = "", value: str = ""):
        self.mapped = mapped
        self.anchor_text = anchor
        self.extracted_value = value
        self._update_style()
        
        # Update label to show value when mapped
        if mapped and value:
            # Truncate value if too long
            display_val = value[:15] + "..." if len(value) > 15 else value
            self.setText(f"✓ {display_val}")
            self.setToolTip(f"Field: {self.field_label}\nAnchor: {anchor}\nValue: {value}")
        else:
            # Reset to original label
            self.setText(f"{'*' if self.required else ''}{self.field_label}")
            self.setToolTip("")
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.drag_start = event.pos()
    
    def mouseMoveEvent(self, event):
        if hasattr(self, 'drag_start') and event.buttons() == Qt.MouseButton.LeftButton:
            # Move the widget
            new_pos = self.mapToParent(event.pos() - self.drag_start)
            self.move(new_pos)
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            # Emit position in parent coordinates
            try:
                pos = self.pos()
                # Visual feedback - temporarily change color to show drop detected
                self.setStyleSheet("""
                    QLabel {
                        background-color: rgba(251, 191, 36, 200);
                        color: #000000;
                        border: 2px solid #f59e0b;
                        border-radius: 4px;
                        font-weight: bold;
                        font-size: 11px;
                        padding: 2px 6px;
                    }
                """)
                
                # Use direct callback only (signal was causing double-fire)
                if self.drop_callback:
                    self.drop_callback(self.field_name, float(pos.x()), float(pos.y()))
            except Exception as e:
                pass


class PDFPageView(QLabel):
    """Widget to display PDF page image with field overlays and right-click panning."""
    
    fieldDropped = pyqtSignal(str, float, float)  # field_name, x, y (in PDF coords)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.pdf_pixmap = None
        self.original_pixmap = None  # Keep original for rescaling
        self.scale_factor = 2.0
        self.display_scale = 1.0  # Additional scale for display
        self._panning = False
        self._pan_start = None
        self._scroll_area = None  # Will be set by parent
    
    def set_scroll_area(self, scroll_area):
        """Set the scroll area for panning."""
        self._scroll_area = scroll_area
    
    def set_pdf_image(self, image_data: bytes, scale_factor: float = 2.0):
        """Set the PDF page image from PNG bytes."""
        self.scale_factor = scale_factor
        pixmap = QPixmap()
        pixmap.loadFromData(image_data)
        self.pdf_pixmap = pixmap
        self.original_pixmap = pixmap  # Keep original for rescaling
        self.setPixmap(pixmap)
        self.setFixedSize(pixmap.size())
    
    def scale_to_width(self, target_width: int):
        """Scale the PDF image to fit a target width."""
        if not self.original_pixmap:
            return
        
        # Calculate scale needed to fit width
        original_width = self.original_pixmap.width()
        self.display_scale = target_width / original_width
        
        # Scale the pixmap
        scaled_pixmap = self.original_pixmap.scaled(
            int(original_width * self.display_scale),
            int(self.original_pixmap.height() * self.display_scale),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.setPixmap(scaled_pixmap)
        self.setFixedSize(scaled_pixmap.size())
    
    def screen_to_pdf_coords(self, screen_x: float, screen_y: float) -> Tuple[float, float]:
        """Convert screen coordinates to PDF coordinates."""
        pdf_x = screen_x / self.scale_factor / self.display_scale
        pdf_y = screen_y / self.scale_factor / self.display_scale
        return (pdf_x, pdf_y)
    
    def pdf_to_screen_coords(self, pdf_x: float, pdf_y: float) -> Tuple[int, int]:
        """Convert PDF coordinates to screen coordinates."""
        screen_x = int(pdf_x * self.scale_factor * self.display_scale)
        screen_y = int(pdf_y * self.scale_factor * self.display_scale)
        return (screen_x, screen_y)
    
    def mousePressEvent(self, event):
        """Handle right-click for panning."""
        if event.button() == Qt.MouseButton.RightButton:
            self._panning = True
            self._pan_start = event.globalPosition().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        else:
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Handle panning movement."""
        if self._panning and self._scroll_area and self._pan_start:
            delta = event.globalPosition().toPoint() - self._pan_start
            self._pan_start = event.globalPosition().toPoint()
            
            # Scroll the scroll area
            h_bar = self._scroll_area.horizontalScrollBar()
            v_bar = self._scroll_area.verticalScrollBar()
            h_bar.setValue(h_bar.value() - delta.x())
            v_bar.setValue(v_bar.value() - delta.y())
        else:
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Handle end of panning."""
        if event.button() == Qt.MouseButton.RightButton:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            super().mouseReleaseEvent(event)


class PDFFieldMappingDialog(QDialog):
    """Visual dialog for mapping PDF fields by dragging boxes onto the PDF."""
    
    def __init__(self, db, utility_type: str, pdf_path: str, parent=None):
        super().__init__(parent)
        self.db = db
        self.utility_type = utility_type
        self.pdf_path = pdf_path
        self.extractor = None
        self.field_boxes = {}  # field_name -> DraggableFieldBox
        self.field_mappings = {}  # field_name -> {anchor, pattern, x, y}
        self.text_only_mode = False  # True if PyMuPDF not available
        self.current_page = 0  # Current page being viewed
        self.total_pages = 1  # Total pages in PDF
        
        self.setWindowTitle("📝 Map PDF Fields")
        
        # Make it larger and resizable (15% larger than before)
        self.setMinimumWidth(1150)
        self.setMinimumHeight(860)
        self.resize(1380, 980)  # Default size (15% larger)
        
        # Allow resizing (remove fixed size constraints)
        self.setSizeGripEnabled(True)
        
        self._load_pdf()
        self._setup_ui()
    
    def _load_pdf(self):
        """Load the PDF and extract text."""
        from pdf_import import PDFExtractor
        self.extractor = PDFExtractor()
        success = self.extractor.load_pdf(self.pdf_path)
        
        # Get total pages
        if success and self.extractor.page_images:
            self.total_pages = len(self.extractor.page_images)
        
        # Check if we're in text-only mode (no image available)
        if success and self.extractor.page_images and self.extractor.page_images[0] is None:
            self.text_only_mode = True
        elif not success:
            self.text_only_mode = True
    
    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(12, 12, 12, 12)
        
        # Check for text-only mode
        if self.text_only_mode:
            self._setup_text_only_ui(main_layout)
            return
        
        # Instructions
        instructions = QLabel("Drag each field box onto the corresponding value in the PDF. "
                             "The box will snap to nearby text and detect the anchor label.")
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: #a3a3a3; font-size: 12px; padding: 4px;")
        main_layout.addWidget(instructions)
        
        # Main content area
        content_layout = QHBoxLayout()
        content_layout.setSpacing(12)
        
        # === Left: PDF viewer with page navigation ===
        left_panel = QVBoxLayout()
        left_panel.setSpacing(8)
        
        # Page navigation bar
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(8)
        
        self.prev_page_btn = QPushButton("◀ Prev")
        self.prev_page_btn.setFixedWidth(80)
        self.prev_page_btn.clicked.connect(self._prev_page)
        self.prev_page_btn.setEnabled(False)  # Disabled on first page
        nav_layout.addWidget(self.prev_page_btn)
        
        self.page_label = QLabel(f"Page 1 of {self.total_pages}")
        self.page_label.setStyleSheet("color: #a3a3a3; font-size: 12px;")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav_layout.addWidget(self.page_label, 1)
        
        self.next_page_btn = QPushButton("Next ▶")
        self.next_page_btn.setFixedWidth(80)
        self.next_page_btn.clicked.connect(self._next_page)
        self.next_page_btn.setEnabled(self.total_pages > 1)
        nav_layout.addWidget(self.next_page_btn)
        
        left_panel.addLayout(nav_layout)
        
        # Tip for panning
        pan_tip = QLabel("💡 Right-click and drag to pan around the PDF")
        pan_tip.setStyleSheet("color: #737373; font-size: 10px;")
        left_panel.addWidget(pan_tip)
        
        # Scroll area for PDF
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                background-color: #1e293b;
            }
        """)
        
        # Container for PDF and draggable boxes
        self.pdf_container = QWidget()
        self.pdf_container.setStyleSheet("background-color: #374151;")
        container_layout = QVBoxLayout(self.pdf_container)
        container_layout.setContentsMargins(10, 10, 10, 10)
        
        # PDF page view
        self.pdf_view = PDFPageView()
        self.pdf_view.set_scroll_area(self.scroll_area)  # Connect for panning
        if self.extractor:
            image_data = self.extractor.get_page_image_data(0)
            if image_data:
                self.pdf_view.set_pdf_image(image_data, self.extractor.scale_factor)
        
        container_layout.addWidget(self.pdf_view)
        container_layout.addStretch()
        
        self.scroll_area.setWidget(self.pdf_container)
        left_panel.addWidget(self.scroll_area)
        
        content_layout.addLayout(left_panel, 3)  # PDF gets 3 parts of space
        
        # === Right: Field boxes and mapping info ===
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)
        
        # Field boxes tray
        tray_label = QLabel("📦 Fields to Map")
        tray_label.setStyleSheet("font-weight: bold; color: #ffffff; font-size: 13px;")
        right_layout.addWidget(tray_label)
        
        tray_help = QLabel("Drag boxes onto the PDF values")
        tray_help.setStyleSheet("color: #737373; font-size: 11px;")
        right_layout.addWidget(tray_help)
        
        # Tray for unmapped fields
        self.fields_tray = QWidget()
        self.fields_tray.setStyleSheet("""
            QWidget {
                background-color: #1e293b;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
            }
        """)
        tray_layout = QGridLayout(self.fields_tray)
        tray_layout.setSpacing(8)
        tray_layout.setContentsMargins(10, 10, 10, 10)
        
        # Create field boxes - parent will be set in _reposition_field_boxes
        from pdf_import import get_field_definitions
        fields = get_field_definitions(self.utility_type)
        
        for i, field in enumerate(fields):
            # Skip fields marked as non-mappable (e.g., water service_charge, water_cost)
            if not field.get('mappable', True):
                continue
            
            box = DraggableFieldBox(
                field['name'], 
                field['label'], 
                field['required'],
                None  # No parent initially - will be set when repositioned
            )
            box.positionChanged.connect(self._on_field_dropped)
            self.field_boxes[field['name']] = box
            
            # Don't add to tray - they'll be positioned on PDF container
            row = i // 2
            col = i % 2
        
        right_layout.addWidget(self.fields_tray)
        
        # Mapping details section
        details_label = QLabel("📋 Mapping Details")
        details_label.setStyleSheet("font-weight: bold; color: #ffffff; font-size: 13px; margin-top: 12px;")
        right_layout.addWidget(details_label)
        
        # Scroll area for mapping details
        details_scroll = QScrollArea()
        details_scroll.setWidgetResizable(True)
        details_scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                background-color: #0f172a;
            }
        """)
        
        self.details_widget = QWidget()
        self.details_widget.setStyleSheet("background-color: #0f172a;")
        self.details_layout = QVBoxLayout(self.details_widget)
        self.details_layout.setSpacing(8)
        self.details_layout.setContentsMargins(8, 8, 8, 8)
        self.details_layout.addStretch()
        
        details_scroll.setWidget(self.details_widget)
        right_layout.addWidget(details_scroll, 1)
        
        # Give PDF viewer more space (3 parts PDF, 1 part controls)
        content_layout.addWidget(right_panel, 1)
        main_layout.addLayout(content_layout, 1)  # Allow content to stretch
        
        # === Buttons ===
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("Save Mappings")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._save_template)
        button_layout.addWidget(save_btn)
        
        main_layout.addLayout(button_layout)
        
        # Scale PDF to fit width and reposition field boxes after layout is set up
        QTimer.singleShot(150, self._fit_pdf_to_width)
        QTimer.singleShot(200, self._reposition_field_boxes)
    
    def _fit_pdf_to_width(self):
        """Scale the PDF to fit the available width (no horizontal scroll)."""
        if not hasattr(self, 'scroll_area') or not hasattr(self, 'pdf_view'):
            return
        
        # Get available width (scroll area width minus some padding)
        available_width = self.scroll_area.viewport().width() - 40
        
        if available_width > 100:  # Sanity check
            self.pdf_view.scale_to_width(available_width)
    
    def _setup_text_only_ui(self, main_layout):
        """Setup UI for text-only mode (when PyMuPDF is not available)."""
        # Warning message
        warning = QLabel("⚠️ PyMuPDF not installed - using text-only mode.\n"
                        "For visual PDF mapping, install PyMuPDF: pip install PyMuPDF")
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #f59e0b; font-size: 12px; padding: 8px; "
                             "background-color: #422006; border-radius: 4px;")
        main_layout.addWidget(warning)
        
        # Instructions
        instructions = QLabel("Enter the anchor text (label) that appears before each value in your PDF.")
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: #a3a3a3; font-size: 12px; padding: 4px;")
        main_layout.addWidget(instructions)
        
        # Content area (horizontal split)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)
        
        # === Left panel: PDF text content ===
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)
        
        left_label = QLabel("PDF Text Content")
        left_label.setStyleSheet("font-weight: bold; color: #ffffff; font-size: 13px;")
        left_layout.addWidget(left_label)
        
        # Get full text from extractor
        pdf_text = ""
        if self.extractor:
            pdf_text = self.extractor.get_full_text(0)
        
        self.pdf_text_view = QTextEdit()
        self.pdf_text_view.setReadOnly(True)
        self.pdf_text_view.setPlainText(pdf_text)
        self.pdf_text_view.setStyleSheet("""
            QTextEdit {
                background-color: #1e293b;
                color: #fafafa;
                font-family: Consolas, monospace;
                font-size: 11px;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        left_layout.addWidget(self.pdf_text_view)
        
        content_layout.addWidget(left_widget, 1)
        
        # === Right panel: Field mappings ===
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)
        
        right_label = QLabel("Field Anchors")
        right_label.setStyleSheet("font-weight: bold; color: #ffffff; font-size: 13px;")
        right_layout.addWidget(right_label)
        
        # Scroll area for fields
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { 
                border: 1px solid #3a3a3a; 
                border-radius: 4px;
                background-color: #0f172a;
            }
        """)
        
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background-color: #0f172a;")
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(8)
        scroll_layout.setContentsMargins(8, 8, 8, 8)
        
        # Get existing template
        template = self.db.get_pdf_template(self.utility_type) or {}
        
        from pdf_import import get_field_definitions
        fields = get_field_definitions(self.utility_type)
        
        self.anchor_inputs = {}
        self.pattern_inputs = {}
        
        for field in fields:
            name = field['name']
            label = field['label']
            required = field['required']
            
            # Field container
            field_frame = QFrame()
            field_frame.setStyleSheet("""
                QFrame {
                    background-color: #1e293b;
                    border: 1px solid #3a3a3a;
                    border-radius: 4px;
                }
            """)
            field_inner = QVBoxLayout(field_frame)
            field_inner.setSpacing(4)
            field_inner.setContentsMargins(10, 8, 10, 8)
            
            # Field name with required indicator
            req_mark = " *" if required else ""
            name_label = QLabel(f"{label}{req_mark}")
            name_label.setStyleSheet("font-weight: bold; color: #86efac; font-size: 12px;")
            field_inner.addWidget(name_label)
            
            # Anchor input row
            anchor_row = QHBoxLayout()
            anchor_row.setSpacing(8)
            
            anchor_lbl = QLabel("Anchor:")
            anchor_lbl.setStyleSheet("color: #a3a3a3; font-size: 11px;")
            anchor_lbl.setFixedWidth(50)
            anchor_row.addWidget(anchor_lbl)
            
            anchor_input = QLineEdit()
            anchor_input.setPlaceholderText("e.g., 'Amount Due'")
            anchor_input.setStyleSheet("""
                QLineEdit {
                    background-color: #0f172a;
                    border: 1px solid #475569;
                    border-radius: 3px;
                    padding: 4px 8px;
                    color: #fafafa;
                }
                QLineEdit:focus {
                    border-color: #86efac;
                }
            """)
            
            # Pre-fill from template
            if name in template:
                anchor_input.setText(template[name].get('anchor', ''))
            
            self.anchor_inputs[name] = anchor_input
            anchor_row.addWidget(anchor_input)
            field_inner.addLayout(anchor_row)
            
            # Pattern input row
            pattern_row = QHBoxLayout()
            pattern_row.setSpacing(8)
            
            pattern_lbl = QLabel("Pattern:")
            pattern_lbl.setStyleSheet("color: #a3a3a3; font-size: 11px;")
            pattern_lbl.setFixedWidth(50)
            pattern_row.addWidget(pattern_lbl)
            
            pattern_input = QLineEdit()
            pattern_input.setPlaceholderText("regex pattern (optional)")
            pattern_input.setStyleSheet("""
                QLineEdit {
                    background-color: #0f172a;
                    border: 1px solid #475569;
                    border-radius: 3px;
                    padding: 4px 8px;
                    color: #fafafa;
                    font-family: monospace;
                }
            """)
            
            # Pre-fill pattern from template or default
            if name in template:
                pattern_input.setText(template[name].get('pattern', ''))
            elif field.get('patterns'):
                pattern_input.setText(field['patterns'][0])
            
            self.pattern_inputs[name] = pattern_input
            pattern_row.addWidget(pattern_input)
            field_inner.addLayout(pattern_row)
            
            scroll_layout.addWidget(field_frame)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        right_layout.addWidget(scroll)
        
        content_layout.addWidget(right_widget, 1)
        
        main_layout.addLayout(content_layout)
        
        # === Buttons at bottom ===
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("Save")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._save_text_only_template)
        button_layout.addWidget(save_btn)
        
        main_layout.addLayout(button_layout)
    
    def _save_text_only_template(self):
        """Save template from text-only mode inputs."""
        template = {}
        for name, anchor_input in self.anchor_inputs.items():
            anchor = anchor_input.text().strip()
            pattern = self.pattern_inputs.get(name, QLineEdit()).text().strip()
            if anchor:
                template[name] = {
                    'anchor': anchor,
                    'pattern': pattern,
                }
                # Also extract value for immediate use
                if self.extractor:
                    text = self.extractor.get_text_near_anchor(anchor, 0)
                    if text and pattern:
                        match = re.search(pattern, text, re.IGNORECASE)
                        if match:
                            self.field_mappings[name] = {
                                'anchor': anchor,
                                'pattern': pattern,
                                'value': match.group(1) if match.groups() else match.group()
                            }
                    elif text:
                        self.field_mappings[name] = {
                            'anchor': anchor,
                            'pattern': pattern,
                            'value': text
                        }
        
        self.db.save_pdf_template(self.utility_type, template)
        QMessageBox.information(self, "Saved", "Field mappings saved successfully!")
        self.accept()
    
    def _prev_page(self):
        """Go to previous PDF page."""
        if self.current_page > 0:
            self.current_page -= 1
            self._update_page_display()
    
    def _next_page(self):
        """Go to next PDF page."""
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self._update_page_display()
    
    def _update_page_display(self):
        """Update the PDF view for the current page."""
        if not self.extractor:
            return
        
        # Update page label
        self.page_label.setText(f"Page {self.current_page + 1} of {self.total_pages}")
        
        # Update navigation buttons
        self.prev_page_btn.setEnabled(self.current_page > 0)
        self.next_page_btn.setEnabled(self.current_page < self.total_pages - 1)
        
        # Load new page image
        image_data = self.extractor.get_page_image_data(self.current_page)
        if image_data:
            self.pdf_view.set_pdf_image(image_data, self.extractor.scale_factor)
            # Scale to fit width
            self._fit_pdf_to_width()
        
        # Reposition field boxes on new page
        self._reposition_field_boxes()
        
        # Scroll to top
        if hasattr(self, 'scroll_area'):
            self.scroll_area.verticalScrollBar().setValue(0)
            self.scroll_area.horizontalScrollBar().setValue(0)
    
    def _reposition_field_boxes(self):
        """Move field boxes into the PDF container for dragging."""
        # Make sure pdf_view exists
        if not hasattr(self, 'pdf_view') or self.pdf_view is None:
            return
        
        # Load existing template to position boxes at saved locations
        template = self.db.get_pdf_template(self.utility_type)
        
        # Default position for unmapped fields
        x_offset = 10
        y_offset = 10
        unmapped_index = 0
        
        for name, box in self.field_boxes.items():
            # Disconnect old signal connections
            try:
                box.positionChanged.disconnect()
            except:
                pass
            
            box.setParent(self.pdf_container)
            
            # Connect callback
            box.positionChanged.connect(self._on_field_dropped)
            box.drop_callback = self._on_field_dropped
            
            # Check if this field has a saved position in template
            if template and name in template:
                mapping = template[name]
                saved_page = mapping.get('page', 0)
                saved_x = mapping.get('x')
                saved_y = mapping.get('y')
                
                # Only position if on current page and has coordinates
                if saved_page == self.current_page and saved_x is not None and saved_y is not None:
                    # Convert PDF coords to screen coords
                    screen_x, screen_y = self.pdf_view.pdf_to_screen_coords(saved_x, saved_y)
                    # Adjust for pdf_view position in container and box center
                    pdf_view_pos = self.pdf_view.pos()
                    box_x = pdf_view_pos.x() + screen_x - 60  # Center of box
                    box_y = pdf_view_pos.y() + screen_y - 14
                    box.move(int(box_x), int(box_y))
                    
                    # Mark as mapped and load the value
                    self.field_mappings[name] = {
                        'page': saved_page,
                        'x': saved_x,
                        'y': saved_y,
                        'value': ''
                    }
                    
                    # Extract value at this position
                    nearby_blocks = self.extractor.find_text_at_position(saved_x, saved_y, saved_page, radius=60)
                    if nearby_blocks:
                        closest_text = nearby_blocks[0].text
                        combined_text = " ".join(b.text for b in nearby_blocks[:3])
                        
                        # Try to extract value with patterns
                        import re
                        from pdf_import import get_field_definitions
                        fields = get_field_definitions(self.utility_type)
                        field_def = next((f for f in fields if f['name'] == name), None)
                        
                        extracted_value = ""
                        if field_def:
                            for text_to_try in [closest_text, combined_text]:
                                if not text_to_try:
                                    continue
                                for pattern in field_def.get('patterns', []):
                                    try:
                                        match = re.search(pattern, text_to_try, re.IGNORECASE)
                                        if match:
                                            extracted_value = match.group(1) if match.groups() else match.group()
                                            break
                                    except re.error:
                                        continue
                                if extracted_value:
                                    break
                        
                        if not extracted_value:
                            extracted_value = closest_text
                        
                        self.field_mappings[name]['value'] = extracted_value
                        box.set_mapped(True, f"Page {saved_page+1}", extracted_value)
                else:
                    # Field is on different page, put in default position
                    box.move(x_offset + (unmapped_index % 3) * 130, y_offset + (unmapped_index // 3) * 35)
                    unmapped_index += 1
            else:
                # No saved position, use default
                box.move(x_offset + (unmapped_index % 3) * 130, y_offset + (unmapped_index // 3) * 35)
                unmapped_index += 1
            
            box.show()
            box.raise_()
        
        # Update details panel
        self._update_details_panel()
    
    def _on_field_dropped(self, field_name: str, screen_x: float, screen_y: float):
        """Handle when a field box is dropped on the PDF - just save coordinates."""
        try:
            if not self.extractor or not hasattr(self, 'pdf_view') or self.pdf_view is None:
                return
            
            import re
            
            # Convert screen coords to PDF coords
            pdf_view_pos = self.pdf_view.pos()
            box_center_x = screen_x + 60
            box_center_y = screen_y + 14
            rel_x = box_center_x - pdf_view_pos.x()
            rel_y = box_center_y - pdf_view_pos.y()
            pdf_x, pdf_y = self.pdf_view.screen_to_pdf_coords(rel_x, rel_y)
            
            page = self.current_page
            
            # Get text at this position - combine nearby blocks for better pattern matching
            nearby_blocks = self.extractor.find_text_at_position(pdf_x, pdf_y, page, radius=60)
            
            # Get closest block text and combined text from nearby blocks
            closest_text = ""
            combined_text = ""
            if nearby_blocks:
                closest_text = nearby_blocks[0].text
                combined_text = " ".join(b.text for b in nearby_blocks[:3])
            
            # Extract value using patterns for this field type
            from pdf_import import get_field_definitions
            fields = get_field_definitions(self.utility_type)
            field_def = next((f for f in fields if f['name'] == field_name), None)
            
            extracted_value = ""
            
            # Try to extract value with patterns - try closest first, then combined
            if field_def:
                for text_to_try in [closest_text, combined_text]:
                    if not text_to_try:
                        continue
                    for pattern in field_def.get('patterns', []):
                        try:
                            match = re.search(pattern, text_to_try, re.IGNORECASE)
                            if match:
                                extracted_value = match.group(1) if match.groups() else match.group()
                                break
                        except re.error:
                            continue
                    if extracted_value:
                        break
            
            # If no pattern matched, use the raw closest text
            if not extracted_value:
                extracted_value = closest_text
            
            # Store mapping - just coordinates and page
            self.field_mappings[field_name] = {
                'page': page,
                'x': pdf_x,
                'y': pdf_y,
                'value': extracted_value
            }
            
            # Update box visual
            box = self.field_boxes.get(field_name)
            if box:
                display_value = extracted_value if extracted_value else f"({pdf_x:.0f}, {pdf_y:.0f})"
                box.set_mapped(True, f"Page {page+1}", display_value)
            
            # Update details panel
            self._update_details_panel()
            
        except Exception as e:
            QMessageBox.warning(self, "Drop Error", f"Error: {e}")
            
            # Update details panel
            self._update_details_panel()
            
        except Exception as e:
            print(f"Error in _on_field_dropped: {e}")
            import traceback
            traceback.print_exc()
    
    def _update_details_panel(self):
        """Update the mapping details panel."""
        try:
            # Check if details_layout exists
            if not hasattr(self, 'details_layout') or self.details_layout is None:
                return
            
            # Clear existing (keep the stretch at the end)
            while self.details_layout.count() > 1:
                item = self.details_layout.takeAt(0)
                if item and item.widget():
                    item.widget().deleteLater()
            
            # Add mapping details
            from pdf_import import get_field_definitions
            fields = get_field_definitions(self.utility_type)
            
            for field in fields:
                name = field['name']
                mapping = self.field_mappings.get(name, {})
                
                if mapping and 'x' in mapping:
                    frame = QFrame()
                    frame.setStyleSheet("""
                        QFrame {
                            background-color: #1e293b;
                            border: 1px solid #3a3a3a;
                            border-radius: 4px;
                        }
                    """)
                    frame_layout = QVBoxLayout(frame)
                    frame_layout.setContentsMargins(8, 6, 8, 6)
                    frame_layout.setSpacing(2)
                    
                    # Field name
                    name_lbl = QLabel(field['label'])
                    name_lbl.setStyleSheet("font-weight: bold; color: #86efac; font-size: 11px;")
                    frame_layout.addWidget(name_lbl)
                    
                    # Coordinates
                    x = mapping.get('x', 0)
                    y = mapping.get('y', 0)
                    page = mapping.get('page', 0)
                    coord_lbl = QLabel(f"Page {page+1} @ ({x:.0f}, {y:.0f})")
                    coord_lbl.setStyleSheet("color: #a3a3a3; font-size: 10px;")
                    frame_layout.addWidget(coord_lbl)
                    
                    # Value
                    value = mapping.get('value', '')
                    if value:
                        val_lbl = QLabel(f"Value: {value}")
                        val_lbl.setStyleSheet("color: #22c55e; font-size: 10px;")
                    else:
                        val_lbl = QLabel("Value: (pending)")
                        val_lbl.setStyleSheet("color: #f59e0b; font-size: 10px;")
                    frame_layout.addWidget(val_lbl)
                    
                    self.details_layout.insertWidget(self.details_layout.count() - 1, frame)
                    
        except Exception as e:
            pass
    
    def _save_template(self):
        """Save the field mappings as a template (using coordinates)."""
        template = {}
        for field_name, mapping in self.field_mappings.items():
            if 'x' in mapping and 'y' in mapping:
                template[field_name] = {
                    'page': mapping.get('page', 0),
                    'x': mapping['x'],
                    'y': mapping['y'],
                }
        
        if not template:
            QMessageBox.warning(self, "No Mappings", 
                "No field mappings to save. Please drag at least one field box onto the PDF.")
            return
        
        self.db.save_pdf_template(self.utility_type, template)
        
        # Re-extract all values using coordinates
        self._extract_all_values()
        
        QMessageBox.information(self, "Saved", "Field mappings saved successfully!")
        self.accept()
    
    def _extract_all_values(self):
        """Extract values for all mapped fields using coordinates."""
        if not self.extractor:
            return
        
        import re
        from pdf_import import get_field_definitions
        fields = get_field_definitions(self.utility_type)
        
        for field_name, mapping in self.field_mappings.items():
            x = mapping.get('x')
            y = mapping.get('y')
            page = mapping.get('page', 0)
            
            if x is None or y is None:
                continue
            
            # Get text at these coordinates - use same radius as during drop
            nearby_blocks = self.extractor.find_text_at_position(x, y, page, radius=60)
            if not nearby_blocks:
                continue
            
            # Get closest and combined text like in _on_field_dropped
            closest_text = nearby_blocks[0].text
            combined_text = " ".join(b.text for b in nearby_blocks[:3])
            
            # Find field definition for patterns
            field_def = next((f for f in fields if f['name'] == field_name), None)
            
            # Try to extract clean value with patterns - try both texts
            extracted_value = ""
            if field_def:
                for text_to_try in [closest_text, combined_text]:
                    if not text_to_try:
                        continue
                    for pattern in field_def.get('patterns', []):
                        try:
                            match = re.search(pattern, text_to_try, re.IGNORECASE)
                            if match:
                                extracted_value = match.group(1) if match.groups() else match.group()
                                break
                        except re.error:
                            continue
                    if extracted_value:
                        break
            
            # Fall back to raw closest text
            if not extracted_value:
                extracted_value = closest_text
            
            mapping['value'] = extracted_value
    
    def get_extracted_values(self) -> Dict[str, str]:
        """Get the extracted values from mappings."""
        # Make sure we have values extracted
        self._extract_all_values()
        return {name: m.get('value', '') for name, m in self.field_mappings.items()}


# ============== MAIN WINDOW ==============

class MainWindow(QMainWindow):
    def __init__(self, db_path="data/utilities.db"):
        super().__init__()
        self.db = DatabaseManager(db_path)
        self.weather_thread = None
        
        self._setup_window()
        self._create_menus()
        self._setup_ui()
        self._load_data()
        
        self.setStyleSheet(CARBON_SAGE_THEME)
        
        # Auto-update weather on startup (silent mode - no dialogs)
        # 10 second delay to let UI fully initialize
        # Disabled by default - user must enable in Settings
        auto_update = self.db.get_config('auto_update_weather')
        if auto_update == '1':  # Only if explicitly enabled
            QTimer.singleShot(10000, self._auto_update_weather_silent)
    
    def _auto_update_weather_silent(self):
        """Automatically update weather data on startup - silent mode (no dialogs)."""
        try:
            # Check if we have a weather source configured
            source = self.db.get_config('weather_source') or 'open-meteo'
            
            if source == 'open-meteo':
                self._update_weather_openmeteo_silent()
            # Skip other sources on auto-update as they require interaction
        except Exception as e:
            print(f"Auto weather update failed: {e}")
    
    def _update_weather_openmeteo_silent(self):
        """Fetch weather data from Open-Meteo API silently (no dialogs)."""
        from weather_api import OpenMeteoAPI, WeatherDemandCalculator
        from database import WeatherDay
        
        try:
            lat = float(self.db.get_config('location_latitude') or 35.3187)
            lon = float(self.db.get_config('location_longitude') or -82.4612)
            
            latest = self.db.get_latest_weather_date()
            start_date = (latest + timedelta(days=1)) if latest else date(2024, 1, 1)
            end_date = date.today() - timedelta(days=1)
            
            if start_date > end_date:
                return  # Already up to date
            
            # Limit to last 30 days for silent update
            if (end_date - start_date).days > 30:
                start_date = end_date - timedelta(days=30)
            
            api = OpenMeteoAPI(latitude=lat, longitude=lon)
            observations = api.get_date_range(start_date, end_date)
            
            # Get demand calculator settings
            demand_settings = self.db.get_demand_settings()
            calc = WeatherDemandCalculator(
                heating_min=demand_settings['heating_min_temp'],
                heating_max=demand_settings['heating_max_temp'],
                cooling_min=demand_settings['cooling_min_temp'],
                cooling_max=demand_settings['cooling_max_temp']
            )
            
            # Save to database
            for obs in observations:
                demands = calc.calculate_demands(obs.temp_high, obs.temp_low)
                weather_day = WeatherDay(
                    date=obs.date,
                    temp_high=obs.temp_high,
                    temp_low=obs.temp_low,
                    temp_avg=obs.temp_avg,
                    dewpoint_high=obs.dewpoint_high,
                    dewpoint_avg=obs.dewpoint_avg,
                    dewpoint_low=obs.dewpoint_low,
                    humidity_high=obs.humidity_high,
                    humidity_avg=obs.humidity_avg,
                    humidity_low=obs.humidity_low,
                    wind_max=obs.wind_max,
                    wind_avg=obs.wind_avg,
                    wind_gust=obs.wind_gust,
                    pressure_max=obs.pressure_max,
                    pressure_min=obs.pressure_min,
                    rain_total=obs.rain_total,
                    heating_demand=demands['heating_demand'],
                    cooling_demand=demands['cooling_demand'],
                )
                self.db.save_weather_day(weather_day)
            
            # Refresh data silently
            self._load_data()
            
        except Exception as e:
            print(f"Silent weather update failed: {e}")
    
    def _setup_window(self):
        self.setWindowTitle("UtilityHQ - Home Utilities Tracker")
        self.setMinimumSize(1300, 850)
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry((screen.width()-1400)//2, (screen.height()-900)//2, 1400, 900)
        
        # Set window icon (for taskbar and title bar)
        resources = Path(__file__).parent.parent / "resources"
        icon_path = resources / "icon.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
    
    def _create_menus(self):
        # Menu bar hidden - functionality moved to sidebar
        self.menuBar().hide()
    
    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)  # Changed to horizontal for sidebar
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create sidebar
        self._create_sidebar(main_layout)
        
        # Right side: content area
        content_area = QWidget()
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        # Top bar removed - context info now in ribbon/status bar
        # self._create_top_bar(content_layout)
        
        # Stacked widget for pages
        self.stack = QStackedWidget()
        self.stack.addWidget(self._create_dashboard())  # 0
        
        # Utility pages
        self.electric_page = UtilityPage("electric", self.db)
        self.electric_page.add_bill_requested.connect(self._add_bill)
        self.electric_page.import_pdf_requested.connect(self._import_pdf)
        self.stack.addWidget(self.electric_page)  # 1
        
        self.gas_page = UtilityPage("gas", self.db)
        self.gas_page.add_bill_requested.connect(self._add_bill)
        self.gas_page.import_pdf_requested.connect(self._import_pdf)
        self.stack.addWidget(self.gas_page)  # 2
        
        self.water_page = UtilityPage("water", self.db)
        self.water_page.add_bill_requested.connect(self._add_bill)
        self.water_page.import_pdf_requested.connect(self._import_pdf)
        self.stack.addWidget(self.water_page)  # 3
        
        self.stack.addWidget(self._create_weather_view())  # 4
        
        # Demand page
        self.demand_page = DemandPage(self.db)
        self.stack.addWidget(self.demand_page)  # 5
        
        content_layout.addWidget(self.stack, 1)
        
        self._create_status_bar(content_layout)
        
        main_layout.addWidget(content_area, 1)
    
    def _create_sidebar(self, parent):
        """Create fixed sidebar navigation."""
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(180)
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(4)
        
        # Logo section
        logo_frame = QHBoxLayout()
        logo_frame.setSpacing(10)
        
        # Logo icon with gradient background
        logo_icon = QLabel("⚡")
        logo_icon.setFixedSize(32, 32)
        logo_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_icon.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #86efac, stop:1 #4ade80);
            border-radius: 8px;
            font-size: 14px;
        """)
        logo_frame.addWidget(logo_icon)
        
        logo_text = QLabel("UtilityHQ")
        logo_text.setStyleSheet("font-size: 15px; font-weight: 700; color: #fafafa;")
        logo_frame.addWidget(logo_text)
        logo_frame.addStretch()
        
        layout.addLayout(logo_frame)
        layout.addSpacing(20)
        
        # Navigation sections
        self.nav_buttons = []
        
        # Overview section
        section_label = QLabel("OVERVIEW")
        section_label.setStyleSheet("font-size: 10px; color: #737373; letter-spacing: 1px; padding-left: 8px; padding-bottom: 4px;")
        layout.addWidget(section_label)
        
        self._add_nav_button(layout, "📊", "Dashboard", 0)
        
        layout.addSpacing(16)
        
        # Utilities section
        section_label2 = QLabel("UTILITIES")
        section_label2.setStyleSheet("font-size: 10px; color: #737373; letter-spacing: 1px; padding-left: 8px; padding-bottom: 4px;")
        layout.addWidget(section_label2)
        
        self._add_nav_button(layout, "⚡", "Electric", 1)
        self._add_nav_button(layout, "🔥", "Gas", 2)
        self._add_nav_button(layout, "💧", "Water", 3)
        
        layout.addSpacing(16)
        
        # Analytics section
        section_label3 = QLabel("ANALYTICS")
        section_label3.setStyleSheet("font-size: 10px; color: #737373; letter-spacing: 1px; padding-left: 8px; padding-bottom: 4px;")
        layout.addWidget(section_label3)
        
        self._add_nav_button(layout, "🌤️", "Weather", 4)
        self._add_nav_button(layout, "📈", "Demand", 5)
        
        layout.addSpacing(12)
        
        # Separator before Import section
        import_sep = QFrame()
        import_sep.setFrameShape(QFrame.Shape.HLine)
        import_sep.setStyleSheet("background-color: #2e2e2e;")
        layout.addWidget(import_sep)
        layout.addSpacing(8)
        
        # Import Data section
        section_label4 = QLabel("IMPORT DATA")
        section_label4.setStyleSheet("font-size: 10px; color: #737373; letter-spacing: 1px; padding-left: 8px; padding-bottom: 4px;")
        layout.addWidget(section_label4)
        
        # Import Weather button - abbreviate location for tooltip
        location_name = self.db.get_config('location_name') or 'Hendersonville, North Carolina'
        # Remove country and abbreviate state (e.g., "Nashville, Tennessee, United States" -> "Nashville, TN")
        location_parts = location_name.split(', ')
        if len(location_parts) >= 2:
            city = location_parts[0]
            state = location_parts[1]
            # Common state abbreviations
            state_abbrevs = {
                'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR', 'California': 'CA',
                'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE', 'Florida': 'FL', 'Georgia': 'GA',
                'Hawaii': 'HI', 'Idaho': 'ID', 'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA',
                'Kansas': 'KS', 'Kentucky': 'KY', 'Louisiana': 'LA', 'Maine': 'ME', 'Maryland': 'MD',
                'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN', 'Mississippi': 'MS', 'Missouri': 'MO',
                'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV', 'New Hampshire': 'NH', 'New Jersey': 'NJ',
                'New Mexico': 'NM', 'New York': 'NY', 'North Carolina': 'NC', 'North Dakota': 'ND', 'Ohio': 'OH',
                'Oklahoma': 'OK', 'Oregon': 'OR', 'Pennsylvania': 'PA', 'Rhode Island': 'RI', 'South Carolina': 'SC',
                'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX', 'Utah': 'UT', 'Vermont': 'VT',
                'Virginia': 'VA', 'Washington': 'WA', 'West Virginia': 'WV', 'Wisconsin': 'WI', 'Wyoming': 'WY'
            }
            state_abbrev = state_abbrevs.get(state, state[:2].upper() if len(state) > 2 else state)
            location_short = f"{city}, {state_abbrev}"
        else:
            location_short = location_name
        
        import_weather_btn = QPushButton("🌡️  Weather")
        import_weather_btn.setObjectName("navButton")
        import_weather_btn.setToolTip(f"Update weather for {location_short}")
        import_weather_btn.clicked.connect(self._update_weather)
        layout.addWidget(import_weather_btn)
        
        # Import Electric Bill button
        import_electric_btn = QPushButton("⚡  Electric Bill")
        import_electric_btn.setObjectName("navButton")
        import_electric_btn.setToolTip("Import electric bill from PDF")
        import_electric_btn.clicked.connect(lambda: self._import_pdf("electric"))
        layout.addWidget(import_electric_btn)
        
        # Import Gas Bill button
        import_gas_btn = QPushButton("🔥  Gas Bill")
        import_gas_btn.setObjectName("navButton")
        import_gas_btn.setToolTip("Import gas bill from PDF")
        import_gas_btn.clicked.connect(lambda: self._import_pdf("gas"))
        layout.addWidget(import_gas_btn)
        
        # Import Water Bill button
        import_water_btn = QPushButton("💧  Water Bill")
        import_water_btn.setObjectName("navButton")
        import_water_btn.setToolTip("Import water bill from PDF")
        import_water_btn.clicked.connect(lambda: self._import_pdf("water"))
        layout.addWidget(import_water_btn)
        
        layout.addStretch()
        
        # Bottom section with settings/help
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #2e2e2e;")
        layout.addWidget(sep)
        layout.addSpacing(8)
        
        # Update button
        update_btn = QPushButton("🔄  Check for Updates")
        update_btn.setObjectName("navButton")
        update_btn.clicked.connect(self._check_for_updates)
        layout.addWidget(update_btn)
        
        # Settings button
        settings_btn = QPushButton("⚙️  Settings")
        settings_btn.setObjectName("navButton")
        settings_btn.clicked.connect(self._open_settings)
        layout.addWidget(settings_btn)
        
        # Help button
        help_btn = QPushButton("❓  Help")
        help_btn.setObjectName("navButton")
        help_btn.clicked.connect(self._show_about)
        layout.addWidget(help_btn)
        
        parent.addWidget(sidebar)
        
        # Select first button by default
        if self.nav_buttons:
            self.nav_buttons[0].setChecked(True)
    
    def _add_nav_button(self, layout, icon: str, text: str, page_index: int):
        """Add a navigation button to the sidebar."""
        btn = QPushButton(f"{icon}  {text}")
        btn.setObjectName("navButton")
        btn.setCheckable(True)
        btn.clicked.connect(lambda: self._navigate_to(page_index))
        layout.addWidget(btn)
        self.nav_buttons.append(btn)
    
    def _navigate_to(self, index: int):
        """Navigate to a page and update button states."""
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
        
        # Update top bar title
        titles = ["Dashboard", "Electric", "Gas", "Water", "Weather", "Demand"]
        if hasattr(self, 'topbar_title'):
            self.topbar_title.setText(titles[index] if index < len(titles) else "")
    
    def _create_top_bar(self, parent):
        """Create top bar with page title and context info."""
        topbar = QFrame()
        topbar.setObjectName("topBar")
        topbar.setFixedHeight(48)
        
        layout = QHBoxLayout(topbar)
        layout.setContentsMargins(20, 0, 20, 0)
        
        # Page title
        self.topbar_title = QLabel("Dashboard")
        self.topbar_title.setStyleSheet("font-size: 18px; font-weight: 600; color: #fafafa;")
        layout.addWidget(self.topbar_title)
        
        layout.addStretch()
        
        # Context info
        location_name = self.db.get_config('location_name') or 'Hendersonville, NC'
        
        loc_icon = QLabel("📍")
        loc_icon.setStyleSheet("font-size: 14px;")
        layout.addWidget(loc_icon)
        
        loc_text = QLabel(location_name)
        loc_text.setStyleSheet("font-size: 12px; color: #a3a3a3;")
        layout.addWidget(loc_text)
        
        layout.addSpacing(20)
        
        date_icon = QLabel("📅")
        date_icon.setStyleSheet("font-size: 14px;")
        layout.addWidget(date_icon)
        
        date_text = QLabel(datetime.now().strftime("%A, %b %d, %Y"))
        date_text.setStyleSheet("font-size: 12px; color: #a3a3a3;")
        layout.addWidget(date_text)
        
        parent.addWidget(topbar)
    
    def _create_title_bar(self, parent):
        """Legacy method - replaced by sidebar."""
        pass
    
    def _create_dashboard(self):
        """Create the main dashboard with ribbon sections."""
        dashboard = QWidget()
        layout = QVBoxLayout(dashboard)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # Title
        title = QLabel("📊 Dashboard")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        
        # ========== RIBBON - TWO ROW D1 LAYOUT ==========
        ribbon_container = QFrame()
        ribbon_container.setObjectName("statsBar")
        ribbon_container_layout = QVBoxLayout(ribbon_container)
        ribbon_container_layout.setContentsMargins(12, 12, 12, 12)
        ribbon_container_layout.setSpacing(10)
        
        # ===== ROW 1: UTILITY CARDS =====
        row1 = QHBoxLayout()
        row1.setSpacing(12)
        
        # Helper to create utility card with colored left border
        def create_utility_card(color):
            card = QFrame()
            card.setObjectName("utilityCard")
            card.setStyleSheet(f"""
                QFrame#utilityCard {{
                    background: #1a1a1a;
                    border: 1px solid #2e2e2e;
                    border-left: 3px solid {color};
                    border-radius: 8px;
                }}
            """)
            return card
        
        # --- Electric Card ---
        elec_card = create_utility_card("#f39c12")
        elec_layout = QVBoxLayout(elec_card)
        elec_layout.setContentsMargins(0, 0, 0, 0)
        elec_layout.setSpacing(0)
        
        # Top zone (Usage tooltip) - contains title and cost/usage only
        self.elec_usage_zone = InstantTooltipFrame()
        self.elec_usage_zone.setStyleSheet("background: transparent;")
        elec_usage_layout = QVBoxLayout(self.elec_usage_zone)
        elec_usage_layout.setContentsMargins(14, 12, 14, 8)
        elec_usage_layout.setSpacing(4)
        
        elec_title = QLabel("⚡ ELECTRIC")
        elec_title.setStyleSheet("color: #737373; font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px;")
        elec_usage_layout.addWidget(elec_title)
        
        elec_main = QHBoxLayout()
        elec_main.setSpacing(0)
        self.cost_electric = QLabel("$0.00")
        self.cost_electric.setStyleSheet("color: #f39c12; font-size: 22px; font-weight: bold;")
        elec_main.addWidget(self.cost_electric)
        elec_divider = QLabel(" / ")
        elec_divider.setStyleSheet("color: #737373; font-size: 16px;")
        elec_main.addWidget(elec_divider)
        self.usage_electric = QLabel("0 kWh")
        self.usage_electric.setStyleSheet("color: #f39c12; font-size: 18px;")
        elec_main.addWidget(self.usage_electric)
        elec_main.addStretch()
        self.elec_change = QLabel("")
        self.elec_change.setStyleSheet("color: #737373; font-size: 10px;")
        elec_main.addWidget(self.elec_change)
        elec_usage_layout.addLayout(elec_main)
        
        elec_layout.addWidget(self.elec_usage_zone)
        
        # Separator
        elec_sep = QFrame()
        elec_sep.setFixedHeight(1)
        elec_sep.setStyleSheet("background: #2e2e2e; margin-left: 14px; margin-right: 14px;")
        elec_layout.addWidget(elec_sep)
        
        # Footer row with Per Day zone (tooltip) and Meter (no tooltip)
        elec_footer = QHBoxLayout()
        elec_footer.setContentsMargins(14, 6, 14, 10)
        elec_footer.setSpacing(6)
        
        # Per Day zone (with tooltip)
        self.elec_perday_zone = InstantTooltipFrame()
        self.elec_perday_zone.setStyleSheet("background: transparent;")
        elec_perday_layout = QHBoxLayout(self.elec_perday_zone)
        elec_perday_layout.setContentsMargins(0, 0, 0, 0)
        elec_perday_layout.setSpacing(4)
        per_day_lbl = QLabel("Per Day:")
        per_day_lbl.setStyleSheet("color: #737373; font-size: 11px;")
        elec_perday_layout.addWidget(per_day_lbl)
        self.elec_per_day = QLabel("0.0 kWh")
        self.elec_per_day.setStyleSheet("color: #737373; font-size: 12px;")
        elec_perday_layout.addWidget(self.elec_per_day)
        elec_footer.addWidget(self.elec_perday_zone)
        
        elec_footer.addStretch()
        
        # Meter section (no tooltip)
        meter_lbl = QLabel("Meter:")
        meter_lbl.setStyleSheet("color: #737373; font-size: 11px;")
        elec_footer.addWidget(meter_lbl)
        self.meter_electric = QLineEdit()
        self.meter_electric.setFixedWidth(75)
        self.meter_electric.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.meter_electric.setPlaceholderText("0")
        self.meter_electric.setStyleSheet("background: #121212; border: 1px solid #2e2e2e; border-radius: 4px; padding: 2px 6px; color: #fafafa; font-size: 12px;")
        self.meter_electric.editingFinished.connect(self._update_meter_estimates)
        elec_footer.addWidget(self.meter_electric)
        elec_unit = QLabel("kWh")
        elec_unit.setStyleSheet("color: #737373; font-size: 11px;")
        elec_footer.addWidget(elec_unit)
        
        elec_layout.addLayout(elec_footer)
        
        row1.addWidget(elec_card, 1)
        
        # --- Gas Card ---
        gas_card = create_utility_card("#e74c3c")
        gas_layout = QVBoxLayout(gas_card)
        gas_layout.setContentsMargins(0, 0, 0, 0)
        gas_layout.setSpacing(0)
        
        # Top zone (Usage tooltip)
        self.gas_usage_zone = InstantTooltipFrame()
        self.gas_usage_zone.setStyleSheet("background: transparent;")
        gas_usage_layout = QVBoxLayout(self.gas_usage_zone)
        gas_usage_layout.setContentsMargins(14, 12, 14, 8)
        gas_usage_layout.setSpacing(4)
        
        gas_title = QLabel("🔥 GAS")
        gas_title.setStyleSheet("color: #737373; font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px;")
        gas_usage_layout.addWidget(gas_title)
        
        gas_main = QHBoxLayout()
        gas_main.setSpacing(0)
        self.cost_gas = QLabel("$0.00")
        self.cost_gas.setStyleSheet("color: #e74c3c; font-size: 22px; font-weight: bold;")
        gas_main.addWidget(self.cost_gas)
        gas_divider = QLabel(" / ")
        gas_divider.setStyleSheet("color: #737373; font-size: 16px;")
        gas_main.addWidget(gas_divider)
        self.usage_gas = QLabel("0 Thm")
        self.usage_gas.setStyleSheet("color: #e74c3c; font-size: 18px;")
        gas_main.addWidget(self.usage_gas)
        gas_main.addStretch()
        self.gas_change = QLabel("")
        self.gas_change.setStyleSheet("color: #737373; font-size: 10px;")
        gas_main.addWidget(self.gas_change)
        gas_usage_layout.addLayout(gas_main)
        
        gas_layout.addWidget(self.gas_usage_zone)
        
        # Separator
        gas_sep = QFrame()
        gas_sep.setFixedHeight(1)
        gas_sep.setStyleSheet("background: #2e2e2e; margin-left: 14px; margin-right: 14px;")
        gas_layout.addWidget(gas_sep)
        
        # Footer row with Per Day zone (tooltip) and Meter (no tooltip)
        gas_footer = QHBoxLayout()
        gas_footer.setContentsMargins(14, 6, 14, 10)
        gas_footer.setSpacing(6)
        
        # Per Day zone (with tooltip)
        self.gas_perday_zone = InstantTooltipFrame()
        self.gas_perday_zone.setStyleSheet("background: transparent;")
        gas_perday_layout = QHBoxLayout(self.gas_perday_zone)
        gas_perday_layout.setContentsMargins(0, 0, 0, 0)
        gas_perday_layout.setSpacing(4)
        gas_pd_lbl = QLabel("Per Day:")
        gas_pd_lbl.setStyleSheet("color: #737373; font-size: 11px;")
        gas_perday_layout.addWidget(gas_pd_lbl)
        self.gas_per_day = QLabel("0.0 Thm")
        self.gas_per_day.setStyleSheet("color: #737373; font-size: 12px;")
        gas_perday_layout.addWidget(self.gas_per_day)
        gas_footer.addWidget(self.gas_perday_zone)
        
        gas_footer.addStretch()
        
        # Meter section (no tooltip)
        gas_meter_lbl = QLabel("Meter:")
        gas_meter_lbl.setStyleSheet("color: #737373; font-size: 11px;")
        gas_footer.addWidget(gas_meter_lbl)
        self.meter_gas = QLineEdit()
        self.meter_gas.setFixedWidth(75)
        self.meter_gas.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.meter_gas.setPlaceholderText("0")
        self.meter_gas.setStyleSheet("background: #121212; border: 1px solid #2e2e2e; border-radius: 4px; padding: 2px 6px; color: #fafafa; font-size: 12px;")
        self.meter_gas.editingFinished.connect(self._update_meter_estimates)
        gas_footer.addWidget(self.meter_gas)
        gas_unit = QLabel("Thm")
        gas_unit.setStyleSheet("color: #737373; font-size: 11px;")
        gas_footer.addWidget(gas_unit)
        
        gas_layout.addLayout(gas_footer)
        
        row1.addWidget(gas_card, 1)
        
        # --- Water Card (no meter input) ---
        water_card = create_utility_card("#3498db")
        water_layout = QVBoxLayout(water_card)
        water_layout.setContentsMargins(0, 0, 0, 0)
        water_layout.setSpacing(0)
        
        # Top zone (Usage tooltip)
        self.water_usage_zone = InstantTooltipFrame()
        self.water_usage_zone.setStyleSheet("background: transparent;")
        water_usage_layout = QVBoxLayout(self.water_usage_zone)
        water_usage_layout.setContentsMargins(14, 12, 14, 8)
        water_usage_layout.setSpacing(4)
        
        water_title = QLabel("💧 WATER")
        water_title.setStyleSheet("color: #737373; font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px;")
        water_usage_layout.addWidget(water_title)
        
        water_main = QHBoxLayout()
        water_main.setSpacing(0)
        self.cost_water = QLabel("$0.00")
        self.cost_water.setStyleSheet("color: #3498db; font-size: 22px; font-weight: bold;")
        water_main.addWidget(self.cost_water)
        water_divider = QLabel(" / ")
        water_divider.setStyleSheet("color: #737373; font-size: 16px;")
        water_main.addWidget(water_divider)
        self.usage_water = QLabel("0 gal")
        self.usage_water.setStyleSheet("color: #3498db; font-size: 18px;")
        water_main.addWidget(self.usage_water)
        water_main.addStretch()
        self.water_change = QLabel("")
        self.water_change.setStyleSheet("color: #737373; font-size: 10px;")
        water_main.addWidget(self.water_change)
        water_usage_layout.addLayout(water_main)
        
        water_layout.addWidget(self.water_usage_zone)
        
        # Separator
        water_sep = QFrame()
        water_sep.setFixedHeight(1)
        water_sep.setStyleSheet("background: #2e2e2e; margin-left: 14px; margin-right: 14px;")
        water_layout.addWidget(water_sep)
        
        # Footer row with Per Day zone (tooltip)
        water_footer = QHBoxLayout()
        water_footer.setContentsMargins(14, 6, 14, 10)
        water_footer.setSpacing(6)
        
        # Per Day zone (with tooltip)
        self.water_perday_zone = InstantTooltipFrame()
        self.water_perday_zone.setStyleSheet("background: transparent;")
        water_perday_layout = QHBoxLayout(self.water_perday_zone)
        water_perday_layout.setContentsMargins(0, 0, 0, 0)
        water_perday_layout.setSpacing(4)
        water_pd_lbl = QLabel("Per Day:")
        water_pd_lbl.setStyleSheet("color: #737373; font-size: 11px;")
        water_perday_layout.addWidget(water_pd_lbl)
        self.water_per_day = QLabel("0 gal")
        self.water_per_day.setStyleSheet("color: #737373; font-size: 12px;")
        water_perday_layout.addWidget(self.water_per_day)
        water_footer.addWidget(self.water_perday_zone)
        
        water_footer.addStretch()
        
        water_layout.addLayout(water_footer)
        
        row1.addWidget(water_card, 1)
        
        # --- Total Card ---
        total_card = create_utility_card("#a855f7")
        total_layout = QVBoxLayout(total_card)
        total_layout.setContentsMargins(14, 12, 14, 10)
        total_layout.setSpacing(4)
        
        current_month = datetime.now().strftime("%B").upper()
        total_title = QLabel(f"{current_month} TOTAL")
        total_title.setStyleSheet("color: #737373; font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px;")
        total_layout.addWidget(total_title)
        
        total_main = QHBoxLayout()
        total_main.setSpacing(0)
        self.cost_total = QLabel("$0.00")
        self.cost_total.setStyleSheet("color: #a855f7; font-size: 22px; font-weight: bold;")
        total_main.addWidget(self.cost_total)
        total_main.addStretch()
        self.total_change = QLabel("")
        self.total_change.setStyleSheet("color: #737373; font-size: 10px;")
        total_main.addWidget(self.total_change)
        total_layout.addLayout(total_main)
        
        total_sep = QFrame()
        total_sep.setFixedHeight(1)
        total_sep.setStyleSheet("background: #2e2e2e;")
        total_layout.addWidget(total_sep)
        
        total_footer = QHBoxLayout()
        total_footer.setSpacing(6)
        ytd_lbl = QLabel("YTD:")
        ytd_lbl.setStyleSheet("color: #737373; font-size: 11px;")
        total_footer.addWidget(ytd_lbl)
        total_footer.addStretch()
        self.ytd_value = QLabel("$0.00")
        self.ytd_value.setStyleSheet("color: #fafafa; font-size: 12px; font-weight: 600;")
        total_footer.addWidget(self.ytd_value)
        self.ytd_change = QLabel("")
        self.ytd_change.setStyleSheet("color: #22c55e; font-size: 12px;")
        total_footer.addWidget(self.ytd_change)
        total_layout.addLayout(total_footer)
        
        row1.addWidget(total_card, 1)
        
        ribbon_container_layout.addLayout(row1)
        
        # ===== ROW 2: FORECAST | PERFORMANCE | WEATHER =====
        row2 = QFrame()
        row2.setObjectName("row2Frame")
        row2.setStyleSheet("""
            QFrame#row2Frame { background: #1a1a1a; border: 1px solid #2e2e2e; border-radius: 8px; }
            QFrame#row2Frame QLabel { border: none; background: transparent; }
        """)
        row2_layout = QHBoxLayout(row2)
        row2_layout.setContentsMargins(16, 10, 16, 10)
        row2_layout.setSpacing(16)
        
        # --- Forecast Section ---
        forecast_section = QVBoxLayout()
        forecast_section.setSpacing(6)
        forecast_title = QLabel("FORECAST")
        forecast_title.setStyleSheet("color: #737373; font-size: 9px; text-transform: uppercase; letter-spacing: 1px;")
        forecast_section.addWidget(forecast_title)
        
        forecast_data = self.db.get_monthly_cost_forecast()
        
        forecast_inline = QHBoxLayout()
        forecast_inline.setSpacing(16)
        
        # Previous month
        prev_data = forecast_data['previous_month']
        prev_box = QHBoxLayout()
        prev_box.setSpacing(5)
        self.forecast_prev_label = QLabel(f"{prev_data['label']}:")
        self.forecast_prev_label.setStyleSheet("color: #737373; font-size: 11px;")
        prev_box.addWidget(self.forecast_prev_label)
        self.forecast_prev_val = QLabel(f"${prev_data['value']:,.0f}")
        self.forecast_prev_val.setStyleSheet("color: #fafafa; font-size: 13px; font-weight: 600;")
        prev_box.addWidget(self.forecast_prev_val)
        forecast_inline.addLayout(prev_box)
        
        # Current month
        curr_data = forecast_data['this_month']
        curr_box = QHBoxLayout()
        curr_box.setSpacing(5)
        self.forecast_curr_label = QLabel(f"{curr_data['label']}:")
        self.forecast_curr_label.setStyleSheet("color: #737373; font-size: 11px;")
        curr_box.addWidget(self.forecast_curr_label)
        self.forecast_curr_val = QLabel(f"${curr_data['value']:,.0f}")
        self.forecast_curr_val.setStyleSheet("color: #86efac; font-size: 13px; font-weight: 600;")
        curr_box.addWidget(self.forecast_curr_val)
        forecast_inline.addLayout(curr_box)
        
        # Next month
        next_data = forecast_data['next_month']
        next_box = QHBoxLayout()
        next_box.setSpacing(5)
        self.forecast_next_label = QLabel(f"{next_data['label']}:")
        self.forecast_next_label.setStyleSheet("color: #737373; font-size: 11px;")
        next_box.addWidget(self.forecast_next_label)
        self.forecast_next_val = QLabel(f"${next_data['value']:,.0f}")
        self.forecast_next_val.setStyleSheet("color: #fafafa; font-size: 13px; font-weight: 600;")
        next_box.addWidget(self.forecast_next_val)
        forecast_inline.addLayout(next_box)
        
        forecast_section.addLayout(forecast_inline)
        row2_layout.addLayout(forecast_section)
        
        # Divider
        div1 = QFrame()
        div1.setFixedWidth(1)
        div1.setStyleSheet("background: #2e2e2e;")
        row2_layout.addWidget(div1)
        
        # --- Performance Section ---
        perf_section = QVBoxLayout()
        perf_section.setSpacing(6)
        perf_title = QLabel("PERFORMANCE")
        perf_title.setStyleSheet("color: #737373; font-size: 9px; text-transform: uppercase; letter-spacing: 1px;")
        perf_section.addWidget(perf_title)
        
        perf_inline = QHBoxLayout()
        perf_inline.setSpacing(16)
        
        # $/Day
        cpd_box = QHBoxLayout()
        cpd_box.setSpacing(5)
        self.perf_cpd_label = QLabel("$/Day:")
        self.perf_cpd_label.setStyleSheet("color: #737373; font-size: 11px;")
        cpd_box.addWidget(self.perf_cpd_label)
        self.perf_cpd_val = QLabel("—")
        self.perf_cpd_val.setStyleSheet("color: #86efac; font-size: 13px; font-weight: 600;")
        cpd_box.addWidget(self.perf_cpd_val)
        perf_inline.addLayout(cpd_box)
        
        # $/SqFt
        sqft_box = QHBoxLayout()
        sqft_box.setSpacing(5)
        self.perf_sqft_label = QLabel("$/SqFt:")
        self.perf_sqft_label.setStyleSheet("color: #737373; font-size: 11px;")
        sqft_box.addWidget(self.perf_sqft_label)
        self.perf_sqft_val = QLabel("—")
        self.perf_sqft_val.setStyleSheet("color: #fafafa; font-size: 13px; font-weight: 600;")
        sqft_box.addWidget(self.perf_sqft_val)
        perf_inline.addLayout(sqft_box)
        
        # Demand %
        demand_box = QHBoxLayout()
        demand_box.setSpacing(5)
        demand_lbl = QLabel("Demand:")
        demand_lbl.setStyleSheet("color: #737373; font-size: 11px;")
        demand_box.addWidget(demand_lbl)
        self.perf_demand = QLabel("—")
        self.perf_demand.setStyleSheet("color: #a855f7; font-size: 13px; font-weight: 600;")
        demand_box.addWidget(self.perf_demand)
        perf_inline.addLayout(demand_box)
        
        perf_section.addLayout(perf_inline)
        row2_layout.addLayout(perf_section)
        
        # Divider
        div2 = QFrame()
        div2.setFixedWidth(1)
        div2.setStyleSheet("background: #2e2e2e;")
        row2_layout.addWidget(div2)
        
        # --- Weather Section ---
        weather_section = QVBoxLayout()
        weather_section.setSpacing(6)
        weather_title = QLabel("WEATHER (MTD)")
        weather_title.setStyleSheet("color: #737373; font-size: 9px; text-transform: uppercase; letter-spacing: 1px;")
        weather_section.addWidget(weather_title)
        
        weather_stats = self.db.get_weather_stats()
        
        weather_inline = QHBoxLayout()
        weather_inline.setSpacing(16)
        
        # High temp
        max_data = weather_stats['max_temp']
        high_box = QHBoxLayout()
        high_box.setSpacing(5)
        self.weather_max_label = QLabel("High:")
        self.weather_max_label.setStyleSheet("color: #737373; font-size: 11px;")
        high_box.addWidget(self.weather_max_label)
        self.weather_max_val = QLabel(f"{max_data['current']:.0f}°F" if max_data['current'] else "—")
        self.weather_max_val.setStyleSheet("color: #ef4444; font-size: 13px; font-weight: 600;")
        high_box.addWidget(self.weather_max_val)
        weather_inline.addLayout(high_box)
        
        # Low temp
        min_data = weather_stats['min_temp']
        low_box = QHBoxLayout()
        low_box.setSpacing(5)
        self.weather_min_label = QLabel("Low:")
        self.weather_min_label.setStyleSheet("color: #737373; font-size: 11px;")
        low_box.addWidget(self.weather_min_label)
        self.weather_min_val = QLabel(f"{min_data['current']:.0f}°F" if min_data['current'] else "—")
        self.weather_min_val.setStyleSheet("color: #86efac; font-size: 13px; font-weight: 600;")
        low_box.addWidget(self.weather_min_val)
        weather_inline.addLayout(low_box)
        
        # Rain
        rain_data = weather_stats['rainfall']
        rain_box = QHBoxLayout()
        rain_box.setSpacing(5)
        self.weather_rain_label = QLabel("Rain:")
        self.weather_rain_label.setStyleSheet("color: #737373; font-size: 11px;")
        rain_box.addWidget(self.weather_rain_label)
        self.weather_rain_val = QLabel(f"{rain_data['current']:.1f}\"" if rain_data['current'] else "—")
        self.weather_rain_val.setStyleSheet("color: #3498db; font-size: 13px; font-weight: 600;")
        rain_box.addWidget(self.weather_rain_val)
        weather_inline.addLayout(rain_box)
        
        weather_section.addLayout(weather_inline)
        row2_layout.addLayout(weather_section)
        
        row2_layout.addStretch()
        
        ribbon_container_layout.addWidget(row2)
        
        layout.addWidget(ribbon_container)
        
        # Store references for backward compatibility with old performance fields
        self.perf_kwh_val = QLabel()  # Hidden - populated in _load_data but not displayed
        self.perf_thm_val = QLabel()
        self.perf_gal_val = QLabel()
        self.perf_ytd_val = self.ytd_value  # Alias
        self.perf_actual_cpd = QLabel()
        self.perf_expected_cpd = QLabel()
        
        # Keep weather label references for tooltip updates
        self.weather_max_label.tooltip_data = max_data
        self.weather_min_label.tooltip_data = min_data
        self.weather_rain_label.tooltip_data = rain_data
        
        # Store prev references for compatibility (not displayed in new layout)
        self.prev_electric = QLabel()
        self.prev_gas = QLabel()
        self.prev_water = QLabel()
        self.meter_water = QLabel()
        
        # Charts row 1 - Use ApexCharts if available, else fallback to QtCharts
        charts_layout = QHBoxLayout()
        charts_layout.setSpacing(16)
        
        # Wrap charts in card-styled frames
        demand_card = QFrame()
        demand_card.setObjectName("chartPanel")
        demand_card_layout = QVBoxLayout(demand_card)
        demand_card_layout.setContentsMargins(8, 8, 8, 8)
        if USE_APEX_CHARTS:
            self.demand_cost_chart = ApexDemandCostChart()
        else:
            self.demand_cost_chart = DemandCostChart()
        demand_card_layout.addWidget(self.demand_cost_chart)
        charts_layout.addWidget(demand_card)
        
        cpd_card = QFrame()
        cpd_card.setObjectName("chartPanel")
        cpd_card_layout = QVBoxLayout(cpd_card)
        cpd_card_layout.setContentsMargins(8, 8, 8, 8)
        if USE_APEX_CHARTS:
            self.cpd_index_chart = ApexCPDIndexChart()
        else:
            self.cpd_index_chart = CPDIndexChart()
        cpd_card_layout.addWidget(self.cpd_index_chart)
        charts_layout.addWidget(cpd_card)
        
        layout.addLayout(charts_layout)
        
        # Charts row 2 - Degree Days and Monthly Demand
        charts_layout2 = QHBoxLayout()
        charts_layout2.setSpacing(16)
        
        degree_card = QFrame()
        degree_card.setObjectName("chartPanel")
        degree_card_layout = QVBoxLayout(degree_card)
        degree_card_layout.setContentsMargins(8, 8, 8, 8)
        if USE_APEX_CHARTS:
            self.degree_days_chart = ApexDegreeDaysChart()
        else:
            self.degree_days_chart = DegreeDaysChart()
        degree_card_layout.addWidget(self.degree_days_chart)
        charts_layout2.addWidget(degree_card)
        
        monthly_card = QFrame()
        monthly_card.setObjectName("chartPanel")
        monthly_card_layout = QVBoxLayout(monthly_card)
        monthly_card_layout.setContentsMargins(8, 8, 8, 8)
        if USE_APEX_CHARTS:
            self.monthly_demand_chart = ApexMonthlyDemandChart()
        else:
            self.monthly_demand_chart = MonthlyDemandChart()
        monthly_card_layout.addWidget(self.monthly_demand_chart)
        charts_layout2.addWidget(monthly_card)
        
        layout.addLayout(charts_layout2)
        
        return dashboard
    
    def _create_weather_view(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Header
        header = QHBoxLayout()
        title = QLabel("🌤️ Weather Data")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch()
        
        update_btn = QPushButton("🔄 Fetch Missing")
        update_btn.clicked.connect(self._update_weather)
        header.addWidget(update_btn)
        
        import_btn = QPushButton("📥 Import File")
        import_btn.clicked.connect(self._import_weather)
        header.addWidget(import_btn)
        
        layout.addLayout(header)
        
        # Status
        self.weather_status = QLabel("Weather data: Loading...")
        self.weather_status.setStyleSheet("color: #737373;")
        layout.addWidget(self.weather_status)
        
        # Charts row
        charts_layout = QHBoxLayout()
        charts_layout.setSpacing(16)
        
        # Daily Weather Demand scatter chart
        self.weather_daily_chart = DailyDemandChart()
        charts_layout.addWidget(self.weather_daily_chart)
        
        # Rain Gauge chart
        self.rain_gauge_chart = RainGaugeChart()
        charts_layout.addWidget(self.rain_gauge_chart)
        
        layout.addLayout(charts_layout)
        
        # Table
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        self.weather_table = QTableWidget()
        self.weather_table.setColumnCount(19)
        self.weather_table.setHorizontalHeaderLabels([
            "Date", 
            "Temp Hi", "Temp Avg", "Temp Lo",
            "Dewpt Hi", "Dewpt Avg", "Dewpt Lo",
            "Humid Hi", "Humid Avg", "Humid Lo",
            "Wind Max", "Wind Avg", "Wind Gust",
            "Press Hi", "Press Lo",
            "Rain", "Heat%", "Cool%", "Demand"
        ])
        self.weather_table.verticalHeader().setVisible(False)
        self.weather_table.setColumnWidth(0, 90)
        for i in range(1, 18):
            self.weather_table.setColumnWidth(i, 65)
        
        scroll.setWidget(self.weather_table)
        layout.addWidget(scroll)
        
        return widget
    
    def _create_status_bar(self, parent):
        status = QFrame()
        status.setObjectName("statusBar")
        status.setFixedHeight(28)
        layout = QHBoxLayout(status)
        layout.setContentsMargins(20, 0, 20, 0)
        
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #737373; font-size: 11px;")
        layout.addWidget(self.status_label)
        layout.addStretch()
        
        # Location label
        location_name = self.db.get_config('location_name') or 'Hendersonville, North Carolina'
        self.status_location = QLabel(f"📍 {location_name}")
        self.status_location.setStyleSheet("color: #737373; font-size: 11px;")
        layout.addWidget(self.status_location)
        
        # Separator
        sep = QLabel("  |  ")
        sep.setStyleSheet("color: #475569; font-size: 11px;")
        layout.addWidget(sep)
        
        self.status_weather = QLabel("Weather: —")
        self.status_weather.setStyleSheet("color: #737373; font-size: 11px;")
        layout.addWidget(self.status_weather)
        
        parent.addWidget(status)
    
    # === Actions ===
    
    def _add_bill(self, bill_type):
        dialog = BillEntryDialog(self.db, bill_type, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_data()
            # Switch to appropriate page
            if bill_type == "electric":
                self.stack.setCurrentIndex(1)
            elif bill_type == "gas":
                self.stack.setCurrentIndex(2)
            elif bill_type == "water":
                self.stack.setCurrentIndex(3)
    
    def _import_pdf(self, utility_type):
        """Open PDF import dialog for the specified utility type."""
        dialog = PDFImportDialog(self.db, utility_type, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_data()
            # Switch to appropriate page
            if utility_type == "electric":
                self.stack.setCurrentIndex(1)
            elif utility_type == "gas":
                self.stack.setCurrentIndex(2)
            elif utility_type == "water":
                self.stack.setCurrentIndex(3)
    
    def _open_settings(self):
        dialog = SettingsDialog(self.db, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_data()
    
    def _show_about(self):
        version = get_current_version()
        QMessageBox.about(self, "About UtilityHQ",
            f"UtilityHQ - Home Utilities Tracker\n\n"
            f"Track your electric, gas, and water bills.\n"
            f"Visualize costs and weather correlations.\n\n"
            f"Version {version}")
    
    def _check_for_updates(self):
        """Check GitHub for updates and offer to install if available."""
        # Show checking dialog
        self.statusBar().showMessage("Checking for updates...")
        QApplication.processEvents()
        
        try:
            update_info = check_for_updates()
            
            if update_info is None:
                QMessageBox.information(self, "No Updates Available",
                    f"You're running the latest version ({get_current_version()}).")
                self.statusBar().showMessage("No updates available", 3000)
                return
            
            # Update available - show details
            version = update_info['version']
            notes = update_info.get('release_notes', 'No release notes available.')
            
            # Truncate long release notes
            if len(notes) > 500:
                notes = notes[:500] + "..."
            
            msg = QMessageBox(self)
            msg.setWindowTitle("Update Available")
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setText(f"A new version is available!\n\n"
                       f"Current version: {get_current_version()}\n"
                       f"New version: {version}")
            msg.setDetailedText(f"Release Notes:\n\n{notes}")
            
            if update_info.get('download_url'):
                msg.setStandardButtons(
                    QMessageBox.StandardButton.Yes | 
                    QMessageBox.StandardButton.No
                )
                msg.button(QMessageBox.StandardButton.Yes).setText("Update Now")
                msg.button(QMessageBox.StandardButton.No).setText("Later")
            else:
                msg.setStandardButtons(QMessageBox.StandardButton.Ok)
                msg.setInformativeText("No executable found in release. Please download manually.")
            
            result = msg.exec()
            
            if result == QMessageBox.StandardButton.Yes and update_info.get('download_url'):
                self._download_and_install_update(update_info)
            
        except Exception as e:
            QMessageBox.warning(self, "Update Check Failed",
                f"Could not check for updates:\n{str(e)}")
            self.statusBar().showMessage("Update check failed", 3000)
    
    def _download_and_install_update(self, update_info: dict):
        """Download and install the update."""
        download_url = update_info['download_url']
        version = update_info['version']
        
        # Create progress dialog
        progress = QProgressDialog(
            f"Downloading UtilityHQ {version}...", 
            "Cancel", 0, 100, self
        )
        progress.setWindowTitle("Downloading Update")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        
        cancelled = False
        
        def progress_callback(downloaded, total):
            nonlocal cancelled
            if progress.wasCanceled():
                cancelled = True
                return
            percent = int((downloaded / total) * 100) if total > 0 else 0
            progress.setValue(percent)
            progress.setLabelText(
                f"Downloading UtilityHQ {version}...\n"
                f"{downloaded // 1024 // 1024} MB / {total // 1024 // 1024} MB"
            )
            QApplication.processEvents()
        
        # Download the update
        downloaded_path = download_update(download_url, progress_callback)
        
        progress.close()
        
        if cancelled:
            self.statusBar().showMessage("Update cancelled", 3000)
            return
        
        if not downloaded_path:
            QMessageBox.critical(self, "Download Failed",
                "Failed to download the update. Please try again later.")
            return
        
        # Confirm restart
        reply = QMessageBox.question(self, "Ready to Install",
            f"Update downloaded successfully!\n\n"
            f"The application will now close and restart to complete the update.\n\n"
            f"Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply != QMessageBox.StandardButton.Yes:
            self.statusBar().showMessage("Update postponed", 3000)
            return
        
        # Apply the update
        if apply_update(downloaded_path):
            self.statusBar().showMessage("Installing update...")
            QApplication.processEvents()
            # Close the application - the update script will restart it
            QTimer.singleShot(500, QApplication.instance().quit)
        else:
            QMessageBox.critical(self, "Update Failed",
                "Failed to apply the update. Please try again or download manually.")
    
    def _update_weather(self):
        weather_source = self.db.get_config('weather_source') or 'open-meteo'
        
        if weather_source == 'open-meteo':
            self._update_weather_openmeteo()
        elif weather_source == 'acurite':
            self._update_weather_acurite()
        else:
            self._update_weather_wu()
    
    def _update_weather_acurite(self):
        """Fetch weather data from MyAcurite."""
        from weather_api import MyAcuriteScraper
        
        email = self.db.get_config('acurite_email')
        password = self.db.get_config('acurite_password')
        
        if not email or not password:
            QMessageBox.warning(self, "Setup Required", 
                "Please configure your MyAcurite credentials in Settings.")
            self._open_settings()
            return
        
        # For now, show info about the feature status
        reply = QMessageBox.question(self, "MyAcurite Scraper",
            "The MyAcurite scraper will attempt to:\n\n"
            "1. Log into your MyAcurite account\n"
            "2. Fetch current weather conditions\n\n"
            "Note: Historical data scraping may require manual CSV export.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            scraper = MyAcuriteScraper(email, password)
            
            if not scraper.login():
                QMessageBox.critical(self, "Login Failed", 
                    "Could not log into MyAcurite.\nPlease check your credentials.")
                return
            
            conditions = scraper.get_current_conditions()
            
            if conditions:
                msg = "Current Conditions:\n\n"
                for key, value in conditions.items():
                    if key != 'readings':
                        msg += f"  {key}: {value}\n"
                QMessageBox.information(self, "Current Conditions", msg)
            else:
                QMessageBox.warning(self, "No Data", 
                    "Could not retrieve current conditions.\n\n"
                    "The scraper may need adjustment for the current\n"
                    "MyAcurite page structure.")
            
            scraper.logout()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"MyAcurite fetch failed:\n{e}")
    
    def _update_weather_openmeteo(self):
        """Fetch weather data from Open-Meteo API."""
        from weather_api import OpenMeteoAPI
        
        lat = float(self.db.get_config('location_latitude') or 35.3187)
        lon = float(self.db.get_config('location_longitude') or -82.4612)
        
        latest = self.db.get_latest_weather_date()
        start_date = (latest + timedelta(days=1)) if latest else date(2024, 1, 1)
        end_date = date.today() - timedelta(days=1)
        
        if start_date > end_date:
            QMessageBox.information(self, "Up to Date", "Weather data is already up to date!")
            return
        
        days_to_fetch = (end_date - start_date).days + 1
        reply = QMessageBox.question(self, "Fetch Weather",
            f"Fetch {days_to_fetch} days of weather data from Open-Meteo?\nFrom: {start_date}\nTo: {end_date}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        self.progress = QProgressDialog("Fetching weather data from Open-Meteo...", "Cancel", 0, days_to_fetch, self)
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.show()
        QApplication.processEvents()
        
        try:
            api = OpenMeteoAPI(latitude=lat, longitude=lon)
            observations = api.get_date_range(start_date, end_date)
            
            # Get demand calculator settings
            demand_settings = self.db.get_demand_settings()
            from weather_api import WeatherDemandCalculator
            calc = WeatherDemandCalculator(
                heating_min=demand_settings['heating_min_temp'],
                heating_max=demand_settings['heating_max_temp'],
                cooling_min=demand_settings['cooling_min_temp'],
                cooling_max=demand_settings['cooling_max_temp']
            )
            
            # Save to database
            from database import WeatherDay
            days_updated = 0
            for i, obs in enumerate(observations):
                self.progress.setValue(i + 1)
                self.progress.setLabelText(f"Saving {obs.date}...")
                QApplication.processEvents()
                
                if self.progress.wasCanceled():
                    break
                
                # Calculate demand
                demands = calc.calculate_demands(obs.temp_high, obs.temp_low)
                
                weather_day = WeatherDay(
                    date=obs.date,
                    temp_high=obs.temp_high,
                    temp_avg=obs.temp_avg,
                    temp_low=obs.temp_low,
                    dewpoint_high=obs.dewpoint_high,
                    dewpoint_avg=obs.dewpoint_avg,
                    dewpoint_low=obs.dewpoint_low,
                    humidity_high=obs.humidity_high,
                    humidity_avg=obs.humidity_avg,
                    humidity_low=obs.humidity_low,
                    wind_max=obs.wind_max,
                    wind_avg=obs.wind_avg,
                    wind_gust=obs.wind_gust,
                    pressure_max=obs.pressure_max,
                    pressure_min=obs.pressure_min,
                    rain_total=obs.rain_total,
                    cooling_demand=demands['cooling_demand'],
                    heating_demand=demands['heating_demand'],
                    max_demand=demands['max_demand']
                )
                self.db.add_weather_day(weather_day)
                days_updated += 1
            
            self.progress.close()
            QMessageBox.information(self, "Complete", f"Updated {days_updated} days of weather data from Open-Meteo!")
            self._load_data()
            self._refresh_weather_table()
            
        except Exception as e:
            self.progress.close()
            QMessageBox.critical(self, "Error", f"Weather update failed: {e}")
    
    def _update_weather_wu(self):
        """Fetch weather data from Weather Underground API."""
        api_key = self.db.get_config('wu_api_key')
        station_id = self.db.get_config('station_id')
        
        if not api_key or not station_id:
            QMessageBox.warning(self, "Setup Required", "Please configure your Weather Underground API key in Settings.")
            self._open_settings()
            return
        
        latest = self.db.get_latest_weather_date()
        start_date = (latest + timedelta(days=1)) if latest else date(2024, 1, 1)
        end_date = date.today() - timedelta(days=1)
        
        if start_date > end_date:
            QMessageBox.information(self, "Up to Date", "Weather data is already up to date!")
            return
        
        days_to_fetch = (end_date - start_date).days + 1
        reply = QMessageBox.question(self, "Fetch Weather",
            f"Fetch {days_to_fetch} days of weather data from Weather Underground?\nFrom: {start_date}\nTo: {end_date}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        self.progress = QProgressDialog("Fetching weather data...", "Cancel", 0, days_to_fetch, self)
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        
        api = WeatherUndergroundAPI(api_key, station_id)
        self.weather_thread = WeatherUpdateThread(api, self.db, start_date, end_date)
        self.weather_thread.progress.connect(lambda c, t, m: (self.progress.setValue(c), self.progress.setLabelText(m)))
        self.weather_thread.finished_update.connect(self._on_weather_finished)
        self.weather_thread.error.connect(lambda e: (self.progress.close(), QMessageBox.critical(self, "Error", f"Weather update failed: {e}")))
        self.progress.canceled.connect(self.weather_thread.cancel)
        self.weather_thread.start()
    
    def _on_weather_finished(self, days_updated):
        self.progress.close()
        QMessageBox.information(self, "Complete", f"Updated {days_updated} days of weather data!")
        self._load_data()
        self._refresh_weather_table()
    
    def _import_weather(self):
        dialog = WeatherImportDialog(self.db, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_data()
            self._refresh_weather_table()
            self.stack.setCurrentIndex(4)
    
    def _load_data(self):
        """Refresh all data."""
        try:
            # Update location in status bar
            location_name = self.db.get_config('location_name') or 'Hendersonville, North Carolina'
            if hasattr(self, 'status_location'):
                self.status_location.setText(f"📍 {location_name}")
            
            # Update dashboard - Utility Costs section (D1 layout)
            # Initialize meter fields with last bill readings
            elec_bill = self.db.get_latest_electric_bill()
            if elec_bill and elec_bill.get('meter_reading'):
                self.meter_electric.setText(f"{int(elec_bill['meter_reading']):,}")
            
            gas_bill = self.db.get_latest_gas_bill()
            if gas_bill and gas_bill.get('meter_reading'):
                self.meter_gas.setText(f"{int(gas_bill['meter_reading']):,}")
            
            # Calculate estimates based on meter readings (updates all cost/usage/per-day fields)
            self._update_meter_estimates()
            
            # Update utility card tooltips with usage statistics
            self._update_utility_card_tooltips()
            
            # Update Row 2 tooltips (Forecast, Performance, Weather)
            self._update_row2_tooltips()
            
            # Update comparison arrows for utility cards
            # Get previous month costs for comparison
            prev_costs = self.db.get_previous_month_costs()
            
            # Electric comparison
            if elec_bill and prev_costs.get('electric', 0) > 0:
                elec_curr = elec_bill.get('total_cost', 0) or 0
                elec_prev = prev_costs.get('electric', 0)
                elec_pct = ((elec_curr - elec_prev) / elec_prev) * 100 if elec_prev > 0 else 0
                if elec_pct < 0:
                    self.elec_change.setText(f"▼ {abs(elec_pct):.1f}% vs last")
                    self.elec_change.setStyleSheet("color: #22c55e; font-size: 10px;")
                elif elec_pct > 0:
                    self.elec_change.setText(f"▲ {elec_pct:.1f}% vs last")
                    self.elec_change.setStyleSheet("color: #ef4444; font-size: 10px;")
                else:
                    self.elec_change.setText("")
            
            # Gas comparison
            if gas_bill and prev_costs.get('gas', 0) > 0:
                gas_curr = gas_bill.get('total_cost', 0) or 0
                gas_prev = prev_costs.get('gas', 0)
                gas_pct = ((gas_curr - gas_prev) / gas_prev) * 100 if gas_prev > 0 else 0
                if gas_pct < 0:
                    self.gas_change.setText(f"▼ {abs(gas_pct):.1f}% vs last")
                    self.gas_change.setStyleSheet("color: #22c55e; font-size: 10px;")
                elif gas_pct > 0:
                    self.gas_change.setText(f"▲ {gas_pct:.1f}% vs last")
                    self.gas_change.setStyleSheet("color: #ef4444; font-size: 10px;")
                else:
                    self.gas_change.setText("")
            
            # Water comparison
            water_bill = self.db.get_latest_water_bill()
            if water_bill and prev_costs.get('water', 0) > 0:
                water_curr = water_bill.get('total_cost', 0) or 0
                water_prev = prev_costs.get('water', 0)
                water_pct = ((water_curr - water_prev) / water_prev) * 100 if water_prev > 0 else 0
                if water_pct < 0:
                    self.water_change.setText(f"▼ {abs(water_pct):.1f}% vs last")
                    self.water_change.setStyleSheet("color: #22c55e; font-size: 10px;")
                elif water_pct > 0:
                    self.water_change.setText(f"▲ {water_pct:.1f}% vs last")
                    self.water_change.setStyleSheet("color: #ef4444; font-size: 10px;")
                else:
                    self.water_change.setText("")
            
            # Total comparison vs previous month
            curr_total = (elec_bill.get('total_cost', 0) if elec_bill else 0) + \
                        (gas_bill.get('total_cost', 0) if gas_bill else 0) + \
                        (water_bill.get('total_cost', 0) if water_bill else 0)
            prev_total = prev_costs.get('electric', 0) + prev_costs.get('gas', 0) + prev_costs.get('water', 0)
            
            if prev_total > 0:
                total_pct = ((curr_total - prev_total) / prev_total) * 100
                if total_pct < 0:
                    self.total_change.setText(f"▼ {abs(total_pct):.1f}% vs last")
                    self.total_change.setStyleSheet("color: #22c55e; font-size: 10px;")
                elif total_pct > 0:
                    self.total_change.setText(f"▲ {total_pct:.1f}% vs last")
                    self.total_change.setStyleSheet("color: #ef4444; font-size: 10px;")
                else:
                    self.total_change.setText("")
            
            # Update YTD and comparison
            perf = self.db.get_current_performance()
            ytd_total = perf.get('ytd_total', 0) or 0
            self.ytd_value.setText(f"${ytd_total:,.2f}")
            
            # YTD comparison with same period last year
            ytd_prev = self.db.get_ytd_previous_year() or 0
            if ytd_prev > 0:
                ytd_pct = ((ytd_total - ytd_prev) / ytd_prev) * 100
                if ytd_pct < 0:
                    self.ytd_change.setText(f"▼ {abs(ytd_pct):.1f}%")
                    self.ytd_change.setStyleSheet("color: #22c55e; font-size: 12px;")
                elif ytd_pct > 0:
                    self.ytd_change.setText(f"▲ {ytd_pct:.1f}%")
                    self.ytd_change.setStyleSheet("color: #ef4444; font-size: 12px;")
                else:
                    self.ytd_change.setText("")
            
            # Update Performance section (Row 2)
            self.perf_cpd_val.setText(f"${perf['cost_day']:.2f}" if perf['cost_day'] else "—")
            self.perf_sqft_val.setText(f"${perf['cost_sqft']:.2f}" if perf['cost_sqft'] else "—")
            
            demand = perf['demand_pct']
            self.perf_demand.setText(f"{demand:.0f}%" if demand else "—")
            
            # Update dashboard - Weather section
            weather_stats = self.db.get_weather_stats()
            max_data = weather_stats['max_temp']
            min_data = weather_stats['min_temp']
            rain_data = weather_stats['rainfall']
            
            self.weather_max_val.setText(f"{max_data['current']:.0f}°F" if max_data['current'] else "—")
            self.weather_min_val.setText(f"{min_data['current']:.0f}°F" if min_data['current'] else "—")
            self.weather_rain_val.setText(f"{rain_data['current']:.1f}\"" if rain_data['current'] else "—")
            
            # Update tooltip data for weather labels
            if hasattr(self.weather_max_label, 'tooltip_data'):
                self.weather_max_label.tooltip_data = max_data
            if hasattr(self.weather_min_label, 'tooltip_data'):
                self.weather_min_label.tooltip_data = min_data
            if hasattr(self.weather_rain_label, 'tooltip_data'):
                self.weather_rain_label.tooltip_data = rain_data
            
            # Update utility pages
            self.electric_page.refresh_data()
            self.gas_page.refresh_data()
            self.water_page.refresh_data()
            
            # Update weather status
            latest = self.db.get_latest_weather_date()
            if latest:
                self.status_weather.setText(f"Weather: through {latest.strftime('%b %d, %Y')}")
                self.weather_status.setText(f"Weather data through: {latest.strftime('%b %d, %Y')}")
            
            # Update dashboard charts - use blended values for current year
            matrix_data = self.db.get_demand_matrix()
            current_year = datetime.now().year
            blended = self.db.get_blended_demand(current_year)
            
            # Replace current year's demand values with blended projections
            for d in matrix_data:
                if d['year'] == current_year:
                    d['avg_cooling'] = blended['blended_cooling']
                    d['avg_heating'] = blended['blended_heating']
                    d['total_demand'] = blended['blended_total']
            
            self.demand_cost_chart.update_data(matrix_data)
            self.cpd_index_chart.update_data(matrix_data)
            
            # Update degree days chart (reuse matrix_data)
            degree_days_data = [
                {
                    'year': d['year'],
                    'cooling_days': d['cooling_days'],
                    'heating_days': d['heating_days'],
                    'economy_days': d['econ_days']
                }
                for d in matrix_data
            ]
            self.degree_days_chart.update_data(degree_days_data)
            
            # Update monthly demand chart - pass full data for last 5 years
            monthly_data = self.db.get_demand_monthly()
            self.monthly_demand_chart.update_data(monthly_data)
            
            # Update demand page
            self.demand_page.refresh_data()
            
            self._refresh_weather_table()
            
        except Exception as e:
            print(f"Error loading data: {e}")
            import traceback
            traceback.print_exc()
    
    def _refresh_weather_table(self):
        # Update Weather page charts
        if hasattr(self, 'weather_daily_chart'):
            daily_data = self.db.get_demand_daily()
            current_year = datetime.now().year
            previous_year = current_year - 1
            chart_data = {
                'years': daily_data['years'],
                'data': daily_data['data'],
                'current_year': current_year,
                'previous_year': previous_year,
            }
            self.weather_daily_chart.update_data(chart_data)
        
        if hasattr(self, 'rain_gauge_chart'):
            rain_data = self.db.get_monthly_rainfall()
            self.rain_gauge_chart.update_data(rain_data)
        
        # Show all weather data
        start_date = date(2000, 1, 1)
        end_date = date.today()
        
        weather_data = self.db.get_weather_range(start_date, end_date)
        self.weather_table.setRowCount(len(weather_data))
        
        for row, w in enumerate(reversed(weather_data)):
            col = 0
            self.weather_table.setItem(row, col, QTableWidgetItem(str(w['date']))); col += 1
            self.weather_table.setItem(row, col, QTableWidgetItem(f"{w['temp_high']:.0f}°" if w.get('temp_high') else "—")); col += 1
            self.weather_table.setItem(row, col, QTableWidgetItem(f"{w['temp_avg']:.0f}°" if w.get('temp_avg') else "—")); col += 1
            self.weather_table.setItem(row, col, QTableWidgetItem(f"{w['temp_low']:.0f}°" if w.get('temp_low') else "—")); col += 1
            self.weather_table.setItem(row, col, QTableWidgetItem(f"{w['dewpoint_high']:.0f}°" if w.get('dewpoint_high') else "—")); col += 1
            self.weather_table.setItem(row, col, QTableWidgetItem(f"{w['dewpoint_avg']:.0f}°" if w.get('dewpoint_avg') else "—")); col += 1
            self.weather_table.setItem(row, col, QTableWidgetItem(f"{w['dewpoint_low']:.0f}°" if w.get('dewpoint_low') else "—")); col += 1
            self.weather_table.setItem(row, col, QTableWidgetItem(f"{w['humidity_high']:.0f}%" if w.get('humidity_high') else "—")); col += 1
            self.weather_table.setItem(row, col, QTableWidgetItem(f"{w['humidity_avg']:.0f}%" if w.get('humidity_avg') else "—")); col += 1
            self.weather_table.setItem(row, col, QTableWidgetItem(f"{w['humidity_low']:.0f}%" if w.get('humidity_low') else "—")); col += 1
            self.weather_table.setItem(row, col, QTableWidgetItem(f"{w['wind_max']:.0f}" if w.get('wind_max') else "—")); col += 1
            self.weather_table.setItem(row, col, QTableWidgetItem(f"{w['wind_avg']:.0f}" if w.get('wind_avg') else "—")); col += 1
            self.weather_table.setItem(row, col, QTableWidgetItem(f"{w['wind_gust']:.0f}" if w.get('wind_gust') else "—")); col += 1
            self.weather_table.setItem(row, col, QTableWidgetItem(f"{w['pressure_max']:.2f}" if w.get('pressure_max') else "—")); col += 1
            self.weather_table.setItem(row, col, QTableWidgetItem(f"{w['pressure_min']:.2f}" if w.get('pressure_min') else "—")); col += 1
            self.weather_table.setItem(row, col, QTableWidgetItem(f"{w['rain_total']:.2f}\"" if w.get('rain_total') else "0\"")); col += 1
            
            heat = abs(w.get('heating_demand') or 0)
            cool = w.get('cooling_demand') or 0
            self.weather_table.setItem(row, col, QTableWidgetItem(f"{heat*100:.0f}%" if heat else "—")); col += 1
            self.weather_table.setItem(row, col, QTableWidgetItem(f"{cool*100:.0f}%" if cool else "—")); col += 1
            
            if heat > cool:
                self.weather_table.setItem(row, col, QTableWidgetItem(f"H:{heat*100:.0f}%"))
            elif cool > 0:
                self.weather_table.setItem(row, col, QTableWidgetItem(f"C:{cool*100:.0f}%"))
            else:
                self.weather_table.setItem(row, col, QTableWidgetItem("—"))
    
    # ==================== Dashboard Methods ====================
    
    def _update_meter_estimates(self):
        """Update estimated costs and usage based on current meter readings."""
        elec_est = 0
        gas_est = 0
        elec_usage = 0
        gas_usage = 0
        days_in_period = 30  # Default
        
        # Electric estimate
        try:
            elec_reading = float(self.meter_electric.text().replace(',', '') or 0)
            elec_bill = self.db.get_latest_electric_bill()
            if elec_bill and elec_reading > 0:
                last_reading = elec_bill.get('meter_reading', 0) or 0
                usage = elec_bill.get('usage_kwh', 0) or 0
                total = elec_bill.get('total_cost', 0) or 0
                rate = total / usage if usage > 0 else 0.12
                
                elec_usage = elec_reading - last_reading
                elec_est = elec_usage * rate if elec_usage > 0 else 0
                
                # Calculate days in billing period for per-day
                if elec_bill.get('billing_period_start') and elec_bill.get('billing_period_end'):
                    from datetime import datetime
                    try:
                        start = datetime.strptime(str(elec_bill['billing_period_start']), '%Y-%m-%d').date()
                        end = datetime.strptime(str(elec_bill['billing_period_end']), '%Y-%m-%d').date()
                        days_in_period = (end - start).days or 30
                    except:
                        days_in_period = 30
        except ValueError:
            pass
        
        self.cost_electric.setText(f"${elec_est:,.2f}")
        self.usage_electric.setText(f"{elec_usage:,.0f} kWh" if elec_usage > 0 else "0 kWh")
        
        # Electric per day
        elec_per_day = elec_usage / days_in_period if elec_usage > 0 and days_in_period > 0 else 0
        self.elec_per_day.setText(f"{elec_per_day:.1f} kWh")
        
        # Gas estimate
        try:
            gas_reading = float(self.meter_gas.text().replace(',', '') or 0)
            gas_bill = self.db.get_latest_gas_bill()
            if gas_bill and gas_reading > 0:
                last_reading = gas_bill.get('meter_reading', 0) or 0
                therms = gas_bill.get('therms', 0) or 0
                total = gas_bill.get('total_cost', 0) or 0
                rate = total / therms if therms > 0 else 1.20
                
                # CCF to therms conversion (approx 1.03)
                gas_usage = (gas_reading - last_reading) * 1.03
                gas_est = gas_usage * rate if gas_usage > 0 else 0
                
                # Days for gas
                if gas_bill.get('billing_period_start') and gas_bill.get('billing_period_end'):
                    try:
                        start = datetime.strptime(str(gas_bill['billing_period_start']), '%Y-%m-%d').date()
                        end = datetime.strptime(str(gas_bill['billing_period_end']), '%Y-%m-%d').date()
                        days_in_period = (end - start).days or 30
                    except:
                        days_in_period = 30
        except ValueError:
            pass
        
        self.cost_gas.setText(f"${gas_est:,.2f}")
        self.usage_gas.setText(f"{gas_usage:,.0f} Thm" if gas_usage > 0 else "0 Thm")
        
        # Gas per day
        gas_per_day = gas_usage / days_in_period if gas_usage > 0 and days_in_period > 0 else 0
        self.gas_per_day.setText(f"{gas_per_day:.1f} Thm")
        
        # Water stays as last bill (no meter input)
        water_bill = self.db.get_latest_water_bill()
        water_cost = water_bill.get('total_cost', 0) if water_bill else 0
        water_usage = water_bill.get('usage_gallons', 0) if water_bill else 0
        
        self.cost_water.setText(f"${water_cost:,.2f}")
        self.usage_water.setText(f"{water_usage/1000:.1f}k gal" if water_usage >= 1000 else f"{water_usage:.0f} gal")
        
        # Water per day
        water_days = 30  # Default
        if water_bill and water_bill.get('billing_period_start') and water_bill.get('billing_period_end'):
            try:
                start = datetime.strptime(str(water_bill['billing_period_start']), '%Y-%m-%d').date()
                end = datetime.strptime(str(water_bill['billing_period_end']), '%Y-%m-%d').date()
                water_days = (end - start).days or 30
            except:
                water_days = 30
        water_per_day = water_usage / water_days if water_usage > 0 and water_days > 0 else 0
        self.water_per_day.setText(f"{water_per_day:.0f} gal")
        
        # Update total
        total = elec_est + gas_est + water_cost
        self.cost_total.setText(f"${total:,.2f}")
    
    def _update_utility_card_tooltips(self):
        """Update tooltips on utility cards with usage statistics."""
        def format_usage(val, unit):
            if unit == 'gal' and val >= 1000:
                return f"{val/1000:.1f}k {unit}"
            elif val >= 1000:
                return f"{val:,.0f} {unit}"
            else:
                return f"{val:.0f} {unit}"
        
        def format_per_day(val, unit):
            if unit == 'gal':
                return f"{val:.0f} {unit}"
            else:
                return f"{val:.1f} {unit}"
        
        # Electric card tooltips
        if hasattr(self, 'elec_usage_zone'):
            stats = self.db.get_usage_stats('electric')
            tooltip = (
                f"⚡ Electric Usage Statistics\n"
                f"─────────────────────\n"
                f"Last Month:  {format_usage(stats['last_month'], stats['unit'])}\n"
                f"Average:       {format_usage(stats['average'], stats['unit'])}\n"
                f"Min:              {format_usage(stats['min'], stats['unit'])}\n"
                f"Max:             {format_usage(stats['max'], stats['unit'])}"
            )
            self.elec_usage_zone.setInstantTooltip(tooltip)
        
        if hasattr(self, 'elec_perday_zone'):
            perday_stats = self.db.get_usage_per_day_stats('kwh_day')
            tooltip = (
                f"⚡ Electric Per Day Statistics\n"
                f"─────────────────────\n"
                f"Current:   {format_per_day(perday_stats.get('current', 0), perday_stats['unit'])}\n"
                f"Average:  {format_per_day(perday_stats['average'], perday_stats['unit'])}\n"
                f"Min:          {format_per_day(perday_stats['min'], perday_stats['unit'])}\n"
                f"Max:         {format_per_day(perday_stats['max'], perday_stats['unit'])}"
            )
            self.elec_perday_zone.setInstantTooltip(tooltip)
        
        # Gas card tooltips
        if hasattr(self, 'gas_usage_zone'):
            stats = self.db.get_usage_stats('gas')
            tooltip = (
                f"🔥 Gas Usage Statistics\n"
                f"─────────────────────\n"
                f"Last Month:  {format_usage(stats['last_month'], stats['unit'])}\n"
                f"Average:       {format_usage(stats['average'], stats['unit'])}\n"
                f"Min:              {format_usage(stats['min'], stats['unit'])}\n"
                f"Max:             {format_usage(stats['max'], stats['unit'])}"
            )
            self.gas_usage_zone.setInstantTooltip(tooltip)
        
        if hasattr(self, 'gas_perday_zone'):
            perday_stats = self.db.get_usage_per_day_stats('thm_day')
            tooltip = (
                f"🔥 Gas Per Day Statistics\n"
                f"─────────────────────\n"
                f"Current:   {format_per_day(perday_stats.get('current', 0), perday_stats['unit'])}\n"
                f"Average:  {format_per_day(perday_stats['average'], perday_stats['unit'])}\n"
                f"Min:          {format_per_day(perday_stats['min'], perday_stats['unit'])}\n"
                f"Max:         {format_per_day(perday_stats['max'], perday_stats['unit'])}"
            )
            self.gas_perday_zone.setInstantTooltip(tooltip)
        
        # Water card tooltips
        if hasattr(self, 'water_usage_zone'):
            stats = self.db.get_usage_stats('water')
            tooltip = (
                f"💧 Water Usage Statistics\n"
                f"─────────────────────\n"
                f"Last Month:  {format_usage(stats['last_month'], stats['unit'])}\n"
                f"Average:       {format_usage(stats['average'], stats['unit'])}\n"
                f"Min:              {format_usage(stats['min'], stats['unit'])}\n"
                f"Max:             {format_usage(stats['max'], stats['unit'])}"
            )
            self.water_usage_zone.setInstantTooltip(tooltip)
        
        if hasattr(self, 'water_perday_zone'):
            perday_stats = self.db.get_usage_per_day_stats('gal_day')
            tooltip = (
                f"💧 Water Per Day Statistics\n"
                f"─────────────────────\n"
                f"Current:   {format_per_day(perday_stats.get('current', 0), perday_stats['unit'])}\n"
                f"Average:  {format_per_day(perday_stats['average'], perday_stats['unit'])}\n"
                f"Min:          {format_per_day(perday_stats['min'], perday_stats['unit'])}\n"
                f"Max:         {format_per_day(perday_stats['max'], perday_stats['unit'])}"
            )
            self.water_perday_zone.setInstantTooltip(tooltip)
    
    def _update_row2_tooltips(self):
        """Update tooltips for Forecast, Performance, and Weather items in Row 2."""
        # Get forecast data for tooltips
        forecast_data = self.db.get_monthly_cost_forecast()
        
        # Forecast tooltips (Last Year, Min, Max, Avg)
        for attr, key in [('forecast_prev_val', 'previous_month'), 
                          ('forecast_curr_val', 'this_month'), 
                          ('forecast_next_val', 'next_month')]:
            if hasattr(self, attr):
                data = forecast_data[key]
                tooltip = (
                    f"📊 {data['label']} Statistics\n"
                    f"─────────────────────\n"
                    f"Last Year:  ${data.get('last_yr', 0):,.0f}\n"
                    f"Min:           ${data.get('min', 0):,.0f}\n"
                    f"Max:          ${data.get('max', 0):,.0f}\n"
                    f"Avg:           ${data.get('avg', 0):,.0f}"
                )
                getattr(self, attr).setToolTip(tooltip)
        
        # Performance tooltips ($/Day and $/SqFt only - Min, Max, Avg)
        perf_stats = self.db.get_cpd_sqft_tooltip_stats()
        
        if hasattr(self, 'perf_cpd_val'):
            cpd = perf_stats['cpd']
            tooltip = (
                f"💰 $/Day Statistics\n"
                f"─────────────────────\n"
                f"Min:   ${cpd['min']:.2f}\n"
                f"Max:  ${cpd['max']:.2f}\n"
                f"Avg:   ${cpd['avg']:.2f}"
            )
            self.perf_cpd_val.setToolTip(tooltip)
        
        if hasattr(self, 'perf_sqft_val'):
            sqft = perf_stats['sqft']
            tooltip = (
                f"📐 $/SqFt Statistics\n"
                f"─────────────────────\n"
                f"Min:   ${sqft['min']:.2f}\n"
                f"Max:  ${sqft['max']:.2f}\n"
                f"Avg:   ${sqft['avg']:.2f}"
            )
            self.perf_sqft_val.setToolTip(tooltip)
        
        # Weather tooltips (Last Year, Min, Max, Avg)
        weather_stats = self.db.get_weather_stats()
        
        if hasattr(self, 'weather_max_val'):
            data = weather_stats['max_temp']
            tooltip = (
                f"🌡️ High Temp Statistics\n"
                f"─────────────────────\n"
                f"Last Year:  {data['last_year']:.0f}°F\n"
                f"Min:           {data['average']:.0f}°F\n"
                f"Max:          {data['all_time']:.0f}°F\n"
                f"Avg:           {data['average']:.0f}°F"
            )
            self.weather_max_val.setToolTip(tooltip)
        
        if hasattr(self, 'weather_min_val'):
            data = weather_stats['min_temp']
            tooltip = (
                f"❄️ Low Temp Statistics\n"
                f"─────────────────────\n"
                f"Last Year:  {data['last_year']:.0f}°F\n"
                f"Min:           {data['all_time']:.0f}°F\n"
                f"Max:          {data['average']:.0f}°F\n"
                f"Avg:           {data['average']:.0f}°F"
            )
            self.weather_min_val.setToolTip(tooltip)
        
        if hasattr(self, 'weather_rain_val'):
            data = weather_stats['rainfall']
            tooltip = (
                f"🌧️ Rainfall Statistics\n"
                f"─────────────────────\n"
                f"Last Year:  {data['last_year']:.1f}\"\n"
                f"Min:           {data['average']:.1f}\"\n"
                f"Max:          {data['all_time']:.1f}\"\n"
                f"Avg:           {data['average']:.1f}\""
            )
            self.weather_rain_val.setToolTip(tooltip)

    def _create_usage_popup(self, utility_type: str) -> QFrame:
        """Create a floating popup with usage statistics."""
        stats = self.db.get_usage_stats(utility_type)
        
        icons = {'electric': '⚡', 'gas': '🔥', 'water': '💧'}
        titles = {'electric': 'Electric', 'gas': 'Gas', 'water': 'Water'}
        colors = {'electric': '#f39c12', 'gas': '#e74c3c', 'water': '#3498db'}
        
        # Create frameless popup
        popup = QFrame(self, Qt.WindowType.ToolTip)
        popup.setObjectName("usagePopup")
        popup.setStyleSheet(f"""
            QFrame#usagePopup {{ 
                background: #121212; 
                border: 1px solid {colors[utility_type]}; 
                border-radius: 8px; 
            }}
            QFrame#usagePopup QLabel {{ 
                color: #a3a3a3; 
                background: transparent;
                border: none;
            }}
            QFrame#usagePopup QFrame {{
                border: none;
            }}
        """)
        
        layout = QVBoxLayout(popup)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        
        # Title - muted gray
        title = QLabel(f"{icons[utility_type]} {titles[utility_type]} Usage")
        title.setStyleSheet("font-size: 13px; color: #a3a3a3;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Separator - thin gray line
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #4a5568; border: none;")
        layout.addWidget(sep)
        
        # Stats
        unit = stats['unit']
        
        def format_val(val, unit):
            if unit == 'gal' and val >= 1000:
                return f"{val/1000:.1f}k {unit}"
            elif val >= 1000:
                return f"{val:,.0f} {unit}"
            else:
                return f"{val:.0f} {unit}"
        
        rows = [
            ("Last Month:", stats['last_month']),
            ("Average:", stats['average']),
            ("Min:", stats['min']),
            ("Max:", stats['max']),
        ]
        
        grid = QGridLayout()
        grid.setSpacing(4)
        grid.setColumnMinimumWidth(0, 80)
        grid.setColumnMinimumWidth(1, 85)
        
        for i, (label, value) in enumerate(rows):
            lbl = QLabel(label)
            lbl.setStyleSheet("color: #737373; font-size: 12px;")
            grid.addWidget(lbl, i, 0)
            
            val_lbl = QLabel(format_val(value, unit))
            val_lbl.setStyleSheet("color: #a3a3a3; font-size: 12px;")
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            grid.addWidget(val_lbl, i, 1)
        
        layout.addLayout(grid)
        popup.adjustSize()
        
        return popup

    def _create_performance_popup(self, stat_type: str) -> QFrame:
        """Create a floating popup with performance statistics."""
        # Check if it's a utility type or performance type
        if stat_type in ['electric', 'gas', 'water']:
            return self._create_usage_popup(stat_type)
        
        # Usage per day stats (show Last Month)
        usage_types = ['kwh_day', 'thm_day', 'gal_day']
        # Cost stats (show Last Year)
        cost_types = ['cost_day', 'cost_sqft', 'ytd_total']
        
        if stat_type in usage_types:
            stats = self.db.get_usage_per_day_stats(stat_type)
            first_row_label = "Last Month:"
            first_row_value = stats['last_month']
        elif stat_type in cost_types:
            stats = self.db.get_cost_stats(stat_type)
            first_row_label = "Last Year:"
            first_row_value = stats['last_year']
        else:
            return QFrame()  # Unknown type
        
        titles = {
            'kwh_day': 'kWh/Day',
            'thm_day': 'Therms/Day',
            'gal_day': 'Gallons/Day',
            'cost_day': 'Cost/Day',
            'cost_sqft': '$/SqFt',
            'ytd_total': 'YTD Total',
        }
        colors = {
            'kwh_day': '#f39c12',
            'thm_day': '#e74c3c',
            'gal_day': '#3498db',
            'cost_day': '#86efac',
            'cost_sqft': '#86efac',
            'ytd_total': '#86efac',
        }
        
        color = colors.get(stat_type, '#86efac')
        title_text = titles.get(stat_type, stat_type)
        
        # Create frameless popup
        popup = QFrame(self, Qt.WindowType.ToolTip)
        popup.setObjectName("usagePopup")
        popup.setStyleSheet(f"""
            QFrame#usagePopup {{ 
                background: #121212; 
                border: 1px solid {color}; 
                border-radius: 8px; 
            }}
            QFrame#usagePopup QLabel {{ 
                color: #a3a3a3; 
                background: transparent;
                border: none;
            }}
            QFrame#usagePopup QFrame {{
                border: none;
            }}
        """)
        
        layout = QVBoxLayout(popup)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        
        # Title - muted gray
        title = QLabel(f"{title_text} Stats")
        title.setStyleSheet("font-size: 13px; color: #a3a3a3;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Separator - thin gray line
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #4a5568; border: none;")
        layout.addWidget(sep)
        
        # Stats
        unit = stats['unit']
        
        def format_val(val, unit):
            if unit in ['$', '$/day', '$/sqft']:
                if val >= 1000:
                    return f"${val:,.0f}"
                else:
                    return f"${val:.2f}"
            elif unit == 'gal':
                if val >= 1000:
                    return f"{val/1000:.1f}k gal"
                else:
                    return f"{val:.0f} gal"
            elif unit in ['kWh', 'thm']:
                if val >= 100:
                    return f"{val:,.0f} {unit}"
                else:
                    return f"{val:.1f} {unit}"
            else:
                if val >= 100:
                    return f"{val:,.0f}"
                else:
                    return f"{val:.1f}"
        
        rows = [
            (first_row_label, first_row_value),
            ("Average:", stats['average']),
            ("Min:", stats['min']),
            ("Max:", stats['max']),
        ]
        
        grid = QGridLayout()
        grid.setSpacing(4)
        grid.setColumnMinimumWidth(0, 80)
        grid.setColumnMinimumWidth(1, 85)
        
        for i, (label, value) in enumerate(rows):
            lbl = QLabel(label)
            lbl.setStyleSheet("color: #737373; font-size: 12px;")
            grid.addWidget(lbl, i, 0)
            
            val_lbl = QLabel(format_val(value, unit))
            val_lbl.setStyleSheet("color: #a3a3a3; font-size: 12px;")
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            grid.addWidget(val_lbl, i, 1)
        
        layout.addLayout(grid)
        popup.adjustSize()
        
        return popup

    def _create_weather_popup(self, stat_type: str, data: Dict) -> QFrame:
        """Create a floating popup with weather statistics."""
        titles = {
            'weather_max': 'Max Temp',
            'weather_min': 'Min Temp',
            'weather_rain': 'Rainfall',
        }
        colors = {
            'weather_max': '#ef4444',
            'weather_min': '#86efac',
            'weather_rain': '#3498db',
        }
        
        title_text = titles.get(stat_type, 'Weather')
        color = colors.get(stat_type, '#22c55e')
        
        # Create frameless popup
        popup = QFrame(self, Qt.WindowType.ToolTip)
        popup.setObjectName("usagePopup")
        popup.setStyleSheet(f"""
            QFrame#usagePopup {{ 
                background: #121212; 
                border: 1px solid {color}; 
                border-radius: 8px; 
            }}
            QFrame#usagePopup QLabel {{ 
                color: #a3a3a3; 
                background: transparent;
                border: none;
            }}
            QFrame#usagePopup QFrame {{
                border: none;
            }}
        """)
        
        layout = QVBoxLayout(popup)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        
        # Title - muted gray
        title = QLabel(f"{title_text} Stats")
        title.setStyleSheet("font-size: 13px; color: #a3a3a3;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Separator - thin gray line
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #4a5568; border: none;")
        layout.addWidget(sep)
        
        # Format value based on type
        def format_val(val, stat_type):
            if stat_type == 'weather_rain':
                return f"{val:.1f}\""
            else:
                return f"{val:.0f}°F"
        
        rows = [
            ("Last Year:", data.get('last_year', 0)),
            ("All Time:", data.get('all_time', 0)),
            ("Average:", data.get('average', 0)),
        ]
        
        grid = QGridLayout()
        grid.setSpacing(4)
        grid.setColumnMinimumWidth(0, 80)
        grid.setColumnMinimumWidth(1, 85)
        
        for i, (label, value) in enumerate(rows):
            lbl = QLabel(label)
            lbl.setStyleSheet("color: #737373; font-size: 12px;")
            grid.addWidget(lbl, i, 0)
            
            val_lbl = QLabel(format_val(value, stat_type))
            val_lbl.setStyleSheet("color: #a3a3a3; font-size: 12px;")
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            grid.addWidget(val_lbl, i, 1)
        
        layout.addLayout(grid)
        popup.adjustSize()
        
        return popup

    def _create_forecast_popup(self, data: Dict) -> QFrame:
        """Create a floating popup with cost forecast statistics."""
        # Create frameless popup
        popup = QFrame(self, Qt.WindowType.ToolTip)
        popup.setObjectName("usagePopup")
        popup.setStyleSheet(f"""
            QFrame#usagePopup {{ 
                background: #121212; 
                border: 1px solid #22c55e; 
                border-radius: 8px; 
            }}
            QFrame#usagePopup QLabel {{ 
                color: #a3a3a3; 
                background: transparent;
                border: none;
            }}
            QFrame#usagePopup QFrame {{
                border: none;
            }}
        """)
        
        layout = QVBoxLayout(popup)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        
        # Title - muted gray
        title = QLabel(f"{data['label']} Stats")
        title.setStyleSheet("font-size: 13px; color: #a3a3a3;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Separator - thin gray line
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #4a5568; border: none;")
        layout.addWidget(sep)
        
        # Stats
        def format_cost(val):
            if val >= 1000:
                return f"${val:,.0f}"
            else:
                return f"${val:.2f}"
        
        rows = [
            ("Last Year:", data.get('last_yr', 0)),
            ("Average:", data.get('avg', 0)),
            ("Min:", data.get('min', 0)),
            ("Max:", data.get('max', 0)),
        ]
        
        grid = QGridLayout()
        grid.setSpacing(4)
        grid.setColumnMinimumWidth(0, 80)
        grid.setColumnMinimumWidth(1, 85)
        
        for i, (label, value) in enumerate(rows):
            lbl = QLabel(label)
            lbl.setStyleSheet("color: #737373; font-size: 12px;")
            grid.addWidget(lbl, i, 0)
            
            val_lbl = QLabel(format_cost(value))
            val_lbl.setStyleSheet("color: #a3a3a3; font-size: 12px;")
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            grid.addWidget(val_lbl, i, 1)
        
        layout.addLayout(grid)
        popup.adjustSize()
        
        return popup


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("UtilityHQ")
    db_path = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).parent.parent / "data" / "utilities.db")
    window = MainWindow(db_path)
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
