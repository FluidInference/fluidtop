import time
import click
import asyncio
from collections import deque
from typing import Optional

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import ProgressBar, Static, Label, Button
from textual_plotext import PlotextPlot
import plotext as plt
import os
from datetime import datetime
from .utils import run_powermetrics_process, parse_powermetrics, get_soc_info, get_ram_metrics_dict


class MetricGauge(Static):
    """Custom gauge widget to display metrics with progress bar and text"""
    
    def __init__(self, title: str = "", max_value: int = 100, **kwargs):
        super().__init__(**kwargs)
        self.title = title
        self.max_value = max_value
        self._value = 0
        
    def compose(self) -> ComposeResult:
        yield Label(self.title, id="gauge-title")
        yield ProgressBar(total=self.max_value, show_percentage=True, id="gauge-progress")
    
    def update_value(self, value: int, title: Optional[str] = None):
        self._value = value
        if title:
            self.title = title
        self.query_one("#gauge-title", Label).update(self.title)
        self.query_one("#gauge-progress", ProgressBar).update(progress=value)


class PowerChart(PlotextPlot):
    """Custom chart widget for power consumption data"""
    
    def __init__(self, title: str = "", interval: int = 1, color: str = "cyan", **kwargs):
        super().__init__(**kwargs)
        self.title = title
        self.interval = interval
        self.plot_color = color
        # Store up to 3600 data points (1 hour at 1 second intervals)
        self.data_points = deque(maxlen=3600)
        self.timestamps = deque(maxlen=3600)
        self.start_time = time.time()
        
    def on_mount(self):
        self.plt.title(self.title)
        self.plt.xlabel("Time (minutes ago)")
        self.plt.ylabel("Power (%)")
        # Apply custom colors before setting auto_theme
        # Set auto_theme to False to prevent overriding custom colors
        self.auto_theme = False
        self.plt.plotsize(None, None)  # Auto-size
        # Set Y-axis decimal precision
        self.plt.yfrequency(0)  # This will auto-determine the frequency
    
    def add_data(self, value: float):
        current_time = time.time()
        self.data_points.append(value)
        self.timestamps.append(current_time)
        self.plt.clear_data()
        
        # Always set up axes, even with no data
        # Set y-axis ticks with one decimal, starting from 0
        y_min = 0  # Always start from 0
        if len(self.data_points) > 0:
            y_max = max(self.data_points) if max(self.data_points) > 0 else 1.0
        else:
            y_max = 1.0  # Default max when no data
            
        # Create 5 evenly spaced y-ticks starting from 0
        y_ticks = []
        y_labels = []
        for i in range(5):
            val = y_min + (y_max - y_min) * i / 4
            y_ticks.append(val)
            y_labels.append(f"{val:.1f}")
        self.plt.yticks(y_ticks, y_labels)
        # Set y-axis limits to ensure it starts at 0
        self.plt.ylim(0, y_max * 1.1)  # Add 10% padding at the top
        
        # Set x-axis to show 0.0 to 0.6 minutes ago by default
        default_x_ticks = [0.0, -0.1, -0.2, -0.3, -0.4, -0.5, -0.6]
        default_x_labels = ["0.0", "0.1", "0.2", "0.3", "0.4", "0.5", "0.6"]
        
        if len(self.data_points) > 1:
            # Calculate time differences from now in minutes
            time_diffs = [(current_time - t) / 60 for t in self.timestamps]
            # Reverse so most recent is on the right
            time_diffs = [-td for td in time_diffs]
            
            # Use RGB color for plotting
            self.plt.plot(time_diffs, list(self.data_points), marker="braille", color=self.plot_color)
            
            # Set x-axis labels - show actual time values
            if len(time_diffs) >= 5:
                # Show 5 evenly spaced labels
                indices = [0, len(time_diffs)//4, len(time_diffs)//2, 3*len(time_diffs)//4, len(time_diffs)-1]
                ticks = [time_diffs[i] for i in indices]
                labels = [f"{abs(t):.1f}" for t in ticks]
                self.plt.xticks(ticks, labels)
            else:
                # For fewer points, show all
                labels = [f"{abs(t):.1f}" for t in time_diffs]
                self.plt.xticks(time_diffs, labels)
        else:
            # No data yet, show default x-axis
            self.plt.xticks(default_x_ticks, default_x_labels)
            self.plt.xlim(-0.6, 0)
        
        self.refresh()
    
    def update_title(self, title: str):
        self.title = title
        self.plt.title(title)
        self.refresh()


class UsageChart(PlotextPlot):
    """Custom chart widget for usage percentage data"""
    
    def __init__(self, title: str = "", ylabel: str = "Usage (%)", interval: int = 1, color: str = "cyan", **kwargs):
        super().__init__(**kwargs)
        self.title = title
        self.ylabel = ylabel
        self.interval = interval
        self.plot_color = color
        # Store up to 3600 data points (1 hour at 1 second intervals)
        self.data_points = deque(maxlen=3600)
        self.timestamps = deque(maxlen=3600)
        self.start_time = time.time()
        
    def on_mount(self):
        self.plt.title(self.title)
        self.plt.xlabel("Time (minutes ago)")
        self.plt.ylabel(self.ylabel)
        self.plt.ylim(0, 100)
        # Apply custom colors before setting auto_theme
        # Set auto_theme to False to prevent overriding custom colors
        self.auto_theme = False
        self.plt.plotsize(None, None)  # Auto-size
        # Set Y-axis decimal precision
        self.plt.yfrequency(0)  # This will auto-determine the frequency
    
    def add_data(self, value: float):
        current_time = time.time()
        self.data_points.append(value)
        self.timestamps.append(current_time)
        self.plt.clear_data()
        
        # Always set up axes, even with no data
        # Set y-axis ticks with one decimal for usage (0-100)
        y_ticks = [0, 25, 50, 75, 100]
        y_labels = [f"{val:.1f}" for val in y_ticks]
        self.plt.yticks(y_ticks, y_labels)
        
        # Set x-axis to show 0.0 to 0.6 minutes ago by default
        default_x_ticks = [0.0, -0.1, -0.2, -0.3, -0.4, -0.5, -0.6]
        default_x_labels = ["0.0", "0.1", "0.2", "0.3", "0.4", "0.5", "0.6"]
        
        if len(self.data_points) > 1:
            # Calculate time differences from now in minutes
            time_diffs = [(current_time - t) / 60 for t in self.timestamps]
            # Reverse so most recent is on the right
            time_diffs = [-td for td in time_diffs]
            
            # Use RGB color for plotting
            self.plt.plot(time_diffs, list(self.data_points), marker="braille", color=self.plot_color)
            
            # Set x-axis labels - show actual time values
            if len(time_diffs) >= 5:
                # Show 5 evenly spaced labels
                indices = [0, len(time_diffs)//4, len(time_diffs)//2, 3*len(time_diffs)//4, len(time_diffs)-1]
                ticks = [time_diffs[i] for i in indices]
                labels = [f"{abs(t):.1f}" for t in ticks]
                self.plt.xticks(ticks, labels)
            else:
                # For fewer points, show all
                labels = [f"{abs(t):.1f}" for t in time_diffs]
                self.plt.xticks(time_diffs, labels)
        else:
            # No data yet, show default x-axis
            self.plt.xticks(default_x_ticks, default_x_labels)
            self.plt.xlim(-0.6, 0)
        
        self.refresh()
    
    def update_title(self, title: str):
        self.title = title
        self.plt.title(title)
        self.refresh()


class MultiLineChart(PlotextPlot):
    """Custom chart widget for displaying multiple data series on the same chart"""
    
    def __init__(self, title: str = "", ylabel: str = "Value", interval: int = 1, color: str = "cyan", **kwargs):
        super().__init__(**kwargs)
        self.title = title
        self.ylabel = ylabel
        self.interval = interval
        self.plot_color = color
        # Store up to 3600 data points (1 hour at 1 second intervals) for each series
        self.data_series = {}  # Will store {'series_name': {'data': deque, 'timestamps': deque}}
        self.start_time = time.time()
        
    def on_mount(self):
        self.plt.title(self.title)
        self.plt.xlabel("Time (minutes ago)")
        self.plt.ylabel(self.ylabel)
        # Apply custom colors before setting auto_theme
        # Set auto_theme to False to prevent overriding custom colors
        self.auto_theme = False
        self.plt.plotsize(None, None)  # Auto-size
        # Set Y-axis decimal precision
        self.plt.yfrequency(0)  # This will auto-determine the frequency
    
    def add_data(self, series_name: str, value: float, y_axis: str = "left", color: str | None = None):
        """Add data point to a specific series"""
        current_time = time.time()
        
        # Initialize series if it doesn't exist
        if series_name not in self.data_series:
            # Use provided color or default to the chart's color
            series_color = color if color else self.plot_color
            self.data_series[series_name] = {
                'data': deque(maxlen=3600),
                'timestamps': deque(maxlen=3600),
                'y_axis': y_axis,
                'color': series_color
            }
        
        self.data_series[series_name]['data'].append(value)
        self.data_series[series_name]['timestamps'].append(current_time)
        
        self.plt.clear_data()
        
        # Determine y-axis range based on all data
        all_data_left = []
        all_data_right = []
        
        for name, series in self.data_series.items():
            if series['y_axis'] == 'left':
                all_data_left.extend(list(series['data']))
            else:
                all_data_right.extend(list(series['data']))
        
        # Set up left y-axis (usage percentage)
        if all_data_left:
            y_min_left = 0
            y_max_left = max(max(all_data_left), 100)  # At least 100 for percentage
            y_ticks_left = [0, 25, 50, 75, 100] if y_max_left <= 100 else [0, y_max_left/4, y_max_left/2, 3*y_max_left/4, y_max_left]
            y_labels_left = [f"{val:.1f}" for val in y_ticks_left]
            self.plt.yticks(y_ticks_left, y_labels_left)
            self.plt.ylim(0, y_max_left * 1.1)
        
        # Set x-axis to show 0.0 to 0.6 minutes ago by default
        default_x_ticks = [0.0, -0.1, -0.2, -0.3, -0.4, -0.5, -0.6]
        default_x_labels = ["0.0", "0.1", "0.2", "0.3", "0.4", "0.5", "0.6"]
        
        # Plot all series
        has_data = False
        for name, series in self.data_series.items():
            if len(series['data']) > 1:
                has_data = True
                # Calculate time differences from now in minutes
                time_diffs = [(current_time - t) / 60 for t in series['timestamps']]
                # Reverse so most recent is on the right
                time_diffs = [-td for td in time_diffs]
                
                # Use series-specific color
                self.plt.plot(time_diffs, list(series['data']), marker="braille", color=series['color'], label=name)
        
        if has_data:
            # Use the most recent series' timestamps for x-axis
            most_recent_series = max(self.data_series.values(), key=lambda s: len(s['data']))
            time_diffs = [(current_time - t) / 60 for t in most_recent_series['timestamps']]
            time_diffs = [-td for td in time_diffs]
            
            # Set x-axis labels - show actual time values
            if len(time_diffs) >= 5:
                # Show 5 evenly spaced labels
                indices = [0, len(time_diffs)//4, len(time_diffs)//2, 3*len(time_diffs)//4, len(time_diffs)-1]
                ticks = [time_diffs[i] for i in indices]
                labels = [f"{abs(t):.1f}" for t in ticks]
                self.plt.xticks(ticks, labels)
            else:
                # For fewer points, show all
                labels = [f"{abs(t):.1f}" for t in time_diffs]
                self.plt.xticks(time_diffs, labels)
        else:
            # No data yet, show default x-axis
            self.plt.xticks(default_x_ticks, default_x_labels)
            self.plt.xlim(-0.6, 0)
        
        self.refresh()
    
    def update_title(self, title: str):
        self.title = title
        self.plt.title(title)
        self.refresh()


class FluidTopApp(App):
    """Main FluidTop application using Textual"""
    
    # CSS is set dynamically in _apply_theme method
    
    def __init__(self, interval: int, theme: str, avg: int, max_count: int):
        self.interval = interval
        # Store theme temporarily, don't assign to self.theme yet
        theme_value = theme
        self.theme_colors = self._get_theme_colors(theme_value)
        # Apply theme BEFORE calling super().__init__()
        self._apply_theme(theme_value)
        
        super().__init__()
        
        # Store theme value in a regular instance variable (not reactive)
        self._theme_name = theme_value
        self.avg = avg
        self.max_count = max_count
        
        # Initialize metrics storage
        # No longer tracking averages or peaks
        
        # Total energy consumption tracking (in watt-seconds) for each component
        self.total_energy_consumed = 0
        self.cpu_energy_consumed = 0
        self.gpu_energy_consumed = 0
        self.ane_energy_consumed = 0
        
        # Powermetrics process
        self.powermetrics_process = None
        self.timecode = None
        self.last_timestamp = 0
        self.count = 0
        
        # SoC info
        self.soc_info_dict = get_soc_info()
        
    def _get_theme_colors(self, theme: str) -> str:
        """Get the color mapping for the theme using plotext-compatible color names"""
        # Using plotext-compatible color names instead of hex colors
        theme_chart_colors = {
            'default': 'gray',
            'dark': 'white', 
            'blue': 'blue',
            'green': 'green',
            'red': 'red',
            'purple': 'magenta', 
            'orange': 'yellow',
            'cyan': 'cyan',
            'magenta': 'magenta'
        }
        return theme_chart_colors.get(theme, 'cyan')
        
    def _apply_theme(self, theme: str):
        """Apply color theme to the application"""
        # Using shadcn-inspired hex colors for better design consistency
        themes = {
            'default': {'primary': '#18181b', 'accent': '#71717a'},  # zinc-900, zinc-500
            'dark': {'primary': '#fafafa', 'accent': '#a1a1aa'},     # zinc-50, zinc-400
            'blue': {'primary': '#1e40af', 'accent': '#3b82f6'},     # blue-800, blue-500
            'green': {'primary': '#166534', 'accent': '#22c55e'},    # green-800, green-500
            'red': {'primary': '#dc2626', 'accent': '#ef4444'},      # red-600, red-500
            'purple': {'primary': '#7c3aed', 'accent': '#a855f7'},   # violet-600, purple-500
            'orange': {'primary': '#FD8161', 'accent': '#f97316'},   # orange-600, orange-500
            'cyan': {'primary': '#5DAF8D', 'accent': '#06b6d4'},     # cyan-600, cyan-500
            'magenta': {'primary': '#db2777', 'accent': '#ec4899'}   # pink-600, pink-500
        }
        
        if theme in themes:
            colors = themes[theme]
            # Update CSS with theme colors and reduced padding
            self.CSS = f"""
    Screen {{
        layers: base;
        overflow: hidden hidden;
    }}
    
    Screen > Container {{
        width: 100%;
        height: 100%;
        overflow: hidden hidden;
    }}
    
    MetricGauge {{
        height: 3;
        margin: 0;
        border: solid {colors['primary']};
    }}
    
    PowerChart {{
        height: 1fr;
        margin: 0;
        border: none;
        background: $surface;
    }}
    
    PowerChart PlotextPlot {{
        background: $surface;
    }}
    
    UsageChart {{
        height: 1fr;
        margin: 0;
        border: none;
        background: $surface;
    }}
    
    UsageChart PlotextPlot {{
        background: $surface;
    }}
    
    MultiLineChart {{
        height: 1fr;
        margin: 0;
        border: none;
        background: $surface;
    }}
    
    MultiLineChart PlotextPlot {{
        background: $surface;
    }}
    
    #usage-section {{
        border: solid {colors['primary']};
        padding: 0;
        height: 1fr;
        background: $surface;
    }}
    
    #power-section {{
        border: solid {colors['primary']};
        padding: 0;
        height: 1fr;
        background: $surface;
    }}
    
    #power-section Horizontal {{
        margin-bottom: 1;
    }}
    
    #power-section Horizontal:last-child {{
        margin-bottom: 0;
    }}
    
    #controls-section {{
        border: solid {colors['accent']};
        padding: 0 1;
        height: 3;
        background: $surface;
    }}
    
    #controls-content {{
        layout: horizontal;
        align: center middle;
        width: 100%;
        height: 100%;
    }}
    
    #system-info-label {{
        width: 2fr;
        text-align: left;
        color: $text;
        padding: 0 1;
    }}
    
    #controls-buttons {{
        width: 1fr;
        layout: horizontal;
        align: right middle;
        height: 100%;
    }}
    
    #timestamp-label {{
        width: auto;
        text-align: right;
        color: $text;
        padding: 0 1;
    }}
    
    Button {{
        margin: 0 1;
        min-width: 12;
        height: 1;
        background: {colors['accent']};
        color: white;
        text-style: bold;
        border: none;
    }}
    
    Button:hover {{
        background: {colors['primary']};
        color: white;
    }}
    
    Button:focus {{
        text-style: bold reverse;
    }}
    
    Label {{
        color: $text;
        margin: 0;
        padding: 0;
    }}
    
    #controls-title {{
        text-style: bold;
        margin: 0;
        padding: 0;
    }}
    """
        
    def compose(self) -> ComposeResult:
        """Compose the UI layout"""
        
        # Controls section with power and system info at the top
        with Vertical(id="controls-section"):
            with Horizontal(id="controls-content"):
                # System info on the left
                yield Label("Initializing...", id="system-info-label")
                # Timestamp and buttons on the right
                with Horizontal(id="controls-buttons"):
                    yield Label("", id="timestamp-label")
                    yield Button("📸 Screenshot", id="screenshot-btn", variant="primary")
                    yield Button("❌ Quit", id="quit-btn", variant="error")
        
        # Usage Charts section
        with Vertical(id="usage-section"):
            with Horizontal():
                yield MultiLineChart("CPU Usage (E-CPU & P-CPU)", ylabel="Usage (%)", interval=self.interval, color=self.theme_colors, id="cpu-combined-chart")
                yield UsageChart("GPU", interval=self.interval, color=self.theme_colors, id="gpu-usage-chart")
                yield UsageChart("RAM Usage", ylabel="RAM (%)", interval=self.interval, color=self.theme_colors, id="ram-usage-chart")
        
        # Power section
        with Vertical(id="power-section"):
            with Horizontal():
                yield PowerChart("CPU Power", interval=self.interval, color=self.theme_colors, id="cpu-power-chart")
                yield PowerChart("GPU Power", interval=self.interval, color=self.theme_colors, id="gpu-power-chart")
                yield PowerChart("ANE Power", interval=self.interval, color=self.theme_colors, id="ane-power-chart")
    
    async def on_mount(self):
        """Initialize the application on mount"""
        # Start powermetrics process
        self.timecode = str(int(time.time()))
        self.powermetrics_process = run_powermetrics_process(
            self.timecode, interval=self.interval * 1000
        )
        
        # Wait for first reading
        await self.wait_for_first_reading()
        
        # Start update timer
        self.set_interval(self.interval, self.update_metrics)
        
        # Update system info label
        system_info = f"{self.soc_info_dict['name']} ({self.soc_info_dict['e_core_count']}E+{self.soc_info_dict['p_core_count']}P+{self.soc_info_dict['gpu_core_count']}GPU)"
        self.query_one("#system-info-label", Label).update(system_info)
        
        # Initialize timestamp
        await self.update_timestamp()
    
    async def wait_for_first_reading(self):
        """Wait for the first powermetrics reading"""
        while True:
            ready = parse_powermetrics(timecode=self.timecode)
            if ready:
                self.last_timestamp = ready[-1]
                break
            await asyncio.sleep(0.1)
    
    async def update_metrics(self):
        """Update all metrics - called by timer"""
        try:
            # Handle max_count restart
            if self.max_count > 0 and self.count >= self.max_count:
                self.count = 0
                self.powermetrics_process.terminate()
                self.timecode = str(int(time.time()))
                self.powermetrics_process = run_powermetrics_process(
                    self.timecode, interval=self.interval * 1000
                )
            self.count += 1
            
            # Parse powermetrics data
            ready = parse_powermetrics(timecode=self.timecode)
            if not ready:
                return
                
            cpu_metrics_dict, gpu_metrics_dict, thermal_pressure, _, timestamp = ready
            
            if timestamp <= self.last_timestamp:
                return
                
            self.last_timestamp = timestamp
            
            # CPU, GPU, and ANE gauge widgets have been removed
            
            # Update usage charts
            await self.update_usage_charts(cpu_metrics_dict, gpu_metrics_dict)
            
            # Update power charts
            await self.update_power_charts(cpu_metrics_dict, thermal_pressure)
            
            # Update timestamp
            await self.update_timestamp()
            
        except Exception as e:
            # Handle errors gracefully
            pass
    
    async def update_usage_charts(self, cpu_metrics_dict, gpu_metrics_dict):
        """Update usage chart metrics"""
        # Update combined CPU chart (E-CPU and P-CPU)
        cpu_combined_chart = self.query_one("#cpu-combined-chart", MultiLineChart)
        
        # Get E-CPU and P-CPU usage data
        e_cpu_usage = cpu_metrics_dict['E-Cluster_active']
        p_cpu_usage = cpu_metrics_dict['P-Cluster_active']
        
        # Add both CPU types to the same chart with different colors
        cpu_combined_chart.add_data(f"E-CPU ({self.soc_info_dict['e_core_count']} cores)", e_cpu_usage, y_axis="left", color="blue")
        cpu_combined_chart.add_data(f"P-CPU ({self.soc_info_dict['p_core_count']} cores)", p_cpu_usage, y_axis="left", color="red")
        
        # Update title to show both CPU types
        combined_title = f"E-CPU: {e_cpu_usage}% | P-CPU: {p_cpu_usage}%"
        cpu_combined_chart.update_title(combined_title)
        
        # Update GPU usage chart
        gpu_chart = self.query_one("#gpu-usage-chart", UsageChart)
        gpu_usage = gpu_metrics_dict['active']
        gpu_title = f"GPU ({self.soc_info_dict['gpu_core_count']} cores): {gpu_usage}%"
        gpu_chart.update_title(gpu_title)
        gpu_chart.add_data(gpu_usage)
        
        # Update RAM usage chart with swap information
        ram_metrics_dict = get_ram_metrics_dict()
        ram_chart = self.query_one("#ram-usage-chart", UsageChart)
        ram_usage_percent = 100 - ram_metrics_dict["free_percent"]  # Convert from free to used percentage
        
        # Include swap information in the title
        if ram_metrics_dict["swap_total_GB"] < 0.1:
            ram_title = f"RAM: {ram_usage_percent:.1f}% ({ram_metrics_dict['used_GB']:.1f}/{ram_metrics_dict['total_GB']:.1f}GB) - swap inactive"
        else:
            ram_title = f"RAM: {ram_usage_percent:.1f}% ({ram_metrics_dict['used_GB']:.1f}/{ram_metrics_dict['total_GB']:.1f}GB) - swap: {ram_metrics_dict['swap_used_GB']:.1f}/{ram_metrics_dict['swap_total_GB']:.1f}GB"
        
        ram_chart.update_title(ram_title)
        ram_chart.add_data(ram_usage_percent)
    
    async def update_power_charts(self, cpu_metrics_dict, thermal_pressure):
        """Update power chart metrics"""
        cpu_max_power = self.soc_info_dict["cpu_max_power"]
        gpu_max_power = self.soc_info_dict["gpu_max_power"]
        ane_max_power = 8.0
        
        # Calculate power values (already in watts from powermetrics)
        package_power_W = cpu_metrics_dict["package_W"]
        cpu_power_W = cpu_metrics_dict["cpu_W"]
        gpu_power_W = cpu_metrics_dict["gpu_W"]
        ane_power_W = cpu_metrics_dict["ane_W"]
        
        # Update energy consumption for each component (watts * seconds = watt-seconds)
        self.total_energy_consumed += package_power_W * self.interval
        self.cpu_energy_consumed += cpu_power_W * self.interval
        self.gpu_energy_consumed += gpu_power_W * self.interval
        self.ane_energy_consumed += ane_power_W * self.interval
        
        # Helper function to format energy display
        def format_energy(energy_ws):
            energy_wh = energy_ws / 3600  # Convert watt-seconds to watt-hours
            if energy_wh < 1.0:
                return f"{energy_wh * 1000:.1f}mWh"
            elif energy_wh < 1000:
                return f"{energy_wh:.2f}Wh"
            else:
                return f"{energy_wh / 1000:.3f}kWh"
        
        # Update charts
        cpu_power_chart = self.query_one("#cpu-power-chart", PowerChart)
        cpu_power_percent = int(cpu_power_W / cpu_max_power * 100)
        cpu_energy_display = format_energy(self.cpu_energy_consumed)
        cpu_title = f"CPU: {cpu_power_W:.2f}W (total: {cpu_energy_display})"
        cpu_power_chart.update_title(cpu_title)
        cpu_power_chart.add_data(cpu_power_percent)
        
        gpu_power_chart = self.query_one("#gpu-power-chart", PowerChart)
        gpu_power_percent = int(gpu_power_W / gpu_max_power * 100)
        gpu_energy_display = format_energy(self.gpu_energy_consumed)
        gpu_title = f"GPU: {gpu_power_W:.2f}W (total: {gpu_energy_display})"
        gpu_power_chart.update_title(gpu_title)
        gpu_power_chart.add_data(gpu_power_percent)
        
        ane_power_chart = self.query_one("#ane-power-chart", PowerChart)
        ane_power_percent = int(ane_power_W / ane_max_power * 100)
        ane_energy_display = format_energy(self.ane_energy_consumed)
        ane_title = f"ANE: {ane_power_W:.2f}W (total: {ane_energy_display})"
        ane_power_chart.update_title(ane_title)
        ane_power_chart.add_data(ane_power_percent)
        
        # Update system info label with total power and thermal info
        thermal_throttle = "no" if thermal_pressure == "Nominal" else "yes"
        total_energy_display = format_energy(self.total_energy_consumed)
        system_info = f"{self.soc_info_dict['name']} ({self.soc_info_dict['e_core_count']}E+{self.soc_info_dict['p_core_count']}P+{self.soc_info_dict['gpu_core_count']}GPU) | Total: {package_power_W:.1f}W ({total_energy_display}) | Throttle: {thermal_throttle}"
        self.query_one("#system-info-label", Label).update(system_info)
    
    async def update_timestamp(self):
        """Update the timestamp display"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        timestamp_label = self.query_one("#timestamp-label", Label)
        timestamp_label.update(f"📅 {current_time}")
    
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events"""
        if event.button.id == "screenshot-btn":
            await self.take_screenshot()
        elif event.button.id == "quit-btn":
            await self.quit_application()
    
    async def take_screenshot(self) -> None:
        """Take a screenshot of the current display"""
        try:
            # Create screenshots directory if it doesn't exist
            screenshots_dir = os.path.expanduser("~/fluidtop_screenshots")
            os.makedirs(screenshots_dir, exist_ok=True)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = os.path.join(screenshots_dir, f"fluidtop_{timestamp}.svg")
            
            # Save screenshot as SVG (textual's built-in screenshot format)
            self.save_screenshot(screenshot_path)
            
            # Show success notification
            self.notify(f"Screenshot saved to {screenshot_path}", title="Screenshot Success", severity="information")
            
        except Exception as e:
            # Show error notification
            self.notify(f"Screenshot failed: {str(e)}", title="Screenshot Error", severity="error")
    
    async def quit_application(self) -> None:
        """Gracefully quit the application"""
        self.exit()
    
    def on_unmount(self):
        """Clean up when app is closed"""
        if self.powermetrics_process:
            try:
                self.powermetrics_process.terminate()
            except:
                pass

@click.command()
@click.option('--interval', type=int, default=1,
              help='Display interval and sampling interval for powermetrics (seconds)')
@click.option('--theme', type=click.Choice(['default', 'dark', 'blue', 'green', 'red', 'purple', 'orange', 'cyan', 'magenta']), default='cyan',
              help='Choose color theme')
@click.option('--avg', type=int, default=30,
              help='Interval for averaged values (seconds)')
@click.option('--max_count', type=int, default=0,
              help='Max show count to restart powermetrics')
def main(interval, theme, avg, max_count):
    """fluidtop: Performance monitoring CLI tool for Apple Silicon"""
    return _main_logic(interval, theme, avg, max_count)


def _main_logic(interval, theme, avg, max_count):
    """Main logic using Textual app"""
    print("\nFLUIDTOP - Performance monitoring CLI tool for Apple Silicon")
    print("Get help at `https://github.com/FluidInference/fluidtop`")
    print("P.S. You are recommended to run FLUIDTOP with `sudo fluidtop`\n")
    
    # Create and run the Textual app
    app = FluidTopApp(interval, theme, avg, max_count)
    try:
        app.run()
    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        # Cleanup is handled in app.on_unmount()
        pass
    
    return app.powermetrics_process


if __name__ == "__main__":
    powermetrics_process = main()
    try:
        powermetrics_process.terminate()
        print("Successfully terminated powermetrics process")
    except Exception as e:
        print(e)
        powermetrics_process.terminate()
        print("Successfully terminated powermetrics process")
