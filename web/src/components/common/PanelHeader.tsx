import type { PanelProps } from './panelTypes'

export default function PanelHeader(props: PanelProps): React.ReactNode {
	const { title, description } = props
	return (
		<>
			<h2>{title}</h2>
			{description instanceof String ? (
				<p
					className="small muted"
					style={{ marginTop: 0 }}
					dangerouslySetInnerHTML={{ __html: description }}
				/>
			) : (
				{ description }
			)}
		</>
	)
}
