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

sudo udevadm control --reload-rules
sudo udevadm trigger

echo "Done! You may need to unplug and re-plug your SDR dongle."
