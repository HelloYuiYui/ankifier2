export type PanelType = 'generate' | 'manual' | 'review' | 'results';
export type PanelProps = {
    title: string;
    description: React.ReactNode | string;
}