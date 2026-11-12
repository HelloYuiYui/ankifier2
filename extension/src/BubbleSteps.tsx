import { type AddResult, type CardDraft, needsCloze } from '@ankifier/api'
import type { CSSProperties } from 'react'

import { CardEditor } from './CardEditor'

export function Pill({
	style,
	onCard,
	onAsIs,
}: {
	style: CSSProperties
	onCard: () => void
	onAsIs: () => void
}) {
	return (
		<div className="ankifier pill" style={style}>
			<button type="button" onClick={onCard}>
				Card
			</button>
			<button type="button" onClick={onAsIs}>
				As is
			</button>
		</div>
	)
}

export function Header({
	word,
	asIs,
	draft,
	onClose,
}: {
	word: string
	asIs: boolean
	draft: CardDraft | undefined
	onClose: () => void
}) {
	return (
		<header>
			<strong className="word" title={word}>
				{word}
			</strong>
			{asIs && <span className="badge">as is</span>}
			{draft?.level && <span className="badge">{draft.level}</span>}
			{draft?.partOfSpeech && <span className="badge">{draft.partOfSpeech}</span>}
			{draft?.gender && <span className="badge">{draft.gender}</span>}
			<button
				type="button"
				className="close"
				aria-label="Close"
				onClick={onClose}
			>
				×
			</button>
		</header>
	)
}

export function AsIsStep({
	text,
	onChange,
	onTranslate,
	onCancel,
}: {
	text: string
	onChange: (text: string) => void
	onTranslate: () => void
	onCancel: () => void
}) {
	return (
		<>
			<p className="muted">
				Wrap what the card should hide in <code>[[…]]</code>, or leave it plain
				for a front/back card.
			</p>
			<textarea
				className="mono"
				aria-label="As-is text"
				rows={3}
				value={text}
				// eslint-disable-next-line jsx-a11y/no-autofocus -- the one thing to do next
				autoFocus
				onChange={(e) => onChange(e.target.value)}
				onKeyDown={(e) => {
					if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) onTranslate()
				}}
			/>
			<footer>
				<span className="spacer" />
				<button type="button" onClick={onCancel}>
					Cancel
				</button>
				<button type="button" className="primary" onClick={onTranslate}>
					Translate
				</button>
			</footer>
		</>
	)
}

export function LoadingStep({ asIs }: { asIs: boolean }) {
	return (
		<p className="status">
			<span className="spinner" />
			{asIs ? 'Translating…' : 'Writing a card…'}
		</p>
	)
}

export function ReviewStep({
	draft,
	sense,
	adding,
	onChange,
	onRegenerate,
	onDiscard,
	onAdd,
}: {
	draft: CardDraft
	sense: string | null
	adding: boolean
	onChange: (change: Partial<CardDraft>) => void
	onRegenerate: () => void
	onDiscard: () => void
	onAdd: () => void
}) {
	return (
		<>
			{sense && <p className="muted sense">{sense}</p>}
			<CardEditor draft={draft} onChange={onChange} />
			{needsCloze(draft) && (
				<p className="warn">
					The hidden text was not found in the sentence. Mark it in the front
					as <code>{'{{c1::text::hint}}'}</code>, or regenerate.
				</p>
			)}
			<footer>
				<button type="button" disabled={adding} onClick={onRegenerate}>
					Regenerate
				</button>
				<span className="spacer" />
				<button type="button" onClick={onDiscard}>
					Discard
				</button>
				<button
					type="button"
					className="primary"
					disabled={adding || needsCloze(draft)}
					onClick={onAdd}
				>
					{adding && <span className="spinner" />}
					{adding ? 'Adding…' : 'Add to Anki'}
				</button>
			</footer>
		</>
	)
}

// "duplicate" when addNote rejected it, "already in Anki" when the server's
// check skipped it before generating audio.
const DUPLICATE_DETAILS = ['duplicate', 'already in Anki']

export function DoneStep({
	result,
	onClose,
}: {
	result: AddResult
	onClose: () => void
}) {
	const { card, audio, deck } = result
	return (
		<>
			{card.state === 'ok' && <p className="ok">Added to {deck}.</p>}
			{card.state === 'skipped' && (
				<p className="warn">
					{DUPLICATE_DETAILS.includes(card.detail ?? '')
						? `Already in Anki (${deck}).`
						: (card.detail ?? 'Skipped.')}
				</p>
			)}
			{card.state === 'error' && <p className="error">{card.detail}</p>}
			{card.state === 'ok' && audio.state === 'error' && (
				<p className="warn">Added without audio: {audio.detail}</p>
			)}
			<footer>
				<span className="spacer" />
				<button type="button" onClick={onClose}>
					Close
				</button>
			</footer>
		</>
	)
}

export function ErrorStep({
	message,
	onClose,
	onRetry,
}: {
	message: string
	onClose: () => void
	onRetry: () => void
}) {
	return (
		<>
			<p className="error">{message}</p>
			<footer>
				<span className="spacer" />
				<button type="button" onClick={onClose}>
					Close
				</button>
				<button type="button" className="primary" onClick={onRetry}>
					Retry
				</button>
			</footer>
		</>
	)
}
