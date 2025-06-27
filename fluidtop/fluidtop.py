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
    
    def __init__(self, title: str = "", interval: int = 1, color: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.title = title
        self.interval = interval
        self.color = color or "cyan"  # Default color
        # Store up to 3600 data points (1 hour at 1 second intervals)
        self.data_points = deque(maxlen=3600)
        self.timestamps = deque(maxlen=3600)
        self.start_time = time.time()
        
    def on_mount(self):
        self.plt.title(self.title)
        self.plt.xlabel("Time (minutes ago)")
        self.plt.ylabel("Power (%)")
        # Set color theme
        self.plt.theme("pro")  # Use a theme that works well with custom colors
        self.plt.plotsize(None, None)  # Auto-size
    
    def add_data(self, value: float):
        current_time = time.time()
        self.data_points.append(value)
        self.timestamps.append(current_time)
        self.plt.clear_data()
        
        if len(self.data_points) > 1:
            # Calculate time differences from now in minutes
            time_diffs = [(current_time - t) / 60 for t in self.timestamps]
            # Reverse so most recent is on the right
            time_diffs = [-td for td in time_diffs]
            
            self.plt.plot(time_diffs, list(self.data_points), marker="braille", color=self.color)
            
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
        
        self.refresh()
    
    def update_title(self, title: str):
        self.title = title
        self.plt.title(title)
        self.refresh()


class UsageChart(PlotextPlot):
    """Custom chart widget for usage percentage data"""
    
    def __init__(self, title: str = "", ylabel: str = "Usage (%)", interval: int = 1, color: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.title = title
        self.ylabel = ylabel
        self.interval = interval
        self.color = color or "cyan"  # Default color
        # Store up to 3600 data points (1 hour at 1 second intervals)
        self.data_points = deque(maxlen=3600)
        self.timestamps = deque(maxlen=3600)
        self.start_time = time.time()
        
    def on_mount(self):
        self.plt.title(self.title)
        self.plt.xlabel("Time (minutes ago)")
        self.plt.ylabel(self.ylabel)
        self.plt.ylim(0, 100)
        # Set color theme
        self.plt.theme("pro")  # Use a theme that works well with custom colors
        self.plt.plotsize(None, None)  # Auto-size
    
    def add_data(self, value: float):
        current_time = time.time()
        self.data_points.append(value)
        self.timestamps.append(current_time)
        self.plt.clear_data()
        
        if len(self.data_points) > 1:
            # Calculate time differences from now in minutes
            time_diffs = [(current_time - t) / 60 for t in self.timestamps]
            # Reverse so most recent is on the right
            time_diffs = [-td for td in time_diffs]
            
            self.plt.plot(time_diffs, list(self.data_points), marker="braille", color=self.color)
            
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
        
        self.refresh()
    
    def update_title(self, title: str):
        self.title = title
        self.plt.title(title)
        self.refresh()


class FluidTopApp(App):
    """Main FluidTop application using Textual"""
    
    # CSS is set dynamically in _apply_theme method
    
    def __init__(self, interval: int, theme: str, avg: int, max_count: int):
        super().__init__()
        self.interval = interval
        self.theme = theme
        self.theme_colors = self._get_theme_colors(theme)
        # Apply theme
        self._apply_theme(theme)
        self.avg = avg
        self.max_count = max_count
        
        # Initialize metrics storage
        self.avg_package_power_list = deque([], maxlen=int(avg / interval))
        self.avg_cpu_power_list = deque([], maxlen=int(avg / interval))
        self.avg_gpu_power_list = deque([], maxlen=int(avg / interval))
        
        # Peak power tracking
        self.cpu_peak_power = 0
        self.gpu_peak_power = 0
        self.package_peak_power = 0
        
        # Powermetrics process
        self.powermetrics_process = None
        self.timecode = None
        self.last_timestamp = 0
        self.count = 0
        
        # SoC info
        self.soc_info_dict = get_soc_info()
        
    def _get_theme_colors(self, theme: str) -> dict:
        """Get the color mapping for the theme"""
        theme_chart_colors = {
            'default': 'white',
            'blue': 'blue',
            'green': 'green',
            'red': 'red',
            'purple': 'magenta',
            'orange': 'yellow',  # plotext doesn't have orange, use yellow
            'cyan': 'cyan',
            'magenta': 'magenta'
        }
        return {'chart': theme_chart_colors.get(theme, 'cyan')}
        
    def _apply_theme(self, theme: str):
        """Apply color theme to the application"""
        themes = {
            'default': {'primary': '#e2e8f0', 'accent': '#94a3b8'},  # slate-200/400
            'blue': {'primary': '#3b82f6', 'accent': '#2563eb'},     # blue-500/600
            'green': {'primary': '#22c55e', 'accent': '#16a34a'},    # green-500/600
            'red': {'primary': '#ef4444', 'accent': '#dc2626'},      # red-500/600
            'purple': {'primary': '#a855f7', 'accent': '#9333ea'},   # purple-500/600
            'orange': {'primary': '#f97316', 'accent': '#ea580c'},   # orange-500/600
            'cyan': {'primary': '#06b6d4', 'accent': '#0891b2'},     # cyan-500/600
            'magenta': {'primary': '#ec4899', 'accent': '#db2777'}   # pink-500/600
        }
        
        if theme in themes:
            colors = themes[theme]
            # Update CSS with theme colors and increased chart heights
            self.CSS = f"""
    MetricGauge {{
        height: 3;
        margin: 1;
        border: solid {colors['primary']};
    }}
    
    PowerChart {{
        height: 20;
        margin: 1;
        border: solid {colors['primary']};
        background: $surface;
    }}
    
    PowerChart PlotextPlot {{
        background: $surface;
    }}
    
    UsageChart {{
        height: 20;
        margin: 1;
        border: solid {colors['primary']};
        background: $surface;
    }}
    
    UsageChart PlotextPlot {{
        background: $surface;
    }}
    
    #usage-section {{
        border: solid {colors['primary']};
        padding: 1;
        background: $surface;
    }}
    
    #power-section {{
        border: solid {colors['primary']};
        padding: 1;
        background: $surface;
    }}
    
    #controls-section {{
        border: solid {colors['accent']};
        padding: 1;
        height: 7;
        background: $surface;
    }}
    
    #controls-buttons {{
        align: right middle;
    }}
    
    Button {{
        margin: 0 1;
        min-width: 12;
        height: 3;
        border: none;
        text-align: center;
    }}
    
    Label {{
        color: {colors['primary']};
    }}
    
    #usage-title, #power-title, #controls-title {{
        text-style: bold;
        margin-bottom: 1;
    }}
    """
        
    def compose(self) -> ComposeResult:
        """Compose the UI layout"""
        
        # Usage Charts section
        with Vertical(id="usage-section"):
            yield Label("Device Info", id="usage-title")
            with Horizontal():
                yield UsageChart("E-CPU Usage", interval=self.interval, color=self.theme_colors['chart'], id="e-cpu-usage-chart")
                yield UsageChart("GPU Usage", interval=self.interval, color=self.theme_colors['chart'], id="gpu-usage-chart")
                yield UsageChart("RAM Usage", ylabel="RAM (%)", interval=self.interval, color=self.theme_colors['chart'], id="ram-usage-chart")
        
        # Power section
        with Vertical(id="power-section"):
            yield Label("Power Charts", id="power-title")
            with Horizontal():
                yield PowerChart("CPU Power", interval=self.interval, color=self.theme_colors['chart'], id="cpu-power-chart")
                yield PowerChart("GPU Power", interval=self.interval, color=self.theme_colors['chart'], id="gpu-power-chart")
                yield PowerChart("Total Power", interval=self.interval, color=self.theme_colors['chart'], id="total-power-chart")
        
        # Controls section
        with Vertical(id="controls-section"):
            yield Label("Controls", id="controls-title")
            with Horizontal(id="controls-buttons"):
                yield Button("📸 Screenshot", id="screenshot-btn", variant="primary")
                yield Button("❌ Quit", id="quit-btn", variant="error")
    
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
        
        # Update usage title with device info
        cpu_title = f"{self.soc_info_dict['name']} (cores: {self.soc_info_dict['e_core_count']}E+{self.soc_info_dict['p_core_count']}P+{self.soc_info_dict['gpu_core_count']}GPU)"
        self.query_one("#usage-title", Label).update(cpu_title)
    
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
                
            cpu_metrics_dict, gpu_metrics_dict, thermal_pressure, bandwidth_metrics, timestamp = ready
            
            if timestamp <= self.last_timestamp:
                return
                
            self.last_timestamp = timestamp
            
            # CPU, GPU, and ANE gauge widgets have been removed
            
            # Update usage charts
            await self.update_usage_charts(cpu_metrics_dict, gpu_metrics_dict)
            
            # Update power charts
            await self.update_power_charts(cpu_metrics_dict, thermal_pressure)
            
        except Exception as e:
            # Handle errors gracefully
            pass
    

    
    async def update_usage_charts(self, cpu_metrics_dict, gpu_metrics_dict):
        """Update usage chart metrics"""
        # Update E-CPU usage chart
        e_cpu_chart = self.query_one("#e-cpu-usage-chart", UsageChart)
        e_cpu_usage = cpu_metrics_dict['E-Cluster_active']
        e_cpu_freq = cpu_metrics_dict['E-Cluster_freq_Mhz']
        e_cpu_title = f"E-CPU: {e_cpu_usage}% @ {e_cpu_freq} MHz"
        e_cpu_chart.update_title(e_cpu_title)
        e_cpu_chart.add_data(e_cpu_usage)
        
        # Update GPU usage chart
        gpu_chart = self.query_one("#gpu-usage-chart", UsageChart)
        gpu_usage = gpu_metrics_dict['active']
        gpu_freq = gpu_metrics_dict['freq_MHz']
        gpu_title = f"GPU: {gpu_usage}% @ {gpu_freq} MHz"
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
        
        # Calculate power values
        package_power_W = cpu_metrics_dict["package_W"] / self.interval
        cpu_power_W = cpu_metrics_dict["cpu_W"] / self.interval
        gpu_power_W = cpu_metrics_dict["gpu_W"] / self.interval
        
        # Update peak tracking
        if package_power_W > self.package_peak_power:
            self.package_peak_power = package_power_W
        if cpu_power_W > self.cpu_peak_power:
            self.cpu_peak_power = cpu_power_W
        if gpu_power_W > self.gpu_peak_power:
            self.gpu_peak_power = gpu_power_W
        
        # Update averages
        self.avg_package_power_list.append(package_power_W)
        self.avg_cpu_power_list.append(cpu_power_W)
        self.avg_gpu_power_list.append(gpu_power_W)
        
        avg_package_power = sum(self.avg_package_power_list) / len(self.avg_package_power_list)
        avg_cpu_power = sum(self.avg_cpu_power_list) / len(self.avg_cpu_power_list)
        avg_gpu_power = sum(self.avg_gpu_power_list) / len(self.avg_gpu_power_list)
        
        # Update charts
        cpu_power_chart = self.query_one("#cpu-power-chart", PowerChart)
        cpu_power_percent = int(cpu_power_W / cpu_max_power * 100)
        cpu_title = f"CPU: {cpu_power_W:.2f}W (avg: {avg_cpu_power:.2f}W peak: {self.cpu_peak_power:.2f}W)"
        cpu_power_chart.update_title(cpu_title)
        cpu_power_chart.add_data(cpu_power_percent)
        
        gpu_power_chart = self.query_one("#gpu-power-chart", PowerChart)
        gpu_power_percent = int(gpu_power_W / gpu_max_power * 100)
        gpu_title = f"GPU: {gpu_power_W:.2f}W (avg: {avg_gpu_power:.2f}W peak: {self.gpu_peak_power:.2f}W)"
        gpu_power_chart.update_title(gpu_title)
        gpu_power_chart.add_data(gpu_power_percent)
        
        total_power_chart = self.query_one("#total-power-chart", PowerChart)
        total_max_power = cpu_max_power + gpu_max_power + ane_max_power
        total_power_percent = int(package_power_W / total_max_power * 100)
        thermal_throttle = "no" if thermal_pressure == "Nominal" else "yes"
        total_title = f"Total: {package_power_W:.2f}W (avg: {avg_package_power:.2f}W peak: {self.package_peak_power:.2f}W) throttle: {thermal_throttle}"
        total_power_chart.update_title(total_title)
        total_power_chart.add_data(total_power_percent)
        
        # Update power section title
        power_title = f"CPU+GPU+ANE Power: {package_power_W:.2f}W (avg: {avg_package_power:.2f}W peak: {self.package_peak_power:.2f}W) throttle: {thermal_throttle}"
        self.query_one("#power-title", Label).update(power_title)
    
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
            
            # Update controls title to show success
            controls_title = self.query_one("#controls-title", Label)
            original_text = "Controls"
            controls_title.update(f"✅ Screenshot saved to {screenshot_path}")
            
            # Reset title after 3 seconds
            self.set_timer(3.0, lambda: controls_title.update(original_text))
            
        except Exception as e:
            # Update controls title to show error
            controls_title = self.query_one("#controls-title", Label)
            original_text = "Controls"
            controls_title.update(f"❌ Screenshot failed: {str(e)}")
            
            # Reset title after 3 seconds
            self.set_timer(3.0, lambda: controls_title.update(original_text))
    
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
@click.option('--theme', type=click.Choice(['default', 'dark', 'blue', 'green', 'red', 'purple', 'orange', 'cyan', 'magenta']), default='blue',
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
    print("You can update FLUIDTOP by running `pip install fluid-top --upgrade`")
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
