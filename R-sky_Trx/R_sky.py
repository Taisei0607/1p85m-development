import RPi.GPIO as GPIO
import time
import serial
import subprocess
import os

class R_sky:
    def __init__(self):
        self.gpio_mag_brake = 14 # 電磁ブレーキのON/OFF
        self.gpio_A_phase = 19 # TLP222A
        self.gpio_B_phase = 26 # TLP222A(2)
        self.gpio_sensor_1 = 2 # R
        self.gpio_sensor_2 = 3 # sky
        self.sleep_time = 0.0005 # [sec]
        self._init_gpio()
        return

    def start_gpio(self, gpio_number):
        gpio_path = "/sys/class/gpio/gpio{0:d}".format(gpio_number) # dは整数の頭文字
        if not os.path.exists(gpio_path):
            try:
                with open("/sys/class/gpio/export", "w") as f:
                    f.write(str(gpio_number))
                time.sleep(0.1)
                direction_path = f"/sys/class/gpio/gpio{gpio_number}/direction"
                with open(direction_path, "w") as f:
                    f.write("out")
                return True
            except Exception as e:
                print(f"Failed to export GPIO{gpio_number}: {e}")
                return False
        else:
            return True

    def start_gpio_sensor(self, gpio_number):
        gpio_path = "sys/class/gpio/gpio{0:d}".format(gpio_number)
        if not os.path.exists(gpio_path):
            try:
                with open("/sys/class/gpio/export", "w") as f:
                    f.write(str(gpio_number))
                time.sleep(0.1)
                direction_path = f"/sys/class/gpio/gpio{gpio_number}/direction"
                with open(direction_path, "w") as f:
                    f.write("in")
                return True
            except Exception as e:
                print(f"Failed to export GPIO{gpio_number}: {e}")
                return False
        else:
            return True

    def _init_gpio(self):
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.gpio_mag_brake, GPIO.OUT)
        GPIO.setup(self.gpio_A_phase, GPIO.OUT)
        GPIO.setup(self.gpio_B_phase, GPIO.OUT)
        GPIO.setup(self.gpio_sensor_1, GPIO.IN)
        GPIO.setup(self.gpio_sensor_2, GPIO.IN)
        return True

    def clockwise(self): # 時計回りに1step回転
        GPIO.output(self.gpio_A_phase, GPIO.HIGH); time.sleep(self.sleep_time)
        GPIO.output(self.gpio_B_phase, GPIO.HIGH); time.sleep(self.sleep_time)
        GPIO.output(self.gpio_A_phase, GPIO.LOW); time.sleep(self.sleep_time)
        GPIO.output(self.gpio_B_phase, GPIO.LOW); time.sleep(self.sleep_time)

    def counterclockwise(self): # 半時計回りに1step回転
        GPIO.output(self.gpio_B_phase, GPIO.HIGH); time.sleep(self.sleep_time)
        GPIO.output(self.gpio_A_phase, GPIO.HIGH); time.sleep(self.sleep_time)
        GPIO.output(self.gpio_B_phase, GPIO.LOW); time.sleep(self.sleep_time)
        GPIO.output(self.gpio_A_phase, GPIO.LOW); time.sleep(self.sleep_time)

    def move_sky2r(self):
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            GPIO.output(self.gpio_mag_brake, 1); time.sleep(0.25)

            for i in range(1250):
                sts = GPIO.input(self.gpio_sensor_1)
                if sts == 0:
                    print(i+1)
                    self.clockwise()
                    continue
                elif sts == 1:
                    print("Already R")
                    break

            GPIO.output(self.gpio_mag_brake, 0); time.sleep(0.25)
            print("MOVE-R: Complete")
            GPIO.cleanup()

            return True

        except KeyboardInterrupt:
            print("MOVE-R: Failed")
            GPIO.cleanup()

            return False

    def move_r2sky(self):
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            GPIO.output(self.gpio_mag_brake, 1); time.sleep(0.25)

            for i in range(1250):
                sts = GPIO.input(self.gpio_sensor_2)
                if sts == 0:
                    print(-(i+1))
                    self.counterclockwise()
                    continue
                elif sts == 1:
                    print("Already SKY")
                    break

            GPIO.output(self.gpio_mag_brake, 0); time.sleep(0.25)

            print("MOVE-SKY: Complete")
            GPIO.cleanup()

            return True

        except KeyboardInterrupt:
            print("MOVE-R: Failed")
            GPIO.cleanup()

            return False

    def get_status(self): # 位置判別(stsはstatus)
        sts_1 = GPIO.input(self.gpio_sensor_1) # R
        sts_2 = GPIO.input(self.gpio_sensor_2) # sky

        if sts_1 == 0: # RセンサーがRを見ている状態
            print("R")
        elif sts_2 == 0: # skyセンサーがskyを見ている状態
            print("SKY")
        else:
            print("NONE")
        return

    def move_clockwise(self, count): # Manual mode
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            GPIO.output(self.gpio_mag_brake, 1); time.sleep(0.25)

            for i in range(count):
                print(round(-(i+1)/10, 1))
                self.clockwise()

            time.sleep(0.25); GPIO.output(self.gpio_mag_brake, 0)

            print("ClockWise %s: Complete"%count)
            GPIO.cleanup()

            return True

        except KeyboardInterrupt:
            print("ClockWise %s: Failed"%count)
            GPIO.cleanup()

            return False

    def move_counterclockwise(self, count): # Manual mode
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            GPIO.output(self.gpio_mag_brake, 1); time.sleep(0.25)

            count = abs(count)

            for i in range(count):
                print(round(-(i+1)/10, 1))
                self.counterclockwise()

            time.sleep(0.25); GPIO.output(self.gpio_mag_brake, 0)

            print("CounterClockWise -%s: Complete"%count)
            GPIO.cleanup()
            return True

        except KeyboardInterrupt:
            print("ClockWise -%s: Failed" %count)
            GPIO.cleanup()
            return False