import time
import csv
import datetime
import logging
import math
import sys
import os
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from R_sky import R_sky
from PowerSensor import PowerSensor
from Keithley2450 import Keithley2450

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

K2450_IP = "10.167.197.221"
K2450_PORT = 5025
CURRENT_COMPLIANCE = 100e-3 # 100mA(電流の上限値)

MA24126A_PORT = "/dev/ttyACM0"
MA24126A_FREQ_GHZ = 13.3
MA24126A_AVG_COUNT = 3

DEFAULT_T_HOT = 293.15
DEFAULT_T_COLD = 77.0
DEFAULT_LO_FREQ_GHZ = 230.0
DEFAULT_LO_POWER_UA = 0.0
DEFAULT_V_MIN_MV = 1.0
DEFAULT_V_MAX_MV = 10.0
DEFAULT_V_STEP_MV = 0.1

WAIT_AFTER_BIAS_SET = 0.01
WAIT_AFTER_CHOPPER_MOVE = 0.5

SAVE_DIR_BASE = Path("/home/sumikoshiko/Desktop")
timestamp_day = datetime.datetime.now().strftime("%Y%m%d")
timestamp_time = datetime.datetime.now().strftime("%H%M%S")
OUTPUT_DIR = SAVE_DIR_BASE/timestamp_day
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_CSV = OUTPUT_DIR/f"Y_factor_{timestamp_day}_{timestamp_time}.csv"
OUTPUT_PNG = OUTPUT_DIR/f"Y_factor_{timestamp_day}_{timestamp_time}.png"
LOG_FILE = OUTPUT_DIR/f"Y_factor_{timestamp_day}_{timestamp_time}.log"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()])
log = logging.getLogger(__name__)

def measure_power_avg(sensor: PowerSensor, avg_count: int):
    mw_values = []
    sensor.start()
    for i in range(avg_count):
        dbm = sensor.get_power()
        if dbm is not None:
            mw_values.append(10**(dbm/10.0))
    if not mw_values:
        return None
    avg_mw = sum(mw_values)/len(mw_values)
    avg_dBm = 10*math.log10(avg_mw)
    return avg_dBm

def calc_noise_temp(P_hot_mW: float, P_cold_mW: float, T_hot: float, T_cold: float) -> tuple[float, float]:
    if P_cold_mW <= 0:
        return float('nan'), float('nan')
    Y = P_hot_mW/P_cold_mW
    if Y <= 1.0:
        return Y, float('nan')
    T_rec = (T_hot-Y*T_cold)/(Y-1.0)
    return Y, T_rec

def plot_results(csv_path: Path, output_png_path: Path):
    log.info("測定結果のグラフにプロット中")
    df = pd.read_csv(csv_path)

    bias_mv = df["bias_V"]*1000.0
    current_ua = df["current_A"]*1e6
    p_hot_dbm = df["P_hot_dBm"]
    p_cold_dbm = df["P_cold_dBm"]
    y_factor = df["Y_factor"]

    lo_freq = df["LO_freq_GHz"].iloc[0] if "LO_freq_GHz" in df.columns else DEFAULT_LO_FREQ_GHZ
    lo_power = df["LO_power_uA"].iloc[0] if "LO_power_uA" in df.columns else DEFAULT_LO_POWER_UA

    fig, ax1 = plt.subplots(figsize=(10, 5))

    line_iv, = ax1.plot(bias_mv, current_ua, color="c", label="Current (uA)")
    ax1.set_xlabel("Bias Voltage (mV)", fontsize=14)
    ax1.set_ylabel("Current (uA)", fontsize=14, color="c")
    ax1.tick_params(axis="y", labelcolor="c", labelsize=12)
    ax1.tick_params(axis="x", labelsize=12)
    ax1.grid(True, linestyle="--", alpha=0.5)

    ax2 = ax1.twinx()
    line_phot, = ax2.plot(bias_mv, p_hot_dbm, color="r", label="P_hot (R)")
    line_pcold, = ax2.plot(bias_mv, p_cold_dbm, color="b", label="P_cold (Sky)")
    ax2.set_ylabel("Power (dBm)", fontsize=14)
    ax2.tick_params(axis="y", labelsize=12)

    ax3 = ax1.twinx()
    ax3.spines["right"].set_position(("axes", 1.15)) # 第3軸を外側に配置
    line_y, = ax3.plot(bias_mv, y_factor, color="g", label="Y-factor")
    ax3.set_ylabel("Y-factor", fontsize=14, color="g")
    ax3.tick_params(axis="y", labelcolor="g", labelsize=12)

    plt.title(f"LO={lo_freq:.0f}GHz, Power={lo_power:.2f}uA, date={timestamp_day}-{timestamp_time}", fontsize=15, pad=15)

    lines = [line_iv, line_phot, line_pcold, line_y]
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc="upper left", frameon=True)
    plt.subplots_adjust(right=0.80) # 第3軸が入る右側の余白スペースを確保
    plt.tight_layout()
    plt.savefig(output_png_path, dpi=300, bbox_inches="tight")
    log.info(f"プロット画像を保存しました: {output_png_path}")
    plt.show()
    plt.close(fig)

def run_measurement():
    try:
        do_cal_in = input("パワーセンサーのキャリブレーションを実行しますか？(y/n): ").strip().lower()
        do_calibration = True if do_cal_in == 'y' else False

        t_hot_in = input(f"室温 T_hot [K] (Enterでデフォルト {DEFAULT_T_HOT:.2f}): ").strip()
        t_hot = float(t_hot_in) if t_hot_in else DEFAULT_T_HOT

        t_cold_in = input(f"Sky温度 T_cold [K] (Enterでデフォルト {DEFAULT_T_COLD:.2f}): ").strip()
        t_cold = float(t_cold_in) if t_cold_in else DEFAULT_T_COLD

        lo_f_in = input(f"LO周波数 [GHz] (Enterでデフォルト {DEFAULT_LO_FREQ_GHZ:.4f}): ").strip()
        lo_freq_ghz = float(lo_f_in) if lo_f_in else DEFAULT_LO_FREQ_GHZ

        lo_p_in = input(f"LO パワー [μA] (Enterでデフォルト {DEFAULT_LO_POWER_UA:.1f}): ").strip()
        lo_pwr_ua = float(lo_p_in) if lo_p_in else DEFAULT_LO_POWER_UA

        v_min_in = input(f"バイアス電圧の最小値 [mV] (Enterでデフォルト {DEFAULT_V_MIN_MV:.1f}): ").strip()
        v_min_mv = float(v_min_in) if v_min_in else DEFAULT_V_MIN_MV

        v_max_in = input(f"バイアス電圧の最大値 [mV] (Enterでデフォルト {DEFAULT_V_MAX_MV:.1f}): ").strip()
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
    log.info(f"キャリブレーション実行: {'はい' if do_calibration else 'いいえ'}")
    log.info(f"T_hot = {t_hot} K, T_cold = {t_cold} K")
    log.info(f"LO: {lo_freq_ghz:.4f} GHz, {lo_pwr_ua:.2f} μA")
    log.info(f"バイアス範囲: {v_min_mv:.2f} mV ～ {v_max_mv:.2f} mV (間隔: {v_step_mv:.2f} mV, 全 {len(bias_voltages)} 点)")

    k2450 = None
    sensor = None
    rsky = None

    try:
        log.info("機器初期化中")
        k2450 = Keithley2450(K2450_IP, K2450_PORT)
        k2450.reset()
        k2450.setup_voltage_source(CURRENT_COMPLIANCE)

        sensor = PowerSensor(port=MA24126A_PORT)
        sensor.initialize(freq_ghz=MA24126A_FREQ_GHZ)

        if do_calibration:
            input("\n[確認]センサーの入力を遮蔽し、Enterキーを押してキャリブレーションを開始してください。")
            log.info("パワーセンサーのゼロ校正を実行中")
            sensor.zero_calibration(show_progress=True)
            log.info("キャリブレーション完了")

        rsky = R_sky()
        rsky.move_counterclockwise(700)
        rsky.move_clockwise(700)

        log.info("全機器の初期化完了")

    except Exception as e:
        log.error(f"初期化中にエラーが発生しました: {e}")
        if k2450:
            k2450.close()
        if sensor:
            sensor.close()
        sys.exit(1)

    csv_fields = ["datetime", "bias_V", "current_A", "LO_freq_GHz", "LO_power_uA", "T_hot_K", "T_cold_K", "P_hot_dBm", "P_hot_mW", "P_cold_dBm", "P_cold_mW", "Y_factor", "T_rec_K"]
    results = []

    try:
        k2450.output_on()
        log.info("K2450の出力 ON")

        for idx, v_bias in enumerate(bias_voltages):
            log.info(f"\nバイアス点 [{idx+1}/{len(bias_voltages)}]: {v_bias:.4f} V ({v_bias*1000:.2f} mV)")

            k2450.set_voltage(v_bias)
            time.sleep(WAIT_AFTER_BIAS_SET)
            current = k2450.measure_current()
            log.info(f"バイアス設定完了(電流: {current*1e3:.4f} mA)")

            rsky.move_counterclockwise(700)
            time.sleep(WAIT_AFTER_CHOPPER_MOVE)
            P_hot_dbm = measure_power_avg(sensor, MA24126A_AVG_COUNT)
            P_hot_mw = 10**(P_hot_dbm/10.0) if P_hot_dbm is not None else 0.0
            log.info(f"P_hot: {P_hot_dbm:.4f} dBm ({P_hot_mw*1e3:.6f} mW)")

            rsky.move_clockwise(700)
            time.sleep(WAIT_AFTER_CHOPPER_MOVE)
            P_cold_dbm = measure_power_avg(sensor, MA24126A_AVG_COUNT)
            P_cold_mw = 10**(P_cold_dbm/10.0) if P_cold_dbm is not None else 0.0
            log.info(f"P_cold: {P_cold_dbm:.4f} dBm ({P_cold_mw*1e3:.6f} mW)")

            Y, T_rec = calc_noise_temp(P_hot_mw, P_cold_mw, t_hot, t_cold)
            log.info(f"Y={Y:.4f} | T_rec={T_rec:.2f} K")

            results.append({"datetime": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "bias_V": v_bias, "current_A": current, "LO_freq_GHz": lo_freq_ghz, "LO_power_uA": lo_pwr_ua, "T_hot_K": t_hot, "T_cold_K": t_cold, "P_hot_dBm": P_hot_dbm, "P_hot_mW": P_hot_mw, "P_cold_dBm": P_cold_dbm, "P_cold_mW": P_cold_mw, "Y_factor": Y, "T_rec_K": T_rec})

    except KeyboardInterrupt:
        log.warning("ユーザーによって測定が中断されました。")
    except Exception as e:
        log.error(f"測定中にエラーが発生しました: {e}")
    finally:
        if k2450:
            k2450.close()
        if sensor:
            sensor.close()
        log.info("機器接続を終了しました。")

    if results:
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=csv_fields)
            writer.writeheader()
            writer.writerows(results)
        log.info(f"\n測定を完了して結果を保存しました: {OUTPUT_CSV}")

        _print_summary(results)

        plot_results(OUTPUT_CSV, OUTPUT_PNG)

def _print_summary(results: list[dict]):
    log.info("測定結果サマリー")
    log.info(f"{'Vbias [V]':>10} {'I [mA]':>10} {'P_hot [dBm]':>12} {'P_cold [dBm]':>13} {'Y':>8} {'Trec [K]':>10}")
    for r in results:
        t_rec_str = f"{r['T_rec_K']:>10.2f}" if not math.isnan(r['T_rec_K']) else "NaN"
        log.info(f"{r['bias_V']:>10.4f} {r['current_A']*1e3:>10.4f} {r['P_hot_dBm']:>12.4f} {r['P_cold_dBm']:>13.4f} {r['Y_factor']:>8.4f} {t_rec_str}")

if __name__ == "__main__":
    run_measurement()