from typing import Any
from typing import ClassVar
from typing import final

from pydantic import BaseModel
from pydantic import ValidationInfo
from pydantic import field_validator

from fgmetric._typing_extensions import is_bool


# NB: Inheriting from BaseModel is necessary to declare field validators on the mixin, and for the
# class-level initialization in `__pydantic_init_subclass__` to work.
class BoolTokens(BaseModel):
    """
    Restrict boolean parsing to a narrow, configurable set of tokens.

    Pydantic accepts a broad set of strings as booleans (`true`/`t`/`yes`/`y`/`on`/`1` and their
    false counterparts). With this mixin, fields annotated as `bool` or `bool | None` are instead
    resolved from a narrow set of tokens *before* Pydantic's coercion runs: the incoming string
    must match one of `true_tokens` or `false_tokens` (case-insensitively), or a `ValidationError`
    is raised at the offending cell. `Metric` includes this behavior by default.

    The default token set mirrors `fgpyo.util.types.parse_bool`: `{"true", "t", "1"}` for `True`
    and `{"false", "f", "0"}` for `False`. This is stricter than Pydantic, which would also accept
    `yes`/`y`/`on`/`no`/`n`/`off`. Rejecting those guards against a misaligned or wrong-type column
    being silently coerced, and gives tools ported from fgpyo identical accept/reject behavior.

    This mixin is read-side only; a `bool` still serializes to `"True"`/`"False"`.

    Tokens are matched case-insensitively. `true_tokens` and `false_tokens` must be disjoint;
    declaring a token in both is rejected at class definition.

    Class Variables:
        true_tokens: The strings resolved to `True`. Defaults to `frozenset({"true", "t", "1"})`.
        false_tokens: The strings resolved to `False`. Defaults to `frozenset({"false", "f", "0"})`.

    Note:
        `bool` is a subclass of `int`, but only fields annotated exactly as `bool` or `bool | None`
        are affected; `int` fields are untouched.

        When combined with `NullSentinels`, the model-level null substitution runs first, so an
        empty `bool | None` cell is converted to `None` before this validator sees it (provided
        `""` is a configured null sentinel). Without such a sentinel, an empty cell on a `bool`
        field is rejected, since `""` is in neither token set.

    Examples:
        `Metric` parses bool fields from the default tokens out of the box:

        ```python
        class MyMetric(Metric):
            flag: bool

        MyMetric.model_validate({"flag": "1"}).flag      # -> True
        MyMetric.model_validate({"flag": "yes"})         # -> ValidationError
        ```

        Customize the accepted tokens:

        ```python
        class MyMetric(Metric):
            true_tokens = frozenset({"yes", "y"})
            false_tokens = frozenset({"no", "n"})
            flag: bool
        ```
    """

    # Public, user-specified token sets.
    true_tokens: ClassVar[frozenset[str]] = frozenset({"true", "t", "1"})
    false_tokens: ClassVar[frozenset[str]] = frozenset({"false", "f", "0"})

    # Internal: lowercase copies of the user-specified token sets, used for the actual matching.
    _true_tokens: ClassVar[frozenset[str]]
    _false_tokens: ClassVar[frozenset[str]]

    _bool_fieldnames: ClassVar[set[str]]

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        """
        Record bool fields and the case-folded token sets used for matching.

        1. The names of all fields annotated as `bool` or `bool | None` are stored in the private
           `_bool_fieldnames` class variable.
        2. `true_tokens` and `false_tokens` are case-folded into private sets for case-insensitive
           matching, and validated to be disjoint.
        """
        super().__pydantic_init_subclass__(**kwargs)

        cls._bool_fieldnames = {
            name for name, info in cls.model_fields.items() if is_bool(info.annotation)
        }
        cls._true_tokens = frozenset(token.casefold() for token in cls.true_tokens)
        cls._false_tokens = frozenset(token.casefold() for token in cls.false_tokens)
        cls._require_disjoint_tokens()

    @classmethod
    def _require_disjoint_tokens(cls) -> None:
        """Require that no token is configured as both true and false."""
        overlap = cls._true_tokens & cls._false_tokens
        if overlap:
            raise ValueError(
                "true_tokens and false_tokens must be disjoint,"
                f" got overlapping tokens: {sorted(overlap)}"
            )

    @final
    @field_validator("*", mode="before")
    @classmethod
    def _parse_bool_tokens(cls, value: Any, info: ValidationInfo) -> Any:
        """Resolve string values on bool fields to `True`/`False` from the configured tokens."""
        if isinstance(value, str) and info.field_name in cls._bool_fieldnames:
            token = value.casefold()
            if token in cls._true_tokens:
                return True
            elif token in cls._false_tokens:
                return False
            else:
                raise ValueError(
                    f"Invalid boolean token {value!r}; expected one of"
                    f" {sorted(cls.true_tokens | cls.false_tokens)}"
                )

        return value
