import { FileVerdict } from './categoryGroups';
import { CheckReport, FILE_LIST_KEYS, FileReport } from './checkReport';

const UNRATED_MARKER = 'unrated';

export function fileReportsByPath(report: CheckReport): Map<string, FileReport> {
	return new Map(FILE_LIST_KEYS.flatMap(key => report[key].map(file => [file.path, file] as const)));
}

function formatPercentage(probability: number): string {
	return `${Number((probability * 100).toFixed(1))}%`;
}

function verdictName(verdict: FileVerdict): string {
	switch (verdict) {
		case 'needs-review': return 'Needs review';
		case 'sampled': return 'Sampled';
		case 'no-review': return 'No review';
		case 'not-checked': return 'Not in codetaster check';
	}
}

/**
 * A file node's plain-text hover: upstream's tooltip, then the file's verdict and, if
 * the check listed the file, its AI rating, the highest of its hunks', or a note that it
 * is unrated.
 */
export function fileHover(upstreamTooltip: string, verdict: FileVerdict, fileReport: FileReport | undefined): string {
	const verdictLine = `Verdict: ${verdictName(verdict)}`;
	if (!fileReport) {
		return `${upstreamTooltip}\n\n${verdictLine}`;
	}
	const rating = fileReport.rating;
	const ratingLine = rating
		? `AI rating: ${formatPercentage(rating.probability)}${rating.hunks.length > 1 ? `, the highest of ${rating.hunks.length} hunks` : ''}`
		: 'Unrated: no AI rating matches this version of the file.';
	return `${upstreamTooltip}\n\n${verdictLine}\n${ratingLine}`;
}

/**
 * A file node's description, with unrated files marked. `upstreamDescription` is what
 * upstream set: `true` means VS Code derives it from the file's directory, which
 * `directory` (from the repository root, '' at the root) stands in for once text is added.
 */
export function fileDescription(
	upstreamDescription: string | boolean | undefined,
	directory: string,
	fileReport: FileReport | undefined,
): string | boolean | undefined {
	if (!fileReport?.unrated) {
		return upstreamDescription;
	}
	const rest = upstreamDescription === true ? directory : upstreamDescription || '';
	return rest ? `${UNRATED_MARKER} · ${rest}` : UNRATED_MARKER;
}
