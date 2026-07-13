#!/bin/bash
set -e
echo "=== pi_noaa Dependency Installer ==="

sudo apt-get update
sudo apt-get install -y \
    rtl-sdr \
    sox \
    librtlsdr-dev \
    build-essential \
    cmake \
    git \
    python3-pip \
    python3-venv \
    ffmpeg \
    multimon-ng

# Blacklist DVB-T kernel module (required for RTL-SDR)
echo "blacklist dvb_usb_rtl28xxu" | sudo tee /etc/modprobe.d/blacklist-rtl.conf

PROJECT_ROOT=$(pwd)

# Install SatDump
if ! command -v satdump &> /dev/null; then
    echo "--- Building SatDump ---"
    # Dependencies required by SatDump
    sudo apt-get install -y libfftw3-dev libpng-dev libtiff-dev libvolk-dev libogg-dev libvorbis-dev libnng-dev libcurl4-openssl-dev libsqlite3-dev libjemalloc-dev
    
    BUILD_DIR="$HOME/satdump"
    if [ -d "$BUILD_DIR" ]; then
        echo "--- Updating SatDump source ---"
        cd "$BUILD_DIR"
        git pull
    else
        echo "--- Cloning SatDump ---"
        git clone https://github.com/SatDump/SatDump.git "$BUILD_DIR"
        cd "$BUILD_DIR"
    fi
    
    mkdir -p build && cd build
    
    # Dynamically locate libogg.so and libnng.so to bypass CMake multiarch resolution bugs
    OGG_PATH=$(find /usr/lib -name "libogg.so" 2>/dev/null | head -n 1)
    NNG_PATH=$(find /usr/lib -name "libnng.so" 2>/dev/null | head -n 1)
    
    CMAKE_FLAGS=""
    if [ -n "$OGG_PATH" ]; then
        CMAKE_FLAGS="$CMAKE_FLAGS -DOGG_LIBRARY=$OGG_PATH"
        echo "Found libogg.so at: $OGG_PATH, passing to CMake"
    fi
    if [ -n "$NNG_PATH" ]; then
        CMAKE_FLAGS="$CMAKE_FLAGS -DNNG_LIBRARY=$NNG_PATH"
        echo "Found libnng.so at: $NNG_PATH, passing to CMake"
    fi
    
    echo "--- Configuring SatDump ---" | tee ../satdump_build.log
    cmake -DCMAKE_BUILD_TYPE=Release -DBUILD_GUI=OFF $CMAKE_FLAGS .. 2>&1 | tee -a ../satdump_build.log
    
    echo "--- Compiling SatDump ---" | tee -a ../satdump_build.log
    make -j2 2>&1 | tee -a ../satdump_build.log
    
    echo "--- Installing SatDump ---" | tee -a ../satdump_build.log
    sudo make install 2>&1 | tee -a ../satdump_build.log
    
    cd "$PROJECT_ROOT"
fi

cd "$PROJECT_ROOT"

# Python virtual environment
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Create dummy geojson file just so it doesn't fail on boot, in a real setup this would download from census
mkdir -p ui/static/data/geo
echo '{"type": "FeatureCollection", "features": []}' > ui/static/data/geo/us_counties_simplified.geojson

echo ""
echo "=== Installation complete! ==="
echo "Next steps:"
echo "  1. Edit config.yaml (set your latitude/longitude/alert_zone)"
echo "  2. Activate the virtual environment: source venv/bin/activate"
echo "  3. python main.py --check-hardware"
echo "  4. python main.py --check-connectivity"
echo "  5. python main.py --scan-wx-radio   (find your strongest 162MHz freq)"
echo "  6. python main.py"
