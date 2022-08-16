import asyncio
import re

import hart_protocol
from yaqd_core import aserial, logging


class HartDispatcher:
    def __init__(self, port, baudrate, parity, stop_bits):
        self.port = aserial.ASerial(port, baudrate)
        self.port.parity = parity
        self.port.stop_bits = stop_bits
        self.instances = {}
        self.write_queue = asyncio.Queue()
        self.loop = asyncio.get_event_loop()
        self.unpacker = hart_protocol.Unpacker(port)
        self.tasks = [
            self.loop.create_task(self.do_writes()),
            self.loop.create_task(self.read_dispatch()),
        ]

    def write(self, data):
        self.write_queue.put_nowait(data)

    async def do_writes(self):
        while True:
            data = await self.write_queue.get()
            self.port.write(data)
            self.write_queue.task_done()
            await asyncio.sleep(0.01)

    async def read_dispatch(self):
        for msg in self.unpacker:
            if msg["address"] in self.instances:
                self.instances[msg["address"]]._process_response(msg)

    def flush(self):
        self.port.flush()

    def close(self):
        self.loop.create_task(self._close())

    async def _close(self):
        await self.write_queue.join()
        for worker in self.workers.values():
            await worker.join()
        for task in self.tasks:
            task.cancel()
