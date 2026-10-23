import { CheckReport, parseCheckReport } from './checkReport';
import { NO_EVIDENCE, SamplingEvidence } from './samplingEvidence';

/** Runs the codetaster executable. Faked in tests. */
export interface CodetasterProcess {
	runCodetaster(executable: string, args: readonly string[], cwd: string): Promise<ProcessOutcome>;
}

export type ProcessOutcome =
	| { readonly kind: 'exited', readonly exitCode: number, readonly stdout: string, readonly stderr: string }
	| { readonly kind: 'failedToStart', readonly message: string };

export type CheckOutcome =
	| { readonly kind: 'report', readonly report: CheckReport }
	| { readonly kind: 'error', readonly message: string };

function checkError(message: string): CheckOutcome {
	return { kind: 'error', message };
}

/**
 * Runs `codetaster check <checkout> --base <base> --format json` and parses its report.
 * `needsReviewThreshold` is passed as `--needs-review-threshold` if given, and
 * `evidence` as `--commented-files` and `--viewed-files` unless it is empty.
 */
export async function runCodetasterCheck(
	process: CodetasterProcess,
	executable: string,
	checkout: string,
	base: string,
	needsReviewThreshold?: number,
	evidence: SamplingEvidence = NO_EVIDENCE,
): Promise<CheckOutcome> {
	const thresholdArgs = needsReviewThreshold === undefined ? [] : ['--needs-review-threshold', String(needsReviewThreshold)];
	const evidenceArgs = evidence.commentedFiles === 0 && evidence.viewedFiles === 0
		? []
		: ['--commented-files', String(evidence.commentedFiles), '--viewed-files', String(evidence.viewedFiles)];
	const outcome = await process.runCodetaster(executable, ['check', checkout, '--base', base, ...thresholdArgs, ...evidenceArgs, '--format', 'json'], checkout);
	if (outcome.kind === 'failedToStart') {
		return checkError(`Could not run "${executable}" (${outcome.message}). Install codetaster on your PATH or set codetaster.executablePath.`);
	}
	if (outcome.exitCode !== 0) {
		const stderr = outcome.stderr.trim();
		return checkError(`codetaster check exited with code ${outcome.exitCode}${stderr ? `: ${stderr}` : '.'}`);
	}
	const parsed = parseCheckReport(outcome.stdout);
	if (parsed.kind === 'invalid') {
		return checkError(`codetaster check gave an unexpected result. ${parsed.message}`);
	}
	return parsed;
}

export interface Listener {
	dispose(): void;
}

/** A PR whose files a view shows. */
export interface CheckTarget {
	/** The local checkout the PR is checked out in, or undefined if it is not checked out. */
	readonly checkout: string | undefined;
	/** The PR's base branch, as a revision in the checkout. */
	readonly base: string;
	/** Identifies the PR's head and file list; the check re-runs when it changes. */
	readonly fileListKey: string;
	/** The checkout's HEAD commit; the check re-runs when it changes, e.g. after a local commit. */
	readonly localHead: string | undefined;
	/** Replaces the project config's `[review] needs_review_threshold`, if given. */
	readonly needsReviewThreshold: number | undefined;
	/** What the reviewer found so far, which raises the sampling probability. */
	readonly evidence: SamplingEvidence;
}

/** A check that has not finished yet, or its outcome. */
export type CheckState =
	| {
		readonly kind: 'running',
		readonly finished: Promise<CheckOutcome>,
		/** The last report for the same PR at another local HEAD, or before a refresh, to show until the check finishes. */
		readonly previousReport: CheckReport | undefined,
	}
	| CheckOutcome;

interface CachedCheck {
	readonly finished: Promise<CheckOutcome>;
	outcome?: CheckOutcome;
	/** Whether the check failed and the failure has been returned, so the next request re-runs it. */
	errorReturned: boolean;
}

/**
 * The check results the PR file views group by. Only a checked-out PR is checked.
 * A check re-runs only when the checkout, its HEAD commit, the base, the needs-review
 * threshold, the PR's file list or the reviewer's evidence changes, after it failed, or on
 * refresh, so tree refreshes that change none of these don't each start a process.
 */
export class CodetasterChecks {
	private readonly checks = new Map<string, CachedCheck>();
	private readonly lastReports = new Map<string, CheckReport>();
	private readonly refreshListeners = new Set<() => void>();

	constructor(
		private readonly process: CodetasterProcess,
		private readonly executable: () => string,
	) { }

	/**
	 * The PR's check, starting it if needed, or undefined if the PR is not checked out.
	 * A failed check is returned once after it finishes, and re-run on the next request.
	 */
	requestCheck(target: CheckTarget): CheckState | undefined {
		const { checkout, base, localHead, needsReviewThreshold, evidence } = target;
		if (checkout === undefined) {
			return undefined;
		}
		const pullRequestKey = this.pullRequestKey(target);
		const cacheKey = JSON.stringify([pullRequestKey, localHead ?? null, evidence.commentedFiles, evidence.viewedFiles]);
		let check = this.checks.get(cacheKey);
		if (!check || check.errorReturned) {
			const started: CachedCheck = {
				finished: runCodetasterCheck(this.process, this.executable(), checkout, base, needsReviewThreshold, evidence).then(outcome => {
					started.outcome = outcome;
					if (outcome.kind === 'report') {
						this.lastReports.set(pullRequestKey, outcome.report);
					}
					return outcome;
				}),
				errorReturned: false,
			};
			check = started;
			this.checks.set(cacheKey, started);
		}
		if (!check.outcome) {
			return { kind: 'running', finished: check.finished, previousReport: this.lastReports.get(pullRequestKey) };
		}
		check.errorReturned = check.outcome.kind === 'error';
		return check.outcome;
	}

	/** The report of the PR's check that finished last, at any local HEAD or evidence. */
	latestReport(target: CheckTarget): CheckReport | undefined {
		return this.lastReports.get(this.pullRequestKey(target));
	}

	private pullRequestKey({ checkout, base, fileListKey, needsReviewThreshold }: CheckTarget): string {
		return JSON.stringify([checkout ?? null, base, fileListKey, needsReviewThreshold ?? null]);
	}

	refresh(): void {
		this.checks.clear();
		this.refreshListeners.forEach(listener => listener());
	}

	onDidRefresh(listener: () => void): Listener {
		this.refreshListeners.add(listener);
		return { dispose: () => { this.refreshListeners.delete(listener); } };
	}
}
