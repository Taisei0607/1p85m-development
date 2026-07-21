import time
import csv
import datetime
import logging
import math
import sys
from pathlib import Path
try:
    from R_sky import R_sky
    from PowerSensor import PowerSensor
    from Keithley2450 import Keithley2450
except ImportError as e:
    print(f"エラー: モジュールのインポートに失敗しました ({e})")
    sys.exit(1)

# Keithley2450の接続設定
K2450_IP = "10.167.197.221"
K2450_PORT = 5025 # SCPIのTCPポート
# バイアス電圧リスト[mV]
BIAS_VOLTAGES_MV = [round(v*0.1, 1) for v in range(0, 100)]
BIAS_VOLTAGES = [mv/1000.0 for mv in BIAS_VOLTAGES_MV]
# 電流コンプライアンス[A]
CURRENT_COMPLIANCE = 100e-3 # 100mA(電流の上限値)
# MA24126Aパワーセンサ設定
MA24126A_PORT = "/dev/ttyACM0"
MA24126A_FREQ_GHZ = 10.0 # 測定周波数[GHz]
MA24126A_AVG_COUNT = 3 # 各ポイントでのパワー測定・平均回数
# LO設定(記録用)
LO_FREQ_GHZ = 10.0 # LO周波数[GHz]
LO_POWER_UA = 0.0 # LOパワー[μA]
# 黒体温度[K]
T_COLD = 77.0 # 液体窒素温度(Sky)
T_HOT = 293.15 # 室温(R)
# 待機時間設定[秒]
WAIT_AFTER_BIAS_SET = 0.01 # バイアス設定後の安定待ち時間
WAIT_AFTER_CHOPPER_MOVE = 0.5 # チョッパー切り替え後の安定待ち時間
# 出力ファイル設定
SAVE_DIR_BASE = Path("/home/sumikoshiko/Desktop")
timestamp_day = datetime.datetime.now().strftime("%Y%m%d")
timestamp_time = datetime.datetime.now().strftime("%H%M%S")
OUTPUT_DIR = SAVE_DIR_BASE/timestamp_day
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_CSV = OUTPUT_DIR/f"noise_temp_{timestamp_day}_{timestamp_time}.csv"
LOG_FILE = OUTPUT_DIR/f"noise_temp_{timestamp_day}_{timestamp_time}.log"
# ログの見た目を整えてINFO以上のメッセージをターミナル画面への表示とファイルへの保存の双方へ同時に出力させる
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()])
log = logging.getLogger(__name__)

def measure_power_avg(sensor: PowerSensor, avg_count: int):
    """PowerSensorからavg_count回取得し、線形平均後にdBm化して返す"""
    mw_values = []
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

def run_measurement():
    print("受信機雑音温度の自動測定開始")

    try:
        t_hot_input = input(f"室温 T_hot [K] (Enterでデフォルト {T_HOT}): ").strip()
        t_hot = float(t_hot_input) if t_hot_input else T_HOT

        lo_f_input = input(f"LO 周波数 [GHz] (Enterでデフォルト {LO_FREQ_GHZ:.4f}): ").strip()
        lo_freq_ghz = float(lo_f_input) if lo_f_input else LO_FREQ_GHZ

        lo_p_input = input(f"LO パワー [μA] (Enterでデフォルト {LO_POWER_UA:.1f}): ").strip()
        lo_pwr_ua = float(lo_p_input) if lo_p_input else LO_POWER_UA

    except ValueError:
        print("入力エラーが発生しました。")
        sys.exit(1)

    log.info("測定パラメータ")
    log.info(f"T_hot = {t_hot} K, T_cold = {T_COLD} K")
    log.info(f"LO: {lo_freq_ghz:.4f} GHz, {lo_pwr_ua:.2f} μA")
    log.info(f"バイアス点数: {len(BIAS_VOLTAGES)} ポイント")

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
        log.info("K2450出力 ON")

        # 電圧ごとにR➔Skyを測定するメインループ
        for idx, v_bias in enumerate(BIAS_VOLTAGES):
            log.info(f"\nバイアス点 [{idx+1}/{len(BIAS_VOLTAGES)}]: {v_bias:.4f} V")
            # 電圧設定
            k2450.set_voltage(v_bias)
            time.sleep(WAIT_AFTER_BIAS_SET)
            current = k2450.measure_current()
            log.info(f"バイアス設定完了(電流: {current*1e3:.4f} mA)")
            # R(Hot)位置へ移動➔測定
            rsky.move_counterclockwise(700)
            time.sleep(WAIT_AFTER_CHOPPER_MOVE)
            P_hot_dbm = measure_power_avg(sensor, MA24126A_AVG_COUNT)
            P_hot_mw = 10**(P_hot_dbm/10.0) if P_hot_dbm is not None else 0.0
            log.info(f"P_hot: {P_hot_dbm:.4f} dBm ({P_hot_mw*1e3:.6f} mW)")
            # Sky(Cold)位置へ移動➔測定
            rsky.move_clockwise(700)
            time.sleep(WAIT_AFTER_CHOPPER_MOVE)
            P_cold_dbm = measure_power_avg(sensor, MA24126A_AVG_COUNT)
            P_cold_mw = 10**(P_cold_dbm/10.0) if P_cold_dbm is not None else 0.0
            log.info(f"P_cold: {P_cold_dbm:.4f} dBm ({P_cold_mw*1e3:.6f} mW)")
            # Y因子&雑音温度計算
            Y, T_rec = calc_noise_temp(P_hot_mw, P_cold_mw, t_hot, T_COLD)
            log.info(f"Y={Y:.4f} | T_rec={T_rec:.2f} K")
            # データ保持
            results.append({
                "datetime": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "bias_V": v_bias,
                "current_A": current,
                "LO_freq_GHz": lo_freq_ghz,
                "LO_power_uA": lo_pwr_ua,
                "T_hot_K": t_hot,
                "T_cold_K": T_COLD,
                "P_hot_dBm": P_hot_dbm,
                "P_hot_mW": P_hot_mw,
                "P_cold_dBm": P_cold_dbm,
                "P_cold_mW": P_cold_mw,
                "Y_factor": Y,
                "T_rec_K": T_rec,
            })

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

def _print_summary(results: list[dict]):
    log.info("測定結果サマリー")
    log.info(f"{'Vbias [V]':>10} {'I [mA]':>10} {'P_hot [dBm]':>12} {'P_cold [dBm]':>13} {'Y':>8} {'Trec [K]':>10}")
    for r in results:
        t_rec_str = f"{r['T_rec_K']:>10.2f}" if not math.isnan(r['T_rec_K']) else "NaN"
        log.info(f"{r['bias_V']:>10.4f} {r['current_A']*1e3:>10.4f}", f"{r['P_hot_dBm']:>12.4f} {r['P_cold_dBm']:>13.4f}", f"{r['Y_factor']:>8.4f} {t_rec_str}")

if __name__ == "__main__":
    run_measurement()