__all__ = ["BrooksMfc025x"]


import time
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

from ._dispatcher import WriteQueueItem, SerialWriteQueue

parameters = {"SP Rate": 1, "SP Full Scale": 9}


def is_valid_checksum(raw):
    string = raw.decode().strip()
    lis = string.split(",")
    information_frame = "," + ",".join(lis[1:-1]) + ","
    su = sum(information_frame.encode()) % 256
    checksum = lis[-1]
    b = int(checksum, 16).to_bytes(1, byteorder="big", signed=False)
    b = b"\xff" + b
    cs_int = int.from_bytes(b, byteorder="big", signed=True)
    return su + cs_int == 0


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
    checksum = lis[13]
    checksum_valid = is_valid_checksum(raw)
    return Response(
        predelimiter=lis[0],
        address=int(address),
        port=int(port),
        non_resetable_totalizer_value=float(lis[3]),
        totalizer_value=float(lis[4]),
        value=float(lis[5]),
        checksum=checksum.encode(),
        checksum_valid=checksum_valid,
    )


parity_options = {"even": serial.PARITY_EVEN, "odd": serial.PARITY_ODD, "none": serial.PARITY_NONE}

stop_bit_options = {"one": 1, "one_and_half": 1.5, "two": 2}


class BrooksMfc025x(
    HasTransformedPosition, HasLimits, HasPosition, UsesUart, UsesSerial, IsDaemon
):
    _kind = "brooks-mfc-025x"

    def __init__(self, name, config, config_filepath):
        super().__init__(name, config, config_filepath)
        self._write_queue = SerialWriteQueue(
            config["serial_port"],  # magically ensures single instance per port
            baudrate=config["baud_rate"],
            parity=parity_options[config["parity"]],
            stopbits=stop_bit_options[config["stop_bits"]],
        )
        self._units = "ml/min"
        self._native_units = "ml/min"
        self._last_successful_communication = time.time()

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
        item = WriteQueueItem(command=command.encode())
        self._write_queue.put(item)

    def _transformed_to_relative(self, transformed_position):
        xp = [p["measured"] for p in self._config["calibration"]]
        fp = [p["setpoint"] for p in self._config["calibration"]]
        return np.interp(transformed_position, xp, fp)

    async def update_state(self):
        while True:
            # construct command
            address = self._config["address"]
            port = (self._config["physical_port"] * 2) - 1
            command = "AZ"
            if address:
                command += f"{address:05}"
            command += f".{port:02}K\r\n"
            item = WriteQueueItem(command=command.encode(), callback=self.update_state_callback)
            self._write_queue.put(item)
            await asyncio.sleep(0.5)

    def update_state_callback(self, item):
        try:
            assert not item.error
            response = parse_response(item.response)
            assert response.checksum_valid
            assert response.port == (self._config["physical_port"] * 2) - 1
            self._last_successful_communication = time.time()
            self._state["position"] = response.value
            if abs(self._state["position"] - self._state["destination"]) < 1.0:
                self._busy = False
            if self._state["destination"] == 0.0:
                if self._state["position"] < 1.0:
                    self._busy = False
        except Exception as e:
            print(e)
            if time.time() - self._last_successful_communication > 5 * 60:  # 5 minutes:
                self._state["position"] = np.nan
