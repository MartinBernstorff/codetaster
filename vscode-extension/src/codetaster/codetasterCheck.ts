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

/** Runs `codetaster check <checkout> --base <base> --format json` and parses its report. */
export async function runCodetasterCheck(process: CodetasterProcess, executable: string, checkout: string, base: string): Promise<CheckOutcome> {
	const outcome = await process.runCodetaster(executable, ['check', checkout, '--base', base, '--format', 'json'], checkout);
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
}

/**
 * The check results the PR file views group by. Only a checked-out PR is checked.
 * A check re-runs only when the checkout, base or PR's file list changes, or on refresh,
 * so tree refreshes (viewed state, comments) don't each start a process.
 */
export class CodetasterChecks {
	private readonly checks = new Map<string, Promise<CheckOutcome>>();
	private readonly refreshListeners = new Set<() => void>();

	constructor(
		private readonly process: CodetasterProcess,
		private readonly executable: () => string,
	) { }

	/** The PR's check, or undefined if the PR is not checked out. */
	checkFor(target: CheckTarget): Promise<CheckOutcome> | undefined {
		const { checkout, base, fileListKey } = target;
		if (checkout === undefined) {
			return undefined;
		}
		const cacheKey = JSON.stringify([checkout, base, fileListKey]);
		let check = this.checks.get(cacheKey);
		if (!check) {
			check = runCodetasterCheck(this.process, this.executable(), checkout, base);
			this.checks.set(cacheKey, check);
		}
		return check;
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
