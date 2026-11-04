import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

export function EmptyState({ children }: { children: ReactNode }) {
	return (
		<div className="panel">
			<p className="empty">
				{children} Start from <Link to="/">Generate</Link> or{' '}
				<Link to="/manual">Manual</Link>.
			</p>
		</div>
	)
}
