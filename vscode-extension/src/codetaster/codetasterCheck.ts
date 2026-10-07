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

/** Runs `codetaster check <checkout> --format json` and parses its report. */
export async function runCodetasterCheck(process: CodetasterProcess, executable: string, checkout: string): Promise<CheckOutcome> {
	const outcome = await process.runCodetaster(executable, ['check', checkout, '--format', 'json'], checkout);
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

/**
 * The check results the PR file views group by. A check re-runs only when the checkout
 * or the PR's file list changes, or on refresh, so tree refreshes (viewed state,
 * comments) don't each start a process.
 */
export class CodetasterChecks {
	private readonly checks = new Map<string, Promise<CheckOutcome>>();
	private readonly refreshListeners = new Set<() => void>();

	constructor(
		private readonly process: CodetasterProcess,
		private readonly executable: () => string,
	) { }

	checkFor(checkout: string, fileListKey: string): Promise<CheckOutcome> {
		const cacheKey = JSON.stringify([checkout, fileListKey]);
		let check = this.checks.get(cacheKey);
		if (!check) {
			check = runCodetasterCheck(this.process, this.executable(), checkout);
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
