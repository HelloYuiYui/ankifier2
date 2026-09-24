const generateHeaderTitle: string = 'Words to generate'
const generateHeaderDescription: React.ReactNode =
	'One word or phrase per row. Tick <strong>As is</strong> to keep the text exactly as typed — it is only translated, and any <code>[[…]]</code> you mark becomes the cloze deletion.'

const manualHeaderTitle: string = 'Manual input'
const manualHeaderDescription: React.ReactNode =
	'One word or phrase per row. Tick <strong>Cloze</strong> to mark the text as a cloze deletion — it will be hidden on the front of the card, and shown on the back. Use <code>[[…]]</code> to mark the text you want to hide.'

const PANEL_CONSTANTS = {
	generateTitle: generateHeaderTitle,
	generateDescription: generateHeaderDescription,
	manualTitle: manualHeaderTitle,
	manualDescription: manualHeaderDescription,
}

export default PANEL_CONSTANTS
