import { AnnotatedFile } from './annotationThreads';
import { CheckReport, LineSpanReport } from './checkReport';

/** Lines of a document to dim, counting from 0 as editors do. */
export interface DimmedLines<Uri> {
	readonly uri: Uri;
	readonly firstLine: number;
	/** Inclusive. */
	readonly lastLine: number;
}

function linesOf<Uri>(uri: Uri | undefined, span: LineSpanReport | null): DimmedLines<Uri>[] {
	return uri === undefined || span === null || span.count === 0
		? []
		: [{ uri, firstLine: span.start - 1, lastLine: span.start + span.count - 2 }];
}

/**
 * The lines to dim in the diffs of `files`: in each needs-review file, the hunks rated
 * below the report's needs-review threshold, on the before document for their before
 * lines and the after document for their after lines. Sampled and no-review files are
 * not dimmed, nor are hunks for a whole change without changed lines.
 */
export function dimmedLines<Uri>(report: CheckReport, files: readonly AnnotatedFile<Uri>[]): DimmedLines<Uri>[] {
	const needsReview = new Map(report['needs-review'].map(file => [file.path, file]));
	return files.flatMap(file => (needsReview.get(file.path)?.rating?.hunks ?? [])
		.filter(hunk => hunk.probability < report.needs_review_threshold)
		.flatMap(hunk => [...linesOf(file.beforeUri, hunk.before), ...linesOf(file.afterUri, hunk.after)]));
}

interface OwnerLines<PullRequest, Uri> {
	readonly pullRequest: PullRequest;
	/** The lines each file list showing the pull request asked for. */
	readonly sources: Map<unknown, readonly DimmedLines<Uri>[]>;
}

/**
 * The dimmed lines of each owner's checked-out pull request, e.g. per repository,
 * merged from every file list (source) that shows it, as `AnnotationThreadSet` does for
 * annotations. `onDidChange` is called after every change, to re-apply the lines.
 */
export class DimmedLinesSet<PullRequest, Uri> {
	private readonly owners = new Map<unknown, OwnerLines<PullRequest, Uri>>();

	constructor(
		private readonly samePullRequest: (a: PullRequest, b: PullRequest | undefined) => boolean,
		private readonly onDidChange: () => void,
	) { }

	/** Shows `source`'s `lines` for `pullRequest`. Lines of another pull request of `owner` are removed. */
	show(owner: unknown, pullRequest: PullRequest, source: unknown, lines: readonly DimmedLines<Uri>[]): void {
		let shown = this.owners.get(owner);
		if (!shown || !this.samePullRequest(shown.pullRequest, pullRequest)) {
			shown = { pullRequest, sources: new Map() };
			this.owners.set(owner, shown);
		}
		shown.sources.set(source, lines);
		this.onDidChange();
	}

	/** Removes `owner`'s lines unless they are for `checkedOut`, the pull request it has checked out, if any. */
	clearUnlessFor(owner: unknown, checkedOut: PullRequest | undefined): void {
		const shown = this.owners.get(owner);
		if (shown && !this.samePullRequest(shown.pullRequest, checkedOut)) {
			this.clear(owner);
		}
	}

	clear(owner: unknown): void {
		if (this.owners.delete(owner)) {
			this.onDidChange();
		}
	}

	/** Every shown line range, by `uriKey` of its document. */
	linesByUri(uriKey: (uri: Uri) => string): Map<string, DimmedLines<Uri>[]> {
		const byUri = new Map<string, DimmedLines<Uri>[]>();
		for (const lines of [...this.owners.values()].flatMap(owner => [...owner.sources.values()].flat())) {
			const key = uriKey(lines.uri);
			byUri.set(key, [...(byUri.get(key) ?? []), lines]);
		}
		return byUri;
	}
}
