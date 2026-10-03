"""Marker -> Anki cloze conversion.

The user marks the part(s) to hide as [[like this]]. Two modes share the syntax:

  * "as is" texts get their hints from Mistral, supplied positionally;
  * manual front/back pairs carry their hint inline, as [[word:hint]].

Kept apart from the connectors because the manual path needs it without any API
call.
"""

import re

# Non-greedy, so "[[a]] et [[b]]" is two markers rather than one.
MARKER_RE = re.compile(r"\[\[(.+?)\]\]")

# Half-written markers ("[[sois", "sois]]") left after MARKER_RE. Stripped, since
# ElevenLabs would read them aloud; single brackets can be real punctuation.
_STRAY_MARKER_RE = re.compile(r"\[\[|\]\]")


def _strip_stray_markers(text: str) -> str:
	return _STRAY_MARKER_RE.sub("", text)


def _split_inline_hint(body: str) -> tuple[str, str]:
	"""Split a [[word:hint]] body on the first colon, so a hint may contain one.

	A body starting with a colon is kept whole: an empty cloze would render as a
	bare "[...]" in Anki.
	"""
	head, sep, tail = body.partition(":")
	head, tail = head.strip(), tail.strip()
	if not sep or not head:
		return body, ""
	return head, tail


def render(
	text: str, part_hints: list[str] | None = None, inline_hints: bool = False
) -> tuple[str, str]:
	"""Return (plain_text, cloze_text), both free of [[...]] markers.

	plain_text goes to Mistral and ElevenLabs and never contains a hint;
	cloze_text is what Anki stores. Hints come from `part_hints` positionally, or
	from [[word:hint]] with inline_hints=True. An empty hint gives {{cN::text}},
	since an empty ::hint renders as a stray "[...]".
	"""
	part_hints = part_hints or []
	plain: list[str] = []
	cloze: list[str] = []
	pos = 0

	for n, match in enumerate(MARKER_RE.finditer(text), start=1):
		literal = _strip_stray_markers(text[pos : match.start()])
		plain.append(literal)
		cloze.append(literal)

		body = match.group(1).strip()
		if inline_hints:
			body, hint = _split_inline_hint(body)
		else:
			hint = part_hints[n - 1] if n - 1 < len(part_hints) else ""
		plain.append(body)
		cloze.append(
			f"{{{{c{n}::{body}::{hint}}}}}" if hint else f"{{{{c{n}::{body}}}}}"
		)
		pos = match.end()

	tail = _strip_stray_markers(text[pos:])
	plain.append(tail)
	cloze.append(tail)

	return "".join(plain), "".join(cloze)


def render_as_is(text: str, part_hints: list[str]) -> tuple[str, str]:
	return render(text, part_hints)


def render_manual(text: str) -> tuple[str, str]:
	return render(text, inline_hints=True)


def extract_marked_parts(text: str) -> list[str]:
	return [m.group(1).strip() for m in MARKER_RE.finditer(text)]


def strip_markers(text: str) -> str:
	return render(text)[0]


def build_as_is_cloze(text: str, part_hints: list[str]) -> str:
	return render(text, part_hints)[1]
