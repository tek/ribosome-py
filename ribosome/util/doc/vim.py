from typing import TypeVar, Tuple

from amino import List, IO, Dat, do, Do, Lists, Nil, Just, Nothing
from amino.case import Case
from amino.state import State
from amino.util.string import camelcase
from amino.lenses.lens import lens

from ribosome.util.doc.data import (DocLine, DocCompiler, DocCat, DocFragment, DocString, DocBlock, DocMeta, NoMeta,
                                    Headline, Code, CustomDocMeta, Link, Anchor, AnchorType, VariableAnchor,
                                    MappingAnchor, GeneralAnchor, RpcAnchor)
from ribosome.rpc.data.prefix_style import Full, Short
from ribosome.util.doc.format import CompilerConfig, compile_anchor

A = TypeVar('A')


class VimCompilerConfig(Dat['VimCompilerConfig']):

    @staticmethod
    def cons(
            compiler_config: CompilerConfig,
            width: int=78,
    ) -> 'VimCompilerConfig':
        return VimCompilerConfig(
            compiler_config,
            width,
        )

    def __init__(self, compiler_config: CompilerConfig, width: int) -> None:
        self.compiler_config = compiler_config
        self.width = width


def break_line(line: str, width: int) -> List[str]:
    tokens = Lists.tokens(line)
    def step(z: Tuple[List[str], str], a: str) -> Tuple[List[str], str]:
        lines, current = z
        return (
            (lines.cat(current), a)
            if len(current) + len(a) >= width else (
                (lines, f'{current} {a}')
                if len(current) > 0 else
                (lines, a)
            )
        )
    lines, rest = tokens.fold_left((Nil, ''))(step)
    return lines.cat(rest) if len(rest) > 0 else lines


class compile_string(Case[DocMeta[A], List[str]], alg=DocMeta):

    def __init__(self, string: DocString[A]) -> None:
        self.string = string

    @do(State[VimCompilerConfig, List[str]])
    def no(self, a: NoMeta[A]) -> Do:
        width = yield State.inspect(lambda a: a.width)
        return (
            List('')
            if len(self.string.text) == 0 else
            Lists.lines(self.string.text).flat_map(lambda a: break_line(a, width))
        )

    @do(State[VimCompilerConfig, List[str]])
    def headline(self, a: Headline[A]) -> Do:
        text = self.string.text
        width = yield State.inspect(lambda a: a.width)
        char = '=' if a.level == 1 else '-'
        name = yield State.inspect(lambda a: a.name)
        anchor = yield (
            a.anchor
            .map(compile_anchor)
            .get_or(lambda: State.pure(f'{name}-{self.string.text.lower()}'))
            .zoom(lens.compiler_config)
        )
        ws_len = width - (len(self.string.text) + len(anchor))
        ws = ' ' * ws_len
        main = text.upper() if a.level == 1 else text
        return List(char * width, f'{main}{ws}*{anchor}*', '')

    def code(self, a: Code[A]) -> State[VimCompilerConfig, List[str]]:
        return State.pure(List(f'`{self.string.text}`'))

    def link(self, a: Link[A]) -> State[VimCompilerConfig, List[str]]:
        return State.pure(List(f'`[{a.desc}]({self.string.text})`'))

    def custom(self, a: CustomDocMeta[A]) -> State[VimCompilerConfig, List[str]]:
        return State.pure(List(self.string.text))


class compile_fragment(Case[DocFragment[A], List[str]], alg=DocFragment):

    def cat(self, frag: DocCat[A]) -> State[VimCompilerConfig, List[str]]:
        return frag.fragments.flat_map(self)

    def string(self, frag: DocString[A]) -> State[VimCompilerConfig, List[str]]:
        return compile_string(frag)(frag.meta)


def compile_line(line: DocLine[A]) -> State[VimCompilerConfig, List[str]]:
    return compile_fragment.match(line.data)


def compile_block(block: DocBlock[A]) -> State[VimCompilerConfig, List[str]]:
    return block.lines.flat_traverse(compile_line, State)


def compile_vim(blocks: List[DocBlock[A]], conf: VimCompilerConfig) -> IO[List[str]]:
    return IO.pure(blocks.flat_traverse(compile_block, State).run_a(conf).value)


def vim_compiler(conf: VimCompilerConfig) -> DocCompiler[A, VimCompilerConfig]:
    return DocCompiler(compile_vim, conf)


__all__ = ('compile_vim', 'vim_compiler',)
