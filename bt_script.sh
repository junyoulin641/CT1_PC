#!/system/bin/sh
# Bluetooth initialization and command execution script
echo "=== Executing Bluetooth Initialization and Commands ==="

cat > /data/local/tmp/bt_commands.txt << 'EOF'
btcmd 0x03 0x0003
btcmd 0x03 0x1a 0x03
btcmd 0x03 0x05 0x02 0x00 0x02
btcmd 0x06 0x03
btcmd 0x03 0x0003
btcmd 0x3f 0x0051 66 55 44 33 22 11 01 27 04 01 0F 10 27 09 00 00
exit
EOF

ampak_bt_utils_aarch64 --baudrate 115200 --patchram /vendor/etc/bluetooth/BCM4343A1_001.002.009.1026.1055.hcd /dev/ttyS4 < /data/local/tmp/bt_commands.txt

echo "Bluetooth commands execution completed"
exit 0