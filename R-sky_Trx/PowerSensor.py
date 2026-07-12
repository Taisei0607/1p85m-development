import os
import sys
import time
import serial
import ctypes
import numpy as np
import matplotlib.pyplot as plt

class PowerSensor:
    def __init__(self, port = "/dev/ttyACM*", baudrate = 19200, timeout = 1.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None
        self._init_serial()

    def _init_serial(self):
        try:
            self.ser = serial.Serial(port = self.port, baudrate = self.baudrate, bytesize = 7, parity = serial.PARITY_NONE, stopbits = 1, timeout = self.timeout)
            print(f"Connected to {self.port}")
        except serial.SerialException as e:
            print(f"Error: Unable to connect to serial port: {e}")
            raise

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            print(f"Disconnected from {self.port}")
        return True

    def write(self, command):
        if not self.ser or not self.ser.is_open:
            print("Error: Serial port is not open")
            return False

        try:
            self.ser.write(command.encode())
            return True
        except serial.SerialException as e:
            print(f"Error: Unable to send command: {e}")
            return False

    def read(self, size = 1024):
        if not self.ser or not self.ser.is_open:
            print("Error: Serial port is not open")
            return ""
        try:
            response = self.ser.read(size).decode().strip()
            return response
        except serial.SerialException as e:
            print(f"Error: Unable to read data: {e}")
            return ""

    def query(self, command, size = 1024):
        self.write(command)
        time.sleep(0.1)
        return self.read(size)

    def get_id(self):
        return self.query("IDN?\n")

    def start(self):
        return self.write("START\n")

    def stop(self):
        return self.write("STOP\n")

    def zero_calibration(self, show_progress = True):
        if show_progress:
            print("\nZero calibration start...")

        self.write("ZERO\n")

        if show_progress:
            for i in range(21):
                progress = min(i*5, 100)
                print(f"\rProgress: {progress}%", end = "")
                time.sleep(1.0)
            print("\rProgress: 100%")
            print("Zero calibration finished.\n")
        else:
            time.sleep(20)

        return True

    def get_power(self):
        response = self.query("PWR?\n")
        try:
            parts = response.split()
            if len(parts) > 1 and parts[-1].replace('.', '', 1).replace('-', '', 1).isdigit():
                return float(parts[-1])
            elif len(parts) == 1:
                return float(parts[0])
            else:
                raise ValueError("unable to find figure")

        except ValueError:
            return None

    def measure_power(self, display = True):
        power = self.get_power()
        if power is not None and display:
            print(f"Power: {power:.2f} dBm")
        return power

    def get_frequency(self):
        response = self.query("FREQ?\n")
        try:
            return float(response)
        except ValueError:
            print(f"Error: Unable to get frequency (Response: {response})")
            return None

    def set_frequency(self, freq_ghz):
        command = f"FREQ {freq_ghz:.3f}\n"
        response = self.query(command)
        if response == "OK":
            print(f"Frequency set to {freq_ghz:.3f} GHz")
            return True
        else:
            print(f"Error: Unable to set frequency (Response: {response})")
            return False

    def get_aperture_time(self):
        response = self.query("CHAPERT?\n")
        try:
            return float(response)
        except ValueError:
            print(f"Error: Unable to get aperture time (Response: {response})")
            return None

    def set_aperture_time(self, time_ms):
        if time_ms < 0.01 or time_ms > 300:
            print(f"Error: Please set aperture time within 0.01 ms ~ 300 ms")
            return False
        command = f"CHAPERT {time_ms:.2f}\n"
        response = self.query(command)

        if response == "OK":
            print(f"Aperture time set to {time_ms:.2f} ms")
            return True
        else:
            print(f"Error: Unable to set aperture time (Response: {response})")
            return False

    def get_average_mode(self):
        response = self.query("AVGTYP?\n")

        if response == "0":
            return "Moving"
        elif response == "1":
            return "Repeat"
        else:
            print(f"Error: Unable to get average mode (Response: {response})")
            return None

    def set_average_mode(self, mode):
        if mode == "Moving" or mode == 0:
            command = "AVGTYP 0\n"
            mode_str = "Moving"
        elif mode == "Repeat" or mode == 1:
            command = "AVGTYP 1\n"
            mode_str = "Repeat"
        else:
            print("Error: Please set 'Moving' or 'Repeat' as average mode")
            return False

        response = self.query(command)
        if response == "OK":
            print(f"Average mode set to {mode_str}")
            return True
        else:
            print(f"Error: Unable to set average mode (Response: {response})")
            return False

    def get_average_count(self):
        response = self.query("AVGCNT?\n")
        try:
            return int(response)
        except ValueError:
            print(f"Error: Unable to get average count (Response: {response})")
            return None

    def set_average_count(self, count):
        if count < 1 or count > 1024:
            print("Error: Please set average count within 1 ~ 1024")
            return False

        command = f"AVGCNT {count}\n"
        response = self.query(command)

        if response == "OK":
            print(f"Average count set to {count}")
            return True
        else:
            print(f"Error: Unable to set average count (Response: {response})")
            return False

    def initialize(self, freq_ghz = None, aperture_ms = None, avg_mode = None, avg_count = None):
        print("\nInitializing sensor...")

        device_id = self.get_id()
        print(f"Device ID: {device_id}")

        if freq_ghz is not None:
            self.set_frequency(freq_ghz)

        if aperture_ms is not None:
            self.set_aperture_time(aperture_ms)

        if avg_mode is not None:
            self.set_average_mode(avg_mode)

        if avg_count is not None:
            self.set_average_count(avg_count)

        print("Initialization complete.\n")
        return True

    def show_settings(self):
        print("\n === Current Settings ===")

        freq = self.get_frequency()
        if freq is not None:
            print(f"Frequency: {freq:.3f} GHz")

        aperture = self.get_aperture_time()
        if aperture is not None:
            print(f"Aperture Time: {aperture:.2f} ms")

        avg_mode = self.get_average_mode()
        if avg_mode is not None:
            print(f"Average Mode: {avg_mode}")

        avg_count = self.get_average_count()
        if avg_count is not None:
            print(f"Average Count: {avg_count}")

        print("==========\n")