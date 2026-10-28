"""FakeClient stands in for client.chat.complete and records the messages it was
sent, so the prompts can be asserted on directly."""

import json
from types import SimpleNamespace

from ankifier.mistral_connector import build_prompt, query_senses
from ankifier.models import WordEntry


def entry(raw="glace", function=None):
	return WordEntry(raw=raw, word=raw, function=function)


class FakeClient:
	"""Replies with each list of senses in turn, repeating the last one."""

	def __init__(self, senses, *retries):
		self.sent = []
		self.chat = SimpleNamespace(complete=self._complete)
		self._replies = [json.dumps({"senses": r}) for r in (senses, *retries)]

	def _complete(self, *, messages, **_):
		self.sent.append(list(messages))
		content = self._replies[min(len(self.sent), len(self._replies)) - 1]
		message = SimpleNamespace(content=content)
		return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def raw_sense(
	n,
	gender="feminine",
	part_of_speech="noun",
	sentence="La glace fond.",
	hidden="La glace",
):
	return {
		"sense": f"sense {n}",
		"sentence": sentence,
		"hidden_text": hidden,
		"hint": "ice",
		"translation": "The ice melts.",
		"level": "A2",
		"gender": gender,
		"part_of_speech": part_of_speech,
	}


def test_the_three_sense_prompt_is_unchanged():
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


# ---------------------------------------------------------------------------
# hidden_text that is not in the sentence
# ---------------------------------------------------------------------------
def test_a_matching_hidden_text_is_clozed_without_a_retry():
	client = FakeClient([raw_sense(1)])
	sense = query_senses(client, entry(), "French")[0]
	assert sense.cloze_sentence == "{{c1::La glace::ice}} fond."
	assert len(client.sent) == 1


def test_a_missing_hidden_text_is_retried_once_and_the_fix_is_used():
	bad = raw_sense(1, sentence="L'arbre pousse.", hidden="le arbre")
	fixed = raw_sense(1, sentence="L'arbre pousse.", hidden="L'arbre")
	client = FakeClient([bad], [fixed])
	sense = query_senses(client, entry("arbre"), "French")[0]
	assert sense.cloze_sentence == "{{c1::L'arbre::ice}} pousse."
	assert len(client.sent) == 2
	follow_up = client.sent[1]
	assert follow_up[-2]["role"] == "assistant"
	assert '"le arbre"' in follow_up[-1]["content"]


def test_the_retry_only_replaces_the_senses_that_missed():
	good = raw_sense(1)
	bad = raw_sense(2, sentence="L'arbre pousse.", hidden="le arbre")
	retried_good = raw_sense(1, sentence="Je mange une glace.", hidden="une glace")
	fixed = raw_sense(2, sentence="L'arbre pousse.", hidden="L'arbre")
	client = FakeClient([good, bad], [retried_good, fixed])
	senses = query_senses(client, entry(), "French")
	assert senses[0].sentence == "La glace fond."
	assert senses[1].cloze_sentence.startswith("{{c1::L'arbre")


def test_a_hidden_text_still_missing_after_the_retry_leaves_no_cloze():
	bad = raw_sense(1, sentence="L'arbre pousse.", hidden="le arbre")
	client = FakeClient([bad])
	sense = query_senses(client, entry("arbre"), "French")[0]
	assert sense.cloze_sentence == "L'arbre pousse."
	assert len(client.sent) == 2


def test_a_failed_retry_keeps_the_first_answer():
	bad = raw_sense(1, sentence="L'arbre pousse.", hidden="le arbre")
	client = FakeClient([bad])
	calls = []

	def complete(*, messages, **_):
		calls.append(messages)
		if len(calls) > 1:
			raise RuntimeError("rate limited")
		return FakeClient([bad]).chat.complete(messages=messages)

	client.chat.complete = complete
	sense = query_senses(client, entry("arbre"), "French")[0]
	assert sense.sentence == "L'arbre pousse."
