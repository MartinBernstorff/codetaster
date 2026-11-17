import { FileVerdict } from './categoryGroups';
import { CheckReport, FILE_LIST_KEYS, FileReport } from './checkReport';

const UNRATED_MARKER = 'unrated';

export function fileReportsByPath(report: CheckReport): Map<string, FileReport> {
	return new Map(FILE_LIST_KEYS.flatMap(key => report[key].map(file => [file.path, file] as const)));
}

export function formatPercentage(probability: number): string {
	return `${Number((probability * 100).toFixed(1))}%`;
}

export function verdictName(verdict: FileVerdict): string {
	switch (verdict) {
		case 'needs-review': return 'Needs review';
		case 'sampled': return 'Sampled';
		case 'no-review': return 'No review';
		case 'not-checked': return 'Not in codetaster check';
	}
}

/**
 * A file node's plain-text hover: upstream's tooltip, then the file's verdict and, if
 * the check listed the file, its AI rating or a note that it is unrated.
 */
export function fileHover(upstreamTooltip: string, verdict: FileVerdict, fileReport: FileReport | undefined): string {
	const verdictLine = `Verdict: ${verdictName(verdict)}`;
	if (!fileReport) {
		return `${upstreamTooltip}\n\n${verdictLine}`;
	}
	const ratingLine = fileReport.rating
		? `AI rating: ${formatPercentage(fileReport.rating.probability)}`
		: 'Unrated: no AI rating matches this version of the file.';
	return `${upstreamTooltip}\n\n${verdictLine}\n${ratingLine}`;
}

const VERDICT_GUIDANCE: Record<FileVerdict, string> = {
	'needs-review': 'Read closely: its AI rating is at or above the needs-review threshold.',
	sampled: 'Spot-check: sampled at random from the files below the threshold.',
	'no-review': 'Skim: its AI rating is below the threshold and it was not sampled.',
	'not-checked': 'codetaster check did not assess this file.',
};

export interface FileStatus {
	readonly text: string;
	readonly tooltip: string;
}

/**
 * The status bar's summary of the open file: its place in the review order, its
 * verdict and its AI rating, with how closely to read it on hover. `position` is
 * 1-based, out of `total` files.
 */
export function fileStatus(position: number, total: number, verdict: FileVerdict, fileReport: FileReport | undefined): FileStatus {
	const rating = fileReport?.rating ? ` · ${formatPercentage(fileReport.rating.probability)}` : fileReport?.unrated ? ` · ${UNRATED_MARKER}` : '';
	return {
		text: `codetaster ${position}/${total} · ${verdictName(verdict)}${rating}`,
		tooltip: `${VERDICT_GUIDANCE[verdict]}\nClick to mark it viewed and open the next file.`,
	};
}

/**
 * A file node's description, led by its AI rating, or by a marker if it is unrated, so
 * the list shows each file's priority. `upstreamDescription` is what
 * upstream set: `true` means VS Code derives it from the file's directory, which
 * `directory` (from the repository root, '' at the root) stands in for once text is added.
 */
export function fileDescription(
	upstreamDescription: string | boolean | undefined,
	directory: string,
	fileReport: FileReport | undefined,
): string | boolean | undefined {
	if (!fileReport) {
		return upstreamDescription;
	}
	const marker = fileReport.rating ? formatPercentage(fileReport.rating.probability) : UNRATED_MARKER;
	const rest = upstreamDescription === true ? directory : upstreamDescription || '';
	return rest ? `${marker} · ${rest}` : marker;
}
