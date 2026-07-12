import time
import sys
import numpy as np
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
    print("Initializing R-sky controller and Power Sensor.")
    try:
        rsky = R_sky() # R-sky制御用クラスのインスタンス化
        sensor = PowerSensor() # アンリツパワーセンサクラスのインスタンス化
    except Exception as e:
        print(f"Initialization failed: {e}")
        sys.exit(1)

    T_R = 293.15
    T_Sky = 50.0

    try:
        print("\nMoving to R position.")
        rsky.move_sky2r()
        time.sleep(1.0)
        print("Measuring power at R position.")
        p_hot_dbm = sensor.get_power()
        p_hot_w = 10**(p_hot_dbm/10)/1000
        print(f"P_hot: ({p_hot_w:.3e} W)")

        print("\nMoving to Sky position.")
        rsky.move_r2sky()
        time.sleep(1.0)
        print("Measuring power at Sky position.")
        p_cold_dbm = sensor.get_power()
        p_cold_w = 10**(p_cold_dbm/10)/1000
        print(f"P_cold: ({p_cold_w:.3e} W)")

        print("\nCalculating Receiver Noise Temperature.")
        y_factor = p_hot_w/p_cold_w
        y_factor_db = p_hot_dbm-p_cold_dbm
        t_rx = calculate_trx(p_hot_w, p_cold_w, t_hot=T_R, t_cold=T_Sky)
        if t_rx is not None:
            print(f" Y-Factor : {y_factor:.4f} ({y_factor_db:.3f} dB)")
            print(f" T_rx : {t_rx:.2f} K")

    except KeyboardInterrupt:
        print("\nMeasurement aborted by user.")

if __name__ == "__main__":
    main()