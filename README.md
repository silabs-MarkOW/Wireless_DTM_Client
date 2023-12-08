# Wireless_DTM_Client
pyBGAPI NCP Host application for controlling device running [Bluetooth Wireless DTM](https://github.com/SiliconLabs/bluetooth_applications/tree/c1c8eafe43dc6c5baafdee9f8599affbb3a365df/bluetooth_wireless_dtm) example from Silicon Labs Bluetooth Applications GitHub repo.

<pre>
$ python3 wireless-dtm-client.py
usage: wireless-dtm-client.py [-h] [--xapi XAPI] [--bt-address BT_ADDRESS]
                              [--bt-name BT_NAME]
                              [--scan-timeout SCAN_TIMEOUT]
                              [--wstk-address WSTK_ADDRESS] [--uart UART]
                              [--baudrate BAUDRATE] [-v] --mode {rx,tx,cw}
                              --channel CHANNEL --phy {1m,2m,125k,500k}
                              --duration DURATION [--length LENGTH]
                              [--power POWER]
                              [--packet-type {prbs9,11110000,10101010,11111111,00000000,00001111,01010101,pn9,carrier}]
wireless-dtm-client.py: error: the following arguments are required: --mode, --channel, --phy, --duration
</pre>

<pre>
$ python3 wireless-dtm-client.py --mode=cw --length=50 --phy=1m \
  --uart=${UART} --channel=1 --duration=10 --packet-type=pn9 \
  --power=50 --bt-address=14:b4:57:0a:f6:14
waiting 10 seconds for result
Observed duration of no advertisement: 11.0 seconds
DTM_CONTROL.RESULT: 0
DTM_CONTROL.MODE: 0
DTM_CONTROL.DURATION: 10
DTM_TX.PACKET_TYPE: 253
DTM_TX.CHANNEL: 1
DTM_TX.PHY: 1
DTM_TX.POWER: 50
</pre>