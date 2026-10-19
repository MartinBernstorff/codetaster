import { FileVerdict } from './categoryGroups';

/** A codicon, by ID, coloured with the theme color `color` if given. */
export interface ThemeIconSpec {
	readonly id: string;
	readonly color?: string;
}

/**
 * The icon of a file in the file list, which shows its verdict: a green circle for
 * needs review, a yellow one for sampled, a question mark if the check did not list
 * it, and the file's own icon, `fileIcon`, for no review. `themeIcon` makes an icon
 * from a codicon.
 */
export function verdictIconPath<Icon>(verdict: FileVerdict, fileIcon: Icon, themeIcon: (spec: ThemeIconSpec) => Icon): Icon {
	switch (verdict) {
		case 'needs-review': return themeIcon({ id: 'circle-filled', color: 'charts.green' });
		case 'sampled': return themeIcon({ id: 'circle-filled', color: 'charts.yellow' });
		case 'no-review': return fileIcon;
		case 'not-checked': return themeIcon({ id: 'question' });
	}
}
