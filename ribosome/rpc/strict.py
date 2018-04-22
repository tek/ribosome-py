from queue import Queue
from typing import Any

import msgpack

from amino import Dat, Map, IO

from ribosome.rpc.uv.uv import OnMessage, processing_error
from ribosome.rpc.comm import OnError


class StrictRpc(Dat['StrictRpc']):

    @staticmethod
    def cons(responses: Map[str, Any]) -> 'StrictRpc':
        return StrictRpc(responses, Queue(), False)

    def __init__(self, responses: Map[str, Any], queue: Queue, running: bool) -> None:
        self.responses = responses
        self.queue = queue
        self.running = running

    def send(self, data: bytes) -> None:
        self.queue.put(msgpack.unpackb(data))

    def start_processing(self, on_message: OnMessage, on_error: OnError) -> IO[None]:
        self.running = True
        return IO.fork(self.loop, on_message, on_error)

    def loop(self, on_message: OnMessage, on_error: OnError) -> None:
        while self.running:
            try:
                a = self.queue.get(timeout=.1)
            except Exception as e:
                pass
            else:
                if len(a) == 4 and a[0] == 0:
                    response = self.responses.lift(a[2].decode()).get_or_else(None)
                    on_message(msgpack.packb([1, a[1], None, response])).attempt.lmap(processing_error)

    def stop(self) -> None:
        self.running = False


__all__ = ('StrictRpc',)
