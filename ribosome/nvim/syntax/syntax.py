from amino import Dat, List, Nil

from ribosome.nvim.syntax.expr import SyntaxItem, Highlight, HiLink


class Syntax(Dat['Syntax']):

    @staticmethod
    def cons(
            syntax: List[SyntaxItem]=Nil,
            highlight: List[Highlight]=Nil,
            links: List[HiLink]=Nil,
    ) -> 'Syntax':
        return Syntax(
            syntax,
            highlight,
            links,
        )

    def __init__(self, syntax: List[SyntaxItem], highlight: List[Highlight], links: List[HiLink]) -> None:
        self.syntax = syntax
        self.highlight = highlight
        self.links = links


__all__ = ('Syntax',)
