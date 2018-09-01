#!usr/bin/env python3

from typing import Callable, TypeVar

from amino.logging import module_log
from amino import List, Nil, IO, do, Do, Path

from ribosome.util.doc.data import (StaticDoc, DocBlock, DocLine, DocString, Headline, NoMeta, DocCompiler,
                                    GeneralAnchor, Anchor)
from ribosome.util.doc.markdown import markdown_compiler, MarkdownCompilerConfig
from ribosome.config import settings
from ribosome.util.doc.vim import vim_compiler, VimCompilerConfig
from ribosome.util.doc.generate import generate_plugin_doc
from ribosome.util.doc.format import CompilerConfig

log = module_log()
A = TypeVar('A')
B = TypeVar('B')
vim_conf = VimCompilerConfig.cons(CompilerConfig.cons('ribosome'))
md_conf = MarkdownCompilerConfig.cons(CompilerConfig.cons('ribosome'))


def report_error(output_type: str) -> Callable[[str], None]:
    def report_error(error: str) -> None:
        log.error(f'failed to generate doc as {output_type}: {error}')
    return report_error


intro: DocBlock[None] = DocBlock(List(
    DocLine(DocString('Introduction', Headline.cons(1, Anchor('ribosome', GeneralAnchor())))),
), NoMeta())
pre = List(intro)
post = Nil
static = StaticDoc(pre, post)


@do(IO[None])
def run(compiler: DocCompiler[A, B], outfile: Path) -> Do:
    text = yield generate_plugin_doc('ribosome.components', List(settings), static, compiler)
    yield IO.delay(outfile.write_text, text.join_lines)


pkg_dir = Path(__file__).absolute().parent.parent
run(markdown_compiler(md_conf), pkg_dir / 'README.gen.md').attempt.lmap(report_error('markdown'))
# run(vim_compiler(vim_conf), pkg_dir / 'doc.gen.txt').attempt.lmap(report_error('vimdoc'))
