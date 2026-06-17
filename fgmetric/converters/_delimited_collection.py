from typing import Any
from typing import ClassVar
from typing import final
from typing import get_args
from typing import get_origin

from pydantic import BaseModel
from pydantic import FieldSerializationInfo
from pydantic import SerializerFunctionWrapHandler
from pydantic import ValidationInfo
from pydantic import field_serializer
from pydantic import field_validator

from fgmetric._typing_extensions import is_collection
from fgmetric._typing_extensions import is_optional
from fgmetric._typing_extensions import unpack_optional


# NB: Inheriting from BaseModel is necessary to declare field/model validators on the mixin, and
# for the class-level validations defined in `__pydantic_init_subclass__` to work.
class DelimitedCollection(BaseModel):
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

    collection_delimiter: ClassVar[str] = ","
    _collection_fieldnames: ClassVar[set[str]]
    _uniform_optional_element_fieldnames: ClassVar[set[str]]
    _tuple_optional_positions: ClassVar[dict[str, tuple[bool, ...]]]

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        """
        Validate the collection delimiter and classify the model's collection fields.

        1. The collection delimiter must be a single character.
        2. Each `list`/`set`/`frozenset`/`tuple` field is recorded, along with the
           per-element/per-position optionality needed to map empty cells to `None`.
        """
        super().__pydantic_init_subclass__(**kwargs)

        cls._require_single_character_collection_delimiter()
        cls._classify_collection_fields()

    @classmethod
    def _require_single_character_collection_delimiter(cls) -> None:
        """Require collection delimiters to be single characters."""
        if len(cls.collection_delimiter) != 1:
            raise ValueError(
                "collection_delimiter must be a single character,"
                f" got: {cls.collection_delimiter!r}"
            )

    @classmethod
    def _classify_collection_fields(cls) -> None:
        """Scan the model's fields once, recording each collection field's behavior."""
        cls._collection_fieldnames = set()
        cls._uniform_optional_element_fieldnames = set()
        cls._tuple_optional_positions = {}

        for name, info in cls.model_fields.items():
            annotation = info.annotation
            if not is_collection(annotation):
                continue

            cls._collection_fieldnames.add(name)

            inner = _strip_optional(annotation)
            args = get_args(inner)

            # A fixed-arity tuple (e.g. `tuple[int, str]`) has per-position element types; every
            # other collection — including the variadic `tuple[T, ...]` — has a single, uniform
            # element type.
            is_fixed_tuple = (
                get_origin(inner) is tuple and args != () and not _is_variadic_tuple_args(args)
            )
            if is_fixed_tuple:
                cls._tuple_optional_positions[name] = tuple(is_optional(arg) for arg in args)
            elif args and is_optional(args[0]):
                cls._uniform_optional_element_fieldnames.add(name)

    @final
    @field_validator("*", mode="before")
    @classmethod
    def _split_collections(cls, value: Any, info: ValidationInfo) -> Any:
        """Split any collection field into the intermediate list Pydantic then coerces."""
        if isinstance(value, str) and cls._is_collection_field(info.field_name):
            return cls._split_collection(value, info.field_name)
        return value

    @final
    @classmethod
    def _split_collection(cls, value: str, name: str | None) -> list[Any]:
        """Split a collection cell into a flat list of (string-or-`None`) elements."""
        if not value:
            return []

        elements: list[Any] = value.split(cls.collection_delimiter)

        # Map empty elements to `None` where the corresponding element type is optional.
        if name in cls._uniform_optional_element_fieldnames:
            elements = [None if element == "" else element for element in elements]
        elif name in cls._tuple_optional_positions:
            mask = cls._tuple_optional_positions[name]
            elements = [
                None if (index < len(mask) and mask[index] and element == "") else element
                for index, element in enumerate(elements)
            ]

        return elements

    @final
    @field_serializer("*", mode="wrap")
    def _join_collections(
        self,
        value: Any,
        nxt: SerializerFunctionWrapHandler,
        info: FieldSerializationInfo,
    ) -> Any:
        """Join any collection field back into a single delimited string."""
        if self._is_collection_field(info.field_name) and isinstance(
            value, (list, set, frozenset, tuple)
        ):
            return self._join_collection(value, nxt)
        return nxt(value)

    @final
    def _join_collection(self, value: Any, nxt: SerializerFunctionWrapHandler) -> Any:
        """Serialize each element, then join into a delimited string."""
        # Let the default serializer handle each element first, applying any per-element custom
        # serialization. This returns the elements as an iterable (a list in JSON mode).
        serialized = nxt(value)
        if not isinstance(serialized, (list, set, frozenset, tuple)):
            # If the handler already produced something else (unlikely), return it as-is.
            return serialized

        elements = ["" if item is None else str(item) for item in serialized]

        # `list`/`tuple` are ordered, so preserve order. `set`/`frozenset` are unordered (and
        # string hashing is per-process salted), so sort by serialized form for a stable roundtrip.
        if isinstance(value, (set, frozenset)):
            elements.sort()

        return self.collection_delimiter.join(elements)

    @final
    @classmethod
    def _is_collection_field(cls, field_name: str | None) -> bool:
        """True if the field is annotated as a delimited collection on the class model."""
        return field_name is not None and field_name in cls._collection_fieldnames


def _strip_optional(annotation: Any) -> Any:
    """Return the inner type of an optional annotation, or the annotation unchanged."""
    return unpack_optional(annotation) if is_optional(annotation) else annotation


def _is_variadic_tuple_args(args: tuple[Any, ...]) -> bool:
    """True if a tuple's type arguments describe a variadic `tuple[T, ...]`."""
    return len(args) == 2 and args[1] is Ellipsis
