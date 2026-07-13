#!/bin/bash
# Sets up udev rules for RTL-SDR so it can be used without sudo
set -e

echo "Setting up udev rules for RTL-SDR..."

cat <<EOF | sudo tee /etc/udev/rules.d/20-rtlsdr.rules
# RTL-SDR udev rules
SUBSYSTEMS=="usb", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="2838", MODE:="0666", GROUP="plugdev"
SUBSYSTEMS=="usb", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="2832", MODE:="0666", GROUP="plugdev"
EOF

sudo usermod -a -G plugdev $USER

# Blacklist DVB-T kernel TV tuner modules so they don't claim the SDR
echo "Creating blacklist rules..."
cat <<EOF | sudo tee /etc/modprobe.d/blacklist-rtl.conf
blacklist dvb_usb_rtl28xxu
blacklist rtl2832
blacklist rtl2830
EOF

# Try to unload the module immediately if it's currently loaded
echo "Unloading active kernel TV tuner modules (if any)..."
sudo rmmod dvb_usb_rtl28xxu || true
sudo rmmod rtl2832 || true

sudo udevadm control --reload-rules
sudo udevadm trigger

echo "Done! We have blacklisted the TV tuner drivers and updated permissions."
echo "Please unplug and re-plug your SDR dongle now to apply the changes."
