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
class _DelimitedConverter(BaseModel):
    """
    Shared plumbing for the delimited-collection converters.

    This non-exported base holds the `collection_delimiter` class variable, the single
    field-classification scan run in `__pydantic_init_subclass__`, and the single field validator
    and field serializer that the public delimited-converter mixins (currently
    `DelimitedCollection`) build on.

    The validator and serializer live here, rather than on the mixins, because Pydantic permits
    only *one* serializer per field: two mixins each declaring `field_serializer("*")` would
    collide, with only the first in the MRO taking effect. A single dispatcher on the shared base
    sidesteps that.
    """

    collection_delimiter: ClassVar[str] = ","
    _collection_fieldnames: ClassVar[set[str]]
    _uniform_optional_element_fieldnames: ClassVar[set[str]]
    _tuple_optional_positions: ClassVar[dict[str, tuple[bool, ...]]]

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        """
        Validate the collection delimiter and classify the model's fields.

        1. The collection delimiter must be a single character.
        2. Each `list`/`set`/`frozenset`/`tuple` field is recorded, along with the
           per-element/per-position optionality needed to map empty cells to `None`.
        """
        super().__pydantic_init_subclass__(**kwargs)

        cls._require_single_character_collection_delimiter()
        cls._classify_fields()

    @classmethod
    def _require_single_character_collection_delimiter(cls) -> None:
        """Require collection delimiters to be single characters."""
        if len(cls.collection_delimiter) != 1:
            raise ValueError(
                "collection_delimiter must be a single character,"
                f" got: {cls.collection_delimiter!r}"
            )

    @classmethod
    def _classify_fields(cls) -> None:
        """Scan the model's fields once, recording each field's delimited-converter behavior."""
        cls._collection_fieldnames = set()
        cls._uniform_optional_element_fieldnames = set()
        cls._tuple_optional_positions = {}

        for name, info in cls.model_fields.items():
            if is_collection(info.annotation):
                cls._classify_collection_field(name, info.annotation)

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

    @final
    @field_validator("*", mode="before")
    @classmethod
    def _split_delimited(cls, value: Any, info: ValidationInfo) -> Any:
        """Split a delimited string field into the intermediate shape Pydantic then coerces."""
        if not isinstance(value, str):
            return value

        name = info.field_name
        if name in cls._collection_fieldnames:
            return cls._split_collection(value, name)

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
    def _join_delimited(
        self,
        value: Any,
        nxt: SerializerFunctionWrapHandler,
        info: FieldSerializationInfo,
    ) -> Any:
        """Join a delimited collection field back into a single delimited string."""
        name = info.field_name
        if name in self._collection_fieldnames and isinstance(value, (list, set, frozenset, tuple)):
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


def _strip_optional(annotation: Any) -> Any:
    """Return the inner type of an optional annotation, or the annotation unchanged."""
    return unpack_optional(annotation) if is_optional(annotation) else annotation


def _is_variadic_tuple_args(args: tuple[Any, ...]) -> bool:
    """True if a tuple's type arguments describe a variadic `tuple[T, ...]`."""
    return len(args) == 2 and args[1] is Ellipsis
