import { CheckReport, FILE_LIST_KEYS, FileListKey } from './checkReport';

export type GroupVerdict = FileListKey | 'not-checked';

export interface VerdictGroup<File> {
	readonly verdict: GroupVerdict;
	readonly label: string;
	readonly files: readonly File[];
}

const GROUP_NAMES: Record<GroupVerdict, string> = {
	'needs-review': 'Needs review',
	'sampled': 'Sampled',
	'no-review': 'No review',
	'not-checked': 'Not in codetaster check',
};

function verdictGroup<File>(verdict: GroupVerdict, files: readonly File[]): VerdictGroup<File> {
	return { verdict, label: `${GROUP_NAMES[verdict]} (${files.length})`, files };
}

/**
 * Splits the PR's files into the check's three groups, most urgent first. The three
 * groups are always present. PR files the check did not list (e.g. when the local
 * checkout is not at the PR's head) go in a group before the others, present only when
 * non-empty, so no file is hidden. Files the check lists but the PR does not are ignored.
 */
export function groupFilesByVerdict<File>(
	report: CheckReport,
	files: readonly File[],
	pathOf: (file: File) => string,
): VerdictGroup<File>[] {
	const verdictByPath = new Map<string, FileListKey>();
	for (const key of FILE_LIST_KEYS) {
		for (const fileReport of report[key]) {
			verdictByPath.set(fileReport.path, key);
		}
	}
	const filesByVerdict = new Map<GroupVerdict, File[]>();
	for (const file of files) {
		const verdict = verdictByPath.get(pathOf(file)) ?? 'not-checked';
		filesByVerdict.set(verdict, [...(filesByVerdict.get(verdict) ?? []), file]);
	}
	const groups = FILE_LIST_KEYS.map(key => verdictGroup(key, filesByVerdict.get(key) ?? []));
	const notChecked = filesByVerdict.get('not-checked');
	return notChecked ? [verdictGroup('not-checked', notChecked), ...groups] : groups;
}
