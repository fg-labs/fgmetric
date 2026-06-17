from typing import Optional
from typing import Union

import pytest

from fgmetric._typing_extensions import TypeAnnotation
from fgmetric._typing_extensions import has_optional_elements
from fgmetric._typing_extensions import has_origin
from fgmetric._typing_extensions import is_bool
from fgmetric._typing_extensions import is_list
from fgmetric._typing_extensions import is_optional
from fgmetric._typing_extensions import unpack_optional


@pytest.mark.parametrize(
    "annotation",
    [
        Union[str, None],
        Optional[str],
        str | None,
        Union[str, int, None],
        str | int | None,
    ],
)
def test_is_optional(annotation: TypeAnnotation) -> None:
    """Should identify optional union types, including higher-arity unions."""
    assert is_optional(annotation)


@pytest.mark.parametrize(
    "annotation",
    [
        str,
        Union[str, int],
        str | int,
    ],
)
def test_is_not_optional(annotation: TypeAnnotation) -> None:
    """Should reject non-optional or non-union types."""
    assert not is_optional(annotation)


def test_unpack_optional() -> None:
    """Should retrieve the parameterized type."""
    assert unpack_optional(int | None) is int


def test_unpack_optional_higher_arity() -> None:
    """Should reconstruct a union from higher-arity optionals."""
    result = unpack_optional(str | int | None)
    # The result should be str | int (a UnionType)
    assert result == str | int


@pytest.mark.parametrize(
    "annotation",
    [
        list[int],
        list[str],
        Optional[list[str]],
        list[str] | None,
    ],
)
def test_is_list(annotation: TypeAnnotation) -> None:
    """Should identify lists, even within an Optional."""
    assert is_list(annotation)


@pytest.mark.parametrize(
    "annotation",
    [
        str,
        str | None,
    ],
)
def test_is_not_list(annotation: TypeAnnotation) -> None:
    """Should reject non-list types."""
    assert not is_list(annotation)


@pytest.mark.parametrize(
    "annotation",
    [
        bool,
        Optional[bool],
        bool | None,
    ],
)
def test_is_bool(annotation: TypeAnnotation) -> None:
    """Should identify `bool`, even within an Optional."""
    assert is_bool(annotation)


@pytest.mark.parametrize(
    "annotation",
    [
        int,  # `bool` is a subclass of `int`, but `int` is not `bool`
        int | None,
        str,
        bool | str,  # mixed union is not a pure bool field
        list[bool],
        bool | str | None,
    ],
)
def test_is_not_bool(annotation: TypeAnnotation) -> None:
    """Should reject types that are not exactly `bool` or `bool | None`."""
    assert not is_bool(annotation)


@pytest.mark.parametrize(
    "annotation,collection_type",
    [
        (list[int], list),
        (set[str], set),
        (dict[str, int], dict),
    ],
)
def test_has_origin(annotation: TypeAnnotation, collection_type: type) -> None:
    """Should identify parameterized collection types."""
    assert has_origin(annotation, collection_type)


@pytest.mark.parametrize(
    "annotation,collection_type",
    [
        (list[int] | None, list),
        (Optional[set[str]], set),
    ],
)
def test_has_origin_optional(annotation: TypeAnnotation, collection_type: type) -> None:
    """Should identify optional collection types."""
    assert has_origin(annotation, collection_type)


def test_has_origin_rejects_wrong_type() -> None:
    """Should reject collections of different types."""
    assert not has_origin(list[int], set)
    assert not has_origin(set[str], list)


@pytest.mark.parametrize(
    "annotation",
    [
        list[int | None],
        list[int | float | None],
        list[Optional[int]],
        list[Optional[int | float]],
        list[int | None] | None,
        list[int | float | None] | None,
        list[Optional[int]] | None,
        list[Optional[int | float]] | None,
        Optional[list[int | None]],
        Optional[list[int | float | None]],
        Optional[list[Optional[int]]],
        Optional[list[Optional[int | float]]],
    ],
)
def test_has_optional_elements(annotation: TypeAnnotation) -> None:
    """Should identify optional collection types."""
    assert has_optional_elements(annotation)


@pytest.mark.parametrize(
    "annotation",
    [
        list[int],
        list[int | float],
        list[int] | None,
        list[int | float] | None,
        Optional[list[int]],
        Optional[list[int | float]],
    ],
)
def test_not_has_optional_elements(annotation: TypeAnnotation) -> None:
    """Should reject non-optional collection types."""
    assert not has_optional_elements(annotation)
