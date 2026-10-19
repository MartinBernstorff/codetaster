import { FileVerdict } from './categoryGroups';

/** How a file's verdict decorates it in the file list. `color` is a theme color ID. */
export interface VerdictBadge {
	readonly badge?: string;
	readonly tooltip?: string;
	readonly color?: string;
}

export function verdictBadge(verdict: FileVerdict): VerdictBadge {
	switch (verdict) {
		case 'needs-review': return { badge: 'N', tooltip: 'Needs review', color: 'charts.green' };
		case 'sampled': return { badge: 'S', tooltip: 'Sampled', color: 'charts.yellow' };
		case 'no-review': return { tooltip: 'No review', color: 'disabledForeground' };
		case 'not-checked': return { badge: '?', tooltip: 'Not in codetaster check' };
	}
}
