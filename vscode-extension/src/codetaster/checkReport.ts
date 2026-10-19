/**
 * The JSON that `codetaster check --format json` prints, schema_version 4.
 * The documented schema is the Python `CheckReport` in codetaster's check_report module.
 * New fields can appear without a version bump; they are kept on the parsed objects.
 */

export interface RatingReport {
	readonly probability: number;
	/** The category the file is grouped under in the file list. */
	readonly category: string;
}

export interface FileReport {
	readonly path: string;
	readonly previous_path: string | null;
	readonly change_type: string;
	readonly base_probability: number;
	/** null when no AI rating matches this version of the file. */
	readonly rating: RatingReport | null;
	readonly unrated: boolean;
	readonly draw: number;
}

export interface CategoryReport {
	readonly name: string;
	/** Markdown. */
	readonly description: string;
}

/** The PR summary and category descriptions from the ratings file. */
export interface OverviewReport {
	/** Markdown, referring to the categories by name. */
	readonly summary: string;
	/** In the order a reviewer should read them. */
	readonly categories: readonly CategoryReport[];
}

export interface CheckReport {
	readonly schema_version: 4;
	readonly needs_review: boolean;
	readonly base: { readonly ref: string, readonly merge_base: string };
	readonly head: { readonly commit: string };
	/** The AI rating, from 0 to 1, at or above which a file is in needs-review. */
	readonly needs_review_threshold: number;
	/** Why an invalid ratings file was ignored, leaving every file unrated. Absent from older codetaster versions. */
	readonly ratings_error?: string | null;
	/** null when the ratings file is missing or invalid. Absent from older codetaster versions. */
	readonly overview?: OverviewReport | null;
	readonly 'needs-review': readonly FileReport[];
	readonly sampled: readonly FileReport[];
	readonly 'no-review': readonly FileReport[];
}

export type FileListKey = 'needs-review' | 'sampled' | 'no-review';

/** The report's file lists, most urgent first. */
export const FILE_LIST_KEYS: readonly FileListKey[] = ['needs-review', 'sampled', 'no-review'];

export type ParsedCheckReport =
	| { readonly kind: 'report', readonly report: CheckReport }
	| { readonly kind: 'invalid', readonly message: string };

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isOverview(value: unknown): boolean {
	return isRecord(value)
		&& typeof value.summary === 'string'
		&& Array.isArray(value.categories)
		&& value.categories.every(category => isRecord(category) && typeof category.name === 'string' && typeof category.description === 'string');
}

function invalidReport(message: string): ParsedCheckReport {
	return { kind: 'invalid', message };
}

export function parseCheckReport(output: string): ParsedCheckReport {
	let json: unknown;
	try {
		json = JSON.parse(output);
	} catch {
		return invalidReport('Its output is not valid JSON.');
	}
	if (!isRecord(json)) {
		return invalidReport('Its output is not a JSON object.');
	}
	if (json.schema_version !== 4) {
		return invalidReport(`Its output has schema_version ${JSON.stringify(json.schema_version)}; this extension reads schema_version 4.`);
	}
	if (typeof json.needs_review_threshold !== 'number') {
		return invalidReport('Its output has no "needs_review_threshold".');
	}
	if (!isRecord(json.head) || typeof json.head.commit !== 'string') {
		return invalidReport('Its output has no "head.commit".');
	}
	for (const key of FILE_LIST_KEYS) {
		const files = json[key];
		if (!Array.isArray(files) || !files.every(file => isRecord(file) && typeof file.path === 'string')) {
			return invalidReport(`Its output has no "${key}" list of files with paths.`);
		}
	}
	if (json.overview !== undefined && json.overview !== null && !isOverview(json.overview)) {
		return invalidReport('Its output has an "overview" without a summary and described categories.');
	}
	return { kind: 'report', report: json as unknown as CheckReport };
}
