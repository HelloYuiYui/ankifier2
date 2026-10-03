import re

from ankifier.models import WordEntry


def parse_line(line: str, as_is: bool = False) -> WordEntry:
	"""Parse a single line from the CSV into a WordEntry.

	Handles two formats:
	  1. as_is=True: the line is a whole phrase to be translated verbatim.
	  2. 'promener (verb)'       -> word with function annotation
	  3. 'boulangerie'           -> plain word
	"""
	line = line.strip()

	if as_is:
		return WordEntry(raw=line, word=line, as_is=True)

	func_match = re.match(r"^(.+?)\s*\((\w+)\)$", line)
	if func_match:
		word_part = func_match.group(1).strip()
		function = func_match.group(2).strip()
		return WordEntry(raw=line, word=word_part, function=function)

	tokens = line.split()
	if len(tokens) > 1:
		# Check if first token looks like a French article
		french_articles = {"le", "la", "les", "un", "une", "des"}
		if tokens[0].lower() in french_articles:
			return WordEntry(raw=line, word=tokens[-1], article=tokens[0])

	return WordEntry(raw=line, word=line)
