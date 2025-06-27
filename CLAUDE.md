# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

asitop is a Python-based performance monitoring CLI tool for Apple Silicon Macs, inspired by `nvtop`. It provides real-time monitoring of CPU, GPU, ANE (Apple Neural Engine), memory, and power consumption using macOS's built-in `powermetrics` utility.

**Important**: This tool only works on Apple Silicon Macs and requires `sudo` privileges to access `powermetrics`.

## Architecture

### Core Components

- **`asitop/asitop.py`**: Main application entry point with UI rendering using the `dashing` library
- **`asitop/utils.py`**: System utilities for data collection and `powermetrics` process management
- **`asitop/parsers.py`**: Data parsing functions for `powermetrics` output (plist format)
- **`setup.py`**: Standard Python package configuration

### Key Architecture Patterns

- **Data Collection Pipeline**: `powermetrics` subprocess → plist parsing → metric extraction → UI display
- **Hardware Detection**: Dynamic SoC identification (M1, M1 Pro/Max/Ultra, M2) with hardcoded TDP/bandwidth values
- **Real-time Display**: Terminal UI using `dashing` library with gauges and charts
- **Temporary File Management**: Uses `/tmp/asitop_powermetrics*` files for data exchange

### Hardware Support Matrix

The application includes hardcoded specifications for different Apple Silicon variants:
- **M1**: 20W CPU/GPU, 70 GB/s bandwidth
- **M1 Pro**: 30W CPU, 30W GPU, 200 GB/s bandwidth  
- **M1 Max**: 30W CPU, 60W GPU, 250/400 GB/s bandwidth
- **M1 Ultra**: 60W CPU, 120W GPU, 500/800 GB/s bandwidth
- **M2**: 25W CPU, 15W GPU, 100 GB/s bandwidth

## Development Commands

### Installation & Setup

#### Using uv (Recommended)
```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Quick start - no installation needed, just run:
sudo uv run asitop

# For development work:
# Install in development mode
uv pip install -e .

# Install from PyPI
uv pip install asitop

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
pip install asitop
```

### Running the Application

#### Using uv run (Recommended)
```bash
# Run directly with uv (automatically handles dependencies)
sudo uv run asitop

# Run with options
sudo uv run asitop --interval 2 --color 5 --avg 60 --show_cores true

# Alternative: run the module directly
sudo uv run -m asitop.asitop

# Without sudo (will prompt for password during execution)
uv run asitop
```

#### Traditional method
```bash
# Recommended usage (avoids password prompt during execution)
sudo asitop

# Alternative (will prompt for password)
asitop

# With options
asitop --interval 2 --color 5 --avg 60 --show_cores true
```

### Available Command Line Options
- `--interval INTERVAL`: Display and powermetrics sampling interval (seconds, default: 1)
- `--color COLOR`: Display color theme (0-8, default: 2)
- `--avg AVG`: Averaging window for power values (seconds, default: 30)
- `--show_cores`: Enable individual core monitoring display
- `--max_count`: Restart powermetrics after N samples (for long-running sessions)

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
- **`dashing`**: Terminal dashboard library for UI components
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

### File Structure Notes
- Entry point: `asitop.asitop:main` (defined in pyproject.toml and setup.py)
- No test suite present in codebase
- Dependencies defined in both pyproject.toml and setup.py for compatibility
- Uses plist format for powermetrics data exchange
- Bandwidth monitoring code exists but is disabled (commented out)
- Modern packaging with pyproject.toml supports uv and other modern Python tools

## Troubleshooting

### Common Issues
- **Permission denied**: Run with `sudo asitop`
- **Not compatible**: Only works on Apple Silicon Macs with macOS Monterey+
- **Thermal throttling**: Displayed in power chart title when detected
- **Incomplete data**: Application handles parsing errors gracefully with fallback logic

### Debug Information
- Temporary files: `/tmp/asitop_powermetrics*`
- Process management: Uses subprocess.Popen for powermetrics
- Error handling: Try/except blocks for plist parsing with fallback to previous data