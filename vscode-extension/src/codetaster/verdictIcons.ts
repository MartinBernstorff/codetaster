import { FileVerdict } from './categoryGroups';

/** A codicon, by ID, coloured with the theme color `color` if given. */
export interface ThemeIconSpec {
	readonly id: string;
	readonly color?: string;
}

/**
 * The icon of a file in the file list, which shows its verdict: a large green disc for
 * needs review, a yellow ring for sampled, a question mark if the check did not list
 * it, and the file's own icon, `fileIcon`, for no review. VS Code draws a selected
 * row's icon in the selection colour, so each verdict has its own shape as well as
 * its own colour. `themeIcon` makes an icon from a codicon.
 */
export function verdictIconPath<Icon>(verdict: FileVerdict, fileIcon: Icon, themeIcon: (spec: ThemeIconSpec) => Icon): Icon {
	switch (verdict) {
		case 'needs-review': return themeIcon({ id: 'circle-large-filled', color: 'charts.green' });
		case 'sampled': return themeIcon({ id: 'circle-large', color: 'charts.yellow' });
		case 'no-review': return fileIcon;
		case 'not-checked': return themeIcon({ id: 'question' });
	}
}
