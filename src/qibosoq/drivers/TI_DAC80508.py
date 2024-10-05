import spidev


DACS = [0, 1, 2, 3, 4, 5, 6, 7]
MAX_VOLTAGE = 1.5 # V

class DAC80508:
    def __init__(self):
        self.spi = spidev.SpiDev()
        self.spi.open(1, 0)
        self.spi.mode = 0
        self.spi.max_speed_hz = 500000

        to_send = [0x04, 0x00, 0xff] # All gains set x2
        self.spi.xfer(to_send)

        # Set all dacs to 0V
        for dac in DACS:
            to_send = [0x08+dac, 0x80, 0x00]
            self.spi.xfer(to_send)

    def set_bias(self, dac:int, bias: float):
        if not dac in DACS:
            raise ValueError(f"dac should be any of {DACS}")
        if abs(bias) > MAX_VOLTAGE:
          raise ValueError(f"Bias values should be between -{MAX_VOLTAGE} and {MAX_VOLTAGE} V")
        
        register_value = int(bias * (0xffff - 0x8000) / 2.5000) + 0x8000     
        high_byte = (register_value & 0xff00) >> 8
        low_byte  = (register_value & 0x00ff)
        to_send = [0x08+dac, high_byte, low_byte]
        self.spi.xfer(to_send)