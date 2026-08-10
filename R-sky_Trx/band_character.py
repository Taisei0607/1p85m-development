import socket
import numpy as np
import matplotlib.pyplot as plt
import csv
import time
import os
from datetime import datetime
from pathlib import Path
from Keysight_FieldFox import FieldFox_Trace

if __name__ == "__main__":
    IP_ADDRESS = "10.167.196.7"
    SAVE_DIR_BASE = Path("/home/sumikoshiko/Desktop")
    timestamp_day = datetime.now().strftime("%Y%m%d")
    timestamp_time = datetime.now().strftime("%H%M%S")
    OUTPUT_DIR = SAVE_DIR_BASE/timestamp_day
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_filename = os.path.join(OUTPUT_DIR, f"band_character_{timestamp_day}_{timestamp_time}.csv")
    fig_filename = os.path.join(OUTPUT_DIR, f"band_character_{timestamp_day}_{timestamp_time}.png")
    ff = FieldFox_Trace(ip=IP_ADDRESS)

    try:
        start_freq = int(input("Min frequency: ").strip())
        stop_freq = int(input("Max frequency: ").strip())
        points = int(input("Number of points: ").strip())
        print("FieldFoxを初期設定中")
        ff.setup_sa(start_freq_ghz=start_freq, stop_freq_ghz=stop_freq, sweep_points=points)
        time.sleep(1.0)
        print("トレースデータを取得中")
        freqs, amps = ff.get_trace_data()

        with open(csv_filename, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Frequency (GHz)", "Power (dBm)"])
            for f_val, a_val in zip(freqs, amps):
                writer.writerow([f_val, a_val])
        print(f"データを{csv_filename}に保存しました")

        plt.figure(figsize=(8, 5))
        plt.plot(freqs, amps, color="blue", linewidth=1.5, label="IF_Band_Character")
        plt.title(f"Frequency_Response_{timestamp_day}_{timestamp_time}")
        plt.xlabel("Frequency [GHz]")
        plt.ylabel("Power [dBm]")
        plt.grid(True)
        plt.legend()
        plt.tight_layout()
        plt.savefig(fig_filename, dpi=300)
        print(f"グラフ画像を{fig_filename}に保存しました")
        plt.show()
        plt.close()

    finally:
        ff.close()