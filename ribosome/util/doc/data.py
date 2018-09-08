from typing import Generic, TypeVar, Callable

from amino import List, Dat, ADT, Maybe, Nil

from ribosome.rpc.data.prefix_style import PrefixStyle

A = TypeVar('A')
B = TypeVar('B')


class DocMeta(Generic[A], ADT['DocMeta[A]']):
    pass


class NoMeta(DocMeta[A]):
    pass


class Code(DocMeta[A]):

    def __init__(self, lang: str) -> None:
        self.lang = lang


class AnchorType(ADT['AnchorType']):
    pass


class VariableAnchor(AnchorType):

    def __init__(self, scope: str, prefix: bool) -> None:
        self.scope = scope
        self.prefix = prefix


class MappingAnchor(AnchorType):
    pass


class RpcAnchor(AnchorType):

    def __init__(self, prefix: PrefixStyle) -> None:
        self.prefix = prefix


class GeneralAnchor(AnchorType):
    pass


class Anchor(Dat['Anchor']):

    @staticmethod
    def cons(
            text: str,
            tpe: AnchorType,
    ) -> 'Anchor':
        return Anchor(
            text,
            tpe,
        )

    def __init__(self, text: str, tpe: AnchorType) -> None:
        self.text = text
        self.tpe = tpe


class Headline(DocMeta[A]):

    @staticmethod
    def cons(level: int=1, anchor: Anchor=None) -> 'Headline[A]':
        return Headline(level, Maybe.optional(anchor))

    def __init__(self, level: int, anchor: Maybe[Anchor]) -> None:
        self.level = level
        self.anchor = anchor


class CustomDocMeta(DocMeta[A]):

    def __init__(self, extra: A) -> None:
        self.extra = extra


class LinkType(ADT['LinkType']):
    pass


class WebLinkType(LinkType):
    pass


class DocLinkType(LinkType):
    pass


class Link(Generic[A], DocMeta[A]):

    def __init__(self, target: str, tpe: LinkType, desc: Maybe[str]) -> None:
        self.target = target
        self.tpe = tpe
        self.desc = desc


class DocFragment(Generic[A], ADT['DocFragment[A]']):
    pass


class DocCat(DocFragment[A]):

    def __init__(self, fragments: List[DocFragment]) -> None:
        self.fragments = fragments


class DocString(DocFragment[A]):

    @staticmethod
    def none(text: str) -> 'DocString[A]':
        return DocString(text, NoMeta())

    def __init__(self, text: str, meta: DocMeta[A]) -> None:
        self.text = text
        self.meta = meta


class DocLine(Generic[A], Dat['DocLine[A]']):

    @staticmethod
    def string(text: str) -> 'DocLine[A]':
        return DocLine(DocString.none(text))

    @staticmethod
    def empty() -> 'DocLine[A]':
        return DocLine.string('')

    @staticmethod
    def headline(text: str, level: int, anchor: Anchor=None) -> 'DocLine[A]':
        return DocLine(DocString(text, Headline.cons(level, anchor)))

    def __init__(self, data: DocFragment) -> None:
        self.data = data


class DocBlock(Generic[A], Dat['DocBlock[A]']):

    @staticmethod
    def none(lines: List[DocLine[A]]) -> 'DocBlock[A]':
        return DocBlock(lines, NoMeta())

    @staticmethod
    def string(text: str) -> 'DocBlock[A]':
        return DocBlock.none(List(DocLine.string(text)))

    @staticmethod
    def headline(text: str, level: int, anchor: Anchor=None) -> 'DocLine[B]':
        return DocBlock.none(List(DocLine.headline(text, level, anchor)))

    @staticmethod
    def empty() -> 'DocLine[A]':
        return DocBlock.none(List(DocLine.empty()))

    def __init__(self, lines: List[DocLine[A]], meta: DocMeta[A]) -> None:
        self.lines = lines
        self.meta = meta


class StaticDoc(Dat['StaticDoc']):

    @staticmethod
    def cons(
            pre: List[DocBlock[A]]=Nil,
            post: List[DocBlock[A]]=Nil,
    ) -> 'StaticDoc':
        return StaticDoc(
            pre,
            post,
        )

    def __init__(self, pre: List[DocBlock[A]], post: List[DocBlock[A]]) -> None:
        self.pre = pre
        self.post = post


class DocCompiler(Generic[A, B], Dat['DocCompiler[A, B]']):

    def __init__(self, compile: Callable[[List[DocLine[A]], B], List[str]], conf: B) -> None:
        self.compile = compile
        self.conf = conf


__all__ = ('DocMeta', 'NoMeta', 'Headline', 'Code', 'CustomDocMeta', 'LinkType', 'WebLinkType', 'DocLinkType', 'Link',
           'DocFragment', 'DocCat', 'DocString', 'DocLine', 'DocBlock', 'StaticDoc', 'DocCompiler',)
