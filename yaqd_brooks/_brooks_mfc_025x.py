__all__ = ["BrooksMfc025x"]


import asyncio
from dataclasses import dataclass
from typing import Dict, Any, List
import struct
import serial  # type: ignore
import math
import numpy as np

from yaqd_core import (
    HasTransformedPosition,
    HasLimits,
    HasPosition,
    UsesSerial,
    UsesUart,
    IsDaemon,
    aserial,
)


parameters = {"SP Rate": 1, "SP Full Scale": 9}


@dataclass
class Response:
    predelimiter: str
    address: int
    port: int
    non_resetable_totalizer_value: float
    totalizer_value: float
    value: float
    checksum: bytes
    checksum_valid: bool


def parse_response(raw: bytes) -> Response:
    string = raw.decode().strip()
    lis = string.split(",")
    address, port = lis[1].split(".")
    checksum = lis[14]
    # TODO CHECKSUM
    return Response(
        predelimiter=lis[0],
        address=int(address),
        port=int(port),
        non_resetable_totalizer_value=float(lis[4]),
        totalizer_value=float(lis[5]),
        value=float(lis[7]),
        checksum=checksum.encode(),
        checksum_valid=True,
    )


parity_options = {"even": serial.PARITY_EVEN, "odd": serial.PARITY_ODD, "none": serial.PARITY_NONE}

stop_bit_options = {"one": 1, "one_and_half": 1.5, "two": 2}


class BrooksMfc025x(
    HasTransformedPosition, HasLimits, HasPosition, UsesUart, UsesSerial, IsDaemon
):
    _kind = "brooks-mfc-025x"

    def __init__(self, name, config, config_filepath):
        super().__init__(name, config, config_filepath)
        self._ser = aserial.get_aserial(
            config["serial_port"],  # magically ensures single instance per port
            baudrate=config["baud_rate"],
            parity=parity_options[config["parity"]],
            stopbits=stop_bit_options[config["stop_bits"]],
        )
        self._units = "ml/min"
        self._native_units = "ml/min"

    def close(self):
        self._ser.flush()
        self._ser.close()

    def direct_serial_write(self, _bytes):
        self._ser.write(_bytes)

    def get_position(self):
        return self.to_transformed(self._state["position"])

    def _relative_to_transformed(self, relative_position):
        xp = [p["setpoint"] for p in self._config["calibration"]]
        fp = [p["measured"] for p in self._config["calibration"]]
        out = np.interp(relative_position, xp, fp)
        return out

    def _set_position(self, position):
        address = self._config["address"]
        port = self._config["physical_port"] * 2
        parameter = parameters["SP Rate"]
        command = "AZ"
        if address:
            command += f"{address:05}"
   	command += f".{port:02}P{parameter:02}={position:.2f}\r\n"
        self._ser.write(command.encode())

    def _transformed_to_relative(self, transformed_position):
        xp = [p["measured"] for p in self._config["calibration"]]
        fp = [p["setpoint"] for p in self._config["calibration"]]
        return np.interp(transformed_position, xp, fp)

    async def update_state(self):
        while True:
            # construct command
            address = self._config["address"]
            port = (self._config["physical port"] * 2) - 1
            command = "AZ"
            if address:
                command += f"{address:05}"
            command += f".{port:02}K\r\n"
            # send and recieve
            async with self._ser._readlock:
                self._ser.reset_input_buffer()
                self._ser.reset_output_buffer()
                raw = await self._ser._awrite_then_readline(command.encode())
            # parse response
            response = parse_response(raw)
            if response.parameter == parameters["SP Rate"]:
                self._state["position"] = response.value
            if abs(self._state["position"] - self._state["destination"]) < 1.0:
                self._busy = False
            if self._state["destination"] == 0.0:
                if self._state["position"] < 1.0:
                    self._busy = False
            await asyncio.sleep(0.25)
