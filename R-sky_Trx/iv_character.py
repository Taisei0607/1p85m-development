import time
import csv
import datetime
import logging
import sys
import os
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from Keithley2450 import Keithley2450

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

K2450_IP = "10.167.197.221"
K2450_PORT = 5025
DEFAULT_CURRENT_COMPLIANCE = 50e-3 # 50mA

DEFAULT_V_MIN_MV = -10.0
DEFAULT_V_MAX_MV = 10.0
DEFAULT_V_STEP_MV = 0.1
WAIT_AFTER_BIAS_SET = 0.01
DEFAULT_LO_FREQ_GHZ = 230.0
DEFAULT_LO_POWER_UA = 0.0

SAVE_DIR_BASE = Path("/home/sumikoshiko/Desktop")
timestamp_day = datetime.datetime.now().strftime("%Y%m%d")
timestamp_time = datetime.datetime.now().strftime("%H%M%S")
OUTPUT_DIR = SAVE_DIR_BASE/timestamp_day
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_CSV = OUTPUT_DIR/f"iv_curve_{timestamp_day}_{timestamp_time}.csv"
OUTPUT_PNG = OUTPUT_DIR/f"iv_curve_{timestamp_day}_{timestamp_time}.png"
LOG_FILE = OUTPUT_DIR/f"iv_curve_{timestamp_day}_{timestamp_time}.log"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()])
log = logging.getLogger(__name__)

def plot_iv(csv_path: Path, output_png_path: Path, lo_freq: float = None):
    log.info("I-Vのグラフを作成中")
    df = pd.read_csv(csv_path)

    bias_mv = df["bias_V"]*1000.0
    current_ua = df["current_A"]*1e6

    fig, ax = plt.subplots(figsize=(8, 6))

    title_str = "I-V Characteristic"
    if lo_freq is not None:
        title_str += f"(LO: {lo_freq:.1f} GHz)"

    ax.plot(bias_mv, current_ua, color="r", linewidth=1.5, marker="o", markersize=3, label="I-V Curve")
    ax.axhline(0, color="black", linestyle="--", linewidth=0.8, alpha=0.7)
    ax.axvline(0, color="black", linestyle="--", linewidth=0.8, alpha=0.7)
    ax.set_title(f"{title_str}, data={timestamp_day}-{timestamp_time}", fontsize=15, fontweight="bold", pad=12)
    ax.set_xlabel("Bias Voltage (mV)", fontsize=14)
    ax.set_ylabel("Current (μA)", fontsize=14)
    ax.tick_params(axis="both", labelsize=12)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(fontsize=12, loc="upper left")
    plt.tight_layout()
    plt.savefig(output_png_path, dpi=300, bbox_inches="tight")
    log.info(f"プロット画像を保存しました: {output_png_path}")
    plt.show()
    plt.close(fig)

def run_measurement():
    try:
        lo_f_in = input(f"LO周波数 [GHz] (Enterでデフォルト {DEFAULT_LO_FREQ_GHZ:.1f}): ").strip()
        lo_freq_ghz = float(lo_f_in) if lo_f_in else DEFAULT_LO_FREQ_GHZ

        lo_p_in = input(f"LOパワー [μA] (Enterでデフォルト {DEFAULT_LO_POWER_UA:.1f}): ").strip()
        lo_pwr_ua = float(lo_p_in) if lo_p_in else DEFAULT_LO_POWER_UA

        v_min_in = input(f"バイアス電圧の最小値 [mV] (Enterでデフォルト {DEFAULT_V_MIN_MV:.2f}): ").strip()
        v_min_mv = float(v_min_in) if v_min_in else DEFAULT_V_MIN_MV

        v_max_in = input(f"バイアス電圧の最大値 [mV] (Enterでデフォルト {DEFAULT_V_MAX_MV:.2f}): ").strip()
        v_max_mv = float(v_max_in) if v_max_in else DEFAULT_V_MAX_MV

        v_step_in = input(f"バイアス電圧のステップ間隔 [mV] (Enterでデフォルト {DEFAULT_V_STEP_MV:.2f}): ").strip()
        v_step_mv = float(v_step_in) if v_step_in else DEFAULT_V_STEP_MV

    except ValueError:
        print("入力エラーが発生しました。数値で入力してください。")
        sys.exit(1)

    SCALE = 10000
    start_int = int(round(v_min_mv*SCALE))
    stop_int = int(round(v_max_mv*SCALE))
    step_int = int(round(v_step_mv*SCALE))

    if start_int > stop_int:
        print("エラー: 最小電圧が最大電圧より大きく設定されています。")
        sys.exit(1)
    if step_int <= 0:
        print("エラー: ステップ間隔は0より大きい値を指定してください。")
        sys.exit(1)

    bias_voltages_mv = [round(v/SCALE, 4) for v in range(start_int, stop_int+1, step_int)]
    bias_voltages = [mv/1000.0 for mv in bias_voltages_mv]

    log.info("測定設定パラメータ")
    log.info(f"バイアス範囲: {v_min_mv:.2f} mV ～ {v_max_mv:.2f} mV (間隔: {v_step_mv:.2f} mV, 全 {len(bias_voltages)} 点)")
    log.info(f"LO設定: {lo_freq_ghz:.1f} GHz, {lo_pwr_ua:.2f} μA")

    k2450 = None
    results = []
    csv_fields = ["datetime", "bias_V", "current_A", "LO_freq_GHz", "LO_power_uA"]

    try:
        log.info("Keithley2450を初期化中")
        k2450 = Keithley2450(K2450_IP, K2450_PORT)
        k2450.reset()
        k2450.setup_voltage_source(DEFAULT_CURRENT_COMPLIANCE)

        k2450.output_on()
        log.info("K2450の出力 ON")

        for idx, v_bias in enumerate(bias_voltages):
            k2450.set_voltage(v_bias)
            time.sleep(WAIT_AFTER_BIAS_SET)
            current = k2450.measure_current()

            log.info(f"[{idx+1:03d}/{len(bias_voltages)}] V = {v_bias*1000:>7.2f} mV  -->  I = {current*1e6:>8.3f} μA ({current*1e3:>8.4f} mA)")

            results.append({"datetime": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "bias_V": v_bias, "current_A": current, "LO_freq_GHz": lo_freq_ghz, "LO_power_uA": lo_pwr_ua})

    except KeyboardInterrupt:
        log.warning("ユーザーによって測定が中断されました。")
    except Exception as e:
        log.error(f"測定中にエラーが発生しました: {e}")
    finally:
        if k2450:
            k2450.close()

    if results:
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=csv_fields)
            writer.writeheader()
            writer.writerows(results)
        log.info(f"\n測定結果を保存しました: {OUTPUT_CSV}")

        plot_iv(OUTPUT_CSV, OUTPUT_PNG, lo_freq=lo_freq_ghz)

if __name__ == "__main__":
    run_measurement()