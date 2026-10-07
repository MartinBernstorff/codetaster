"""Reads and edits JSON with comments and trailing commas (JSONC), keeping the text.

VS Code's `argv.json` is JSONC and the user may have edited it, so an edit inserts
text instead of re-serialising the document.
"""

import json
import re
from typing import cast

from pydantic import BaseModel, ConfigDict, RootModel
from safe_result import Err, Ok, Result

from codetaster.domain.domain_model.vscode_extension import ProblemDescription


class InvalidJsoncError(Exception):
    """The text is not JSONC of the expected shape."""

    def __init__(self, problem: ProblemDescription) -> None:
        super().__init__(str(problem))
        self.problem = problem

    @staticmethod
    def fake() -> InvalidJsoncError:
        return InvalidJsoncError(ProblemDescription.fake())


class JsoncText(RootModel[str]):
    """The text of a JSONC document."""

    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> JsoncText:
        return JsoncText('{\n\t// A comment\n\t"key": ["value",],\n}\n')


class JsonKey(RootModel[str]):
    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> JsonKey:
        return JsonKey("key")


class JsonString(RootModel[str]):
    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> JsonString:
        return JsonString("value")


class JsonStrings(RootModel[tuple[JsonString, ...]]):
    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> JsonStrings:
        return JsonStrings((JsonString.fake(),))


class Offset(RootModel[int]):
    """A character offset into a JSONC text."""

    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> Offset:
        return Offset(0)


class Token(BaseModel):
    """A string, number, literal or punctuation mark, with its place in the text."""

    model_config = ConfigDict(frozen=True)

    text: JsoncText
    start: Offset
    end: Offset

    @staticmethod
    def fake() -> Token:
        return Token(text=JsoncText("{"), start=Offset(0), end=Offset(1))


class Tokens(RootModel[tuple[Token, ...]]):
    """The tokens of a JSONC text, without whitespace, comments or trailing commas."""

    model_config = ConfigDict(frozen=True)

    def as_json(self) -> JsoncText:
        return JsoncText(" ".join(token.text.root for token in self.root))

    @staticmethod
    def fake() -> Tokens:
        return Tokens((Token.fake(),))


_TOKEN = re.compile(
    r"""
    (?P<skip>\s+|//[^\n]*|/\*.*?(?:\*/|\Z))
    | (?P<token>"(?:[^"\\]|\\.)*"?|[{}\[\]:,]|[^\s{}\[\]:,"/]+|/)
    """,
    re.VERBOSE | re.DOTALL,
)
_OPEN = (JsoncText("{"), JsoncText("["))
_CLOSE = (JsoncText("}"), JsoncText("]"))
_COMMA = JsoncText(",")


def tokenize_jsonc(text: JsoncText) -> Tokens:
    """Split `text` into tokens. Malformed input gives tokens JSON will reject."""
    tokens = [
        Token(
            text=JsoncText(match.group()),
            start=Offset(match.start()),
            end=Offset(match.end()),
        )
        for match in _TOKEN.finditer(text.root)
        if match.lastgroup == "token"
    ]
    without_trailing_commas = [
        token
        for index, token in enumerate(tokens)
        if not (
            token.text == _COMMA
            and index + 1 < len(tokens)
            and tokens[index + 1].text in _CLOSE
        )
    ]
    return Tokens(tuple(without_trailing_commas))


def read_string_list(
    text: JsoncText, key: JsonKey
) -> Result[JsonStrings, InvalidJsoncError]:
    """The strings under top-level `key`; empty if the key or the text is missing."""
    tokens = tokenize_jsonc(text)
    if not tokens.root:
        return Ok(JsonStrings(()))
    try:
        document: object = json.loads(tokens.as_json().root)
    except json.JSONDecodeError as error:
        return Err(
            InvalidJsoncError(
                ProblemDescription(f"not valid JSON with comments: {error}")
            )
        )
    if not isinstance(document, dict):
        return Err(
            InvalidJsoncError(ProblemDescription("the top level is not a JSON object"))
        )
    values = cast("dict[str, object]", document).get(key.root, [])
    items = cast("list[object]", values) if isinstance(values, list) else None
    strings = [item for item in items or [] if isinstance(item, str)]
    if items is None or len(strings) != len(items):
        problem = f'"{key.root}" is not a list of strings'
        return Err(InvalidJsoncError(ProblemDescription(problem)))
    return Ok(JsonStrings(tuple(JsonString(value) for value in strings)))


def append_to_string_list(
    text: JsoncText, key: JsonKey, value: JsonString
) -> Result[JsoncText, InvalidJsoncError]:
    """Append `value` to the list under top-level `key`, adding the key if missing.

    Comments, formatting and the other entries are kept as they are.
    """
    if isinstance(existing := read_string_list(text, key), Err):
        return existing
    tokens = tokenize_jsonc(text)
    encoded = json.dumps(value.root)
    entry = f"{json.dumps(key.root)}: [{encoded}]"
    if not tokens.root:
        separator = "" if text.root.endswith("\n") or not text.root else "\n"
        return Ok(JsoncText(f"{text.root}{separator}{{\n\t{entry}\n}}\n"))
    opening = _value_start_of(tokens, key)
    if opening is None:
        object_start, first_inside = tokens.root[0], tokens.root[1]
        separator = "" if first_inside.text in _CLOSE else ","
        return Ok(
            _insert_at_offset(
                text, object_start.end, JsoncText(f"\n\t{entry}{separator}")
            )
        )
    last = _last_token_inside(tokens, opening)
    if last is None:
        return Ok(_insert_at_offset(text, opening.end, JsoncText(encoded)))
    return Ok(_insert_at_offset(text, last.end, JsoncText(f", {encoded}")))


def _insert_at_offset(text: JsoncText, at: Offset, addition: JsoncText) -> JsoncText:
    return JsoncText(text.root[: at.root] + addition.root + text.root[at.root :])


def _value_start_of(tokens: Tokens, key: JsonKey) -> Token | None:
    """The first token of top-level `key`'s value, if the key exists.

    If the key is repeated, the last one counts, as in VS Code and `json.loads`.
    """
    depth = 0
    items = tokens.root
    found: Token | None = None
    for index, token in enumerate(items):
        if token.text in _OPEN:
            depth += 1
        elif token.text in _CLOSE:
            depth -= 1
        elif (
            depth == 1
            and token.text.root.startswith('"')
            and index + 2 < len(items)
            and items[index + 1].text == JsoncText(":")
            and json.loads(token.text.root) == key.root
        ):
            found = items[index + 2]
    return found


def _last_token_inside(tokens: Tokens, opening: Token) -> Token | None:
    """The last token before the bracket closing `opening`; `None` if it is empty."""
    items = tokens.root
    start = items.index(opening)
    depth = 0
    for index in range(start, len(items)):
        if items[index].text in _OPEN:
            depth += 1
        elif items[index].text in _CLOSE:
            depth -= 1
            if depth == 0:
                return None if index == start + 1 else items[index - 1]
    return None
