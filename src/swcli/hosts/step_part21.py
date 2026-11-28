"""Bounded-profile Part 21 framing and lexical boundaries for STEP evidence."""

from dataclasses import dataclass
import re

# Mask complete text tokens before looking for structural keywords or semicolons.
# Doubled apostrophes are part of a string. A stray opener is an error token.
_TEXT_TOKEN = re.compile(
    r"'[^']*(?:''[^']*)*'|/\*.*?\*/|\"[0-3][0-9A-F]*\"|['\"/\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\U0010ffff]",
    re.S | re.I | re.ASCII,
)
_STRING_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_COMMENT_NON_ASCII = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\U0010ffff]")
_FRAME = re.compile(
    r"\AISO-10303-21;\s*HEADER\s*;(?P<header>.*?)\bENDSEC\s*;\s*"
    r"DATA\s*;(?P<data>.*?)\bENDSEC\s*;\s*END-ISO-10303-21;\s*\Z",
    re.S | re.ASCII,
)
_STATEMENT_END = re.compile(";")
_HEADER_RECORD = re.compile(r"\s*[A-Z][A-Z0-9_]*\s*\(.*\)\s*", re.S | re.I | re.ASCII)
_SCHEMA_NAME = re.compile(r"^\s*FILE_SCHEMA\b", re.I | re.ASCII)
_SCHEMA_ITEM = r"'([A-Z][A-Z0-9_]*)(?:\s+\{\s*\d+(?:\s+\d+)*\})?'"
_SCHEMA = re.compile(
    r"\s*FILE_SCHEMA\s*\(\s*\((\s*" + _SCHEMA_ITEM
    + r"(?:\s*,\s*" + _SCHEMA_ITEM + r")*\s*)\)\s*\)\s*",
    re.I | re.ASCII,
)
_SCHEMA_IDENTIFIER = re.compile(_SCHEMA_ITEM, re.I | re.ASCII)


@dataclass(frozen=True)
class Section:
    text: str
    syntax: str

    def statements(self):
        """Yield text and syntax, aligned on original character indices."""
        start = 0
        for end in _STATEMENT_END.finditer(self.syntax):
            yield self.text[start:end.start()], self.syntax[start:end.start()]
            start = end.end()
        if self.syntax[start:].strip() or self.text[start:].strip():
            raise ValueError("unterminated Part 21 statement")


def read_exchange(raw):
    """Return the original text and lexically isolated HEADER and DATA sections.

    UTF-8 is the Part 21 encoding for high code points in quoted strings.
    This profile requires ASCII elsewhere, including comments and binary tokens.
    The projection is only for inspection. No STEP file is rewritten.
    """
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"invalid Part 21 UTF-8 at byte {exc.start}") from exc

    cleaned, syntax = [], []
    start = 0
    for match in _TEXT_TOKEN.finditer(text):
        token = match[0]
        outside = text[start:match.start()]
        cleaned.append(outside)
        syntax.append(outside)
        if token.startswith("/*"):
            if _COMMENT_NON_ASCII.search(token):
                raise ValueError("non-ASCII or control character in Part 21 comment")
            body = " " * len(token)
            syntax.append(body)
            cleaned.append(body)
        elif len(token) > 1 and token[0] in "'\"":
            if token[0] == "'" and _STRING_CONTROL.search(token):
                raise ValueError("control character in Part 21 string")
            # Keep a delimiter in the syntax projection so a stray quoted token
            # cannot disappear and make a malformed record look valid.
            syntax.append(token[0] + " " * (len(token) - 2) + token[-1])
            cleaned.append(token)
        else:
            raise ValueError(f"invalid Part 21 structural character at character {match.start()}")
        start = match.end()
    cleaned.append(text[start:])
    syntax.append(text[start:])
    layout = "".join(syntax)
    frame = _FRAME.fullmatch(layout)
    if frame is None:
        raise ValueError("Part21 framing mismatch")
    content = "".join(cleaned)
    header = Section(content[frame.start("header"):frame.end("header")], frame["header"])
    data = Section(content[frame.start("data"):frame.end("data")], frame["data"])
    return text, header, data


def file_schema(header):
    """Read the actual FILE_SCHEMA statement and exact ASCII schema identifiers."""
    found = []
    for text, syntax in header.statements():
        if _HEADER_RECORD.fullmatch(syntax) is None:
            raise ValueError("malformed Part 21 HEADER statement")
        if _SCHEMA_NAME.match(syntax):
            match = _SCHEMA.fullmatch(text)
            if match is None:
                raise ValueError("malformed Part 21 FILE_SCHEMA")
            found.append((match[1], {token[1].upper() for token in _SCHEMA_IDENTIFIER.finditer(match[1])}))
    if len(found) != 1:
        raise ValueError("expected one Part 21 FILE_SCHEMA")
    return found[0]
