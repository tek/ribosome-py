import abc
from typing import Any, Tuple

from amino import List, Either, Right, Map
from amino.json.decoder import decode_json_type
from amino.logging import module_log

from ribosome.rpc.args import ParamsSpec

log = module_log()


def starts_with_brace(data: Any) -> bool:
    return isinstance(data, str) and data.startswith('{')


class ArgParser(abc.ABC):

    def __init__(self, params_spec: ParamsSpec) -> None:
        self.params_spec = params_spec

    @abc.abstractmethod
    def parse(self, args: List[Any]) -> Either[str, List[Any]]:
        ...


class TokenArgParser(ArgParser):

    def parse(self, args: List[Any]) -> Either[str, List[Any]]:
        return Right(args)


class JsonArgParser(ArgParser):

    def parse(self, args: List[Any]) -> Either[str, List[Any]]:
        def pick_json(start: int) -> Tuple[str, str]:
            return args[:start], args[start:].join_tokens
        strict, json_args = args.index_where(starts_with_brace).cata(pick_json, (args, '{}'))
        tpe = self.params_spec.types.last | (lambda: Map)
        return decode_json_type(json_args, tpe) / strict.cat


__all__ = ('ArgParser', 'TokenArgParser', 'JsonArgParser')
