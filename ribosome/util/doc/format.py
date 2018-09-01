from amino.case import Case
from amino import do, Do, Dat, Just, Nothing
from amino.state import State
from amino.util.string import camelcase

from ribosome.util.doc.data import Anchor, VariableAnchor, AnchorType, MappingAnchor, RpcAnchor, GeneralAnchor
from ribosome.rpc.data.prefix_style import Short, Full


class CompilerConfig(Dat['CompilerConfig']):

    @staticmethod
    def cons(
            name: str,
            prefix: str=None,
    ) -> 'CompilerConfig':
        return CompilerConfig(
            name,
            prefix or name,
        )

    def __init__(self, name: str, prefix: str) -> None:
        self.name = name
        self.prefix = prefix


def format_variable(name: str, anchor: Anchor, tpe: VariableAnchor) -> str:
    prefix = f'{name}_' if tpe.prefix else ''
    return f'{tpe.scope}:{prefix}{anchor.text}'


class compile_anchor_type(Case[AnchorType, State[CompilerConfig, str]], alg=AnchorType):

    def __init__(self, anchor: Anchor) -> None:
        self.anchor = anchor

    @do(State[CompilerConfig, str])
    def variable(self, a: VariableAnchor) -> Do:
        name = yield State.inspect(lambda a: a.name)
        return format_variable(name, self.anchor, a)

    def mapping(self, a: MappingAnchor) -> State[CompilerConfig, str]:
        return State.pure('')

    @do(State[CompilerConfig, str])
    def rpc(self, a: RpcAnchor) -> Do:
        name = yield State.inspect(lambda a: a.name)
        prefix = yield State.inspect(lambda a: a.prefix)
        rpc_prefix = Just(name) if a.prefix == Full() else Just(prefix) if a.prefix == Short() else Nothing
        prefix_s = rpc_prefix.map(lambda a: f'{a}_').get_or_strict('')
        cc = camelcase(f'{prefix_s}{self.anchor.text}')
        return f':{cc}'

    def general(self, a: GeneralAnchor) -> State[CompilerConfig, str]:
        return State.pure(self.anchor.text)


def compile_anchor(anchor: Anchor) -> State[CompilerConfig, str]:
    return compile_anchor_type(anchor)(anchor.tpe)


__all__ = ('format_variable', 'compile_anchor',)
