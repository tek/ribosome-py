import abc
from typing import Any

from amino import List, Either, Right, Map
from amino.json.decoder import decode_json_type

from ribosome.request.args import ParamsSpec


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
        def parse(start: int) -> Either[str, List[Any]]:
            strict = args[:start]
            json_args = args[start:].join_tokens
            tpe = self.params_spec.types.last | (lambda: Map)
            return decode_json_type(json_args, tpe) / strict.cat
        return args.index_where(starts_with_brace).cata(parse, Right(args))


__all__ = ('ArgParser', 'TokenArgParser', 'JsonArgParser')
