from typing import Any

from amino import List, Try, do, Do, Either, ADT, Left, Right, Lists
from amino.logging import module_log

log = module_log()


class Receive(ADT['Receive']):
    pass


class ReceiveRequest(Receive):

    def __init__(self, id: int, method: str, args: List[Any]) -> None:
        self.id = id
        self.method = method
        self.args = args


class ReceiveNotification(Receive):

    def __init__(self, method: str, args: list) -> None:
        self.method = method
        self.args = args


class ReceiveResponse(Receive):

    def __init__(self, id: int, data: Any) -> None:
        self.id = id
        self.data = data


class ReceiveError(Receive):

    def __init__(self, id: int, error: str) -> None:
        self.id = id
        self.error = error


class ReceiveExit(Receive):
    pass


class ReceiveUnknown(Receive):

    def __init__(self, data: Any, reason: str) -> None:
        self.data = data
        self.reason = reason


@do(Either[str, Receive])
def receive_error(id: int, payload: Any) -> Do:
    data = yield Right(payload) if isinstance(payload, list) else Left(f'error payload not a list: {payload}')
    error = yield Lists.wrap(data).lift(1).to_either_f(lambda: f'too few elements for error payload: {data}')
    return ReceiveError(id, error)


@do(Either[str, Receive])
def receive_request(data: List[Any]) -> Do:
    el1, el2, el3 = yield data.lift_all(0, 1, 2).to_either_f(lambda: f'wrong number of elements: {data.length}')
    id = yield Right(el1) if isinstance(el1, int) else Left(f'id is not an int: {el1}')
    method = yield Try(el2.decode) if isinstance(el2, bytes) else Left(f'method is not a str: {el2}')
    args = yield Right(Lists.wrap(el3)) if isinstance(el3, list) else Left(f'args is not a list: {el3}')
    return ReceiveRequest(id, method, args)


@do(Either[str, Receive])
def receive_response(data: List[Any]) -> Do:
    el1, el2, el3 = yield data.lift_all(0, 1, 2).to_either_f(lambda: f'wrong number of elements: {data.length}')
    id = yield Right(el1) if isinstance(el1, int) else Left(f'id is not an int: {el1}')
    yield (
        receive_error(id, el2)
        if el2 is not None else
        Right(ReceiveResponse(id, el3))
    )


@do(Either[str, Receive])
def receive_notification(data: List[Any]) -> Do:
    el1, el2 = yield data.lift_all(0, 1).to_either_f(lambda: f'wrong number of elements: {data.length}')
    method = yield Try(el1.decode) if isinstance(el1, bytes) else Left(f'method is not a str: {el1}')
    args = yield Right(Lists.wrap(el2)) if isinstance(el2, list) else Left(f'args is not a list: {el2}')
    return ReceiveNotification(method, args)


@do(Either[str, Receive])
def validate_receive_data(raw: Any) -> Do:
    yield Right(None) if isinstance(raw, list) else Left('not a list')
    payload = Lists.wrap(raw)
    rpc_type, data = yield payload.uncons.to_either_f(lambda: f'response is empty list')
    yield (
        receive_request(data)
        if rpc_type == 0 else
        receive_response(data)
        if rpc_type == 1 else
        receive_notification(data)
        if rpc_type == 2 else
        Left(f'invalid rpc type: {rpc_type}')
    )


def cons_receive(data: Any) -> Receive:
    return validate_receive_data(data).value_or(lambda reason: ReceiveUnknown(data, reason))


__all__ = ('Receive', 'ReceiveRequest', 'ReceiveNotification', 'ReceiveResponse', 'ReceiveError', 'ReceiveExit',
           'ReceiveUnknown', 'cons_receive')
