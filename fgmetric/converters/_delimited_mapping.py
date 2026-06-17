from typing import ClassVar

from fgmetric.converters._delimited import _DelimitedConverter


class DelimitedMapping(_DelimitedConverter):
    """
    Serialize and deserialize delimited mappings of (de)serializable types.

    When this mixin is added to `Metric`, fields annotated as `dict[K, V]` will be read and written
    as delimited strings of key/value pairs. During validation, the string is split into pairs on
    `collection_delimiter`, each pair is split into a key and value on `key_value_delimiter`, and
    the keys and values are validated as instances of `K` and `V`. During serialization, the keys
    and values are serialized to string and joined back into the same shape.

    The key and value types may be any serializable type. The field may be annotated as
    `dict[K, V]` or `dict[K, V] | None`; as with any primitive type, `None` is validated from and
    serialized to the empty string. A `dict[K, V | None]` additionally maps an empty value to
    `None`.

    The pair delimiter is shared with `DelimitedCollection` via the `collection_delimiter` class
    variable (default `","`); the key/value delimiter is configured separately via the
    `key_value_delimiter` class variable (default `"="`). The two must be distinct single
    characters.

    Note:
        Only the first occurrence of `key_value_delimiter` splits each pair, so values may contain
        it (e.g. with the default delimiters, `"url=http://a=b"` parses to `{"url": "http://a=b"}`).

    Note:
        `Counter` is a `dict` subclass but is handled by `CounterPivotTable`, not this mixin.

    Note:
        Roundtrips are lossy if keys or values contain a delimiter character. Mappings are also
        flat: nested mappings (e.g. `dict[str, list[int]]`) are not supported, because a flat
        delimited string cannot be unambiguously re-nested.

    Examples:
        Basic usage — comma pair delimiter and `=` key/value delimiter (defaults):

        ```python
        class MyMetric(Metric):
            counts: dict[str, int]  # "a=1,b=2" becomes {"a": 1, "b": 2}

        MyMetric.model_validate({"counts": "a=1,b=2"}).counts  # -> {"a": 1, "b": 2}
        MyMetric(counts={"a": 1, "b": 2}).model_dump()  # -> {"counts": "a=1,b=2"}
        ```

        Custom delimiters:

        ```python
        class MyMetric(Metric):
            collection_delimiter = ";"
            key_value_delimiter = ":"
            counts: dict[str, int]  # "a:1;b:2" becomes {"a": 1, "b": 2}
        ```

        Optional values — individual values may be absent:

        ```python
        class MyMetric(Metric):
            counts: dict[str, int | None]  # "a=,b=2" becomes {"a": None, "b": 2}
        ```
    """

    key_value_delimiter: ClassVar[str] = "="
    _handles_mappings: ClassVar[bool] = True
