import { GroupVerdict, VerdictGroup } from './verdictGroups';

export interface OrderedFile<File> {
	readonly file: File;
	readonly path: string;
	readonly verdict: GroupVerdict;
}

function compareNames(a: string, b: string): number {
	const lowerA = a.toLowerCase();
	const lowerB = b.toLowerCase();
	return lowerA < lowerB ? -1 : lowerA > lowerB ? 1 : 0;
}

/** As upstream's tree layout orders files: directories before files at each level, each by name. */
function compareInTreeLayout(a: string, b: string): number {
	const segmentsA = a.split('/');
	const segmentsB = b.split('/');
	for (let index = 0; index < Math.min(segmentsA.length, segmentsB.length); index++) {
		if (segmentsA[index] === segmentsB[index]) {
			continue;
		}
		const isDirectoryA = index < segmentsA.length - 1;
		const isDirectoryB = index < segmentsB.length - 1;
		if (isDirectoryA !== isDirectoryB) {
			return isDirectoryA ? -1 : 1;
		}
		return segmentsA[index] < segmentsB[index] ? -1 : 1;
	}
	return segmentsA.length - segmentsB.length;
}

/**
 * Every file of `groups` in the order the file list shows them: group by group, and
 * within a group as the `fileListLayout` setting lays them out.
 */
export function reviewOrder<File>(
	groups: readonly VerdictGroup<File>[],
	pathOf: (file: File) => string,
	layout: string | undefined,
): OrderedFile<File>[] {
	const compare = layout === 'tree' ? compareInTreeLayout : compareNames;
	return groups.flatMap(group => group.files
		.map(file => ({ file, path: pathOf(file), verdict: group.verdict }))
		.sort((a, b) => compare(a.path, b.path)));
}

/**
 * The file to review after the one at `currentPath`: the next unviewed file in
 * `ordered`, wrapping around to the start. No-review files are skipped unless the
 * current file is one. Without a current file, the first unviewed file to review.
 * Undefined if every such file is viewed.
 */
export function nextFileToReview<File>(
	ordered: readonly OrderedFile<File>[],
	currentPath: string | undefined,
	isViewed: (file: File) => boolean,
): File | undefined {
	const currentIndex = ordered.findIndex(entry => entry.path === currentPath);
	const current = ordered[currentIndex] as OrderedFile<File> | undefined;
	const includesNoReview = current?.verdict === 'no-review';
	const candidates = [...ordered.slice(currentIndex + 1), ...ordered.slice(0, Math.max(currentIndex, 0))];
	return candidates.find(entry =>
		(includesNoReview || entry.verdict !== 'no-review') && !isViewed(entry.file),
	)?.file;
}
