"""Pinning tests for csv_parser.parse_line.

parse_line applies three heuristics in order: "word (function)", "article word",
then plain word. Several of the cases below pin behaviour that is arguably wrong
(a trailing-token rule that drops adjectives, an elided article that is not
recognised) -- they are here so that any change in it is a decision rather than
an accident.
"""

import pytest

from ankifier.csv_parser import parse_line

# (line, word, article, function)
CASES = [
    ("manger", "manger", None, None),
    ("bonjour", "bonjour", None, None),
    # -- "word (function)": the regex is anchored at both ends
    ("manger (verb)", "manger", None, "verb"),
    ("glace (noun)", "glace", None, "noun"),
    # trailing text after the parens defeats the end anchor, so the whole line
    # becomes the word
    ("mange (verb) extra", "mange (verb) extra", None, None),
    # -- "article word": the LAST token is taken as the word
    ("la glace", "glace", "la", None),
    ("le livre", "livre", "le", None),
    ("un chat", "chat", "un", None),
    ("une maison", "maison", "une", None),
    ("des gens", "gens", "des", None),
    ("les enfants", "enfants", "les", None),
    # an adjective between article and noun is silently dropped from `word`
    ("la grande maison", "maison", "la", None),
    # -- non-article leading tokens fall through to the plain-word branch,
    #    where `word` is the entire line
    ("se promener", "se promener", None, None),
    ("l'eau", "l'eau", None, None),
]


@pytest.mark.parametrize(
    "line,word,article,function",
    CASES,
    ids=[c[0] for c in CASES],
)
def test_parse_line(line, word, article, function):
    entry = parse_line(line)
    assert entry.raw == line
    assert entry.word == word
    assert entry.article == article
    assert entry.function == function
    assert entry.as_is is False


def test_surrounding_whitespace_is_stripped():
    entry = parse_line("  manger  ")
    assert entry.raw == "manger"
    assert entry.word == "manger"


@pytest.mark.parametrize(
    "line",
    [
        "manger (verb)",
        "la glace",
        "la grande maison",
        "Il faut que tu -sois- la",
    ],
)
def test_as_is_short_circuits_every_heuristic(line):
    """as_is text is already the card, so it must survive verbatim."""
    entry = parse_line(line, as_is=True)
    assert entry.raw == line
    assert entry.word == line
    assert entry.article is None
    assert entry.function is None
    assert entry.as_is is True


def test_marked_up_text_is_left_alone_even_without_as_is():
    line = "Il faut que tu -sois- la"
    entry = parse_line(line)
    assert entry.word == line
    assert entry.article is None
    assert entry.function is None
