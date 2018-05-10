from typing import Callable

from amino import List, do, Do, Dat, Nil
from amino.case import Case
from amino.util.string import camelcase
from amino.logging import module_log

from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.api.rpc import channel_id
from ribosome.nvim.api.command import nvim_command, nvim_sync_command
from ribosome.rpc.api import RpcOptions, RpcProgram
from ribosome.rpc.data.rpc_method import RpcMethod, CommandMethod, FunctionMethod, AutocmdMethod
from ribosome.rpc.data.prefix_style import PrefixStyle, Plain, Full, Short
from ribosome.rpc.data.nargs import Nargs

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

    def __init__(self, config: RpcConfig, options: RpcOptions, prog_name: str, rpc_name: str) -> None:
        self.config = config
        self.options = options
        self.prog_name = prog_name
        self.rpc_name = rpc_name


class DefinedHandler(Dat['DefinedHandler']):

    def __init__(self, prog: RpcProgram, method: RpcMethod, channel: int) -> None:
        self.prog = prog
        self.method = method
        self.channel = channel


def quote(a: str) -> str:
    return f'\'{a}\''


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


def autocmd_tokens(pattern: str) -> None:
    return DefinitionTokens('rpcnotify', Nil, 'autocmd', Nil, List('*'), '')


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


def rpc_name(rpc_def: RpcDef) -> str:
    prefixed = rpc_prefix(rpc_def.config.name, rpc_def.config.prefix, rpc_def.rpc_name)(rpc_def.options.prefix)
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
        List(rpc_name(rpc_def)) +
        tokens.rpc_opts_post +
        List(rhs)
    )


@do(NvimIO[None])
def define_trigger(
        rhs: Callable[[str], str],
        rpc_def: RpcDef,
        tokens: DefinitionTokens,
) -> Do:
    trigger = define_trigger_tokens(rhs, rpc_def, tokens)
    yield nvim_command(trigger.join_tokens)


def command_rhs(a: str) -> str:
    return f'call {a}'


def function_rhs(a: str) -> str:
    return f'(...)\nreturn {a}\nendfunction'


class define_method_rpc(Case[RpcMethod, NvimIO[DefinedHandler]], alg=RpcMethod):

    def __init__(self, prog: RpcProgram, rpc_def: RpcDef) -> None:
        self.prog = prog
        self.rpc_def = rpc_def

    def command(self, method: CommandMethod) -> NvimIO[DefinedHandler]:
        tokens = command_tokens(method.bang, self.prog.program.params_spec.nargs)
        return define_trigger(command_rhs, self.rpc_def, tokens)

    def function(self, method: FunctionMethod) -> NvimIO[DefinedHandler]:
        return define_trigger(function_rhs, self.rpc_def, function_tokens)

    @do(NvimIO[DefinedHandler])
    def autocmd(self, method: AutocmdMethod) -> Do:
        tokens = autocmd_tokens(method.pattern)
        yield nvim_command(f'augroup {self.rpc_def.config.name}')
        result = yield define_trigger(command_rhs, self.rpc_def, tokens)
        yield nvim_command(f'augroup end')
        return result


def define_prog_rpc(rpc_config: RpcConfig) -> Callable[[RpcProgram], NvimIO[List[DefinedHandler]]]:
    def traverse(prog: RpcProgram) -> NvimIO[List[DefinedHandler]]:
        @do(NvimIO[DefinedHandler])
        def define(method: RpcMethod) -> Do:
            log.debug1(lambda: f'defining {prog} for {method} on channel {rpc_config.channel}')
            rpc_def = RpcDef(rpc_config, prog.options, prog.program.name, prog.rpc_name)
            yield define_method_rpc(prog, rpc_def)(method)
            return DefinedHandler(prog, method, rpc_config.channel)
        return prog.options.methods.traverse(define, NvimIO)
    return traverse


@do(NvimIO[List[DefinedHandler]])
def define_rpc(progs: List[RpcProgram], name: str, prefix: str) -> Do:
    channel = yield channel_id()
    yield progs.flat_traverse(define_prog_rpc(RpcConfig(channel, name, prefix)), NvimIO)

__all__ = ('define_rpc',)
