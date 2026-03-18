import numpy as np
import serial
import serial.tools.list_ports
import matplotlib.pyplot as plt

# =========================
# Configuration
# =========================
BAUD_RATE = 115200
BASELINE = 3000
DROP_THRESHOLD = 150
SKIP_COUNT = 5
RECORD_COUNT = 3
MAX_POINTS = 200
STOP_AFTER_SAMPLES = 50

MIN_WATER_ML = 0
MAX_WATER_ML = 40

# =========================
# Calibration data
# Replace these with your real ADC values
# Example:
# 0 mL  -> 3700
# 20 mL -> 3200
# 40 mL -> 2700
# 60 mL -> 2200
# =========================
CAL_ADC = np.array([3926, 2414, 1770, 1099, 650], dtype=float)
CAL_WATER = np.array([0,10, 20, 30, 40], dtype=float)


def get_linear_regression(adc_values, water_values):
    """
    Fit a straight line:
        water_ml = slope * adc + intercept
    """
    slope, intercept = np.polyfit(adc_values, water_values, 1)
    return slope, intercept


def adc_to_water_ml(adc_value, slope, intercept):
    """
    Convert ADC to water (mL) using linear regression.
    Clamp result to 0 to 60 mL.
    """
    water_ml = slope * adc_value + intercept
    water_ml = max(MIN_WATER_ML, min(water_ml, MAX_WATER_ML))
    return water_ml


def run_program():
    # Calculate regression equation
    slope, intercept = get_linear_regression(CAL_ADC, CAL_WATER)
    print(f"\nLinear regression equation:")
    print(f"water_ml = {slope:.6f} * adc + {intercept:.6f}")
    print(f"Water output is clamped between {MIN_WATER_ML} and {MAX_WATER_ML} mL\n")

    # Search and connect serial port
    ports = serial.tools.list_ports.comports()
    devices = [port.device for port in ports]
    print("Available ports:", devices)

    try:
        ser = serial.Serial(devices[2], BAUD_RATE, timeout=1)
    except (serial.SerialException, IndexError) as e:
        print(f"Serial port error: {e}")
        return

    print("Monitoring ADC data... Press Ctrl+C to stop.")

    # Detection variables
    drop_detected = False
    skip_buffer = []
    record_buffer = []
    last_mean_adc = None
    last_mean_water = None
    samples_after_trigger = 0

    # Plot history
    adc_history = []
    water_history = []

    # Live plotting
    plt.ion()
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

    # ADC plot
    adc_line, = ax1.plot([], [], label="ADC Data")
    ax1.axhline(BASELINE, linestyle="--", label="Baseline")
    ax1.set_title("Live ADC Data")
    ax1.set_xlabel("Sample Index")
    ax1.set_ylabel("ADC Value")
    ax1.grid(True)
    ax1.legend()

    # Water plot
    water_line, = ax2.plot([], [], label="Water Level (mL)")
    ax2.axhline(MAX_WATER_ML, linestyle="--", label="Max = 60 mL")
    ax2.axhline(MIN_WATER_ML, linestyle="--", label="Min = 0 mL")
    ax2.set_title("Estimated Water Level")
    ax2.set_xlabel("Sample Index")
    ax2.set_ylabel("Water (mL)")
    ax2.grid(True)
    ax2.legend()

    try:
        while True:
            raw_data = ser.read_until(b"\r\n")

            if not raw_data:
                continue

            try:
                line_in = raw_data.decode().strip()

                if "ADC Value" in line_in:
                    adc_value = int(line_in.split("=")[-1].strip())
                else:
                    adc_value = int(line_in)

                water_ml = adc_to_water_ml(adc_value, slope, intercept)

                print(f"ADC: {adc_value} | Water: {water_ml:.2f} mL")

                # Store history for plotting
                adc_history.append(adc_value)
                water_history.append(water_ml)

                if len(adc_history) > MAX_POINTS:
                    adc_history.pop(0)
                if len(water_history) > MAX_POINTS:
                    water_history.pop(0)

                # Update ADC plot
                adc_line.set_xdata(range(len(adc_history)))
                adc_line.set_ydata(adc_history)
                ax1.relim()
                ax1.autoscale_view()

                # Update water plot
                water_line.set_xdata(range(len(water_history)))
                water_line.set_ydata(water_history)
                ax2.relim()
                ax2.autoscale_view()

                plt.draw()
                plt.pause(0.01)

                # Wait until sudden drop is detected
                if not drop_detected:
                    if adc_value < (BASELINE - DROP_THRESHOLD):
                        drop_detected = True
                        skip_buffer = []
                        record_buffer = []
                        samples_after_trigger = 0

                        print(f"\nSudden drop detected at ADC = {adc_value}")
                        print(f"Estimated water at trigger = {water_ml:.2f} mL")
                        print(f"Skipping next {SKIP_COUNT} values...")
                        print(f"Stopping after {STOP_AFTER_SAMPLES} samples from trigger.\n")
                    continue

                # Count every sample after trigger
                samples_after_trigger += 1

                # Stop after enough samples
                if samples_after_trigger >= STOP_AFTER_SAMPLES:
                    print(f"\nReached {STOP_AFTER_SAMPLES} samples after trigger.")
                    if last_mean_adc is not None:
                        print(f"Last mean ADC value: {last_mean_adc:.2f}")
                        print(f"Last mean water value: {last_mean_water:.2f} mL")
                    else:
                        print("No mean value calculated yet.")
                    break

                # Skip first few values after trigger
                if len(skip_buffer) < SKIP_COUNT:
                    skip_buffer.append(adc_value)
                    print(f"Skipped value {len(skip_buffer)}: {adc_value} ({water_ml:.2f} mL)")
                    continue

                # Record next 10 values
                if len(record_buffer) < RECORD_COUNT:
                    record_buffer.append(adc_value)
                    print(f"Recorded value {len(record_buffer)}: {adc_value} ({water_ml:.2f} mL)")

                # Once 10 values are collected, compute mean
                if len(record_buffer) == RECORD_COUNT:
                    last_mean_adc = np.mean(record_buffer)
                    last_mean_water = adc_to_water_ml(last_mean_adc, slope, intercept)

                    converted_water = [
                        adc_to_water_ml(adc, slope, intercept)
                        for adc in record_buffer
                    ]

                    print("\nRecorded 10 ADC values:")
                    print(record_buffer)
                    print(f"Mean ADC value: {last_mean_adc:.2f}")

                    print("\nConverted water values (mL):")
                    print([f"{w:.2f}" for w in converted_water])
                    print(f"Mean water value: {last_mean_water:.2f} mL\n")

                    # Reset only record buffer for next batch
                    record_buffer = []

            except ValueError:
                continue

    except KeyboardInterrupt:
        print("\nCtrl+C detected.")
        if last_mean_adc is not None:
            print(f"Last mean ADC value: {last_mean_adc:.2f}")
            print(f"Last mean water value: {last_mean_water:.2f} mL")
        else:
            print("No mean value calculated yet.")

    finally:
        ser.close()
        plt.ioff()
        plt.close(fig)


# =========================
# Main restart loop
# =========================
while True:
    run_program()
    user_input = input("\nPress Enter to restart, or type q to quit: ")
    if user_input.lower() == "q":
        print("Program exited.")
        break