import socket
import logging
import pyvisa
import csv
import time
import numpy as np

log = logging.getLogger(__name__)

class Keysight_FieldFox:
    def __init__(self, resource_name: str, timeout_ms: int = 20000):
        """PyVISAリソースを開き接続を初期化, :param resource_name: TCPIP0::<IP>::inst0::INSTR形式のVISAアドレス, :param timeout_ms: タイムアウト時間[ms](アベレージ待ちを考慮して長めに設定)"""
        self.rm = pyvisa.ResourceManager()
        try:
            self.inst = self.rm.open_resource(resource_name)
            self.inst.timeout = timeout_ms
            if "SOCKET" in resource_name:
                self.inst.read_termination = "\n"
                self.inst.write_termination = "\n"
            idn = self.inst.query("*IDN?").strip()
            log.info(f"Keysight_FieldFoxへの接続成功: {idn}")
        except Exception as e:
            log.error(f"Keysight_FieldFoxへの接続に失敗しました: {e}")
            raise

    def setup_spectrum(self, center_hz: float, span_hz: float, rbw_hz: float, avg_count: int = 10):
        """スペクトラムアナライザモードの基本条件設定"""
        self.inst.write(":INST:SEL 'SA'") # SA(Spectrum Analyzer)モードに切り替え
        self.inst.write(f":FREQ:CENT {center_hz}")
        self.inst.write(f":FREQ:SPAN {span_hz}")
        self.inst.write(f":BAND {rbw_hz}")
        self.inst.write(":DET:FUNC AVERAGE") # 検出器: RMS Average
        self.inst.write(f":AVER:COUN {avg_count}") # アベレージング回数
        self.inst.write(":AVER:TYPE POW") # パワー平均化
        self.inst.write(":AVER:CLE") # アベレージクリア
        log.info(f"Keysight_FieldFoxの設定完了(Center: {center_hz/1e9:.3f} GHz, Span: {span_hz/1e6:.1f} MHz, Avg: {avg_count})")

    def get_trace_data(self) -> tuple[list[float], list[float]]:
        """アベレージング完了を待ってトレースデータを取得 :return:(周波数[Hz]のリスト, パワー[dBm]のリスト)"""
        # シングルスイープモードで測定開始し、完了を待つ
        self.inst.write(":AVER:CLE")
        self.inst.write(":INIT:CONT OFF") # シングルスィープ化
        self.inst.write(":INIT:IMM") # 測定実行
        self.inst.query("*OPC?") # Operation Complete待ち
        # 周波数軸データの生成
        start_freq = float(self.inst.query(":FREQ:STAR?"))
        stop_freq = float(self.inst.query(":FREQ:STOP?"))
        # トレースデータ(dBm)取得
        raw_data = self.inst.query(":TRAC:DATA?")
        power_dbm_list = [float(x) for x in raw_data.strip().split(",")]

        num_points = len(power_dbm_list)
        step = (stop_freq-start_freq)/(num_points-1)
        freq_hz_list = [start_freq+i*step for i in range(num_points)]

        self.inst.write(":INIT:CONT ON") # 連続測定に戻す
        return freq_hz_list, power_dbm_list

    def close(self):
        if hasattr(self, "inst") and self.inst:
            self.inst.close()
            log.info("接続を切断しました。")

class FieldFox_Trace:
    def __init__(self, ip, port=5025, timeout=10.0):
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.sock = None
        self.connect()

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect((self.ip, self.port))
        print(f"Connected to FieldFox at {self.ip}")

    def write(self, cmd):
        msg = (cmd.strip() + "\n").encode('utf-8')
        self.sock.sendall(msg)
        time.sleep(0.05)

    def query(self, cmd):
        self.write(cmd)
        time.sleep(0.2)
        data = b""
        while True:
            try:
                chunk = self.sock.recv(16384)
                if not chunk:
                    break
                data += chunk
                # 改行コードが到達したら受信完了
                if b"\n" in chunk or b"\r" in chunk:
                    break
            except socket.timeout:
                break
        return data.decode('utf-8', errors='ignore').strip()

    def close(self):
        if self.sock:
            self.sock.close()

    def setup_sa(self, start_freq_ghz, stop_freq_ghz, sweep_points=401):
        self.write(':INSTrument:SELect "SA"')
        time.sleep(1.0)
        self.write(f':SENSe:FREQuency:STARt {start_freq_ghz:.6f}GHz')
        self.write(f':SENSe:FREQuency:STOP {stop_freq_ghz:.6f}GHz')
        self.write(f':SENSe:SWEep:POINts {sweep_points}')
        # データフォーマット指定
        self.write(':FORMat:DATA ASCii')
        time.sleep(0.5)

    def get_trace_data(self):
        start_f = float(self.query(':SENSe:FREQuency:STARt?')) / 1e9
        stop_f = float(self.query(':SENSe:FREQuency:STOP?')) / 1e9
        points = int(self.query(':SENSe:SWEep:POINts?'))
        freqs = np.linspace(start_f, stop_f, points)

        raw_data = self.query(':CALCulate:DATA?')

        if not raw_data:
            raw_data = self.query(':CALCulate:TRACe1:DATA?')

        if not raw_data:
            raw_data = self.query(':TRACe:DATA?')

        print(f"DEBUG: raw_data length = {len(raw_data)}")

        if not raw_data:
            raise ValueError("FieldFoxからトレースデータを受信できませんでした。")

        amps_list = []
        for val in raw_data.split(','):
            val_str = val.strip()
            if val_str:
                try:
                    amps_list.append(float(val_str))
                except ValueError:
                    pass

        amps = np.array(amps_list)
        return freqs, amps