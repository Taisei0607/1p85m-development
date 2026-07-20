import time
import sys
import os
import numpy as np
import matplotlib.pyplot as plt
from R_sky import R_sky
from PowerSensor import PowerSensor

def calculate_trx(p_hot, p_cold, t_hot, t_cold):
    Y = p_hot/p_cold
    if Y <= 1.0:
        print(f"Warning: Y-factor is invalid ({Y:.4f}). P_hot must be larger than P_cold.")
        return None
    t_rx = (t_hot-Y*t_cold)/(Y-1)
    return t_rx

def main():
#   min_frequency = int(input("Minimum Frequency: ")) # minimum is 0.01GHz
#   max_frequency = int(input("Maximum Frequency: ")) # maximum is 26GHz
    T_R = int(input("Temperature of R: ")) # default is 293.15
    T_Sky = int(input("Temperature of Sky: ")) # default is 50.0
    measurement_count = int(input("Measurement Count: "))
#   frequency_range = list(range(min_frequency, max_frequency, 1)) # 0.01GHz~26GHz -> 0.18GHz~468GHz
#   frequency_results = []
    p_hot_w_results = []
    p_cold_w_results = []
    t_rx_results = []
    print("Initializing R-sky controller and PowerSensor.")
    try:
        rsky = R_sky() # R-sky制御用クラスのインスタンス化
        sensor = PowerSensor() # アンリツパワーセンサクラスのインスタンス化
        print("R-Sky controller and Power Sensor is initialized.")
        sensor.get_id()
        sensor.zero_calibration()
        sensor.show_settings()
        rsky.move_clockwise(100)
        rsky.get_status()
        time.sleep(1.0)
        rsky.move_counterclockwise(100)
        rsky.get_status()
    except Exception as e:
        print(f"Initialization failed: {e}")
        sys.exit(1)

    for count in list(range(measurement_count)):
        print(f"Starting Measurement at {count} count.")
        try:
            print("\nMoving to R position.")
#           rsky.move_sky2r()
            rsky.move_counterclockwise(700)
            time.sleep(1.0)
            print("Measuring power at R position.")
            p_hot_dbm = sensor.get_power()
            p_hot_w = 10**(p_hot_dbm/10)/1000
            print(f"P_hot: ({p_hot_w:.3e} W)")

            print("\nMoving to Sky position.")
#           rsky.move_r2sky()
            rsky.move_clockwise(700)
            time.sleep(1.0)
            print("Measuring power at Sky position.")
            p_cold_dbm = sensor.get_power()
            p_cold_w = 10**(p_cold_dbm/10)/1000
            print(f"P_cold: ({p_cold_w:.3e} W)")

            print("\nCalculating Receiver Noise Temperature.")
            y_factor = p_hot_w/p_cold_w
            y_factor_dbm = p_hot_dbm-p_cold_dbm
            t_rx = calculate_trx(p_hot_w, p_cold_w, t_hot=T_R, t_cold=T_Sky)
            if t_rx is not None:
                print(f" Y-Factor : {y_factor:.4f}")
                print(f" T_rx : {t_rx:.2f} K")
                t_rx_results.append(t_rx)
                measurement_count.append(count)
            else:
                print(f"[Error] Invalid Y-factor at {count} count.")

        except KeyboardInterrupt:
            print("\nMeasurement aborted by user.")

    print("\nGenerating plot.")
    timestamp_day = time.strftime('%Y%m%d')
    timestamp_time = time.strftime('%H%M%S')
    save_path = f'/home/sumikoshiko/Desktop/{timestamp_day}'
    if not os.path.exists(save_path):
        os.makedirs(save_path)

    plt.figure(figsize=(8, 5))
    plt.plot(np.linspace(0, measurement_count), t_rx_results, marker='o', linestyle='-', color='b', linewidth=2, label='$T_{rx}$')
    plt.title(f'Trx and Frequency {timestamp_day}_{timestamp_time}¥n{T_R}, {T_Sky}', fontsize=12)
    plt.xlabel('Frequency [GHz]', fontsize=12)
    plt.ylabel('$T_{rx}$ [K]', fontsize=12)
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.legend(fontsize=12)
    plt.ylim(0, max(t_rx_results)*1.2)
    plt.savefig('trx_frequency_profile.png', dpi=300)
    print("Graph saved as 'trx_frequency_profile.png'")
    plt.show()

if __name__ == "__main__":
    main()