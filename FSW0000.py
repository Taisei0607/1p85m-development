import time
import serial
import os

class FSW0000(object):

    def __init__(self,port):

        self.ser = serial.Serial(port)

    def query(self,cmd):
        self.ser.write(cmd)
        val = self.ser.readline()
        return val

    def search_usb_port(self):
        for file in os.listdir('/dev'):
            if "tty.usbmodem" in file:
                self.port = '/dev/'+file

    def freq_set(self, freq):
        """
        FREQ : Set CW frequency

        < unit : str : 'GHz','MHz','kHz','Hz' >
            Specify the units of the <freq>.
            'GHz', 'MHz', 'kHz' or 'Hz'. default = 'GHz'

        """
        self.ser.write(b'FREQ %f GHz'%(freq))
        return

    def freq_query(self):
        """
        FREQ? : Query CW frequency
        """
        ret = self.query(b'FREQ?')
        return ret

    def status_query(self):

        ret = self.query(b'STATUS?')
        return ret

    def power_set(self, pow, unit='dBm'):
        """
        POW : Set RF output power
        """
        self.ser.write(b'POW %f'%(pow))
        return

    def power_query(self):
        """
        POW? : Query RF output power
        """
        ret = self.query(b'POW?')
        ret2 = float(ret)
        return ret2

    def output_set(self, output):
        """
        OUTP : Enable/disable RF output

        Examples
        ========
        >>> s.output_set('ON')
        >>> s.output_set(1)
        >>> s.output_set('OFF')
        >>> s.output_set(0)
        """
        self.ser.write(b'OUTP:STAT %s'%(str(output)))
        return

    def output_on(self):
        """
        (Helper method) OUTP : Enable the RF output
        """
        self.ser.write(b'OUTP:STAT ON')
        return

    def output_off(self):
        """
        (Helper method) OUTP : Disable the RF output
        """
        self.ser.write(b'OUTP:STAT OFF')
        return

    def output_query(self):
        """
        OUTP? : Query RF output status
        """
        ret = self.query(b'OUTP:STAT?')
        return ret
