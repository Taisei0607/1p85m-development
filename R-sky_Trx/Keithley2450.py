import time
import logging
import pyvisa

log = logging.getLogger(__name__)

class Keithley2450:
    def __init__(self, ip: str, port: int = 5025):
        rm = pyvisa.ResourceManager('@py')
        resource_str = f"TCPIP0::{ip}::{port}::SOCKET"
        log.info(f"K2450 接続: {resource_str}")
        self.inst = rm.open_resource(resource_str)
        self.inst.read_termination = "\n"
        self.inst.write_termination = "\n"
        self.inst.timeout = 10000

    def reset(self):
        self.inst.write("*RST")
        self.inst.write("*CLS")
        time.sleep(0.5)

    def setup_voltage_source(self, compliance_A: float):
        self.inst.write('SOUR:FUNC VOLT')
        self.inst.write(f'SOUR:VOLT:ILIM {compliance_A}')
        self.inst.write('SENS:FUNC "CURR"')
        self.inst.write('SENS:CURR:RANG:AUTO ON')
        self.inst.write('OUTP:STAT OFF')
        log.info(f"K2450 電圧源設定完了 (コンプライアンス: {compliance_A*1e3:.1f} mA)")

    def set_voltage(self, voltage_V: float):
        self.inst.write(f'SOUR:VOLT {voltage_V}')

    def output_on(self):
        self.inst.write('OUTP:STAT ON')

    def output_off(self):
        try:
            self.inst.write('SOUR:VOLT 0.0')
            self.inst.write('OUTP:STAT OFF')
        except Exception:
            pass

    def measure_current(self):
        resp = self.inst.query('MEAS:CURR?')
        return float(resp.strip())

    def close(self):
        self.output_off()
        try:
            self.inst.close()
        except Exception:
            pass
        log.info("K2450 接続終了")