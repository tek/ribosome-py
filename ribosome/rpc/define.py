from typing import Callable

from amino import List, do, Do, Dat, Nil, Just, Nothing, Maybe
from amino.case import Case
from amino.util.string import camelcase
from amino.logging import module_log

from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.api.rpc import channel_id
from ribosome.nvim.api.command import nvim_atomic_commands
from ribosome.rpc.api import RpcOptions, RpcProgram
from ribosome.rpc.data.rpc_method import RpcMethod, CommandMethod, FunctionMethod, AutocmdMethod
from ribosome.rpc.data.prefix_style import PrefixStyle, Plain, Full, Short
from ribosome.rpc.data.nargs import Nargs, NargsStar

log = module_log()


# FIXME do multiple handlers work?
# @property
# def distinct_specs(self) -> List[RpcProgram]:
#     return self.specs.distinct_by(_.rpc_method)


class RpcConfig(Dat['RpcConfig']):

    def __init__(self, channel: int, name: str, prefix: str) -> None:
        self.channel = channel
        self.name = name
        self.prefix = prefix


class RpcDef(Dat['RpcDef']):

    def __init__(
            self,
            config: RpcConfig,
            options: RpcOptions,
            prog_name: str,
            rpc_name: str,
            trigger_name: str,
    ) -> None:
        self.config = config
        self.options = options
        self.prog_name = prog_name
        self.rpc_name = rpc_name
        self.trigger_name = trigger_name


class ActiveRpcTrigger(Dat['ActiveRpcTrigger']):

    def __init__(self, name: str, prog: RpcProgram, method: RpcMethod, channel: int, definition: List[str]) -> None:
        self.name = name
        self.prog = prog
        self.method = method
        self.channel = channel
        self.definition = definition


def quote(a: str) -> str:
    return f'\'{a}\''


class undef_command(Case[RpcMethod, Maybe[str]], alg=RpcMethod):

    def function(self, method: FunctionMethod) -> Maybe[str]:
        return Just('delfunction')

    def command(self, method: CommandMethod) -> Maybe[str]:
        return Just('delcommand')

    def autocmd(self, method: AutocmdMethod) -> Maybe[str]:
        return Nothing


class DefinitionTokens(Dat['DefinitionTokens']):

    def __init__(
            self,
            rpc_function: str,
            rpc_args: List[str],
            def_cmd: str,
            rpc_opts_pre: List[str],
            rpc_opts_post: List[str],
            method_prefix: str,
    ) -> None:
        self.rpc_function = rpc_function
        self.rpc_args = rpc_args
        self.def_cmd = def_cmd
        self.rpc_opts_pre = rpc_opts_pre
        self.rpc_opts_post = rpc_opts_post
        self.method_prefix = method_prefix



def command_tokens(bang: bool, nargs: Nargs) -> DefinitionTokens:
    bang_opt = List('-bang') if bang else Nil
    bang_arg = List("<q-bang> == '!'") if bang else Nil
    nargs_arg = List('[<f-args>]')
    opts = List(f'-nargs={nargs.for_vim}') + bang_opt
    args = bang_arg + nargs_arg
    return DefinitionTokens('rpcnotify', args, 'command!', opts, Nil, '')


function_tokens = DefinitionTokens('rpcrequest', List('a:000'), 'function!', Nil, Nil, '')


def autocmd_tokens(pattern: str, sync: bool) -> DefinitionTokens:
    func = 'rpcrequest' if sync else 'rpcnotify'
    return DefinitionTokens(func, Nil, 'autocmd', Nil, List('*'), '')


class rpc_prefix(Case[PrefixStyle, str], alg=PrefixStyle):

    def __init__(self, name: str, prefix: str, method: str) -> None:
        self.name = name
        self.prefix = prefix
        self.method = method

    def plain(self, style: Plain) -> str:
        return self.method

    def full(self, style: Full) -> str:
        return f'{self.name}_{self.method}'

    def short(self, style: Short) -> str:
        return f'{self.prefix}_{self.method}'


def rpc_trigger_name(config: RpcConfig, options: RpcOptions, rpc_name: str) -> str:
    prefixed = rpc_prefix(config.name, config.prefix, rpc_name)(options.prefix)
    return camelcase(prefixed)


def define_trigger_tokens(
        rhs_f: Callable[[str], str],
        rpc_def: RpcDef,
        tokens: DefinitionTokens,
) -> List[str]:
    method = f'{tokens.method_prefix}{rpc_def.rpc_name}'
    args = tokens.rpc_args.cons(quote(method)).join_comma
    rpc_call = f'{tokens.rpc_function}({rpc_def.config.channel}, {args})'
    rhs = rhs_f(rpc_call)
    return (
        List(tokens.def_cmd) +
        tokens.rpc_opts_pre +
        List(rpc_def.trigger_name) +
        tokens.rpc_opts_post +
        List(rhs)
    )


def trigger_definition(
        rhs: Callable[[str], str],
        rpc_def: RpcDef,
        tokens: DefinitionTokens,
) -> str:
    return define_trigger_tokens(rhs, rpc_def, tokens).join_tokens


def command_rhs(a: str) -> str:
    return f'call {a}'


def function_rhs(a: str) -> str:
    return f'(...)\nreturn {a}\nendfunction'


class method_definition(Case[RpcMethod, List[str]], alg=RpcMethod):

    def __init__(self, prog: RpcProgram, rpc_def: RpcDef) -> None:
        self.prog = prog
        self.rpc_def = rpc_def

    def command(self, method: CommandMethod) -> List[str]:
        nargs = (
            NargsStar()
            if self.prog.options.json else
            self.prog.program.params_spec.nargs
        )
        tokens = command_tokens(method.bang, nargs)
        return List(trigger_definition(command_rhs, self.rpc_def, tokens))

    def function(self, method: FunctionMethod) -> List[str]:
        return List(trigger_definition(function_rhs, self.rpc_def, function_tokens))

    def autocmd(self, method: AutocmdMethod) -> List[str]:
        tokens = autocmd_tokens(method.pattern, method.sync)
        return List(
            f'augroup {self.rpc_def.config.name}',
            trigger_definition(command_rhs, self.rpc_def, tokens),
            f'augroup end'
        )


def prog_triggers(rpc_config: RpcConfig) -> Callable[[RpcProgram], ActiveRpcTrigger]:
    def traverse(prog: RpcProgram) -> ActiveRpcTrigger:
        def define(method: RpcMethod) -> List[str]:
            log.debug1(lambda: f'defining {prog} for {method} on channel {rpc_config.channel}')
            trigger_name = rpc_trigger_name(rpc_config, prog.options, prog.rpc_name)
            rpc_def = RpcDef(rpc_config, prog.options, prog.program.name, prog.rpc_name, trigger_name)
            return ActiveRpcTrigger(trigger_name, prog, method, rpc_config.channel,
                                    method_definition(prog, rpc_def)(method))
        return prog.options.methods.map(define)
    return traverse


def rpc_triggers(progs: List[RpcProgram], name: str, prefix: str, channel: int) -> List[ActiveRpcTrigger]:
    return progs.flat_map(prog_triggers(RpcConfig(channel, name, prefix)))


@do(NvimIO[List[ActiveRpcTrigger]])
def define_rpc(progs: List[RpcProgram], name: str, prefix: str) -> Do:
    channel = yield channel_id()
    triggers = rpc_triggers(progs, name, prefix, channel)
    definitions = triggers.flat_map(lambda a: a.definition)
    yield nvim_atomic_commands(definitions)
    return triggers

__all__ = ('define_rpc',)
