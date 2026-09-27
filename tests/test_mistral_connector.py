"""Prompt construction and response parsing, with the Mistral client faked.

No network: FakeClient stands in for client.chat.complete and records the
messages it was sent, so the prompt the model would have seen can be asserted
on directly.
"""

import json
from types import SimpleNamespace

from ankifier.mistral_connector import build_prompt, query_senses
from ankifier.models import WordEntry


def entry(raw="glace"):
	return WordEntry(raw=raw, word=raw)


class FakeClient:
	def __init__(self, senses):
		self.sent = []
		self.chat = SimpleNamespace(complete=self._complete)
		self._content = json.dumps({"senses": senses})

	def _complete(self, *, messages, **_):
		self.sent.append(messages)
		message = SimpleNamespace(content=self._content)
		return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def raw_sense(n, gender="feminine"):
	return {
		"sense": f"sense {n}",
		"sentence": "La glace fond.",
		"hidden_text": "La glace",
		"hint": "ice",
		"translation": "The ice melts.",
		"level": "A2",
		"gender": gender,
	}


def test_the_three_sense_prompt_is_unchanged():
	"""The web table's prompt is what it was before max_senses existed."""
	assert build_prompt(entry(), "French") == (
		'Given the French word "glace", provide UP TO 3 '
		"(can be less) of its most common distinct senses. If senses are similar, "
		"you MUST combine them into one. If there are less than 3 senses for the "
		"word, provide however many there are, DO NOT pad the list. Format should "
		"be as below:"
	)


def test_one_sense_without_context_asks_for_the_most_common():
	prompt = build_prompt(entry(), "French", max_senses=1)
	assert "exactly ONE sense" in prompt
	assert "most common" in prompt
	assert "UP TO 3" not in prompt


def test_one_sense_with_context_quotes_the_sentence():
	prompt = build_prompt(
		entry(), "French", max_senses=1, context="Il se regarde dans la glace."
	)
	assert '"Il se regarde dans la glace."' in prompt
	assert "in that sentence" in prompt
	assert "NEW simple example sentence" in prompt


def test_query_senses_never_returns_more_than_asked_for():
	client = FakeClient([raw_sense(1), raw_sense(2), raw_sense(3)])
	senses = query_senses(client, entry(), "French", max_senses=1)
	assert [s.sense_description for s in senses] == ["sense 1"]


def test_query_senses_reads_a_noun_gender():
	client = FakeClient([raw_sense(1)])
	assert query_senses(client, entry(), "French")[0].gender == "feminine"


def test_a_non_noun_or_unexpected_gender_is_none():
	"""The schema says "none" for a non-noun; anything else is not trusted."""
	client = FakeClient([raw_sense(1, "none"), raw_sense(2, "neuter")])
	assert [s.gender for s in query_senses(client, entry(), "French")] == [None, None]


def test_query_senses_sends_the_context_to_the_model():
	client = FakeClient([raw_sense(1)])
	query_senses(client, entry(), "French", max_senses=1, context="Le miroir.")
	user = client.sent[0][1]["content"]
	assert '"Le miroir."' in user
