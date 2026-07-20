import logging
import pyvisa

log = logging.getLogger(__name__)

class Keysight_FieldFox:
    """KeysightのFieldFox(N9938A)用のSCPI通信クラス"""
    def __init__(self, resource_name: str, timeout_ms: int = 20000):
        """PyVISAリソースを開き接続を初期化, :param resource_name: TCPIP0::<IP>::inst0::INSTR形式のVISAアドレス, :param timeout_ms: タイムアウト時間[ms](アベレージ待ちを考慮して長めに設定)"""
        self.rm = pyvisa.ResourceManager()
        try:
            self.inst = self.rm.open_resource(resource_name)
            self.inst.timeout = timeout_ms
            idn = self.inst.query("*IDN?").strip()
            log.info(f"Keysight_FieldFoxへの接続成功: {idn}")
        except Exception as e:
            log.error(f"Keysight_FieldFoxへの接続に失敗しました: {e}")
            raise

    def setup_spectrum(self, center_hz: float, span_hz: float, rbw_hz: float, avg_count: int = 10):
        """スペクトラムアナライザモードの基本条件設定"""
        self.inst.write(":INST:SEL 'SA'") # SA(Spectrum Analyzer)モードに切り替え
        self.inst.write(f":FREQ:CENT {center_hz}") # 中心周波数
        self.inst.write(f":FREQ:SPAN {span_hz}") # スパン
        self.inst.write(f":BAND {rbw_hz}") # RBW
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