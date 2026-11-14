"""Signed 64-bit range checks for integers.

TOML 1.0.0 / 1.1.0, "Integer": arbitrary 64-bit signed integers (from
-2^63 to 2^63-1) must be accepted and handled losslessly; if an integer
cannot be represented losslessly, an error must be thrown.

Both integer entry points are covered here:
* the parse path (``parse()``, ``value()``) through ``Parser._parse_number``
* the construction path (``tomlkit.integer()``, ``item()``) through
  ``Integer.__init__``
"""

from collections.abc import Callable

import pytest

from tomlkit import integer
from tomlkit import item
from tomlkit import parse
from tomlkit import value
from tomlkit.exceptions import IntegerOverflowError
from tomlkit.exceptions import InvalidNumberError
from tomlkit.exceptions import ParseError
from tomlkit.items import Integer


INT64_MIN = -(2**63)
INT64_MAX = 2**63 - 1

# Four boundary magnitudes: the highest/lowest value that fits, and the
# neighbouring values one step outside on each side.
BOUNDARIES = [
    pytest.param(INT64_MAX, id="max"),
    pytest.param(INT64_MAX + 1, id="max-plus-1"),
    pytest.param(INT64_MIN, id="min"),
    pytest.param(INT64_MIN - 1, id="min-minus-1"),
]


def _group(digits: str, size: int) -> str:
    """Group ``digits`` from the right with underscores every ``size`` chars."""
    if len(digits) <= size:
        return digits

    head = len(digits) % size or size
    parts = [digits[:head]]
    parts.extend(digits[i : i + size] for i in range(head, len(digits), size))
    return "_".join(parts)


def _decimal(n: int) -> str:
    return "-" + str(-n) if n < 0 else str(n)


def _decimal_grouped(n: int) -> str:
    return ("-" if n < 0 else "") + _group(str(abs(n)), 3)


def _hex(n: int) -> str:
    return ("-" if n < 0 else "") + "0x" + f"{abs(n):x}"


def _hex_grouped(n: int) -> str:
    return ("-" if n < 0 else "") + "0x" + _group(f"{abs(n):X}", 4)


def _octal(n: int) -> str:
    return ("-" if n < 0 else "") + "0o" + _group(f"{abs(n):o}", 3)


def _binary(n: int) -> str:
    return ("-" if n < 0 else "") + "0b" + _group(f"{abs(n):b}", 4)


# Six literal forms. Each builder takes a value and returns the literal text;
# "signed" says whether a negative value can be expressed at all (hex/octal/
# binary take no sign in TOML, so a negative value written with a leading "-"
# must be rejected as invalid syntax instead).
FORMS = [
    pytest.param(_decimal, True, id="decimal"),
    pytest.param(_decimal_grouped, True, id="decimal-underscored"),
    pytest.param(_hex, False, id="hex"),
    pytest.param(_hex_grouped, False, id="hex-underscored"),
    pytest.param(_octal, False, id="octal-underscored"),
    pytest.param(_binary, False, id="binary-underscored"),
]


def _expected(n: int, signed: bool) -> type[Exception] | None:
    """The exception a literal for ``n`` in this form must raise, or None."""
    if not signed and n < 0:
        # No sign is allowed on a prefixed literal: a grammar error, but still
        # an error -- such a value must never reach the document.
        return InvalidNumberError

    if INT64_MIN <= n <= INT64_MAX:
        return None

    return IntegerOverflowError


@pytest.mark.parametrize("build,signed", FORMS)
@pytest.mark.parametrize("n", BOUNDARIES)
def test_parser_boundary_matrix(
    build: Callable[[int], str], signed: bool, n: int
) -> None:
    """Six literal forms x four boundaries on the parse path."""
    literal = build(n)
    expected = _expected(n, signed)

    if expected is None:
        parsed = parse(f"a = {literal}")["a"]
        assert isinstance(parsed, Integer)
        assert int(parsed) == n
        assert parsed.as_string() == literal
        # the value survives a dumps()/parse() round trip unchanged
        bare = value(literal)
        assert isinstance(bare, Integer)
        assert int(bare) == n
        return

    with pytest.raises(expected):
        parse(f"a = {literal}")

    # value() is the same parse path, without a surrounding document
    with pytest.raises(expected):
        value(literal)


@pytest.mark.parametrize("build,signed", FORMS)
@pytest.mark.parametrize("n", BOUNDARIES)
def test_construction_boundary_matrix(
    build: Callable[[int], str], signed: bool, n: int
) -> None:
    """Six literal forms x four boundaries on the tomlkit.integer() path."""
    literal = build(n)

    if not signed and n < 0:
        # A prefixed literal takes no sign; integer() has no source position
        # to attach, so this stays a plain ValueError as before.
        with pytest.raises(ValueError):
            integer(literal)
        return

    expected = _expected(n, signed)

    if expected is None:
        built = integer(literal)
        assert int(built) == n
        assert built.as_string() == literal
        return

    with pytest.raises(expected):
        integer(literal)


@pytest.mark.parametrize("n", BOUNDARIES)
def test_item_from_int_boundaries(n: int) -> None:
    """The other construction entry point: item() given a Python int."""
    if INT64_MIN <= n <= INT64_MAX:
        assert int(item(n)) == n
        assert item(n).as_string() == _decimal(n)
        return

    with pytest.raises(IntegerOverflowError):
        item(n)

    with pytest.raises(IntegerOverflowError):
        integer(n)


@pytest.mark.parametrize(
    "literal",
    [
        "9223372036854775808",  # max + 1
        "-9223372036854775809",  # min - 1
        "+9223372036854775808",
        "0x8000_0000_0000_0000",
        "0o1_000_000_000_000_000_000_000",
        "0b1000_0000_0000_0000_0000_0000_0000_0000"
        "_0000_0000_0000_0000_0000_0000_0000_0000",
        "0x" + "f" * 32,  # an overlong literal as a collector tool may emit
    ],
)
def test_parser_reports_overflow_at_literal_start(literal: str) -> None:
    """The error type is IntegerOverflowError (an InvalidNumberError) and the
    position points at the start of the literal, not at its end."""
    content = "ok = 1\nbad = " + literal + "\n"
    with pytest.raises(IntegerOverflowError) as e:
        parse(content)

    # `bad = ` starts at column 0, so the literal starts at column 6 on line 2
    assert e.value.line == 2
    assert e.value.col == 6
    assert e.value.literal == literal
    assert isinstance(e.value, InvalidNumberError)
    assert isinstance(e.value, ParseError)


def test_parser_overflow_position_inside_array() -> None:
    content = "a = [\n  1,\n  0x8000_0000_0000_0000,\n]"
    with pytest.raises(IntegerOverflowError) as e:
        parse(content)

    assert e.value.line == 3
    assert e.value.col == 2


def test_parser_overflow_position_with_crlf() -> None:
    content = "a = 1\r\nb = -9223372036854775809\r\n"
    with pytest.raises(IntegerOverflowError) as e:
        parse(content)

    assert e.value.line == 2
    assert e.value.col == 4


def test_construction_overflow_reports_its_own_input() -> None:
    with pytest.raises(IntegerOverflowError) as e:
        integer("0x8000_0000_0000_0000")

    assert e.value.line == 1
    assert e.value.col == 0
    assert e.value.literal == "0x8000_0000_0000_0000"
    assert isinstance(e.value, ValueError)


def test_overlong_hex_and_binary_are_not_silently_truncated() -> None:
    """Regression for the upstream collector emitting overlong literals:
    these used to be accepted as arbitrary-precision Python ints."""
    for literal in (
        "0x" + "f" * 16,  # 2**64 - 1
        "0b" + "1" * 64,  # 2**64 - 1
        "0o" + "7" * 22,
        "9" * 40,
    ):
        with pytest.raises(InvalidNumberError):
            parse(f"a = {literal}")

    # one bit fewer is still inside the signed 64-bit range
    for literal in (
        "0x7" + "f" * 15,  # 0x7fffffffffffffff == 2**63 - 1
        "0b" + "1" * 63,  # 2**63 - 1
        "0o" + "7" * 21,  # 2**63 - 1
        "9223372036854775807",
    ):
        assert int(parse(f"a = {literal}")["a"]) == INT64_MAX


def test_spec_compatible_long_integers_still_parse() -> None:
    """The upstream toml-test `valid/integer/long` cases must not regress."""
    content = "int64-max     = 9223372036854775807\nint64-max-neg = -9223372036854775808\n"
    doc = parse(content)
    assert doc["int64-max"] == INT64_MAX
    assert doc["int64-max-neg"] == INT64_MIN
    assert doc.as_string() == content
