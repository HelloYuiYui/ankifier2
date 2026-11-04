import base64

import requests

from ankifier.settings import get_settings


def _invoke(action: str, params: dict | None = None) -> dict:
	settings = get_settings()

	payload = {"action": action, "version": 6}
	if params:
		payload["params"] = params

	# Without a timeout an Anki that is running but wedged hangs the request
	# forever, and every card queued behind it with it.
	response = requests.post(
		settings.ankiconnect_url, json=payload, timeout=settings.anki_timeout
	)
	response.raise_for_status()

	result = response.json()
	if result.get("error"):
		raise RuntimeError(f"AnkiConnect error: {result['error']}")

	return result.get("result")


def check_connection() -> bool:
	try:
		version = _invoke("version")
		return version is not None
	except (requests.ConnectionError, requests.Timeout):
		return False


def get_version() -> int | None:
	try:
		return _invoke("version")
	except (requests.ConnectionError, requests.Timeout):
		return None


def deck_names() -> list[str]:
	return _invoke("deckNames") or []


def ensure_deck(deck_name: str) -> None:
	_invoke("createDeck", {"deck": deck_name})


def store_media_file(filename: str, path: str) -> None:
	with open(path, "rb") as f:
		data = base64.b64encode(f.read()).decode("utf-8")

	_invoke(
		"storeMediaFile",
		{
			"filename": filename,
			"data": data,
		},
	)


def cloze_note(
	deck_name: str,
	cloze_text: str,
	back_extra: str,
	audio_filename: str | None = None,
	tags: list[str] | None = None,
) -> dict:
	return {
		"deckName": deck_name,
		"modelName": "Cloze",
		"fields": {
			"Text": cloze_text,
			"Back Extra": f"{back_extra} [sound:{audio_filename}]"
			if audio_filename
			else back_extra,
		},
		"tags": tags or ["ankifier"],
		"options": {
			"allowDuplicate": False,
		},
	}


def basic_note(
	deck_name: str,
	front: str,
	back: str,
	audio_filename: str | None = None,
	tags: list[str] | None = None,
) -> dict:
	if audio_filename:
		back = f"{back} [sound:{audio_filename}]"

	return {
		"deckName": deck_name,
		"modelName": "Basic",
		"fields": {
			"Front": front,
			"Back": back,
		},
		"tags": tags or ["ankifier"],
		"options": {
			"allowDuplicate": False,
		},
	}


def add_cloze_note(
	deck_name: str,
	cloze_text: str,
	back_extra: str,
	audio_filename: str | None = None,
	tags: list[str] | None = None,
) -> int:
	note = cloze_note(deck_name, cloze_text, back_extra, audio_filename, tags)
	return _invoke("addNote", {"note": note})


def add_basic_note(
	deck_name: str,
	front: str,
	back: str,
	audio_filename: str | None = None,
	tags: list[str] | None = None,
) -> int:
	note = basic_note(deck_name, front, back, audio_filename, tags)
	return _invoke("addNote", {"note": note})


def can_add_notes(notes: list[dict]) -> list[bool]:
	"""Whether addNote would accept each note. False also covers a deck or note
	type that does not exist, not only a duplicate."""
	return _invoke("canAddNotes", {"notes": notes}) or []


def find_notes(query: str) -> list[int]:
	return _invoke("findNotes", {"query": query}) or []
