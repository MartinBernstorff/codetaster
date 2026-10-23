import { CheckReport, SamplingReport } from './checkReport';

/**
 * What the signed-in reviewer found in the files codetaster asked them to review,
 * passed to `codetaster check` to raise the probability of sampling the rest.
 */
export interface SamplingEvidence {
	/** Reviewable files with at least one comment thread by the reviewer, draft or submitted. */
	readonly commentedFiles: number;
	/** Reviewable files the reviewer marked viewed, without a thread by them. */
	readonly viewedFiles: number;
}

export const NO_EVIDENCE: SamplingEvidence = { commentedFiles: 0, viewedFiles: 0 };

/** A review thread's file, and who started it. */
export interface ReviewThreadAuthorship {
	readonly path: string;
	/** undefined if GitHub did not say, e.g. for a deleted account. */
	readonly authorLogin: string | undefined;
}

/** The files the reviewer is asked to look at: those in needs-review or sampled. */
export function reviewablePaths(report: CheckReport): string[] {
	return [...report['needs-review'], ...report.sampled].map(file => file.path);
}

/**
 * Counts each reviewable file once: as commented if it has a thread by the viewer
 * (resolved or not), else as viewed if the viewer marked it viewed.
 */
export function countSamplingEvidence(input: {
	readonly reviewablePaths: Iterable<string>,
	readonly threads: readonly ReviewThreadAuthorship[],
	readonly viewedPaths: ReadonlySet<string>,
	readonly viewerLogin: string,
}): SamplingEvidence {
	const commentedPaths = new Set(input.threads.filter(thread => thread.authorLogin === input.viewerLogin).map(thread => thread.path));
	let commentedFiles = 0;
	let viewedFiles = 0;
	for (const path of new Set(input.reviewablePaths)) {
		if (commentedPaths.has(path)) {
			commentedFiles++;
		} else if (input.viewedPaths.has(path)) {
			viewedFiles++;
		}
	}
	return { commentedFiles, viewedFiles };
}

/**
 * Every file that was reviewable in any report for a pull request this session.
 * Evidence counts over these, not just the latest report's: a viewed file sampled only
 * because of the evidence would otherwise lower the probability that sampled it, drop
 * out, raise it again, and flip back and forth.
 */
export class ReviewablePathsSeen<PullRequest extends object> {
	private readonly seen = new WeakMap<PullRequest, Set<string>>();

	/** Adds `paths` to those seen for `pullRequest`, and returns them all. */
	record(pullRequest: PullRequest, paths: Iterable<string>): ReadonlySet<string> {
		let seen = this.seen.get(pullRequest);
		if (!seen) {
			seen = new Set();
			this.seen.set(pullRequest, seen);
		}
		for (const path of paths) {
			seen.add(path);
		}
		return seen;
	}
}

/** A probability as a percentage with two significant digits, e.g. 10%, 18%, 0.5%. */
function formatPercentage(probability: number): string {
	return `${Number((probability * 100).toPrecision(2))}%`;
}

/** The file list's description of the sampling probability, e.g. `Sampling 10% → 18% (1 commented, 5 viewed)`. */
export function samplingDescription(sampling: SamplingReport): string {
	const base = `Sampling ${formatPercentage(sampling.base_probability)}`;
	if (sampling.commented_files === 0 && sampling.viewed_files === 0) {
		return base;
	}
	return `${base} → ${formatPercentage(sampling.effective_probability)} (${sampling.commented_files} commented, ${sampling.viewed_files} viewed)`;
}
