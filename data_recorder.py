import numpy as np
import serial.tools.list_ports
import wave
import serial
import matplotlib.pyplot as plt
import time

# Configuration
BAUD_RATE = 115200
# SAMPLE_RATE = 44100
# AUDIO_LENGTH = 10
# BUFFER_SIZE = 256

# Private variables
data = []

# Search and connect serial port
ports = serial.tools.list_ports.comports()
devices = [port.device for port in ports]
print(devices)
try:
    ser = serial.Serial(devices[2], BAUD_RATE, timeout = 1)
except serial.SerialException as e:
    print(f"Serial port error: {e}")
    exit(1)

print("Collecting audio data...")

stopFlag = True
while stopFlag:
    try:
        # dataCount = int(input("Enter data count: "))
        dataRec = []

        for i in range(2):
            data = ser.read_until(b"\r\n")
            dataRec.append(int(data.decode().strip("ADC Value = ")))

        dataMean = np.mean(np.array(dataRec))

        print(f"Mean data: {dataMean}\n")

        # Piecewise conversion
        if dataMean > 2414:
            mlConverter = -0.00661 * dataMean + 25.96
        else:
            mlConverter = -0.01364 * dataMean + 42.93

        # Clamp (optional but good practice)
        mlConverter = max(0, mlConverter)

        print(f"Ml converter: {mlConverter:.2f}ml")

    except KeyboardInterrupt:
        stopFlag = False
        print("Closing program...")
        break