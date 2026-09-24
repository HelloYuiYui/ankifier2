"""Tests for cloze.py.

Originally written against the old -word:hint- syntax to pin the behaviour
before it moved to [[word:hint]]. Every expectation below came through that port
unchanged except for the marker characters themselves, which is the evidence
that the syntax change was only a syntax change -- the numbering, the inline
hint splitting and the empty-hint rule all still produce exactly what they did.

The two groups that did change meaning are called out in place: hyphens are now
ordinary characters, and half-written markers are doubled brackets.
"""

import pytest

from ankifier import cloze

# ---------------------------------------------------------------------------
# render() with positional hints -- the "as is" path, hints supplied by Mistral
# (label, text, hints, expected_plain, expected_cloze)
# ---------------------------------------------------------------------------
POSITIONAL = [
	(
		"no markers at all",
		"Je mange une pomme",
		[],
		"Je mange une pomme",
		"Je mange une pomme",
	),
	(
		"one marker, no hint supplied -- bare cloze, never an empty ::hint",
		"Je [[mange]] une pomme",
		[],
		"Je mange une pomme",
		"Je {{c1::mange}} une pomme",
	),
	(
		"one marker, one hint",
		"Je [[mange]] une pomme",
		["to eat"],
		"Je mange une pomme",
		"Je {{c1::mange::to eat}} une pomme",
	),
	(
		"an empty-string hint is treated as no hint",
		"Je [[mange]] une pomme",
		[""],
		"Je mange une pomme",
		"Je {{c1::mange}} une pomme",
	),
	(
		"two markers number c1, c2 in order of appearance",
		"Je [[mange]] une [[pomme]]",
		["eat", "apple"],
		"Je mange une pomme",
		"Je {{c1::mange::eat}} une {{c2::pomme::apple}}",
	),
	(
		"fewer hints than markers -- the surplus marker goes bare",
		"Je [[mange]] une [[pomme]]",
		["eat"],
		"Je mange une pomme",
		"Je {{c1::mange::eat}} une {{c2::pomme}}",
	),
	(
		"more hints than markers -- the surplus hint is dropped",
		"Je [[mange]] une pomme",
		["eat", "unused"],
		"Je mange une pomme",
		"Je {{c1::mange::eat}} une pomme",
	),
	(
		"marker spanning several words",
		"Je veux [[aller au cinema]] ce soir",
		["go to the movies"],
		"Je veux aller au cinema ce soir",
		"Je veux {{c1::aller au cinema::go to the movies}} ce soir",
	),
	(
		"accented content survives intact",
		"Il a [[brûlé]] le dîner",
		["burned"],
		"Il a brûlé le dîner",
		"Il a {{c1::brûlé::burned}} le dîner",
	),
	(
		"apostrophe inside the marker",
		"Il faut [[s'asseoir]] ici",
		["to sit"],
		"Il faut s'asseoir ici",
		"Il faut {{c1::s'asseoir::to sit}} ici",
	),
	(
		"empty input",
		"",
		[],
		"",
		"",
	),
]


# ---------------------------------------------------------------------------
# Marker placement against string edges and punctuation
# ---------------------------------------------------------------------------
PLACEMENT = [
	(
		"marker at start of string",
		"[[Bonjour]] tout le monde",
		["hello"],
		"Bonjour tout le monde",
		"{{c1::Bonjour::hello}} tout le monde",
	),
	(
		"marker at end of string",
		"Je dis [[bonjour]]",
		["hello"],
		"Je dis bonjour",
		"Je dis {{c1::bonjour::hello}}",
	),
	(
		"marker is the whole string",
		"[[bonjour]]",
		["hello"],
		"bonjour",
		"{{c1::bonjour::hello}}",
	),
	(
		"marker inside parentheses",
		"Je mange ([[une pomme]]) ici",
		["an apple"],
		"Je mange (une pomme) ici",
		"Je mange ({{c1::une pomme::an apple}}) ici",
	),
	(
		"marker followed by a comma",
		"Je [[mange]], puis je dors",
		["eat"],
		"Je mange, puis je dors",
		"Je {{c1::mange::eat}}, puis je dors",
	),
	(
		"marker inside double quotes",
		'Il dit "[[bonjour]]" ici',
		["hello"],
		'Il dit "bonjour" ici',
		'Il dit "{{c1::bonjour::hello}}" ici',
	),
]


@pytest.mark.parametrize(
	"label,text,hints,expected_plain,expected_cloze",
	POSITIONAL + PLACEMENT,
	ids=[c[0] for c in POSITIONAL + PLACEMENT],
)
def test_render_positional(label, text, hints, expected_plain, expected_cloze):
	plain, cloze_text = cloze.render(text, hints)
	assert plain == expected_plain
	assert cloze_text == expected_cloze


# ---------------------------------------------------------------------------
# render(inline_hints=True) -- the manual path, hints carried in the marker
# ---------------------------------------------------------------------------
INLINE = [
	(
		"word:hint splits on the colon",
		"Il faut que tu [[sois:etre]] la",
		"Il faut que tu sois la",
		"Il faut que tu {{c1::sois::etre}} la",
	),
	(
		"no colon means no hint",
		"Il faut que tu [[sois]] la",
		"Il faut que tu sois la",
		"Il faut que tu {{c1::sois}} la",
	),
	(
		"only the FIRST colon separates, so a hint may contain one",
		"Le [[truc:a: thing]] ici",
		"Le truc ici",
		"Le {{c1::truc::a: thing}} ici",
	),
	(
		"a body starting with a colon is text, not an empty cloze",
		"Un [[:chose]] ici",
		"Un :chose ici",
		"Un {{c1:::chose}} ici",
	),
	(
		"hint never reaches plain text -- TTS must not read it aloud",
		"Je [[mange:to eat]] une [[pomme:apple]]",
		"Je mange une pomme",
		"Je {{c1::mange::to eat}} une {{c2::pomme::apple}}",
	),
]


@pytest.mark.parametrize(
	"label,text,expected_plain,expected_cloze",
	INLINE,
	ids=[c[0] for c in INLINE],
)
def test_render_inline_hints(label, text, expected_plain, expected_cloze):
	plain, cloze_text = cloze.render(text, inline_hints=True)
	assert plain == expected_plain
	assert cloze_text == expected_cloze


# ---------------------------------------------------------------------------
# HYPHENS: the whole point of the [[...]] syntax.
#
# Under the old single-hyphen marker these needed eight lines of lookbehind and
# lookahead to get right, plus a separate orphan-stripping pass. Now a hyphen is
# an ordinary character and these are regression guards: if anything ever starts
# treating hyphens specially again, this group fails.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
	"text",
	[
		"Est-ce que tu viens",
		"Le rendez-vous est demain",
		"C'est peut-etre vrai",
		"Je mange - une pomme",  # a freestanding dash is punctuation
		"Je -mange une pomme",  # would have been an orphan marker before
		"Je mange- une pomme",
		"c'est-a-dire",
	],
)
def test_hyphens_are_never_touched(text):
	plain, cloze_text = cloze.render(text)
	assert plain == text
	assert cloze_text == text
	assert cloze.extract_marked_parts(text) == []


def test_hyphenated_word_can_itself_be_marked():
	plain, cloze_text = cloze.render("Le [[rendez-vous]] est demain", ["meeting"])
	assert plain == "Le rendez-vous est demain"
	assert cloze_text == "Le {{c1::rendez-vous::meeting}} est demain"


# ---------------------------------------------------------------------------
# Half-written markers
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
	"text,expected",
	[
		("Je [[mange une pomme", "Je mange une pomme"),
		("Je mange]] une pomme", "Je mange une pomme"),
		("[[", ""),
		("[[]]", ""),  # too short to be a marker, so both brackets are stray
	],
)
def test_stray_brackets_are_stripped(text, expected):
	"""A stray bracket must never reach ElevenLabs -- it would be read aloud."""
	plain, cloze_text = cloze.render(text)
	assert plain == expected
	assert cloze_text == expected


def test_a_stray_bracket_does_not_disturb_a_complete_marker():
	plain, cloze_text = cloze.render("Je [[mange]] une [[pomme", ["eat"])
	assert plain == "Je mange une pomme"
	assert cloze_text == "Je {{c1::mange::eat}} une pomme"


@pytest.mark.parametrize("text", ["Voir [1] ici", "Un tableau [x] la", "a] b [c"])
def test_single_brackets_are_left_alone(text):
	"""Only doubled brackets are marker syntax; a single one is punctuation."""
	plain, cloze_text = cloze.render(text)
	assert plain == text
	assert cloze_text == text


def test_adjacent_markers_do_not_merge():
	"""Non-greedy matching: two markers, not one spanning the middle."""
	plain, cloze_text = cloze.render("[[a]] et [[b]]", ["A", "B"])
	assert plain == "a et b"
	assert cloze_text == "{{c1::a::A}} et {{c2::b::B}}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
	"text,expected",
	[
		("Je mange une pomme", []),
		("Je [[mange]] une pomme", ["mange"]),
		("Je [[mange]] une [[pomme]]", ["mange", "pomme"]),
		("Il faut que tu [[sois:etre]] la", ["sois:etre"]),
		("Le [[rendez-vous]] est demain", ["rendez-vous"]),
	],
)
def test_extract_marked_parts(text, expected):
	assert cloze.extract_marked_parts(text) == expected


def test_strip_markers_keeps_content():
	assert cloze.strip_markers("Je [[mange]] une [[pomme]]") == "Je mange une pomme"


def test_render_as_is_matches_render_with_hints():
	assert cloze.render_as_is("Je [[mange]] ici", ["eat"]) == cloze.render(
		"Je [[mange]] ici", ["eat"]
	)


def test_render_manual_matches_render_with_inline_hints():
	assert cloze.render_manual("Je [[mange:eat]] ici") == cloze.render(
		"Je [[mange:eat]] ici", inline_hints=True
	)


def test_build_as_is_cloze_returns_only_the_cloze():
	assert (
		cloze.build_as_is_cloze("Je [[mange]] ici", ["eat"])
		== "Je {{c1::mange::eat}} ici"
	)
