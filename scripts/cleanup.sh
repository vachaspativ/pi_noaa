#!/bin/bash
set -e
echo "=== pi_noaa Post-Installation Cleanup Script ==="

BUILD_DIR="$HOME/satdump"

# 1. Remove SatDump source and build files (takes ~600MB - 1GB)
if [ -d "$BUILD_DIR" ]; then
    echo "Removing SatDump build folder: $BUILD_DIR..."
    rm -rf "$BUILD_DIR"
    echo "✓ Build folder removed."
else
    echo "No SatDump build folder found at $BUILD_DIR. Skipping."
fi

# 2. Clean up any leftovers in /tmp
if [ -d "/tmp/satdump" ]; then
    echo "Removing temporary SatDump folder in /tmp..."
    rm -rf /tmp/satdump
    echo "✓ Temporary folder removed."
fi

# 3. Clean apt cache and remove unused packages (saves SD card writes/space)
echo "Cleaning up apt packages and clearing package cache..."
sudo apt-get autoremove -y
sudo apt-get clean
echo "✓ Package manager cleaned."

# 4. Clean up Python cache files inside the pi_noaa project
echo "Cleaning up Python cache files (__pycache__)..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
echo "✓ Python cache files cleaned."

echo ""
echo "=== Cleanup Complete! ==="
echo "Your Raspberry Pi has been cleared of all compile-related source files and temporary caches."
echo "Only the pi_noaa application, logs, and installed binary dependencies have been retained."
