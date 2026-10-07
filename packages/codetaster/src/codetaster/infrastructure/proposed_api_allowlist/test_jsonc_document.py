import json

from hypothesis import given
from hypothesis import strategies as st
from safe_result import Err, Ok

from codetaster.infrastructure.proposed_api_allowlist.jsonc_document import (
    JsoncText,
    JsonKey,
    JsonString,
    JsonStrings,
    append_to_string_list,
    read_string_list,
)


def appended_values(text: JsoncText, value: JsonString) -> JsonStrings:
    """Append `value`, then read the list back."""
    key = JsonKey.fake()
    appended = append_to_string_list(text, key, value)
    assert isinstance(appended, Ok)
    read = read_string_list(appended.value, key)
    assert isinstance(read, Ok)
    return read.value


def test_appends_to_an_existing_list_and_keeps_comments() -> None:
    comment = "// keep this comment"
    existing = JsonString("first")
    value = JsonString.fake()
    text = JsoncText(
        f'{comment}\n{{\n\t/* block */ "{JsonKey.fake().root}": ["{existing.root}"], // why\n\t"other": 1,\n}}\n'
    )

    appended = append_to_string_list(text, JsonKey.fake(), value)

    assert isinstance(appended, Ok)
    assert comment in appended.value.root
    assert appended_values(text, value) == JsonStrings((existing, value))


def test_appends_to_a_list_with_a_trailing_comma() -> None:
    existing = JsonString("first")
    value = JsonString.fake()
    text = JsoncText(f'{{"{JsonKey.fake().root}": ["{existing.root}",]}}')

    assert appended_values(text, value) == JsonStrings((existing, value))


def test_appends_to_an_empty_list() -> None:
    value = JsonString.fake()
    text = JsoncText(f'{{"{JsonKey.fake().root}": [ ]}}')

    assert appended_values(text, value) == JsonStrings((value,))


def test_adds_the_key_to_an_object_without_it() -> None:
    value = JsonString.fake()
    other_key = "other"
    text = JsoncText(f'{{\n\t// comment\n\t"{other_key}": true\n}}')

    appended = append_to_string_list(text, JsonKey.fake(), value)

    assert isinstance(appended, Ok)
    assert other_key in appended.value.root
    assert appended_values(text, value) == JsonStrings((value,))


def test_adds_the_key_to_an_empty_object() -> None:
    value = JsonString.fake()

    assert appended_values(JsoncText("{}"), value) == JsonStrings((value,))


def test_creates_a_document_from_empty_or_comment_only_text() -> None:
    value = JsonString.fake()

    assert appended_values(JsoncText(""), value) == JsonStrings((value,))
    assert appended_values(JsoncText("// nothing\n"), value) == JsonStrings((value,))


def test_comment_markers_inside_strings_are_kept() -> None:
    url = "https://example.com/*not-a-comment*/"
    value = JsonString.fake()
    text = JsoncText(f'{{"url": "{url}", "{JsonKey.fake().root}": []}}')

    appended = append_to_string_list(text, JsonKey.fake(), value)

    assert isinstance(appended, Ok)
    assert url in appended.value.root


def test_ignores_the_same_key_in_nested_objects() -> None:
    value = JsonString.fake()
    nested = JsonString("nested")
    text = JsoncText(f'{{"outer": {{"{JsonKey.fake().root}": ["{nested.root}"]}}}}')

    assert appended_values(text, value) == JsonStrings((value,))


def test_a_value_that_is_not_a_list_of_strings_is_a_problem() -> None:
    text = JsoncText(f'{{"{JsonKey.fake().root}": true}}')

    assert isinstance(read_string_list(text, JsonKey.fake()), Err)
    assert isinstance(
        append_to_string_list(text, JsonKey.fake(), JsonString.fake()), Err
    )


def test_invalid_json_is_a_problem() -> None:
    text = JsoncText('{"unterminated": [')

    assert isinstance(
        append_to_string_list(text, JsonKey.fake(), JsonString.fake()), Err
    )


def test_a_top_level_value_that_is_not_an_object_is_a_problem() -> None:
    assert isinstance(read_string_list(JsoncText("[]"), JsonKey.fake()), Err)


@given(
    existing=st.lists(st.text()),
    value=st.text(),
    trailing_comma=st.booleans(),
)
def test_appending_any_string_to_any_list_round_trips(
    *, existing: list[str], value: str, trailing_comma: bool
) -> None:
    encoded = ", ".join(json.dumps(each) for each in existing)
    comma = "," if trailing_comma and existing else ""
    text = JsoncText(
        f'// header\n{{\n\t"{JsonKey.fake().root}": [{encoded}{comma}] /* note */\n}}\n'
    )

    assert appended_values(text, JsonString(value)) == JsonStrings(
        tuple(JsonString(each) for each in [*existing, value])
    )
