__all__ = ["BrooksMfcGf"]


import asyncio
from typing import Dict, Any, List
import struct
import serial  # type: ignore

from yaqd_core import HasLimits, HasPosition, UsesSerial, UsesUart, IsDaemon
import hart_protocol

from ._dispatcher import HartDispatcher


class BrooksMfcGf(HasLimits, HasPosition, UsesUart, UsesSerial, IsDaemon):
    _kind = "brooks-mfc-gf"

    hart_dispatchers: Dict[str, HartDispatcher] = {}

    def __init__(self, name, config, config_filepath):
        super().__init__(name, config, config_filepath)
        if config["serial_port"] in BrooksMfcGf.hart_dispatchers:
            self._ser = BrooksMfcGf.hart_dispatchers[config["serial_port"]]
        else:
            self._ser = HartDispatcher(config["serial_port"], baudrate=config["baud_rate"])
            BrooksMfcGf.hart_dispatchers[config["serial_port"]] = self._ser
        self._ser.instances[self._config["address"]] = self

    def close(self):
        self._ser.flush()
        self._ser.close()

    def direct_serial_write(self, _bytes):
        self._ser.write(_bytes)

    def get_position(self):
        return self._state["position"]

    def _process_response(self, msg):
        if msg["command"] == 1:
            self._state["position"] = msg["primary_variable"]

    def _set_position(self, position):
        units_code = 250  # sets units of decimal or position to be in the same units as the flow

        # setting a command not defined in hart_protocol
        data = struct.pack(">Bf", units_code, position)
        command = hart_protocol.tools.pack_command(
            address=self._ser.address, command_id=236, data=data
        )
        self._ser.write(command)

    async def update_state(self):
        while True:
            self._ser.write(hart_protocol.universal.read_primary_variable(self._config["address"]))
            if abs(self._state["position"] - self._state["destination"]) < 1.0:
                self._busy = False
            await asyncio.sleep(0.1)
