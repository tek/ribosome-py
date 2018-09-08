from typing import TypeVar

from amino import List, IO, Dat, do, Do
from amino.case import Case
from amino.state import State
from amino.lenses.lens import lens

from ribosome.util.doc.data import (DocLine, DocCompiler, DocCat, DocFragment, DocString, DocBlock, DocMeta, NoMeta,
                                    Headline, Code, CustomDocMeta, Link, AnchorType, GeneralAnchor, VariableAnchor,
                                    RpcAnchor, MappingAnchor)
from ribosome.util.doc.format import CompilerConfig, compile_anchor

A = TypeVar('A')


class MarkdownCompilerConfig(Dat['MarkdownCompilerConfig']):

    @staticmethod
    def cons(
            basic: CompilerConfig,
    ) -> 'MarkdownCompilerConfig':
        return MarkdownCompilerConfig(
            basic,
        )

    def __init__(self, basic: CompilerConfig) -> None:
        self.basic = basic


class postproc_anchor(Case[AnchorType, str], alg=AnchorType):

    def __init__(self, text: str) -> None:
        self.text = text

    def variable(self, a: VariableAnchor) -> str:
        return f'`{self.text}`'

    def rpc(self, a: RpcAnchor) -> str:
        return f'`{self.text}`'

    def mapping(self, a: MappingAnchor) -> str:
        return f'`{self.text}`'

    def general(self, a: GeneralAnchor) -> str:
        return self.text


class compile_string(Case[DocMeta[A], State[MarkdownCompilerConfig, List[str]]], alg=DocMeta):

    def __init__(self, string: DocString[A]) -> None:
        self.string = string

    def no(self, a: NoMeta[A]) -> State[MarkdownCompilerConfig, List[str]]:
        return State.pure(List(self.string.text))

    @do(State[MarkdownCompilerConfig, List[str]])
    def headline(self, a: Headline[A]) -> Do:
        hashes = '#' * a.level
        anchor = yield (
            a.anchor
            .map(lambda b: compile_anchor(b).map(lambda c: postproc_anchor(c)(b.tpe)))
            .get_or(lambda: State.pure(f'{self.string.text}'))
            .zoom(lens.basic)
        )
        return List(f'{hashes} {anchor}', '')

    def code(self, a: Code[A]) -> State[MarkdownCompilerConfig, List[str]]:
        return State.pure(List(f'`{self.string.text}`'))

    def link(self, a: Link[A]) -> State[MarkdownCompilerConfig, List[str]]:
        return State.pure(List(f'`[{a.desc}]({self.string.text})`'))

    def custom(self, a: CustomDocMeta[A]) -> State[MarkdownCompilerConfig, List[str]]:
        return State.pure(List(self.string.text))


class compile_fragment(Case[DocFragment[A], List[str]], alg=DocFragment):

    @do(State[MarkdownCompilerConfig, List[str]])
    def cat(self, frag: DocCat[A]) -> Do:
        parts = yield frag.fragments.flat_traverse(self, State)
        return List(parts.join_tokens)

    def string(self, frag: DocString[A]) -> State[MarkdownCompilerConfig, List[str]]:
        return compile_string(frag)(frag.meta)


def compile_line(line: DocLine[A]) -> State[MarkdownCompilerConfig, List[str]]:
    return compile_fragment.match(line.data)


def compile_block(block: DocBlock[A]) -> State[MarkdownCompilerConfig, List[str]]:
    return block.lines.flat_traverse(compile_line, State)


def compile_markdown(blocks: List[DocBlock[A]], conf: MarkdownCompilerConfig) -> IO[List[str]]:
    return IO.pure(blocks.flat_traverse(compile_block, State).run_a(conf).value)


def markdown_compiler(conf: MarkdownCompilerConfig) -> DocCompiler[A, MarkdownCompilerConfig]:
    return DocCompiler(compile_markdown, conf)


__all__ = ('compile_markdown', 'markdown_compiler',)
