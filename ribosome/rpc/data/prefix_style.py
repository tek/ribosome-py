from amino import ADT, Boolean


class PrefixStyle(ADT['PrefixStyle']):

    @property
    def short(self) -> Boolean:
        return Boolean.isinstance(self, Short)

    @property
    def full(self) -> Boolean:
        return Boolean.isinstance(self, Full)

    @property
    def plain(self) -> Boolean:
        return Boolean.isinstance(self, Plain)


class Short(PrefixStyle): pass


class Full(PrefixStyle): pass


class Plain(PrefixStyle): pass



__all__ = ('PrefixStyle', 'Short', 'Full', 'Plain',)
