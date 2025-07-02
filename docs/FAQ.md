# FluidTop - Frequently Asked Questions

## Apple Silicon Architecture

### What's the difference between E-CPU and P-CPU cores?

Apple Silicon chips use a **hybrid architecture** with two types of CPU cores:

**P-CPU (Performance Cores)**
- High-performance cores optimized for demanding computational tasks
- Higher clock speeds and more powerful execution units
- Consume more power but deliver maximum single-threaded performance
- Used for: Heavy applications, gaming, video editing, intensive calculations
- Typically 4-8 cores depending on chip variant (M1: 4, M2 Pro: 8, etc.)

**E-CPU (Efficiency Cores)**  
- Energy-efficient cores optimized for background tasks and battery life
- Lower clock speeds but much better performance-per-watt
- Designed to handle routine system tasks with minimal power consumption
- Used for: Background processes, web browsing, light multitasking, system maintenance
- Typically 4 cores across most Apple Silicon variants

**How FluidTop displays them:**
- Individual core utilization shows both types when using `--show_cores`
- P-cores are typically listed first, followed by E-cores
- Total CPU utilization combines both core types
- Power consumption reflects the hybrid architecture's efficiency benefits

## System Requirements & Compatibility

### Which Apple Silicon chips are supported?

FluidTop supports all Apple Silicon variants:
- **M1 family:** M1, M1 Pro, M1 Max, M1 Ultra
- **M2 family:** M2, M2 Pro, M2 Max, M2 Ultra  
- **M3 family:** M3, M3 Pro, M3 Max
- **M4 family:** M4, M4 Pro, M4 Max (and future variants)

### Why do I need sudo/root privileges?

FluidTop requires root access because it uses macOS's `powermetrics` utility, which accesses low-level hardware performance counters. This is a macOS security requirement, not a FluidTop limitation.

## Monitoring & Accuracy

### How accurate are the power consumption readings?

FluidTop uses hardware energy counters provided by `powermetrics`, which are the same data sources used by macOS's Activity Monitor and system diagnostics. Power readings are highly accurate for relative measurements and trends, though absolute values may vary slightly based on system calibration.

### What is the Neural Engine (ANE) and how is it monitored?

The Neural Engine is Apple's dedicated AI/ML processor designed for machine learning workloads. FluidTop monitors ANE utilization when AI frameworks like Core ML, TensorFlow, or PyTorch offload computations to it. High ANE usage typically indicates active machine learning inference or training.

### How does FluidTop compare to Activity Monitor?

FluidTop provides more detailed real-time hardware metrics than Activity Monitor, including:
- Individual CPU core utilization (P-cores vs E-cores)
- Real-time power consumption with averaging
- Neural Engine utilization tracking
- Memory usage monitoring
- Terminal-based interface for remote monitoring

## Features & Limitations

### Can I monitor specific applications or processes?

This feature is currently in development. For now, FluidTop provides system-wide monitoring. Process-specific monitoring will be available in a future release.

### Why doesn't the display fit my terminal properly?

FluidTop automatically adapts to terminal width but currently has fixed height requirements. Ensure your terminal window is large enough to display all monitoring sections. Terminal height adaptation is planned for a future update.

### Can I export monitoring data?

Data export capabilities (CSV, JSON) are planned for a future release. Currently, FluidTop is designed for real-time monitoring only.

## Troubleshooting

### FluidTop shows "Permission denied" errors

Make sure you're running FluidTop with sudo privileges:
```bash
sudo fluidtop
```

### The display appears corrupted or scrambled

Try these solutions:
1. Resize your terminal window to be larger
2. Use a different color theme: `sudo fluidtop --color 0`
3. Clear your terminal: `clear` before running FluidTop
4. Update to the latest version: `uv tool install fluidtop@latest -U`

### FluidTop crashes or becomes unresponsive

This can happen during long monitoring sessions. Use the `--max_count` option to automatically restart:
```bash
sudo fluidtop --max_count 1000
```

### High CPU usage from FluidTop itself

Reduce the refresh rate to lower system impact:
```bash
sudo fluidtop --interval 2.0
```

## Migration & Compatibility

### How does FluidTop differ from the original asitop?

FluidTop is an enhanced and actively maintained fork of asitop with:
- Support for newer Apple Silicon chips (M3, M4+)
- Optimizations for modern terminal emulators (Ghostty compatibility)
- Enhanced AI/ML workload monitoring focus
- Regular updates and bug fixes
- Improved documentation and user experience

### Can I use FluidTop alongside other monitoring tools?

Yes, FluidTop can run alongside other monitoring tools like htop, Activity Monitor, or iStat Menus without conflicts. However, running multiple tools simultaneously may slightly increase system resource usage.

---

**Need more help?** Check out the [main README](../README.md) or [submit an issue](https://github.com/FluidInference/fluidtop/issues) on GitHub. 