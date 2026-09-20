"""Marker -> Anki cloze conversion.

The user marks the part(s) to hide as -like this-. Two modes share the syntax:

  * "as is" texts get their hints from Mistral, supplied positionally;
  * manual front/back pairs carry their hint inline, as -word:hint-.

This lives apart from the connectors because the manual path needs the markers
without making a single API call.
"""

import re

# The outer hyphens must sit against whitespace (or a string edge / bracket /
# quote) on the outside and against non-space on the inside. That is what keeps
# the syntax usable in French: the hyphen in "est-ce", "peut-etre" or
# "rendez-vous" has a letter on both sides, so it can never open or close a
# marker, while the content between markers may itself contain hyphens
# ("-c'est-a-dire-" marks the whole phrase).
MARKER_RE = re.compile(
    r"""(?<![^\s(\[{«"'])   # opening - : nothing but space/open punct before it
        -
        (\S|\S.*?\S)        # content, no leading or trailing space
        -
        (?![^\s)\]}»"'.,;:!?])  # closing - : nothing but space/close punct after
    """,
    re.VERBOSE,
)

# A hyphen glued to a word on exactly one side and open on the other is a
# half-written marker ("-sois", "sois-"), never real French. It is stripped from
# everything that leaves this module, because a stray hyphen reaching ElevenLabs
# is read as an unnatural pause. A free-standing " - " dash is deliberate
# punctuation and is left alone.
_ORPHAN_HYPHEN_RE = re.compile(r"(?<![^\s])-(?=\S)|(?<=\S)-(?![^\s])")


def _strip_orphan_hyphens(text: str) -> str:
    """Remove half-written marker hyphens from a literal (unmarked) fragment."""
    return _ORPHAN_HYPHEN_RE.sub("", text)


def _split_inline_hint(body: str) -> tuple[str, str]:
    """Split a -word:hint- body into (word, hint) on the first colon.

    Only the first colon separates, so a hint may itself contain one. A body
    with nothing before the colon is not a hint at all -- it is a text that
    happens to start with a colon -- so it is kept whole rather than producing
    an empty cloze, which Anki renders as a bare "[...]".
    """
    head, sep, tail = body.partition(":")
    head, tail = head.strip(), tail.strip()
    if not sep or not head:
        return body, ""
    return head, tail


def render(text: str, part_hints: list[str] | None = None, inline_hints: bool = False) -> tuple[str, str]:
    """Return (plain_text, cloze_text) for a marked-up source text.

    Both outputs are free of the -...- markers themselves: plain_text is what
    Mistral and ElevenLabs are given, cloze_text is what Anki stores. Clozes are
    numbered c1, c2, ... in order of appearance. A missing or empty hint yields
    a bare {{cN::text}} rather than an empty ::hint, which Anki renders as a
    stray "[...]" gap.

    Hints come from `part_hints` positionally, or -- with inline_hints=True --
    from the marker itself as -word:hint-. A hint never reaches plain_text, so
    the TTS only ever reads the sentence as written.
    """
    part_hints = part_hints or []
    plain: list[str] = []
    cloze: list[str] = []
    pos = 0

    for n, match in enumerate(MARKER_RE.finditer(text), start=1):
        literal = _strip_orphan_hyphens(text[pos:match.start()])
        plain.append(literal)
        cloze.append(literal)

        body = match.group(1).strip()
        if inline_hints:
            body, hint = _split_inline_hint(body)
        else:
            hint = part_hints[n - 1] if n - 1 < len(part_hints) else ""
        plain.append(body)
        cloze.append(f"{{{{c{n}::{body}::{hint}}}}}" if hint else f"{{{{c{n}::{body}}}}}")
        pos = match.end()

    tail = _strip_orphan_hyphens(text[pos:])
    plain.append(tail)
    cloze.append(tail)

    return "".join(plain), "".join(cloze)


def render_as_is(text: str, part_hints: list[str]) -> tuple[str, str]:
    """Render an "as is" text, taking its hints from Mistral positionally."""
    return render(text, part_hints)


def render_manual(text: str) -> tuple[str, str]:
    """Render a manual card front, taking each hint from its -word:hint- marker."""
    return render(text, inline_hints=True)


def extract_marked_parts(text: str) -> list[str]:
    """Return the -...- marked substrings of text, in order of appearance."""
    return [m.group(1).strip() for m in MARKER_RE.finditer(text)]


def strip_markers(text: str) -> str:
    """Return text with the markers removed but their content kept."""
    return render(text)[0]


def build_as_is_cloze(text: str, part_hints: list[str]) -> str:
    """Turn -...- markers into Anki clozes. See render."""
    return render(text, part_hints)[1]
