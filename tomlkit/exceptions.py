from __future__ import annotations

from collections.abc import Collection


class TOMLKitError(Exception):
    pass


class ParseError(ValueError, TOMLKitError):
    """
    This error occurs when the parser encounters a syntax error
    in the TOML being parsed. The error references the line and
    location within the line where the error was encountered.
    """

    def __init__(self, line: int, col: int, message: str | None = None) -> None:
        self._line = line
        self._col = col

        if message is None:
            message = "TOML parse error"

        super().__init__(f"{message} at line {self._line} col {self._col}")

    @property
    def line(self) -> int:
        return self._line

    @property
    def col(self) -> int:
        return self._col


class MixedArrayTypesError(ParseError):
    """
    An array was found that had two or more element types.
    """

    def __init__(self, line: int, col: int) -> None:
        message = "Mixed types found in array"

        super().__init__(line, col, message=message)


class InvalidNumberError(ParseError):
    """
    A numeric field was improperly specified.
    """

    def __init__(self, line: int, col: int) -> None:
        message = "Invalid number"

        super().__init__(line, col, message=message)


def _brief(literal: str, limit: int = 40) -> str:
    # A collector tool can emit a literal thousands of characters long; keep
    # the message readable while ``IntegerOverflowError.literal`` retains it.
    if len(literal) <= limit:
        return literal
    return f"{literal[:limit]}... ({len(literal)} chars)"


class IntegerOverflowError(InvalidNumberError):
    """
    An integer literal did not fit in a signed 64-bit integer.

    TOML requires integers outside ``[-2**63, 2**63 - 1]`` to be rejected
    rather than wrapped or truncated. ``line`` and ``col`` point at the start
    of the offending integer literal when it comes from parsed TOML; the
    constructing helpers (``tomlkit.integer()``, ``item()``) have no source
    text, so they report the start of their single-line input (line 1, col 0).
    """

    def __init__(self, line: int, col: int, literal: str) -> None:
        self._literal = literal
        message = f"Integer {_brief(literal)!r} does not fit in a signed 64-bit integer"

        # Bypass InvalidNumberError's fixed message: this is an invalid number,
        # but the message has to name the offending literal.
        ParseError.__init__(self, line, col, message=message)

    @property
    def literal(self) -> str:
        """The literal (or value) that was out of range."""
        return self._literal


class InvalidDateTimeError(ParseError):
    """
    A datetime field was improperly specified.
    """

    def __init__(self, line: int, col: int) -> None:
        message = "Invalid datetime"

        super().__init__(line, col, message=message)


class InvalidDateError(ParseError):
    """
    A date field was improperly specified.
    """

    def __init__(self, line: int, col: int) -> None:
        message = "Invalid date"

        super().__init__(line, col, message=message)


class InvalidTimeError(ParseError):
    """
    A date field was improperly specified.
    """

    def __init__(self, line: int, col: int) -> None:
        message = "Invalid time"

        super().__init__(line, col, message=message)


class InvalidNumberOrDateError(ParseError):
    """
    A numeric or date field was improperly specified.
    """

    def __init__(self, line: int, col: int) -> None:
        message = "Invalid number or date format"

        super().__init__(line, col, message=message)


class InvalidUnicodeValueError(ParseError):
    """
    A unicode code was improperly specified.
    """

    def __init__(self, line: int, col: int) -> None:
        message = "Invalid unicode value"

        super().__init__(line, col, message=message)


class UnexpectedCharError(ParseError):
    """
    An unexpected character was found during parsing.
    """

    def __init__(self, line: int, col: int, char: str) -> None:
        message = f"Unexpected character: {char!r}"

        super().__init__(line, col, message=message)


class EmptyKeyError(ParseError):
    """
    An empty key was found during parsing.
    """

    def __init__(self, line: int, col: int) -> None:
        message = "Empty key"

        super().__init__(line, col, message=message)


class EmptyTableNameError(ParseError):
    """
    An empty table name was found during parsing.
    """

    def __init__(self, line: int, col: int) -> None:
        message = "Empty table name"

        super().__init__(line, col, message=message)


class InvalidCharInStringError(ParseError):
    """
    The string being parsed contains an invalid character.
    """

    def __init__(self, line: int, col: int, char: str) -> None:
        message = f"Invalid character {char!r} in string"

        super().__init__(line, col, message=message)


class UnexpectedEofError(ParseError):
    """
    The TOML being parsed ended before the end of a statement.
    """

    def __init__(self, line: int, col: int) -> None:
        message = "Unexpected end of file"

        super().__init__(line, col, message=message)


class InternalParserError(ParseError):
    """
    An error that indicates a bug in the parser.
    """

    def __init__(self, line: int, col: int, message: str | None = None) -> None:
        msg = "Internal parser error"
        if message:
            msg += f" ({message})"

        super().__init__(line, col, message=msg)


class NonExistentKey(KeyError, TOMLKitError):
    """
    A non-existent key was used.
    """

    def __init__(self, key: object) -> None:
        message = f'Key "{key}" does not exist.'

        super().__init__(message)


class KeyAlreadyPresent(TOMLKitError):
    """
    An already present key was used.
    """

    def __init__(self, key: object) -> None:
        key = getattr(key, "key", key)
        message = f'Key "{key}" already exists.'

        super().__init__(message)


class InvalidControlChar(ParseError):
    def __init__(self, line: int, col: int, char: int, type: str) -> None:
        display_code = "\\u00"

        if char < 16:
            display_code += "0"

        display_code += hex(char)[2:]

        message = (
            "Control characters (codes less than 0x1f and 0x7f)"
            f" are not allowed in {type}, "
            f"use {display_code} instead"
        )

        super().__init__(line, col, message=message)


class InvalidStringError(ValueError, TOMLKitError):
    def __init__(self, value: str, invalid_sequences: Collection[str], delimiter: str):
        repr_ = repr(value)[1:-1]
        super().__init__(
            f"Invalid string: {delimiter}{repr_}{delimiter}. "
            f"The character sequences {invalid_sequences} are invalid."
        )


class ConvertError(TypeError, ValueError, TOMLKitError):
    """Raised when item() fails to convert a value.
    It should be a TypeError, but due to historical reasons
    it needs to subclass ValueError as well.
    """
