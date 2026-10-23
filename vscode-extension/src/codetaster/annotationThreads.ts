import { CheckReport } from './checkReport';
import { fileReportsByPath } from './fileRatings';

/**
 * A PR file and the documents its diff shows, as URIs of type `Uri`. A side is
 * undefined if the file has no such version: no before for an added file, no after
 * for a deleted one.
 */
export interface AnnotatedFile<Uri> {
	readonly path: string;
	readonly beforeUri: Uri | undefined;
	readonly afterUri: Uri | undefined;
}

/** Where to show an annotation as a comment thread. */
export interface AnnotationPlacement<Uri> {
	readonly uri: Uri;
	/** Counting from 0, as editors do. */
	readonly line: number;
	/** Markdown. */
	readonly text: string;
}

/**
 * The annotations of each file's rating, placed on the document of their side.
 * An unrated file, whose rating is for another version, has none. Annotations on a
 * side the file does not have, or on files `files` leaves out, are skipped.
 */
export function annotationPlacements<Uri>(report: CheckReport, files: readonly AnnotatedFile<Uri>[]): AnnotationPlacement<Uri>[] {
	const reports = fileReportsByPath(report);
	return files.flatMap(file => (reports.get(file.path)?.rating?.annotations ?? []).flatMap(annotation => {
		const uri = annotation.side === 'before' ? file.beforeUri : file.afterUri;
		return uri === undefined ? [] : [{ uri, line: annotation.line - 1, text: annotation.text }];
	}));
}

/** Identifies a placement, so a thread already showing it is not recreated. */
export function placementKey<Uri>({ uri, line, text }: AnnotationPlacement<Uri>, uriKey: (uri: Uri) => string): string {
	return JSON.stringify([uriKey(uri), line, text]);
}

/** The threads to create and remove so that exactly `wanted` show, each once. */
export interface PlacementChanges<Uri> {
	readonly added: readonly AnnotationPlacement<Uri>[];
	/** The keys of the shown threads to remove. */
	readonly removed: readonly string[];
}

/**
 * How to go from the threads `shownKeys` identify to one thread per distinct placement
 * in `wanted`, leaving threads that stay as they are, e.g. collapsed by the user.
 */
export function placementChanges<Uri>(
	shownKeys: ReadonlySet<string>,
	wanted: readonly AnnotationPlacement<Uri>[],
	uriKey: (uri: Uri) => string,
): PlacementChanges<Uri> {
	const wantedByKey = new Map(wanted.map(placement => [placementKey(placement, uriKey), placement]));
	return {
		added: [...wantedByKey].filter(([key]) => !shownKeys.has(key)).map(([, placement]) => placement),
		removed: [...shownKeys].filter(key => !wantedByKey.has(key)),
	};
}

interface OwnerThreads<PullRequest, Uri, Thread> {
	readonly pullRequest: PullRequest;
	/** The placements each file list showing the pull request asked for. */
	readonly sources: Map<unknown, readonly AnnotationPlacement<Uri>[]>;
	/** By `placementKey`. */
	readonly threads: Map<string, Thread>;
}

/**
 * The annotation threads of each owner's checked-out pull request, e.g. per repository.
 * Several file lists (sources) can show the same pull request, each with the URIs of
 * the diffs it opens; their placements are merged. A thread is only created for a
 * placement no thread shows yet and removed when no source wants it any more, so a
 * thread the user collapsed stays collapsed across refreshes.
 */
export class AnnotationThreadSet<PullRequest, Uri, Thread extends { dispose(): void }> {
	private readonly owners = new Map<unknown, OwnerThreads<PullRequest, Uri, Thread>>();

	constructor(
		private readonly createThread: (placement: AnnotationPlacement<Uri>) => Thread,
		private readonly uriKey: (uri: Uri) => string,
		private readonly samePullRequest: (a: PullRequest, b: PullRequest | undefined) => boolean,
	) { }

	/** Shows `source`'s `placements` for `pullRequest`. Threads of another pull request of `owner` are removed first. */
	show(owner: unknown, pullRequest: PullRequest, source: unknown, placements: readonly AnnotationPlacement<Uri>[]): void {
		let shown = this.owners.get(owner);
		if (shown && !this.samePullRequest(shown.pullRequest, pullRequest)) {
			this.clear(owner);
			shown = undefined;
		}
		if (!shown) {
			shown = { pullRequest, sources: new Map(), threads: new Map() };
			this.owners.set(owner, shown);
		}
		shown.sources.set(source, placements);
		const changes = placementChanges(new Set(shown.threads.keys()), [...shown.sources.values()].flat(), this.uriKey);
		for (const key of changes.removed) {
			shown.threads.get(key)?.dispose();
			shown.threads.delete(key);
		}
		for (const placement of changes.added) {
			shown.threads.set(placementKey(placement, this.uriKey), this.createThread(placement));
		}
	}

	/** Removes `owner`'s threads unless they are for `checkedOut`, the pull request it has checked out, if any. */
	clearUnlessFor(owner: unknown, checkedOut: PullRequest | undefined): void {
		const shown = this.owners.get(owner);
		if (shown && !this.samePullRequest(shown.pullRequest, checkedOut)) {
			this.clear(owner);
		}
	}

	clear(owner: unknown): void {
		this.owners.get(owner)?.threads.forEach(thread => thread.dispose());
		this.owners.delete(owner);
	}

	dispose(): void {
		[...this.owners.keys()].forEach(owner => this.clear(owner));
	}
}
