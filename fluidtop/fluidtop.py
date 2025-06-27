import time
import click
import asyncio
from collections import deque

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import ProgressBar, Static, Label
from textual_plotext import PlotextPlot
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
    
    def update_value(self, value: int, title: str = None):
        self._value = value
        if title:
            self.title = title
        self.query_one("#gauge-title", Label).update(self.title)
        self.query_one("#gauge-progress", ProgressBar).update(progress=value)


class PowerChart(PlotextPlot):
    """Custom chart widget for power consumption data"""
    
    def __init__(self, title: str = "", **kwargs):
        super().__init__(**kwargs)
        self.title = title
        self.data_points = deque(maxlen=100)
        
    def on_mount(self):
        self.plt.title(self.title)
        self.plt.xlabel("Time")
        self.plt.ylabel("Power (%)")
    
    def add_data(self, value: float):
        self.data_points.append(value)
        self.plt.clear_data()
        if len(self.data_points) > 1:
            self.plt.plot(list(range(len(self.data_points))), list(self.data_points))
        self.refresh()
    
    def update_title(self, title: str):
        self.title = title
        self.plt.title(title)
        self.refresh()


class FluidTopApp(App):
    """Main FluidTop application using Textual"""
    
    CSS = """
    MetricGauge {
        height: 3;
        margin: 1;
        border: solid $primary;
    }
    
    PowerChart {
        height: 10;
        margin: 1;
        border: solid $primary;
    }
    
    #processor-section {
        border: solid $primary;
        padding: 1;
    }
    
    #memory-section {
        border: solid $primary;
        padding: 1;
    }
    
    #power-section {
        border: solid $primary;
        padding: 1;
    }
    """
    
    def __init__(self, interval: int, color: int, avg: int, show_cores: bool, max_count: int):
        super().__init__()
        self.interval = interval
        self.color = color
        self.avg = avg
        self.show_cores = show_cores
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
        
    def compose(self) -> ComposeResult:
        """Compose the UI layout"""
        
        # Processor section
        with Vertical(id="processor-section"):
            yield Label("Processor Utilization", id="processor-title")
            
            if self.show_cores:
                # E-cores
                with Horizontal():
                    for i in range(self.soc_info_dict["e_core_count"]):
                        yield MetricGauge(f"E-Core {i+1}", id=f"e-core-{i}")
                
                # P-cores
                p_core_count = self.soc_info_dict["p_core_count"]
                with Horizontal():
                    for i in range(min(p_core_count, 8)):
                        yield MetricGauge(f"P-Core {i+1}", id=f"p-core-{i}")
                
                if p_core_count > 8:
                    with Horizontal():
                        for i in range(8, p_core_count):
                            yield MetricGauge(f"P-Core {i+1}", id=f"p-core-{i}")
            else:
                with Horizontal():
                    yield MetricGauge("E-CPU Usage", id="e-cpu-gauge")
                    yield MetricGauge("P-CPU Usage", id="p-cpu-gauge")
            
            with Horizontal():
                yield MetricGauge("GPU Usage", id="gpu-gauge")
                yield MetricGauge("ANE Usage", id="ane-gauge")
        
        # Memory section
        with Vertical(id="memory-section"):
            yield Label("Memory", id="memory-title")
            yield MetricGauge("RAM Usage", id="ram-gauge")
        
        # Power section
        with Vertical(id="power-section"):
            yield Label("Power Charts", id="power-title")
            if self.show_cores:
                yield PowerChart("CPU Power", id="cpu-power-chart")
                yield PowerChart("GPU Power", id="gpu-power-chart")
                yield PowerChart("Total Power", id="total-power-chart")
            else:
                with Horizontal():
                    yield PowerChart("CPU Power", id="cpu-power-chart")
                    yield PowerChart("GPU Power", id="gpu-power-chart")
                    yield PowerChart("Total Power", id="total-power-chart")
    
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
        
        # Update processor title
        cpu_title = f"{self.soc_info_dict['name']} (cores: {self.soc_info_dict['e_core_count']}E+{self.soc_info_dict['p_core_count']}P+{self.soc_info_dict['gpu_core_count']}GPU)"
        self.query_one("#processor-title", Label).update(cpu_title)
    
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
            
            # Update CPU metrics
            await self.update_cpu_metrics(cpu_metrics_dict)
            
            # Update GPU metrics
            await self.update_gpu_metrics(gpu_metrics_dict)
            
            # Update ANE metrics  
            await self.update_ane_metrics(cpu_metrics_dict)
            
            # Update memory metrics
            await self.update_memory_metrics()
            
            # Update power charts
            await self.update_power_charts(cpu_metrics_dict, thermal_pressure)
            
        except Exception as e:
            # Handle errors gracefully
            pass
    
    async def update_cpu_metrics(self, cpu_metrics_dict):
        """Update CPU gauge metrics"""
        if self.show_cores:
            # Update individual E-cores
            for i, core_idx in enumerate(cpu_metrics_dict["e_core"]):
                gauge = self.query_one(f"#e-core-{i}", MetricGauge)
                title = f"Core-{core_idx + 1} {cpu_metrics_dict[f'E-Cluster{core_idx}_active']}%"
                gauge.update_value(cpu_metrics_dict[f"E-Cluster{core_idx}_active"], title)
            
            # Update individual P-cores
            for i, core_idx in enumerate(cpu_metrics_dict["p_core"]):
                gauge = self.query_one(f"#p-core-{i}", MetricGauge)
                title = f"Core-{core_idx + 1} {cpu_metrics_dict[f'P-Cluster{core_idx}_active']}%"
                gauge.update_value(cpu_metrics_dict[f"P-Cluster{core_idx}_active"], title)
        else:
            # Update cluster gauges
            e_cpu_gauge = self.query_one("#e-cpu-gauge", MetricGauge)
            title = f"E-CPU Usage: {cpu_metrics_dict['E-Cluster_active']}% @ {cpu_metrics_dict['E-Cluster_freq_Mhz']} MHz"
            e_cpu_gauge.update_value(cpu_metrics_dict["E-Cluster_active"], title)
            
            p_cpu_gauge = self.query_one("#p-cpu-gauge", MetricGauge)
            title = f"P-CPU Usage: {cpu_metrics_dict['P-Cluster_active']}% @ {cpu_metrics_dict['P-Cluster_freq_Mhz']} MHz"
            p_cpu_gauge.update_value(cpu_metrics_dict["P-Cluster_active"], title)
    
    async def update_gpu_metrics(self, gpu_metrics_dict):
        """Update GPU gauge metrics"""
        gpu_gauge = self.query_one("#gpu-gauge", MetricGauge)
        title = f"GPU Usage: {gpu_metrics_dict['active']}% @ {gpu_metrics_dict['freq_MHz']} MHz"
        gpu_gauge.update_value(gpu_metrics_dict["active"], title)
    
    async def update_ane_metrics(self, cpu_metrics_dict):
        """Update ANE gauge metrics"""
        ane_max_power = 8.0
        ane_util_percent = int(cpu_metrics_dict["ane_W"] / self.interval / ane_max_power * 100)
        ane_power = cpu_metrics_dict["ane_W"] / self.interval
        
        ane_gauge = self.query_one("#ane-gauge", MetricGauge)
        title = f"ANE Usage: {ane_util_percent}% @ {ane_power:.1f} W"
        ane_gauge.update_value(ane_util_percent, title)
    
    async def update_memory_metrics(self):
        """Update memory gauge metrics"""
        ram_metrics_dict = get_ram_metrics_dict()
        
        if ram_metrics_dict["swap_total_GB"] < 0.1:
            title = f"RAM Usage: {ram_metrics_dict['used_GB']}/{ram_metrics_dict['total_GB']}GB - swap inactive"
        else:
            title = f"RAM Usage: {ram_metrics_dict['used_GB']}/{ram_metrics_dict['total_GB']}GB - swap:{ram_metrics_dict['swap_used_GB']}/{ram_metrics_dict['swap_total_GB']}GB"
        
        ram_gauge = self.query_one("#ram-gauge", MetricGauge)
        ram_gauge.update_value(ram_metrics_dict["free_percent"], title)
    
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
@click.option('--color', type=int, default=2,
              help='Choose display color (0~8)')
@click.option('--avg', type=int, default=30,
              help='Interval for averaged values (seconds)')
@click.option('--show_cores', is_flag=True,
              help='Choose show cores mode')
@click.option('--max_count', type=int, default=0,
              help='Max show count to restart powermetrics')
def main(interval, color, avg, show_cores, max_count):
    """fluidtop: Performance monitoring CLI tool for Apple Silicon"""
    return _main_logic(interval, color, avg, show_cores, max_count)


def _main_logic(interval, color, avg, show_cores, max_count):
    """Main logic using Textual app"""
    print("\nFLUIDTOP - Performance monitoring CLI tool for Apple Silicon")
    print("You can update FLUIDTOP by running `pip install fluid-top --upgrade`")
    print("Get help at `https://github.com/FluidInference/fluidtop`")
    print("P.S. You are recommended to run FLUIDTOP with `sudo fluidtop`\n")
    
    # Create and run the Textual app
    app = FluidTopApp(interval, color, avg, show_cores, max_count)
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
