import sys
from typing import TypeVar, Any, Iterable

from lenses import UnboundLens

from amino.state import EitherState
from amino import do, Do, __, _, Map, Maybe, Lists, Just, Regex, L, IO, List
from amino.json import dump_json
from amino.dat import Dat
from amino.lenses.lens import lens
from amino.regex import Match
from amino.logging import module_log

from ribosome.compute.api import prog
from ribosome.data.plugin_state import PluginState
from ribosome.nvim.io.state import NS
from ribosome.config.component import ComponentData
from ribosome.compute.prog import Prog
from ribosome.config.basic_config import NoData
from ribosome.components.internal.update import undef_triggers, def_triggers
from ribosome.compute.program import Program, bind_nullary_program
from ribosome.config.settings import run_internal_init
from ribosome.compute.ribosome_api import Ribo
from ribosome.rpc.data.rpc_method import RpcMethod
from ribosome.rpc.define import ActiveRpcTrigger
from ribosome.compute.output import Echo
from ribosome.nvim.api.rpc import plugin_name

log = module_log()
D = TypeVar('D')
CC = TypeVar('CC')


@prog
@do(NS[ComponentData[PluginState[D, CC], NoData], str])
def program_log() -> Do:
    yield NS.inspect_either(lambda s: dump_json(s.main.program_log))


@prog.unit
def set_log_level(level: str) -> NS[PluginState[D, CC], None]:
    handler = yield NS.inspect_f(_.file_log_handler)
    handler.setLevel(level)


@prog
@do(NS[ComponentData[PluginState[D, CC], NoData], str])
def state_data() -> Do:
    yield NS.inspect_either(lambda s: dump_json(s.main.data))


@prog
@do(NS[PluginState[D, CC], str])
def component_state_data(name: str) -> Do:
    data = yield NS.inspect_either(lambda s: s.data_by_name(name))
    yield NS.e(dump_json(data))


class RpcTrigger(Dat['RpcTrigger']):

    @staticmethod
    def from_active(trigger: ActiveRpcTrigger) -> 'RpcTrigger':
        return RpcTrigger(trigger.name, trigger.method)

    def __init__(self, name: str, method: RpcMethod) -> None:
        self.name = name
        self.method = method


@prog
def rpc_triggers() -> NS[PluginState[D, CC], List[RpcTrigger]]:
    return NS.inspect_either(lambda s: dump_json(s.rpc_triggers.map(RpcTrigger.from_active)))


class PatchQuery(Dat['PatchQuery']):

    def __init__(self, query: str, data: Map[str, Any]) -> None:
        self.query = query
        self.data = data


class UpdateQuery(Dat['UpdateQuery']):

    def __init__(self, patch: Maybe[PatchQuery]) -> None:
        self.patch = patch


find_rex = Regex(r'(?P<id>\w+)\((?P<key>\w+)=(?P<value>\w+)\)')


@do(Maybe[UnboundLens])
def find_lens(z: UnboundLens, m: Match) -> Do:
    id, key, value = yield m.all_groups('id', 'key', 'value').to_maybe
    yield Just(z.getattr_(id).each_().filter_(lambda a: Maybe.getattr(a, key).contains(value)))


# TODO `Regex.match_as(tpe)` that constructs a `Dat` from the `Match`
def lens_step(z: UnboundLens, s: str) -> Maybe[UnboundLens]:
    return find_rex.match(s) / L(find_lens)(z, _) | (lambda: Maybe.getattr(z, s))


def mk_lens(query: str) -> UnboundLens:
    return Lists.split(query, '.').fold_m(Just(lens))(lens_step)


@do(NS[PluginState[D, CC], None])
def patch_update(query: PatchQuery) -> Do:
    lns = yield NS.m(mk_lens(query.query), f'invalid state update query: {query.query}')
    lns1 = lens.data & lns
    yield NS.modify(lns1.modify(__.typed_copy(**query.data)))


@prog.unit
@do(NS[PluginState[D, CC], None])
def update_state(query: UpdateQuery) -> Do:
    yield query.patch / patch_update | NS.pure(None)


@do(NS[PluginState[D, CC], None])
def patch_update_component(comp: str, query: PatchQuery) -> Do:
    lns = yield NS.m(mk_lens(query.query), f'invalid component state update query for {comp}: {query.query}')
    yield NS.modify(__.modify_component_data(comp, lns.modify(__.typed_copy(**query.data))))


@prog.unit
@do(NS[PluginState[D, CC], None])
def update_component_state(comp: str, query: UpdateQuery) -> Do:
    yield query.patch / L(patch_update_component)(comp, _) | NS.pure(None)


@prog
def poll() -> NS[D, bool]:
    return NS.pure(True)


@prog.unit
def append_python_path(path: str) -> NS[D, None]:
    return NS.from_io(IO.delay(sys.path.append, path))


@prog
def show_python_path() -> NS[D, Iterable[str]]:
    return NS.pure(sys.path)


# FIXME need to update component type map
@prog.unit
@do(NS[PluginState[D, CC], None])
def enable_components(*names: str) -> Do:
    comps = (
        yield NS.inspect_either(
            __.comp.available.lift_all(*names).to_either(f'couldn\'t find some components: {names}'))
    )
    yield undef_triggers()
    yield NS.modify(lens.components.all.modify(__.add(comps)))
    yield def_triggers()
    print


class MapOptions(Dat['MapOptions']):

    @staticmethod
    def cons(
            buffer: int=None,
    ) -> 'MapOptions':
        return MapOptions(
            Maybe.optional(buffer),
        )

    def __init__(self, buffer: Maybe[int]) -> None:
        self.buffer = buffer


def mapping_data(ident: str, keys: str) -> NS[PluginState[D, CC], Program]:
    return NS.inspect_either(lambda a: a.active_mappings.lift(ident).to_either(f'no program for mapping `{keys}`'))


@prog
@do(NS[PluginState[D, CC], Program])
def mapping_program(ident: str, keys: str) -> Do:
    mapping, program = yield mapping_data(ident, keys)
    return program


@prog.do(None)
def mapping(ident: str, keys: str) -> Do:
    program = yield mapping_program(ident, keys)
    yield program()
    yield Prog.unit


@prog
@do(NS[PluginState[D, CC], Maybe[Program]])
def internal_init_program() -> Do:
    yield NS.inspect(_.init)


@prog.do(None)
def internal_init() -> Do:
    enabled = yield Ribo.setting_prog(run_internal_init)
    if enabled:
        program = yield internal_init_program()
        yield program / bind_nullary_program | Prog.unit


@prog.echo
@do(NS[D, Echo])
def rpc_job_stderr(id: int, data: list, event: str) -> Do:
    errors = Lists.wrap(data).filter(lambda a: len(a) > 0)
    name = yield NS.lift(plugin_name())
    log.debug(f'error in {name} rpc job on channel {id}:')
    errors.foreach(log.debug)
    msg = '' if len(errors) > 1 else errors.head.map(lambda a: f': {a}').get_or_strict('')
    yield NS.pure(Echo.error(f'fatal error in plugin {name}{msg}'))


__all__ = ('internal_init', 'mapping', 'MapOptions', 'enable_components', 'show_python_path', 'append_python_path',
           'poll', 'program_log', 'set_log_level', 'state_data', 'rpc_triggers', 'update_state',
           'update_component_state', 'component_state_data',)
