from typing import TypeVar
from types import ModuleType

from amino.logging import module_log
from amino import List, IO, do, Do, Path
from amino.io import IOException

from ribosome.util.doc.data import StaticDoc, DocCompiler
from ribosome.util.doc.markdown import markdown_compiler, MarkdownCompilerConfig
from ribosome.util.doc.vim import vim_compiler, VimCompilerConfig
from ribosome.util.doc.generate import generate_plugin_doc
from ribosome.util.doc.format import CompilerConfig

log = module_log()
A = TypeVar('A')
B = TypeVar('B')


def report_error(error: IOException) -> None:
    log.error(f'failed to generate doc: {error}')


@do(IO[None])
def run(
        components: str,
        settings: List[ModuleType],
        compiler: DocCompiler[A, B],
        outfile: Path,
        static: StaticDoc,
) -> Do:
    text = yield generate_plugin_doc(components, settings, static, compiler)
    yield IO.delay(outfile.write_text, text.join_lines)


@do(IO[None])
def run_default(
        components: str,
        settings: List[ModuleType],
        pkg_dir: Path,
        name: str,
        prefix: str,
        static: StaticDoc,
) -> Do:
    vim_conf = VimCompilerConfig.cons(CompilerConfig.cons(name, prefix))
    md_conf = MarkdownCompilerConfig.cons(CompilerConfig.cons(name, prefix))
    yield run(components, settings, markdown_compiler(md_conf), pkg_dir / 'README.md', static)
    yield run(components, settings, vim_compiler(vim_conf), pkg_dir / 'data' / 'runtime' / f'{name}.txt', static)


def write_default_docs(
        components: str,
        settings: List[ModuleType],
        pkg_dir: Path,
        name: str,
        prefix: str,
        static: StaticDoc,
) -> None:
    run_default(components, settings, pkg_dir, name, prefix, static).attempt.lmap(report_error)

__all__ = ('write_default_docs',)
