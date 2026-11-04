import type { ReactNode } from 'react'

export function Banner({
	tone,
	children,
}: {
	tone: 'error' | 'warn' | 'ok'
	children: ReactNode
}) {
	return <div className={`banner ${tone}`}>{children}</div>
}
