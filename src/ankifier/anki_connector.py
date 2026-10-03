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


def add_cloze_note(
	deck_name: str,
	cloze_text: str,
	back_extra: str,
	audio_filename: str | None = None,
	tags: list[str] | None = None,
) -> int:
	note = {
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

	return _invoke("addNote", {"note": note})


def add_basic_note(
	deck_name: str,
	front: str,
	back: str,
	audio_filename: str | None = None,
	tags: list[str] | None = None,
) -> int:
	if audio_filename:
		back = f"{back} [sound:{audio_filename}]"

	note = {
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

	return _invoke("addNote", {"note": note})
