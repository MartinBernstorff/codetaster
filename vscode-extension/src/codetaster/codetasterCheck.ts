import { CheckReport, parseCheckReport } from './checkReport';

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
 * `topRatedPercentage` is passed as `--top-rated-percentage` if given.
 */
export async function runCodetasterCheck(
	process: CodetasterProcess,
	executable: string,
	checkout: string,
	base: string,
	topRatedPercentage?: number,
): Promise<CheckOutcome> {
	const topRatedArgs = topRatedPercentage === undefined ? [] : ['--top-rated-percentage', String(topRatedPercentage)];
	const outcome = await process.runCodetaster(executable, ['check', checkout, '--base', base, ...topRatedArgs, '--format', 'json'], checkout);
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
	/** Overrides the project config's `[review] top_rated_percentage`, if given. */
	readonly topRatedPercentage: number | undefined;
}

/** A check that has not finished yet, or its outcome. */
export type CheckState =
	| { readonly kind: 'running', readonly finished: Promise<CheckOutcome> }
	| CheckOutcome;

interface CachedCheck {
	readonly finished: Promise<CheckOutcome>;
	outcome?: CheckOutcome;
	/** Whether the check failed and the failure has been returned, so the next request re-runs it. */
	errorReturned: boolean;
}

/**
 * The check results the PR file views group by. Only a checked-out PR is checked.
 * A check re-runs only when the checkout, its HEAD commit, the base, the top-rated
 * percentage or the PR's file list changes, after it failed, or on refresh, so tree refreshes (viewed state, comments)
 * don't each start a process.
 */
export class CodetasterChecks {
	private readonly checks = new Map<string, CachedCheck>();
	private readonly refreshListeners = new Set<() => void>();

	constructor(
		private readonly process: CodetasterProcess,
		private readonly executable: () => string,
	) { }

	/**
	 * The PR's check, or undefined if the PR is not checked out. A failed check is
	 * returned once after it finishes, and re-run on the next request.
	 */
	checkFor(target: CheckTarget): CheckState | undefined {
		const { checkout, base, fileListKey, localHead, topRatedPercentage } = target;
		if (checkout === undefined) {
			return undefined;
		}
		const cacheKey = JSON.stringify([checkout, base, fileListKey, localHead ?? null, topRatedPercentage ?? null]);
		let check = this.checks.get(cacheKey);
		if (!check || check.errorReturned) {
			const started: CachedCheck = {
				finished: runCodetasterCheck(this.process, this.executable(), checkout, base, topRatedPercentage).then(outcome => {
					started.outcome = outcome;
					return outcome;
				}),
				errorReturned: false,
			};
			check = started;
			this.checks.set(cacheKey, started);
		}
		if (!check.outcome) {
			return { kind: 'running', finished: check.finished };
		}
		check.errorReturned = check.outcome.kind === 'error';
		return check.outcome;
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
