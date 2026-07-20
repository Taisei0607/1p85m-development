import time
import datetime
import logging
import math
import sys
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

try:
    from R_sky import R_sky
    from Keithley2450 import Keithley2450
    from Keysight_FieldFox import Keysight_FieldFox
except ImportError as e:
    print(f"エラー: モジュールのインポートに失敗しました ({e})")
    sys.exit(1)

# 機器接続設定
K2450_IP = "10.167.197.221"
K2450_PORT = 5025
FIELDFOX_IP = "192.168.1.100" # FieldFoxのIPアドレス
FIELDFOX_VISA_ADDR = f"TCPIP0::{FIELDFOX_IP}::inst0::INSTR"

# SISバイアス設定
SET_BIAS_V = 0.007 # 測定時の固定バイアス電圧[V](例:7mV)
CURRENT_COMPLIANCE = 100e-3 # 電流コンプライアンス[A]

# FieldFox測定設定
AUTO_SETUP_SPECTRUM = True
CENTER_FREQ_HZ = 8e9 # 中心周波数[Hz](8GHz)
SPAN_HZ = 1.0e9 # スパン[Hz](1.0GHz)
RBW_HZ = 3e6 # RBW[Hz](3MHz)
AVERAGE_COUNT = 10 # アベレージング回数

# 黒体温度[K]
T_COLD = 77.0 # Sky
T_HOT = 293.15 # R

# 出力設定
SAVE_DIR_BASE = Path("/home/sumikoshiko/Desktop")
timestamp_day = datetime.datetime.now().strftime("%Y%m%d")
timestamp_time = datetime.datetime.now().strftime("%H%M%S")
OUTPUT_DIR = SAVE_DIR_BASE/timestamp_day
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_CSV = OUTPUT_DIR/f"noise_temp_spectrum_{timestamp_day}_{timestamp_time}.csv"
OUTPUT_PNG = OUTPUT_DIR/f"noise_temp_spectrum_{timestamp_day}_{timestamp_time}.png"
LOG_FILE = OUTPUT_DIR/f"noise_temp_spectrum_{timestamp_day}_{timestamp_time}.log"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()])
log = logging.getLogger(__name__)

def main():
    log.info("FieldFox_N9938Aによる周波数依存の雑音温度測定開始")

    k2450 = None
    ff = None
    rsky = None

    try:
        log.info("機器初期化中")
        k2450 = Keithley2450(K2450_IP, K2450_PORT)
        k2450.reset()
        k2450.setup_voltage_source(CURRENT_COMPLIANCE)

        ff = Keysight_FieldFox(FIELDFOX_VISA_ADDR)
        if AUTO_SETUP_SPECTRUM:
            ff.setup_spectrum(CENTER_FREQ_HZ, SPAN_HZ, RBW_HZ, AVERAGE_COUNT)

        rsky = R_sky()

        log.info("全機器の初期化完了")

        # バイアス印加
        k2450.set_voltage(SET_BIAS_V)
        k2450.output_on()
        time.sleep(0.5)
        current = k2450.measure_current()
        log.info(f"バイアス電圧: {SET_BIAS_V*1000:.2f} mV (電流: {current*1e6:.2f} uA)")

        # Hot(R)測定
        log.info("Hot(R)位置へ移動中")
        rsky.counterclockwise(700)
        time.sleep(1.0)
        log.info("Hotスペクトルデータ取得中")
        freq_hz, p_hot_dbm = ff.get_trace_data()
        # Cold(Sky)測定
        log.info("Cold(Sky)位置へ移動中")
        rsky.clockwise(700)
        time.sleep(1.0)
        log.info("Coldスペクトルデータ取得中")
        _, p_cold_dbm = ff.get_trace_data()

    except Exception as e:
        log.error(f"測定中にエラーが発生しました: {e}")
        return
    finally:
        if k2450:
            k2450.close()
        if ff:
            ff.close()

    # 計算処理(mW換算->Y-factor->T_rec)
    freq_ghz = [f/1e9 for f in freq_hz]
    p_hot_mw = [10**(p/10.0) for p in p_hot_dbm]
    p_cold_mw = [10**(p/10.0) for p in p_cold_dbm]
    y_factors = []
    t_rec_list = []

    for phot, pcold in zip(p_hot_mw, p_cold_mw):
        if pcold > 0:
            y = phot/pcold
            y_factors.append(y)
            t_rec = (T_HOT-y*T_COLD)/(y-1.0) if y > 1.0 else float('nan')
            t_rec_list.append(t_rec)
        else:
            y_factors.append(float('nan'))
            t_rec_list.append(float('nan'))

    # データ保存
    df = pd.DataFrame({"Freq_GHz": freq_ghz, "P_hot_dBm": p_hot_dbm, "P_cold_dBm": p_cold_dbm, "Y_factor": y_factors, "T_rec_K": t_rec_list})
    df.to_csv(OUTPUT_CSV, index=False)
    log.info(f"データ保存完了: {OUTPUT_CSV}")

    fig, ax1 = plt.subplots(figsize=(10, 8))

    line1 = ax1.plot(freq_ghz, p_hot_dbm, color="r", label="P_hot(R)")
    ax1.plot(freq_ghz, p_cold_dbm, color="b", label="P_cold(Sky)")
    ax1.set_xlabel("IF Frequency (GHz)", fontsize=14)
    ax1.set_ylabel("Power (dBm)", fontsize=14)
    ax1.set_title(f"Receiver IF Spectrum & Noise Temperature (Bias: {SET_BIAS_V*1000:.1f} mV)", fontsize=16)
    ax1.grid(True, linestyle="--", alpha=0.6)

    ax2 = ax1.twinx()
    line2 = ax2.plot(freq_ghz, t_rec_list, color="g", linewidth=1.5, label="T_rec (K)")
    ax2.set_ylabel("Noise Temperature (K)", fontsize=14)
    ax2.tick_params(axis="y", labelsize=16)

    lines = [line1, line2]
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc="upper left", frameon=True)
    plt.tight_layout

    valid_trec = [t for t in t_rec_list if not math.isnan(t) and t > 0]
    if valid_trec:
        min_t, max_t = min(valid_trec), max(valid_trec)
        ax1.set_ylim(max(0, min_t*0.8), min(max_t*1.5, min_t*5.0))

    plt.savefig(OUTPUT_PNG, dpi=300)
    log.info(f"プロット画像保存完了: {OUTPUT_PNG}")
    plt.close()

if __name__ == "__main__":
    main()