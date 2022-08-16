__all__ = ["BrooksMfcGf"]


import asyncio
from typing import Dict, Any, List
import struct
import serial
import hart_protocol

from yaqd_core import HasLimits, HasPosition, UsesSerial, UsesUart, IsDaemon


class BrooksMfcGf(HasLimits, HasPosition, UsesUart, UsesSerial, IsDaemon):
    _kind = "brooks-mfc-gf"

    def __init__(self, name, config, config_filepath):
        super().__init__(name, config, config_filepath)
        # Perform any unique initialization
        self._ser = serial.Serial(self._config["serial_port"], self._config["baud_rate"], timeout = 0.1)
        self._ser.tag = hart_protocol.tools.pack_ascii(self._config["tag"][-8:])
        self._ser.address = int(self._config["address"])
        self._ser.parity = self._config["parity"]
        self._ser.stop_bits = self._config["stop_bits"]


    def get_position(self):
        self._ser.write(hart_protocol.universal.read_primary_variable(self._ser.address))

        unpacker = hart_protocol.Unpacker(self._ser)
        for msg in unpacker:
            print(msg.primary_variable)
            break

        return(msg.primary_variable)


    def _set_position(self, position):
        units_code = 250 # sets units of decimal or position to be in the same units as the flow
     
        # setting a command not defined in hart_protocol
        data = struct.pack(">Bf", units_code, position)
        command = hart_protocol.tools.pack_command(address=self._ser.address, command_id=236, data=data)
        self._ser.write(command)
     
        unpacker = hart_protocol.Unpacker(self._ser)    
        for i in unpacker:
           (percent_unit, percent, flow_unit, flow) = struct.unpack_from(">BfBf", i.data)
           break
    
        return percent_unit, percent, flow_unit, flow


    def direct_serial_write(self, _bytes):
        raise NotImplementedError


    async def update_state(self):
        """Continually monitor and update the current daemon state."""
        # If there is no state to monitor continuously, delete this function
        while True:
            # Perform any updates to internal state
            self._busy = False
            # There must be at least one `await` in this loop
            # This one waits for something to trigger the "busy" state
            # (Setting `self._busy = True)
            # Otherwise, you can simply `await asyncio.sleep(0.01)`
            await self._busy_sig.wait()

