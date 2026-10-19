import { CheckReport, FILE_LIST_KEYS, FileListKey, FileReport } from './checkReport';

/** A PR file's verdict: the list the check put it in, or not-checked if the check did not list it. */
export type FileVerdict = FileListKey | 'not-checked';

export interface GroupedFile<File> {
	readonly file: File;
	readonly verdict: FileVerdict;
}

/** A category from the files' ratings, or one of the two groups outside the categories. */
export type CategoryGroupKind = 'not-checked' | 'category' | 'unrated';

export interface CategoryGroup<File> {
	readonly kind: CategoryGroupKind;
	readonly label: string;
	readonly files: readonly GroupedFile<File>[];
	/** Whether the group starts collapsed. A group whose files all need no review is, as they need no attention. */
	readonly collapsed: boolean;
}

function categoryGroup<File>(kind: CategoryGroupKind, name: string, files: readonly GroupedFile<File>[]): CategoryGroup<File> {
	return {
		kind,
		label: `${name} (${files.length})`,
		files,
		collapsed: files.every(entry => entry.verdict === 'no-review'),
	};
}

/**
 * Splits the PR's files by the category of their AI rating, sorted by name with
 * numbers compared by value, so "2." comes before "10.". Each file keeps the verdict
 * the check gave it. PR files the check did not list (e.g. when the local checkout is
 * not at the PR's head) go in a group before the categories, and files the check
 * listed without a rating in a group after them, each present only when non-empty,
 * so no file is hidden. Files the check lists but the PR does not are ignored.
 */
export function groupFilesByCategory<File>(
	report: CheckReport,
	files: readonly File[],
	pathOf: (file: File) => string,
): CategoryGroup<File>[] {
	const checkedByPath = new Map<string, { verdict: FileListKey, fileReport: FileReport }>();
	for (const key of FILE_LIST_KEYS) {
		for (const fileReport of report[key]) {
			checkedByPath.set(fileReport.path, { verdict: key, fileReport });
		}
	}
	const notChecked: GroupedFile<File>[] = [];
	const unrated: GroupedFile<File>[] = [];
	const filesByCategory = new Map<string, GroupedFile<File>[]>();
	for (const file of files) {
		const checked = checkedByPath.get(pathOf(file));
		if (!checked) {
			notChecked.push({ file, verdict: 'not-checked' });
		} else if (!checked.fileReport.rating) {
			unrated.push({ file, verdict: checked.verdict });
		} else {
			const category = checked.fileReport.rating.category;
			filesByCategory.set(category, [...(filesByCategory.get(category) ?? []), { file, verdict: checked.verdict }]);
		}
	}
	const categories = [...filesByCategory.keys()].sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
	return [
		...(notChecked.length ? [categoryGroup('not-checked', 'Not in codetaster check', notChecked)] : []),
		...categories.map(category => categoryGroup('category', category, filesByCategory.get(category)!)),
		...(unrated.length ? [categoryGroup('unrated', 'Unrated', unrated)] : []),
	];
}

/** The file list's description: which files the check put in needs-review. */
export function needsReviewRuleDescription(report: CheckReport): string {
	return `needs review = rating ≥ ${report.needs_review_threshold}`;
}
