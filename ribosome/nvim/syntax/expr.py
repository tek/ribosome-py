from amino import Dat, Map, ADT, List, Nil, Maybe, Lists


class SyntaxItem(ADT['SyntaxItem']):
    pass


class SyntaxKeyword(SyntaxItem):

    @staticmethod
    def cons(
            group: str,
            keyword: str,
            *options: str,
            keywords: List[str]=Nil,
            **params: str,
    ) -> 'SyntaxKeyword':
        return SyntaxKeyword(
            group,
            keyword,
            keywords,
            Lists.wrap(options),
            Map(params),
        )

    def __init__(
            self,
            group: str,
            keyword: str,
            keywords: List[str],
            options: List[str],
            params: Map[str, str],
    ) -> None:
        self.group = group
        self.keyword = keyword
        self.keywords = keywords
        self.params = params
        self.options = options
        self.params = params


class SyntaxMatch(SyntaxItem):

    @staticmethod
    def cons(
            group: str,
            pattern: str,
            *options: str,
            **params: str,
    ) -> 'SyntaxMatch':
        return SyntaxMatch(
            group,
            pattern,
            Lists.wrap(options),
            Map(params),
        )

    def __init__(self, group: str, pattern: str, options: List[str], params: Map[str, str]) -> None:
        self.group = group
        self.pattern = pattern
        self.options = options
        self.params = params


class SyntaxRegion(SyntaxItem):

    @staticmethod
    def cons(
            group: str,
            start: str,
            end: str,
            *options: str,
            skip: str=None,
            starts: List[str]=Nil,
            stops: List[str]=Nil,
            **params: str,
    ) -> 'SyntaxRegion':
        return SyntaxRegion(
            group,
            start,
            end,
            Maybe.optional(skip),
            Lists.wrap(options),
            Map(params),
        )

    def __init__(
            self,
            group: str,
            start: str,
            end: str,
            skip: Maybe[str],
            options: List[str],
            params: Map[str, str],
    ) -> None:
        self.group = group
        self.start = start
        self.end = end
        self.skip = skip
        self.options = options
        self.params = params


class SyntaxLiteral(SyntaxItem):

    def __init__(self, cmd: str) -> None:
        self.cmd = cmd


class Highlight(Dat['Highlight']):

    @staticmethod
    def cons(
            group: str,
            **values: int,
    ) -> 'Highlight':
        return Highlight(
            group,
            Map(values),
        )

    def __init__(self, group: str, values: Map[str, int]) -> None:
        self.group = group
        self.values = values


class HiLink(Dat['HiLink']):

    @staticmethod
    def cons(
            group: str,
            target: str,
    ) -> 'HiLink':
        return HiLink(
            group,
            target,
        )

    def __init__(self, group: str, target: str) -> None:
        self.group = group
        self.target = target


__all__ = ('SyntaxMatch',)
