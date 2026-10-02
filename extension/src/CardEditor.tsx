import type { CardDraft } from '@ankifier/api'
import { type ReactNode, useId, useLayoutEffect, useRef } from 'react'

import { ClozePreview } from './ClozePreview'

/**
 * The review row from web/'s Review table, as a form for one card.
 *
 * Plain textareas rather than web's click-to-edit cells: the table needed those
 * to stay readable at sixty rows, and a bubble with one card does not.
 */
export function CardEditor({
	draft,
	onChange,
}: {
	draft: CardDraft
	onChange: (patch: Partial<CardDraft>) => void
}) {
	// Bound to whichever field is read aloud, exactly as in Review.tsx: a
	// "Spoken text" box that showed the front of a back-read card would be a
	// lie, and editing it would change nothing.
	const spokenField = draft.audioSide === 'back' ? 'translation' : 'sentence'

	return (
		<div className="editor">
			<Field
				label="Spoken text"
				note="Read aloud by ElevenLabs. Edit this too if you change the front."
				value={draft[spokenField]}
				onChange={(v) => onChange({ [spokenField]: v })}
			/>
			<Field
				label="Card front"
				mono
				value={draft.clozeSentence}
				onChange={(v) => onChange({ clozeSentence: v })}
			>
				<ClozePreview cloze={draft.clozeSentence} />
			</Field>
			<Field
				label="Back"
				value={draft.translation}
				onChange={(v) => onChange({ translation: v })}
			/>
			<Field
				label="Tags"
				note="Comma-separated, added to the level and word-class tags."
				value={draft.extraTags ?? ''}
				onChange={(v) => onChange({ extraTags: v })}
			/>
		</div>
	)
}

function Field({
	label,
	note,
	value,
	onChange,
	mono,
	children,
}: {
	label: string
	note?: string
	value: string
	onChange: (next: string) => void
	mono?: boolean
	children?: ReactNode
}) {
	const id = useId()
	const box = useRef<HTMLTextAreaElement>(null)

	// Grown to fit, so a long sentence is never hidden behind a scrollbar.
	useLayoutEffect(() => {
		const el = box.current
		if (!el) return
		el.style.height = 'auto'
		el.style.height = `${el.scrollHeight}px`
	}, [value])

	return (
		<div className="field">
			<label htmlFor={id}>{label}</label>
			<textarea
				id={id}
				ref={box}
				rows={1}
				className={mono ? 'mono' : undefined}
				value={value}
				title={note}
				onChange={(e) => onChange(e.target.value)}
			/>
			{children}
		</div>
	)
}
