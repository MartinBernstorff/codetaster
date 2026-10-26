/**
 * The JSON that `codetaster check --format json` prints, schema_version 6.
 * The documented schema is the Python `CheckReport` in codetaster's check_report module.
 * New fields can appear without a version bump; they are kept on the parsed objects.
 */

/** A note the AI attached to a line of the rated file version. Never posted to GitHub. */
export interface AnnotationReport {
	/** Which version of the file `line` is in. */
	readonly side: 'before' | 'after';
	/** Counting from 1. */
	readonly line: number;
	/** Markdown. */
	readonly text: string;
}

/** Lines in one version of a file, numbered as in a diff's `@@ -start,count +start,count @@` header. */
export interface LineSpanReport {
	/** The first line, counting from 1. With a count of 0, the line before the gap, or 0 at the top of the file. */
	readonly start: number;
	/** How many lines. 0 if the hunk has none in this version. */
	readonly count: number;
}

/** A run of changed lines and the AI's rating of it. */
export interface HunkReport {
	/** null, as is `after`, for a hunk for the whole change of a file without changed lines, e.g. a binary file. */
	readonly before: LineSpanReport | null;
	readonly after: LineSpanReport | null;
	readonly probability: number;
}

export interface RatingReport {
	/** The highest of the hunks' probabilities. */
	readonly probability: number;
	/** The category the file is grouped under in the file list. */
	readonly category: string;
	/** In order, as `git diff --unified=0` reports them. */
	readonly hunks: readonly HunkReport[];
	readonly annotations: readonly AnnotationReport[];
}

export interface FileReport {
	readonly path: string;
	readonly previous_path: string | null;
	readonly change_type: string;
	/** Without evidence from the reviewer: the matching path rule's probability, or [review] base_probability. */
	readonly base_probability: number;
	/** base_probability raised by the reviewer's evidence. The file is sampled if draw < sampling_probability. */
	readonly sampling_probability: number;
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

/** How the reviewer's evidence raised the probability files are sampled at. */
export interface SamplingReport {
	/** [review] base_probability, before any evidence. */
	readonly base_probability: number;
	readonly base_probability_weight: number;
	/** Sampled or needs-review files with a comment thread by the reviewer, as passed to the check. */
	readonly commented_files: number;
	/** Sampled or needs-review files the reviewer viewed without commenting, as passed to the check. */
	readonly viewed_files: number;
	/** The probability, from 0 to 1, files without a path rule are sampled at. base_probability without evidence. */
	readonly effective_probability: number;
}

export interface CheckReport {
	readonly schema_version: 6;
	readonly needs_review: boolean;
	readonly base: { readonly ref: string, readonly merge_base: string };
	readonly head: { readonly commit: string };
	/** The AI rating, from 0 to 1, at or above which a file is in needs-review. */
	readonly needs_review_threshold: number;
	readonly sampling: SamplingReport;
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

function isSampling(value: unknown): boolean {
	return isRecord(value)
		&& ['base_probability', 'base_probability_weight', 'commented_files', 'viewed_files', 'effective_probability']
			.every(key => typeof value[key] === 'number');
}

function isAnnotation(value: unknown): boolean {
	return isRecord(value)
		&& (value.side === 'before' || value.side === 'after')
		&& Number.isInteger(value.line) && (value.line as number) >= 1
		&& typeof value.text === 'string';
}

/** Whether `file` has no rating, or a rating whose annotations are well-formed. */
function hasValidAnnotations(file: Record<string, unknown>): boolean {
	const rating = file.rating;
	return !isRecord(rating) || (Array.isArray(rating.annotations) && rating.annotations.every(isAnnotation));
}

function isLineSpan(value: unknown): boolean {
	return isRecord(value)
		&& Number.isInteger(value.start) && (value.start as number) >= 0
		&& Number.isInteger(value.count) && (value.count as number) >= 0;
}

function isHunk(value: unknown): boolean {
	return isRecord(value)
		&& typeof value.probability === 'number'
		&& ((value.before === null && value.after === null) || (isLineSpan(value.before) && isLineSpan(value.after)));
}

/** Whether `file` has no rating, or a rating whose hunks are well-formed. */
function hasValidHunks(file: Record<string, unknown>): boolean {
	const rating = file.rating;
	return !isRecord(rating) || (Array.isArray(rating.hunks) && rating.hunks.every(isHunk));
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
	if (json.schema_version !== 6) {
		return invalidReport(`Its output has schema_version ${JSON.stringify(json.schema_version)}; this extension reads schema_version 6.`);
	}
	if (typeof json.needs_review_threshold !== 'number') {
		return invalidReport('Its output has no "needs_review_threshold".');
	}
	if (!isSampling(json.sampling)) {
		return invalidReport('Its output has no "sampling" with the base and effective probabilities and the evidence counts.');
	}
	if (!isRecord(json.head) || typeof json.head.commit !== 'string') {
		return invalidReport('Its output has no "head.commit".');
	}
	for (const key of FILE_LIST_KEYS) {
		const files = json[key];
		if (!Array.isArray(files) || !files.every(file => isRecord(file) && typeof file.path === 'string')) {
			return invalidReport(`Its output has no "${key}" list of files with paths.`);
		}
		if (!files.every(hasValidAnnotations)) {
			return invalidReport(`Its output has a file in "${key}" whose rating has malformed "annotations".`);
		}
		if (!files.every(hasValidHunks)) {
			return invalidReport(`Its output has a file in "${key}" whose rating has malformed "hunks". Update codetaster if it predates hunk ratings.`);
		}
	}
	if (json.overview !== undefined && json.overview !== null && !isOverview(json.overview)) {
		return invalidReport('Its output has an "overview" without a summary and described categories.');
	}
	return { kind: 'report', report: json as unknown as CheckReport };
}
