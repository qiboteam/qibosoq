import spidev

class TIDAC80508:
    def __init__(self):
        self.spi = spidev.SpiDev()
        self.spi.open(1, 0)
        to_send = [0x04, 0x00, 0x0f] # All gains set x2
        self.spi.xfer(to_send)
        to_send = [0x08, 0x80, 0x2b] # Initialize DAC0
        self.spi.xfer(to_send)
        to_send = [0x09, 0x80, 0x44] # Initialize DAC1
        self.spi.xfer(to_send)
        to_send = [0x0a, 0x80, 0x41] # Initialize DAC2
        self.spi.xfer(to_send)
        to_send = [0x0b, 0x7f, 0xc9] # Initialize DAC3
        self.spi.xfer(to_send)

    def set_bias(self, dac, bias_value: float):
        if abs(bias_value) > 1.:
           raise ValueError("Bias values should be between -1 and 1")
        if dac==0:
            register_value = int(bias_value * (0xffff - 0x802b) / 2.4934) + 0x802b
            dest = 0x08
        elif dac==1:
            register_value = int(bias_value * (0xffff - 0x8044) / 2.4854) + 0x8044
            dest = 0x09
        elif dac==2:
            register_value = int(bias_value * (0xffff - 0x8041) / 2.4857) + 0x8041
            dest = 0x0a
        elif dac==3:
            register_value = int(bias_value * (0xffff - 0x7fc9) / 2.5002) + 0x7fc9
            dest = 0x0b
        high_byte = (register_value & 0xff00) >> 8
        low_byte  = (register_value & 0x00ff)
        to_send = [dest, high_byte, low_byte]
        self.spi.xfer(to_send)
