from typing import TypeVar
from types import ModuleType
import pkgutil
import importlib

from amino import do, Do, IO, List, Either, Lists, Try, Just, Nil
from amino.either import ImportFailure
from amino.mod import instances_from_module

from ribosome.config.setting import StrictSetting
from ribosome.util.doc.data import (StaticDoc, DocCompiler, DocBlock, DocLine, DocString, Headline, Anchor,
                                    VariableAnchor, RpcAnchor)
from ribosome.config.component import Component
from ribosome.rpc.api import RpcProgram

A = TypeVar('A')
B = TypeVar('B')


def rpc_doc(rpc: RpcProgram) -> List[DocBlock[A]]:
    name = DocBlock.headline(rpc.program_name, 4, Anchor(rpc.program_name, RpcAnchor(rpc.options.prefix)))
    return List(name) + List(rpc.options.help, DocBlock.empty())


def component_doc(component: Component) -> IO[List[DocBlock[A]]]:
    headline = DocBlock.headline(component.name, 2)
    desc = component.help.to_list
    rpc = component.rpc.flat_map(rpc_doc).cons(DocBlock.headline('RPC', 3))
    return IO.pure(List(headline) + desc + rpc.cat(DocBlock.empty()))


@do(IO[List[DocBlock[A]]])
def components_doc(components: List[Component]) -> Do:
    main = yield components.flat_traverse(component_doc, IO)
    return main.cons(DocBlock.none(List(DocLine.headline('Components', 1))))


def setting_doc(setting: StrictSetting) -> IO[List[DocBlock[A]]]:
    anchor = Anchor(setting.name, VariableAnchor('g', setting.prefix))
    headline = DocLine(DocString(setting.name, Headline(2, Just(anchor))))
    desc = DocLine.string(setting.desc)
    block1: DocBlock[A] = DocBlock.none(List(headline, desc, DocLine.empty()))
    blocks = List(block1, setting.help, DocBlock.none(List(DocLine.empty())))
    return IO.pure(blocks)


@do(IO[List[DocBlock[A]]])
def settings_doc(settings: List[StrictSetting]) -> Do:
    main = yield settings.flat_traverse(setting_doc, IO)
    return main.cons(DocBlock.none(List(DocLine.headline('Settings', 1))))


@do(IO[List[str]])
def generate_doc(
        components: List[Component],
        settings: List[StrictSetting],
        static: StaticDoc,
        compiler: DocCompiler[A, B],
) -> Do:
    components_lines = yield components_doc(components)
    settings_lines = yield settings_doc(settings)
    yield compiler.compile(static.pre + components_lines + settings_lines + static.post, compiler.conf)


def submodules(mod: ModuleType) -> List[str]:
    return Lists.wrap(pkgutil.iter_modules(mod.__path__)).map(lambda a: f'{mod.__name__}.{a.name}')


def import_mods(mods: List[str]) -> Either[str, List[ModuleType]]:
    return mods.traverse(lambda a: Try(importlib.import_module, a), Either)


@do(Either[ImportFailure, List[Component]])
def resolve_components(module: str) -> Do:
    base = yield Try(importlib.import_module, module)
    component_names = submodules(base)
    component_pkgs = yield import_mods(component_names)
    component_mod_names = component_pkgs.flat_map(submodules)
    component_modules = yield import_mods(component_mod_names)
    modules = component_modules + component_pkgs
    return modules.flat_map(lambda a: instances_from_module(a, Component)).join


@do(IO[List[str]])
def generate_plugin_doc(
        components_module: str,
        settings_modules: List[ModuleType],
        static: StaticDoc,
        compiler: DocCompiler[A, B],
) -> Do:
    components = yield IO.e(resolve_components(components_module))
    settings = yield IO.e(settings_modules.flat_traverse(lambda a: instances_from_module(a, StrictSetting), Either))
    yield generate_doc(components, settings, static, compiler)


__all__ = ('generate_doc', 'generate_plugin_doc', 'setting_doc', 'settings_doc',)
