import { useLayoutEffect, useRef, useState } from 'react'

/**
 * A table cell that reads as text until it is clicked.
 *
 * The review table used to be a wall of textareas, which made it hard to read
 * the thing you are supposed to be reviewing. Here the value is plain text and
 * only the cell you click becomes an input, so the table stays readable while
 * every field remains editable.
 *
 * Edits go straight to the store as they are typed -- the cloze preview under
 * the card-front cell depends on that -- so leaving the cell commits nothing,
 * it only stops editing. Escape puts the value back to what it was when the
 * cell was opened.
 */
export function EditableCell({
	value,
	onChange,
	label,
	className,
}: {
	value: string
	onChange: (next: string) => void
	/** Names the textarea, which has no visible label of its own. */
	label: string
	className?: string
}) {
	const [editing, setEditing] = useState(false)
	const box = useRef<HTMLTextAreaElement>(null)
	// The value as it was when editing started, for Escape to restore.
	const opened = useRef(value)

	// Grown to fit rather than left at a fixed `rows`: the display is as tall as
	// its text, so a fixed-height textarea would make the row jump on click and
	// hide the end of a long sentence behind a scrollbar.
	const fit = (el: HTMLTextAreaElement) => {
		el.style.height = 'auto'
		el.style.height = `${el.scrollHeight}px`
	}

	useLayoutEffect(() => {
		const el = box.current
		if (!editing || !el) return
		fit(el)
		el.focus()
		// Caret at the end, not a select-all: clicking a cell here means "fix
		// this", and a select-all loses the text to the first keystroke.
		el.setSelectionRange(el.value.length, el.value.length)
	}, [editing])

	if (!editing) {
		return (
			<button
				type="button"
				className={className ? `cell ${className}` : 'cell'}
				title="Click to edit"
				onClick={() => {
					opened.current = value
					setEditing(true)
				}}
			>
				{value || <span className="muted">Add {label.toLowerCase()}</span>}
			</button>
		)
	}

	return (
		<textarea
			ref={box}
			rows={2}
			className={className}
			aria-label={label}
			value={value}
			onChange={(e) => {
				fit(e.currentTarget)
				onChange(e.target.value)
			}}
			onBlur={() => setEditing(false)}
			onKeyDown={(e) => {
				if (e.key !== 'Escape') return
				onChange(opened.current)
				setEditing(false)
			}}
		/>
	)
}
