from typing import ClassVar

from fgmetric.converters._delimited import _DelimitedConverter


class DelimitedCollection(_DelimitedConverter):
    """
    Serialize and deserialize delimited collections of (de)serializable types.

    When this mixin is added to `Metric`, fields annotated as `list[T]`, `set[T]`, `frozenset[T]`,
    or `tuple[...]` will be read and written as delimited strings. During validation, a delimited
    string is split into its elements, which are validated as instances of the declared element
    type(s); Pydantic performs the container coercion (list, set, frozenset, or tuple). During
    serialization, the elements are serialized to string and joined back into a delimited string.

    The element type(s) may be any serializable type. A field may be annotated as `list[T]`,
    `set[T]`, `frozenset[T]`, the variadic `tuple[T, ...]`, or the fixed-arity, heterogeneous
    `tuple[T1, T2, ...]` (whose arity and per-position types Pydantic validates). Any of these may
    also be made optional (e.g. `list[T] | None`); as with any primitive type, `None` is validated
    from and serialized to the empty string.

    The delimiter may be configured by specifying the `collection_delimiter` class variable when
    declaring a model.

    Note:
        `list` and `tuple` are ordered, so their element order is preserved. `set` and `frozenset`
        are unordered (and string hashing is per-process salted), so their elements are serialized
        sorted by their serialized form, which keeps the output stable across runs and roundtrips.

    Note:
        Roundtrips are lossy if elements contain the delimiter character. For example, with the
        default comma delimiter, `["a,b", "c"]` serializes to `"a,b,c"` and deserializes back to
        `["a", "b", "c"]`. Avoid using delimiters that may appear in element values. Collections
        are also flat: nested collections (e.g. `list[list[int]]`) are not supported, because a
        flat delimited string cannot be unambiguously re-nested.

    Examples:
        Basic usage — comma delimiter (default):

        ```python
        class MyMetric(Metric):
            tags: list[int]  # "1,2,3" becomes [1, 2, 3]

        MyMetric.model_validate({"tags": "1,2,3"}).tags        # -> [1, 2, 3]
        MyMetric(tags=[1, 2, 3]).model_dump()  # -> {"tags": "1,2,3"}
        ```

        Sets and frozensets — output is sorted by serialized form:

        ```python
        class MyMetric(Metric):
            tags: set[int]  # "3,1,2" becomes {1, 2, 3}

        MyMetric.model_validate({"tags": "3,1,2"}).tags        # -> {1, 2, 3}
        MyMetric(tags={3, 1, 2}).model_dump()  # -> {"tags": "1,2,3"}
        ```

        Heterogeneous tuples — arity and per-position types are validated:

        ```python
        class MyMetric(Metric):
            point: tuple[int, str]  # "1,foo" becomes (1, "foo")

        MyMetric.model_validate({"point": "1,foo"}).point     # -> (1, "foo")
        ```

        Custom delimiter:

        ```python
        class MyMetric(Metric):
            collection_delimiter = ";"
            tags: list[int]  # "1;2;3" becomes [1, 2, 3]

        MyMetric.model_validate({"tags": "1;2;3"}).tags        # -> [1, 2, 3]
        MyMetric(tags=[1, 2, 3]).model_dump()  # -> {"tags": "1;2;3"}
        ```

        Optional collection field — the whole field may be absent:

        ```python
        class MyMetric(Metric):
            tags: list[int] | None  # "" becomes None

        MyMetric.model_validate({"tags": ""}).tags             # -> None
        MyMetric(tags=None).model_dump()   # -> {"tags": None}
        ```

        Collection with optional elements — individual elements may be absent:

        ```python
        class MyMetric(Metric):
            tags: list[int | None]  # "1,,3" becomes [1, None, 3]

        MyMetric.model_validate({"tags": "1,,3"}).tags         # -> [1, None, 3]
        MyMetric(tags=[1, None, 3]).model_dump()  # -> {"tags": "1,,3"}
        ```
    """

    _handles_collections: ClassVar[bool] = True
