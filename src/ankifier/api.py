"""The HTTP layer: schema in, service call, schema out.

There is no session, no cookie and no server-side batch. The client holds its
cards between generating and adding and posts back the ones it kept, which is
why every route here is independent of every other.

Handlers are plain `def`, not `async def`. Every connector is blocking, so an
`async def` handler would pin the event loop for the length of a batch; a `def`
handler is run in a threadpool by FastAPI instead.
"""

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ankifier import anki_connector, services
from ankifier.schemas import (
	AddRequest,
	AddResponse,
	AnkiStatus,
	AudioPreviewRequest,
	AudioPreviewResponse,
	ClozePreviewRequest,
	ClozePreviewResponse,
	DeckConfig,
	GenerateRequest,
	GenerateResponse,
	HealthResponse,
	KeyStatus,
)
from ankifier.settings import Settings, get_settings

# Note: no load_dotenv() here. Settings reads .env itself, and calling
# load_dotenv() as well would copy every secret into os.environ for the life of
# the process -- where anything that dumps the environment can print it.
app = FastAPI(title="Ankifier", version="0.2.0")

# The SPA build. Vite writes here (build.outDir), so it is absent on a fresh
# clone until `pnpm build` has run.
DIST = Path(__file__).parent / "static"


def settings_dep() -> Settings:
	return get_settings()


_settings = get_settings()
if _settings.cors_origin_list:
	# Only when explicitly configured. This server writes to the user's Anki
	# collection and spends API credits, so it is never opened by default -- a
	# wildcard here would make it reachable from any page they have open.
	from fastapi.middleware.cors import CORSMiddleware

	app.add_middleware(
		CORSMiddleware,
		allow_origins=_settings.cors_origin_list,
		allow_methods=["*"],
		allow_headers=["*"],
	)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/api/health", response_model=HealthResponse)
def health(settings: Settings = Depends(settings_dep)) -> HealthResponse:
	"""One call at boot. Also the place a missing key surfaces, rather than as a
	500 in the middle of a batch."""
	version, error = None, None
	try:
		version = anki_connector.get_version()
		if version is None:
			error = "Anki is not reachable"
	except Exception as e:
		error = str(e)

	decks = None
	if version is not None:
		try:
			decks = anki_connector.deck_names()
		except Exception:
			# Reachable but the call failed -- not worth failing health over.
			decks = None

	return HealthResponse(
		anki=AnkiStatus(ok=version is not None, version=version, error=error),
		keys=KeyStatus(
			mistral=bool(settings.ai_key), elevenlabs=bool(settings.eleven_labs_key)
		),
		decks=DeckConfig(
			generated=settings.deck_for("generated"),
			as_is=settings.deck_for("as_is"),
			manual=settings.deck_for("manual"),
		),
		target_lang=settings.target_lang,
		anki_decks=decks,
	)


@app.get("/api/decks", response_model=list[str])
def decks() -> list[str]:
	try:
		return anki_connector.deck_names()
	except Exception as e:
		raise HTTPException(503, f"Anki is not reachable: {e}") from e


# ---------------------------------------------------------------------------
# Cloze preview
# ---------------------------------------------------------------------------
@app.post("/api/cloze/preview", response_model=ClozePreviewResponse)
def cloze_preview(req: ClozePreviewRequest) -> ClozePreviewResponse:
	"""Marker -> cloze, for the live preview as the user types.

	Batched so a whole table is one request. Pure string work, so this is the
	one route with no I/O at all.
	"""
	return ClozePreviewResponse(results=services.render_cloze(req.texts))


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------
@app.post("/api/generate", response_model=GenerateResponse)
def generate(
	req: GenerateRequest, settings: Settings = Depends(settings_dep)
) -> GenerateResponse:
	"""Serial, ~2s per row -- a 20-row batch holds this request for ~40s."""
	if not req.rows:
		return GenerateResponse()
	if not settings.ai_key:
		raise HTTPException(503, "AI_KEY is not set")

	cards, errors = services.generate_batch(req.rows, settings)
	return GenerateResponse(cards=cards, errors=errors)


# ---------------------------------------------------------------------------
# Adding to Anki
# ---------------------------------------------------------------------------
@app.post("/api/cards/add", response_model=AddResponse)
def add_cards(
	req: AddRequest, settings: Settings = Depends(settings_dep)
) -> AddResponse:
	"""Audio and notes for the cards the client kept.

	Anything that would fail every card identically (Anki down, key missing)
	raises here, before the first side effect, so the client gets a status code
	rather than a list of identical per-card errors.
	"""
	try:
		results = services.add_cards(req.cards, settings, dry_run=req.dry_run)
	except services.PreflightError as e:
		raise HTTPException(503, str(e)) from e
	return AddResponse(results=results)


# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------
@app.post("/api/audio/preview", response_model=AudioPreviewResponse)
def audio_preview(
	req: AudioPreviewRequest, settings: Settings = Depends(settings_dep)
) -> AudioPreviewResponse:
	"""Generate (or reuse) the audio for one text.

	Cheap to call twice: the path is content-addressed, so a second request for
	the same text returns the existing file and spends nothing -- and a later
	add finds that same file and skips generating it again.
	"""
	if not settings.eleven_labs_key:
		raise HTTPException(503, "ELEVEN_LABS_KEY is not set")
	try:
		path = services.synthesize(req.text, req.stem, settings)
	except Exception as e:
		raise HTTPException(502, f"Audio generation failed: {e}") from e
	return AudioPreviewResponse(audio_url=services.audio_url(path.name))


@app.get("/api/audio/{filename}")
def audio(filename: str, settings: Settings = Depends(settings_dep)) -> FileResponse:
	root = settings.audio_root
	# Never os.path.join a user string onto a root -- an absolute second
	# argument wins. Resolve and prove containment instead.
	target = (root / filename).resolve()
	if not target.is_relative_to(root) or not target.is_file():
		raise HTTPException(404, "No such audio file")
	return FileResponse(target, media_type="audio/mpeg")


# ---------------------------------------------------------------------------
# The SPA.
#
# Registered LAST: Starlette matches routes in registration order and the
# catch-all below matches everything, so anything added after it is dead.
# ---------------------------------------------------------------------------
if DIST.is_dir():
	# StaticFiles raises at import time if the directory is missing, which would
	# stop the app (and every test that imports it) from starting on a fresh
	# clone -- hence the guard.
	app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

	@app.get("/{full_path:path}", include_in_schema=False)
	def spa(full_path: str) -> FileResponse:
		# StaticFiles(html=True) only falls back for *directory* paths, so a
		# client-side route like /review would 404 without this.
		if full_path.startswith("api/"):
			# Otherwise a mistyped endpoint returns index.html with status 200
			# and the client's res.json() throws "Unexpected token <".
			raise HTTPException(404, "No such endpoint")
		candidate = DIST / full_path
		if full_path and candidate.is_file():
			return FileResponse(candidate)
		return FileResponse(DIST / "index.html")


def run() -> None:
	import uvicorn

	settings = get_settings()
	uvicorn.run(
		"ankifier.api:app",
		host=settings.host,
		port=settings.port,
		# Off by default: a file save mid-batch used to kill in-flight Anki
		# adds. Vite handles the frontend's hot reload on its own.
		reload=settings.reload,
	)


if __name__ == "__main__":
	run()
