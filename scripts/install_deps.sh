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

# Install aptdec (APT image decoder)
if ! command -v aptdec &> /dev/null; then
    echo "--- Building aptdec ---"
    git clone https://github.com/csete/aptdec.git /tmp/aptdec
    cd /tmp/aptdec && mkdir build && cd build
    cmake .. && make -j4
    sudo make install
    cd -
fi

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
echo "  2. python main.py --check-hardware"
echo "  3. python main.py --check-connectivity"
echo "  4. python main.py --scan-wx-radio   (find your strongest 162MHz freq)"
echo "  5. python main.py"
