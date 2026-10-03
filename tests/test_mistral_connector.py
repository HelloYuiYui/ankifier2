"""Prompt construction and response parsing, with the Mistral client faked.

No network: FakeClient stands in for client.chat.complete and records the
messages it was sent, so the prompt the model would have seen can be asserted
on directly.
"""

import json
from types import SimpleNamespace

from ankifier.mistral_connector import build_prompt, query_senses
from ankifier.models import WordEntry


def entry(raw="glace", function=None):
	return WordEntry(raw=raw, word=raw, function=function)


class FakeClient:
	def __init__(self, senses):
		self.sent = []
		self.chat = SimpleNamespace(complete=self._complete)
		self._content = json.dumps({"senses": senses})

	def _complete(self, *, messages, **_):
		self.sent.append(messages)
		message = SimpleNamespace(content=self._content)
		return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def raw_sense(n, gender="feminine", part_of_speech="noun"):
	return {
		"sense": f"sense {n}",
		"sentence": "La glace fond.",
		"hidden_text": "La glace",
		"hint": "ice",
		"translation": "The ice melts.",
		"level": "A2",
		"gender": gender,
		"part_of_speech": part_of_speech,
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


def test_query_senses_reads_the_part_of_speech():
	client = FakeClient([raw_sense(1), raw_sense(2, "none", "adverb")])
	senses = query_senses(client, entry(), "French")
	assert [s.part_of_speech for s in senses] == ["noun", "adverb"]


def test_a_function_word_or_unexpected_part_of_speech_is_none():
	""" "other" means a pronoun, article and so on: no part of speech, no tag."""
	client = FakeClient(
		[raw_sense(1, "none", "other"), raw_sense(2, "none", "interjection")]
	)
	senses = query_senses(client, entry(), "French")
	assert [s.part_of_speech for s in senses] == [None, None]


def test_only_a_noun_keeps_its_gender():
	"""A verb the model also called feminine must not be tagged feminine."""
	client = FakeClient([raw_sense(1, "feminine", "verb")])
	sense = query_senses(client, entry(), "French")[0]
	assert (sense.part_of_speech, sense.gender) == ("verb", None)


def test_the_users_annotation_overrides_the_models_part_of_speech():
	"""'devoir (verb)': the user said verb, whatever the model thinks."""
	client = FakeClient([raw_sense(1, "masculine", "noun")])
	sense = query_senses(client, entry("devoir", function="Verbe"), "French")[0]
	assert (sense.part_of_speech, sense.gender) == ("verb", None)


def test_an_annotation_that_is_no_part_of_speech_is_ignored():
	client = FakeClient([raw_sense(1)])
	sense = query_senses(client, entry("glace", function="food"), "French")[0]
	assert sense.part_of_speech == "noun"


def test_query_senses_sends_the_context_to_the_model():
	client = FakeClient([raw_sense(1)])
	query_senses(client, entry(), "French", max_senses=1, context="Le miroir.")
	user = client.sent[0][1]["content"]
	assert '"Le miroir."' in user
