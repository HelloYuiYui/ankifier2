"""Route-level tests, with the services layer faked where it would do I/O.

These check the HTTP contract -- status codes, camelCase on the wire, and the
two routing traps in the SPA fallback -- not the business logic, which
test_services.py covers.
"""

import pytest
from fastapi.testclient import TestClient

from ankifier import api, services
from ankifier.schemas import AddResult, CardDraft, Status
from ankifier.settings import Settings


@pytest.fixture
def settings(tmp_path):
	return Settings(
		_env_file=None,
		ai_key="test-key",
		eleven_labs_key="test-key",
		audio_dir=tmp_path / "audio",
	)


@pytest.fixture
def client(settings):
	api.app.dependency_overrides[api.settings_dep] = lambda: settings
	yield TestClient(api.app)
	api.app.dependency_overrides.clear()


@pytest.fixture
def anki_down(monkeypatch):
	monkeypatch.setattr(api.anki_connector, "get_version", lambda: None)
	monkeypatch.setattr(
		api.anki_connector,
		"deck_names",
		lambda: (_ for _ in ()).throw(RuntimeError("not reachable")),
	)


@pytest.fixture
def anki_up(monkeypatch):
	monkeypatch.setattr(api.anki_connector, "get_version", lambda: 6)
	monkeypatch.setattr(
		api.anki_connector, "deck_names", lambda: ["Default", "French::Vocabulary"]
	)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
def test_health_when_anki_is_up(client, anki_up):
	body = client.get("/api/health").json()
	assert body["anki"] == {"ok": True, "version": 6, "error": None}
	assert body["keys"] == {"mistral": True, "elevenlabs": True}
	assert body["ankiDecks"] == ["Default", "French::Vocabulary"]
	assert body["targetLang"] == "French"


def test_health_is_200_even_when_anki_is_down(client, anki_down):
	"""The banner needs to render; a 5xx would give it nothing to say."""
	response = client.get("/api/health")
	assert response.status_code == 200
	body = response.json()
	assert body["anki"]["ok"] is False
	# None, not [] -- "Anki is down" is not "the collection is empty".
	assert body["ankiDecks"] is None


def test_health_reports_missing_keys(tmp_path, anki_up):
	api.app.dependency_overrides[api.settings_dep] = lambda: Settings(
		_env_file=None, ai_key="", eleven_labs_key="", audio_dir=tmp_path
	)
	try:
		body = TestClient(api.app).get("/api/health").json()
		assert body["keys"] == {"mistral": False, "elevenlabs": False}
	finally:
		api.app.dependency_overrides.clear()


def test_health_uses_camelcase_on_the_wire(client, anki_up):
	body = client.get("/api/health").json()
	assert "targetLang" in body and "target_lang" not in body
	assert "asIs" in body["decks"] and "as_is" not in body["decks"]


def test_decks_is_503_when_anki_is_down(client, anki_down):
	assert client.get("/api/decks").status_code == 503


# ---------------------------------------------------------------------------
# Cloze preview
# ---------------------------------------------------------------------------
def test_cloze_preview(client):
	body = client.post(
		"/api/cloze/preview",
		json={"texts": [{"id": "a", "text": "Il faut que tu [[sois:etre]] la"}]},
	).json()
	assert body["results"] == [
		{
			"id": "a",
			"plain": "Il faut que tu sois la",
			"cloze": "Il faut que tu {{c1::sois::etre}} la",
		}
	]


def test_cloze_preview_is_batched(client):
	body = client.post(
		"/api/cloze/preview",
		json={"texts": [{"id": str(i), "text": f"[[w{i}]]"} for i in range(50)]},
	).json()
	assert len(body["results"]) == 50


def test_cloze_preview_rejects_a_malformed_body(client):
	assert (
		client.post("/api/cloze/preview", json={"texts": [{"id": "a"}]}).status_code
		== 422
	)


# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------
def test_generate_returns_cards_and_errors(client, monkeypatch):
	card = CardDraft(
		id="a#1",
		source_id="a",
		kind="generated",
		word="manger",
		sentence="Je mange",
		cloze_sentence="Je {{c1::mange}}",
		translation="I eat",
		level="A1",
	)
	monkeypatch.setattr(services, "generate_batch", lambda rows, s: ([card], []))

	body = client.post(
		"/api/generate", json={"rows": [{"sourceId": "a", "text": "manger"}]}
	).json()
	assert body["errors"] == []
	assert body["cards"][0]["sourceId"] == "a"
	assert body["cards"][0]["clozeSentence"] == "Je {{c1::mange}}"


def test_generate_with_no_rows_is_an_empty_result_not_an_error(client):
	body = client.post("/api/generate", json={"rows": []}).json()
	assert body == {"cards": [], "errors": []}


def test_generate_is_503_without_a_key(tmp_path):
	api.app.dependency_overrides[api.settings_dep] = lambda: Settings(
		_env_file=None, ai_key="", audio_dir=tmp_path
	)
	try:
		response = TestClient(api.app).post(
			"/api/generate", json={"rows": [{"sourceId": "a", "text": "x"}]}
		)
		assert response.status_code == 503
		assert "AI_KEY" in response.json()["detail"]
	finally:
		api.app.dependency_overrides.clear()


def test_generate_rejects_an_unknown_kind(client):
	"""manual never reaches the model, so it is not a valid generate kind."""
	response = client.post(
		"/api/generate",
		json={"rows": [{"sourceId": "a", "text": "x", "kind": "manual"}]},
	)
	assert response.status_code == 422


# ---------------------------------------------------------------------------
# Add
# ---------------------------------------------------------------------------
def card_payload(**overrides):
	base = {
		"id": "a#1",
		"sourceId": "a",
		"kind": "generated",
		"word": "manger",
		"sentence": "Je mange",
		"clozeSentence": "Je {{c1::mange}}",
		"translation": "I eat",
	}
	return {**base, **overrides}


def test_add_returns_per_card_results(client, monkeypatch):
	monkeypatch.setattr(
		services,
		"add_cards",
		lambda cards, s, dry_run=False: [
			AddResult(
				id=c.id,
				audio=Status(state="ok"),
				card=Status(state="ok"),
				deck="French::Vocabulary",
				audio_url="/api/audio/x.mp3",
			)
			for c in cards
		],
	)
	body = client.post(
		"/api/cards/add", json={"cards": [card_payload(), card_payload(id="b#1")]}
	).json()
	assert [r["id"] for r in body["results"]] == ["a#1", "b#1"]
	assert body["results"][0]["audioUrl"] == "/api/audio/x.mp3"


def test_add_turns_a_preflight_failure_into_503(client, monkeypatch):
	"""A batch-wide problem is one status code, not N identical card errors."""

	def boom(cards, s, dry_run=False):
		raise services.PreflightError("Anki is not reachable")

	monkeypatch.setattr(services, "add_cards", boom)
	response = client.post("/api/cards/add", json={"cards": [card_payload()]})
	assert response.status_code == 503
	assert "not reachable" in response.json()["detail"]


def test_add_passes_dry_run_through(client, monkeypatch):
	seen = {}
	monkeypatch.setattr(
		services,
		"add_cards",
		lambda cards, s, dry_run=False: seen.update(dry_run=dry_run) or [],
	)
	client.post("/api/cards/add", json={"cards": [card_payload()], "dryRun": True})
	assert seen["dry_run"] is True


def test_the_client_cannot_choose_a_deck(client, monkeypatch):
	"""Deck and tags are derived from `kind` server-side, so a stray deck name
	in the payload is ignored rather than honoured."""
	seen = []
	monkeypatch.setattr(
		services,
		"add_cards",
		lambda cards, s, dry_run=False: seen.extend(cards) or [],
	)
	client.post(
		"/api/cards/add",
		json={"cards": [card_payload(deck="Attacker::Deck", tags=["evil"])]},
	)
	assert not hasattr(seen[0], "deck")
	assert not hasattr(seen[0], "tags")


# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------
def test_audio_serves_a_file(client, settings):
	settings.audio_root.mkdir(parents=True, exist_ok=True)
	(settings.audio_root / "ankifier_x_123.mp3").write_bytes(b"ID3fake")

	response = client.get("/api/audio/ankifier_x_123.mp3")
	assert response.status_code == 200
	assert response.headers["content-type"] == "audio/mpeg"
	assert response.content == b"ID3fake"


def test_audio_404s_for_a_missing_file(client, settings):
	settings.audio_root.mkdir(parents=True, exist_ok=True)
	assert client.get("/api/audio/nope.mp3").status_code == 404


@pytest.mark.parametrize(
	"attack",
	[
		"..%2F..%2Fetc%2Fpasswd",
		"%2Fetc%2Fpasswd",
		"....//....//etc/passwd",
		"..%5C..%5Cwindows",
	],
)
def test_audio_refuses_to_escape_the_audio_directory(client, settings, attack):
	settings.audio_root.mkdir(parents=True, exist_ok=True)
	response = client.get(f"/api/audio/{attack}")
	assert response.status_code == 404
	assert b"root" not in response.content


def test_audio_preview_is_503_without_a_key(tmp_path):
	api.app.dependency_overrides[api.settings_dep] = lambda: Settings(
		_env_file=None, eleven_labs_key="", audio_dir=tmp_path
	)
	try:
		response = TestClient(api.app).post("/api/audio/preview", json={"text": "x"})
		assert response.status_code == 503
	finally:
		api.app.dependency_overrides.clear()


def test_audio_preview_returns_a_url(client, settings, monkeypatch):
	def fake_synth(text, stem, s):
		s.audio_root.mkdir(parents=True, exist_ok=True)
		path = s.audio_root / "ankifier_je_mange_abc.mp3"
		path.write_bytes(b"ID3")
		return path

	monkeypatch.setattr(services, "synthesize", fake_synth)
	body = client.post("/api/audio/preview", json={"text": "Je mange"}).json()
	assert body["audioUrl"] == "/api/audio/ankifier_je_mange_abc.mp3"


# ---------------------------------------------------------------------------
# SPA fallback
# ---------------------------------------------------------------------------
def test_an_unknown_api_path_is_404_json_not_the_spa(client):
	"""Without the api/ guard in the catch-all this returns index.html with
	status 200 and the client's res.json() throws "Unexpected token <"."""
	response = client.get("/api/nope")
	assert response.status_code == 404
	assert "text/html" not in response.headers.get("content-type", "")


def test_the_app_starts_without_a_frontend_build():
	"""StaticFiles raises at import time if its directory is missing, so a fresh
	clone with no `pnpm build` must not blow up."""
	assert TestClient(api.app).get("/api/health").status_code in (200, 503)
