import re

from ankifier.models import WordEntry


def parse_line(line: str, as_is: bool = False) -> WordEntry:
    """Parse a single line from the CSV into a WordEntry.

    Handles three formats:
      1. 'boulangerie'           -> plain word
      2. 'la glace'              -> word with article
      3. 'promener (verb)'       -> word with function annotation

    With as_is=True the line is a whole phrase to be translated verbatim, so
    none of that applies: article/function heuristics would happily mangle
    "la glace fond au soleil" into article="la", word="soleil".
    """
    line = line.strip()

    if as_is:
        return WordEntry(raw=line, word=line, as_is=True)

    # Format 3: word (function) e.g. "promener (verb)"
    func_match = re.match(r'^(.+?)\s*\((\w+)\)$', line)
    if func_match:
        word_part = func_match.group(1).strip()
        function = func_match.group(2).strip()
        return WordEntry(raw=line, word=word_part, function=function)

    # Format 2: article word e.g. "la glace" or "une glace"
    # Format 1: plain word e.g. "boulangerie"
    tokens = line.split()
    if len(tokens) > 1:
        # Check if first token looks like a French article
        french_articles = {'le', 'la', 'les', 'un', 'une', 'des', "l'"}
        if tokens[0].lower() in french_articles:
            return WordEntry(raw=line, word=tokens[-1], article=tokens[0])

    return WordEntry(raw=line, word=line)


def read_csv(file_path: str) -> list[WordEntry]:
    """Read a CSV file and return a list of WordEntry objects."""
    entries = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(parse_line(line))
    return entries
