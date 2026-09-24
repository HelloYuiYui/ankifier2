import { NavLink } from 'react-router-dom'

const t = ({ isActive }: { isActive: boolean }) => (isActive ? 'active' : undefined)

const tabs = [
	{ path: '/', label: 'Generate' },
	{ path: '/manual', label: 'Manual' },
	{ path: '/review', label: 'Review' },
	{ path: '/results', label: 'Results' },
]

export default function Navbar(): React.ReactNode {
	return (
		<nav className="tabs">
			{tabs.map((tab) => (
				<NavLink to={tab.path} end className={t}>
					{tab.label}
				</NavLink>
			))}
		</nav>
	)
}
