import { CheckReport, FILE_LIST_KEYS, FileReport } from './checkReport';

const UNRATED_MARKER = 'unrated';

export function fileReportsByPath(report: CheckReport): Map<string, FileReport> {
	return new Map(FILE_LIST_KEYS.flatMap(key => report[key].map(file => [file.path, file] as const)));
}

function formatPercentage(probability: number): string {
	return `${Number((probability * 100).toFixed(1))}%`;
}

/**
 * A file node's plain-text hover: upstream's tooltip, then the file's final probability
 * and either the AI's reason or a note that the file is unrated.
 */
export function fileHover(upstreamTooltip: string, fileReport: FileReport | undefined): string {
	if (!fileReport) {
		return `${upstreamTooltip}\n\nNot in the codetaster check.`;
	}
	const ratingLine = fileReport.rating
		? `AI reason: ${fileReport.rating.reason}`
		: 'Unrated: no AI rating matches this version of the file.';
	return `${upstreamTooltip}\n\nReview probability: ${formatPercentage(fileReport.probability)}\n${ratingLine}`;
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
