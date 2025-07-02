# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

fluidtop is a Python-based performance monitoring CLI tool for Apple Silicon Macs, inspired by `nvtop`. It provides real-time monitoring of CPU, GPU, ANE (Apple Neural Engine), memory, and power consumption using macOS's built-in `powermetrics` utility.

**Important**: This tool only works on Apple Silicon Macs and requires `sudo` privileges to access `powermetrics`.

## Architecture

### Core Components

- **`fluidtop/fluidtop.py`**: Main application entry point with UI rendering using the `textual` library
- **`fluidtop/utils.py`**: System utilities for data collection and `powermetrics` process management
- **`fluidtop/parsers.py`**: Data parsing functions for `powermetrics` output (plist format)
- **`setup.py`**: Standard Python package configuration

### Key Architecture Patterns

- **Data Collection Pipeline**: `powermetrics` subprocess → plist parsing → metric extraction → UI display
- **Hardware Detection**: Dynamic SoC identification (M1, M1 Pro/Max/Ultra, M2) with hardcoded TDP values
- **Real-time Display**: Terminal UI using `textual` library with gauges and charts
- **Temporary File Management**: Uses `/tmp/fluidtop_powermetrics*` files for data exchange

### Hardware Support Matrix

The application includes hardcoded power specifications for different Apple Silicon variants:
- **M1**: 20W CPU/GPU
- **M1 Pro**: 30W CPU, 30W GPU
- **M1 Max**: 30W CPU, 60W GPU
- **M1 Ultra**: 60W CPU, 120W GPU
- **M2**: 25W CPU, 15W GPU
- **M3/M4+**: Dynamic detection with fallback to M2 specifications

**Note**: Bandwidth monitoring was removed as macOS 13 deprecated bandwidth support in powermetrics.

## Development Commands

### Installation & Setup

#### Using uv (Recommended)
```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Quick start - no installation needed, just run:
sudo uv run fluidtop

# For development work:
# Install in development mode
uv pip install -e .

# Install from PyPI
uv pip install fluidtop

# Create and activate virtual environment (optional)
uv venv
source .venv/bin/activate  # On macOS/Linux
# .venv\Scripts\activate   # On Windows

# Install dependencies in virtual environment
uv pip install -e .
```

#### Using pip (Traditional)
```bash
# Install in development mode
pip install -e .

# Install from PyPI
pip install fluidtop
```

### Running the Application

#### Using uv run (Recommended)
```bash
# Run directly with uv (automatically handles dependencies)
sudo uv run fluidtop

# Run with options
sudo uv run fluidtop --interval 2 --color 5 --avg 60 --show_cores

# Alternative: run the module directly
sudo uv run -m fluidtop.fluidtop

# Without sudo (will prompt for password during execution)
uv run fluidtop
```

#### Traditional method
```bash
# Recommended usage (avoids password prompt during execution)
sudo fluidtop

# Alternative (will prompt for password)
fluidtop

# With options
fluidtop --interval 2 --color 5 --avg 60 --show_cores
```

### Available Command Line Options
- `--interval INTERVAL`: Display and powermetrics sampling interval (seconds, default: 1)
- `--color COLOR`: Color theme selection 0-8 (default: 2)
- `--avg AVG`: Averaging window for power values (seconds, default: 30)
- `--show_cores`: Enable individual core monitoring display
- `--max_count COUNT`: Restart powermetrics after N samples (for long-running sessions)

### Package Management

#### Using uv (Recommended)
```bash
# Build distribution
uv build

# Install build dependencies if needed
uv pip install build twine

# Upload to PyPI (maintainer only)
twine upload dist/*
```

#### Using traditional tools
```bash
# Build distribution
python setup.py sdist bdist_wheel

# Upload to PyPI (maintainer only)
twine upload dist/*
```

## Key Technical Details

### Dependencies
- **`click`**: Modern command-line interface creation toolkit (replaces argparse)
- **`textual`**: Modern terminal UI framework with async support
- **`textual-plotext`**: Plotting library for textual applications
- **`psutil`**: Cross-platform system monitoring (RAM/swap metrics)
- **`powermetrics`**: macOS system utility (requires sudo)
- **`sysctl`**: CPU information queries
- **`system_profiler`**: GPU core count detection

### Data Sources
- **CPU/GPU utilization**: `powermetrics` active residency
- **Power consumption**: `powermetrics` energy counters
- **Memory usage**: `psutil` virtual memory stats
- **Core counts**: `sysctl hw.perflevel` queries
- **SoC identification**: `sysctl machdep.cpu.brand_string`

### CLI Implementation
- **Command-line Interface**: Uses Click framework for modern CLI handling
- **Options**: All command-line options use Click decorators (@click.option)
- **Help System**: Automatic help generation with Click's built-in --help
- **Parameter Validation**: Click handles type validation and error reporting
- **Entry Point**: `fluidtop.fluidtop:main` decorated with @click.command()

### File Structure Notes
- Entry point: `fluidtop.fluidtop:main` (defined in pyproject.toml and setup.py)
- No test suite present in codebase
- Dependencies defined in both pyproject.toml and setup.py for compatibility
- Uses plist format for powermetrics data exchange
- Bandwidth monitoring code removed (macOS 13 deprecated bandwidth support in powermetrics)
- Modern packaging with pyproject.toml supports uv and other modern Python tools

### UI Components
- **MetricGauge**: Custom widget combining labels and progress bars for metrics display
- **PowerChart**: Custom plotting widget for power consumption data using PlotextPlot
- **UsageChart**: Custom plotting widget for usage percentage data (CPU, GPU, RAM)
- **FluidTopApp**: Main Textual application class with async update loops
- **Sections**: UI organized into processor, memory, usage charts, and power charts sections
- **Screenshot**: Saves terminal display as SVG to ~/fluidtop_screenshots directory

## Terminal Compatibility

### Ghostty Terminal Support
fluidtop includes enhanced support for [Ghostty](https://ghostty.org/) terminal emulator:
- **Early Compatibility Detection**: Detects Ghostty before importing terminal libraries to prevent compatibility issues
- **Automatic Terminal Mapping**: Maps `xterm-ghostty` and `ghostty` TERM values to `xterm-256color` for maximum compatibility
- **True Color Support**: Automatically enables truecolor support for enhanced visual quality
- **GPU Acceleration**: Leverages Ghostty's GPU acceleration for smoother real-time monitoring
- **Standards Compliance**: Takes advantage of Ghostty's excellent standards compliance for reliable operation
- **Cross-Platform**: Works across all platforms supported by Ghostty (macOS, Linux, Windows)

The application automatically detects when running in Ghostty, applies compatibility fixes before library initialization, and displays a confirmation message during startup. This resolves the common `'xterm-ghostty': unknown terminal type` error that occurs with terminal UI libraries.

## Troubleshooting

### Common Issues
- **Permission denied**: Run with `sudo fluidtop`
- **Not compatible**: Only works on Apple Silicon Macs with macOS Monterey+
- **Thermal throttling**: Displayed in power chart title when detected
- **Incomplete data**: Application handles parsing errors gracefully with fallback logic

### Debug Information
- Temporary files: `/tmp/fluidtop_powermetrics*`
- Process management: Uses subprocess.Popen for powermetrics
- Error handling: Try/except blocks for plist parsing with fallback to previous data