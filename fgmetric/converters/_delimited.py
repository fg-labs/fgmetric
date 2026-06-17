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
from fgmetric._typing_extensions import is_mapping
from fgmetric._typing_extensions import is_optional
from fgmetric._typing_extensions import unpack_optional


# NB: Inheriting from BaseModel is necessary to declare field/model validators on the mixin, and
# for the class-level validations defined in `__pydantic_init_subclass__` to work.
class _DelimitedConverter(BaseModel):
    """
    Shared plumbing for the delimited-collection converters.

    This non-exported base holds the `collection_delimiter` class variable, the single
    field-classification scan run in `__pydantic_init_subclass__`, and the single field validator
    and field serializer shared by `DelimitedCollection` and `DelimitedMapping`.

    The validator and serializer live here, rather than on the individual mixins, because Pydantic
    permits only *one* serializer per field: two mixins each declaring `field_serializer("*")`
    would collide, with only the first in the MRO taking effect. A single dispatcher on the shared
    base sidesteps that. The dispatcher is gated by the `_handles_collections` and
    `_handles_mappings` flags, which each mixin flips on. Because the flags resolve through the
    concrete model's MRO, mixing in `DelimitedCollection` alone enables only collection handling,
    `DelimitedMapping` alone enables only mapping handling, and mixing in both enables both — which
    preserves the granular, per-type opt-in.

    The `key_value_delimiter` class variable is declared (without a default) for the benefit of the
    shared serializer's mapping branch; `DelimitedMapping` supplies the default. It is never read
    unless `_handles_mappings` is set, so collection-only models need not define it.
    """

    collection_delimiter: ClassVar[str] = ","
    key_value_delimiter: ClassVar[str]

    # Opt-in flags, flipped on by the respective mixin and resolved through the model's MRO.
    _handles_collections: ClassVar[bool] = False
    _handles_mappings: ClassVar[bool] = False

    # Field classifications, populated by the shared `__pydantic_init_subclass__` scan.
    _collection_fieldnames: ClassVar[set[str]]
    _mapping_fieldnames: ClassVar[set[str]]
    _uniform_optional_element_fieldnames: ClassVar[set[str]]
    _tuple_optional_positions: ClassVar[dict[str, tuple[bool, ...]]]
    _mapping_optional_value_fieldnames: ClassVar[set[str]]

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        """
        Validate the configured delimiters and classify the model's fields.

        1. The configured delimiters must each be a single character (and, when mapping handling
           is enabled, must differ from each other).
        2. Each field is classified as a delimited collection, a delimited mapping, or neither,
           recording the per-element/per-value optionality needed to map empty cells to `None`.
        """
        super().__pydantic_init_subclass__(**kwargs)

        cls._require_single_character_delimiters()
        cls._classify_fields()

    @classmethod
    def _require_single_character_delimiters(cls) -> None:
        """Require the configured delimiters to be single, distinct characters."""
        if len(cls.collection_delimiter) != 1:
            raise ValueError(
                "collection_delimiter must be a single character,"
                f" got: {cls.collection_delimiter!r}"
            )

        if cls._handles_mappings:
            if len(cls.key_value_delimiter) != 1:
                raise ValueError(
                    "key_value_delimiter must be a single character,"
                    f" got: {cls.key_value_delimiter!r}"
                )
            if cls.key_value_delimiter == cls.collection_delimiter:
                raise ValueError(
                    "key_value_delimiter and collection_delimiter must differ,"
                    f" both are: {cls.collection_delimiter!r}"
                )

    @classmethod
    def _classify_fields(cls) -> None:
        """Scan the model's fields once, recording each field's delimited-converter behavior."""
        cls._collection_fieldnames = set()
        cls._mapping_fieldnames = set()
        cls._uniform_optional_element_fieldnames = set()
        cls._tuple_optional_positions = {}
        cls._mapping_optional_value_fieldnames = set()

        for name, info in cls.model_fields.items():
            annotation = info.annotation
            if is_mapping(annotation):
                cls._classify_mapping_field(name, annotation)
            elif is_collection(annotation):
                cls._classify_collection_field(name, annotation)

    @classmethod
    def _classify_collection_field(cls, name: str, annotation: Any) -> None:
        """Record a `list`/`set`/`frozenset`/`tuple` field and its optional-element structure."""
        cls._collection_fieldnames.add(name)

        inner = _strip_optional(annotation)
        args = get_args(inner)

        # A fixed-arity tuple (e.g. `tuple[int, str]`) has per-position element types; every other
        # collection — including the variadic `tuple[T, ...]` — has a single, uniform element type.
        is_fixed_tuple = (
            get_origin(inner) is tuple and args != () and not _is_variadic_tuple_args(args)
        )
        if is_fixed_tuple:
            cls._tuple_optional_positions[name] = tuple(is_optional(arg) for arg in args)
        elif args and is_optional(args[0]):
            cls._uniform_optional_element_fieldnames.add(name)

    @classmethod
    def _classify_mapping_field(cls, name: str, annotation: Any) -> None:
        """Record a `dict[K, V]` field and whether its value type is optional."""
        cls._mapping_fieldnames.add(name)

        inner = _strip_optional(annotation)
        args = get_args(inner)
        if len(args) == 2 and is_optional(args[1]):
            cls._mapping_optional_value_fieldnames.add(name)

    @final
    @field_validator("*", mode="before")
    @classmethod
    def _split_delimited(cls, value: Any, info: ValidationInfo) -> Any:
        """Split a delimited string field into the intermediate shape Pydantic then coerces."""
        if not isinstance(value, str):
            return value

        name = info.field_name
        if cls._handles_collections and name in cls._collection_fieldnames:
            return cls._split_collection(value, name)
        if cls._handles_mappings and name in cls._mapping_fieldnames:
            return cls._split_mapping(value, name)

        return value

    @final
    @classmethod
    def _split_collection(cls, value: str, name: str) -> list[Any]:
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
    @classmethod
    def _split_mapping(cls, value: str, name: str) -> dict[Any, Any]:
        """Split a mapping cell into a dict of (string-or-`None`) keys and values."""
        if not value:
            return {}

        result: dict[Any, Any] = {}
        for pair in value.split(cls.collection_delimiter):
            if cls.key_value_delimiter not in pair:
                raise ValueError(
                    f"Expected a {cls.key_value_delimiter!r}-delimited key/value pair,"
                    f" got: {pair!r}"
                )
            key, item = pair.split(cls.key_value_delimiter, 1)
            if item == "" and name in cls._mapping_optional_value_fieldnames:
                result[key] = None
            else:
                result[key] = item

        return result

    @final
    @field_serializer("*", mode="wrap")
    def _join_delimited(
        self,
        value: Any,
        nxt: SerializerFunctionWrapHandler,
        info: FieldSerializationInfo,
    ) -> Any:
        """Join a delimited collection/mapping field back into a single delimited string."""
        name = info.field_name
        if (
            self._handles_collections
            and name in self._collection_fieldnames
            and isinstance(value, (list, set, frozenset, tuple))
        ):
            return self._join_collection(value, nxt)
        if self._handles_mappings and name in self._mapping_fieldnames and isinstance(value, dict):
            return self._join_mapping(value, nxt)

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
    def _join_mapping(self, value: Any, nxt: SerializerFunctionWrapHandler) -> Any:
        """Serialize each key and value, then join into a delimited string of pairs."""
        serialized = nxt(value)
        if not isinstance(serialized, dict):
            # If the handler already produced something else (unlikely), return it as-is.
            return serialized

        pairs = [
            f"{'' if key is None else key}{self.key_value_delimiter}{'' if item is None else item}"
            for key, item in serialized.items()
        ]
        return self.collection_delimiter.join(pairs)


def _strip_optional(annotation: Any) -> Any:
    """Return the inner type of an optional annotation, or the annotation unchanged."""
    return unpack_optional(annotation) if is_optional(annotation) else annotation


def _is_variadic_tuple_args(args: tuple[Any, ...]) -> bool:
    """True if a tuple's type arguments describe a variadic `tuple[T, ...]`."""
    return len(args) == 2 and args[1] is Ellipsis
