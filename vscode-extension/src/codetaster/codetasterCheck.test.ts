import * as assert from 'assert';
import { describe, it } from 'mocha';
import { CheckOutcome, CheckTarget, CodetasterChecks, CodetasterProcess, ProcessOutcome, runCodetasterCheck } from './codetasterCheck';

const validReport = {
	schema_version: 3,
	needs_review: true,
	override_label_applied: false,
	base: { ref: 'main', merge_base: 'a'.repeat(40) },
	head: { commit: 'b'.repeat(40) },
	top_rated_percentage: 20,
	'needs-review': [],
	sampled: [{ path: 'a.py', previous_path: null, change_type: 'added', base_probability: 0.1, rating: null, unrated: true, draw: 0.05, from_a_later_schema: true }],
	'no-review': [],
};

class FakeCodetasterProcess implements CodetasterProcess {
	readonly calls: { executable: string, args: readonly string[], cwd: string }[] = [];

	constructor(private readonly outcome: ProcessOutcome) { }

	async runCodetaster(executable: string, args: readonly string[], cwd: string): Promise<ProcessOutcome> {
		this.calls.push({ executable, args, cwd });
		return this.outcome;
	}
}

function exitedWith(exitCode: number, stdout: string, stderr = ''): ProcessOutcome {
	return { kind: 'exited', exitCode, stdout, stderr };
}

function successfulProcess(): FakeCodetasterProcess {
	return new FakeCodetasterProcess(exitedWith(0, JSON.stringify(validReport)));
}

async function errorMessageFrom(process: FakeCodetasterProcess): Promise<string> {
	const outcome = await runCodetasterCheck(process, 'codetaster', '/repo', 'origin/main');
	assert.strictEqual(outcome.kind, 'error');
	return outcome.kind === 'error' ? outcome.message : '';
}

describe('runCodetasterCheck', () => {
	it('runs the configured executable on the checkout against the given base, with JSON output', async () => {
		const process = successfulProcess();

		await runCodetasterCheck(process, '/opt/bin/codetaster', '/repo', 'origin/release');

		assert.deepStrictEqual(process.calls, [{ executable: '/opt/bin/codetaster', args: ['check', '/repo', '--base', 'origin/release', '--format', 'json'], cwd: '/repo' }]);
	});

	it('passes a top-rated percentage override on', async () => {
		const process = successfulProcess();

		await runCodetasterCheck(process, 'codetaster', '/repo', 'origin/main', 35);

		assert.deepStrictEqual(process.calls.map(call => call.args), [['check', '/repo', '--base', 'origin/main', '--top-rated-percentage', '35', '--format', 'json']]);
	});

	it('returns the parsed report, keeping fields it does not know', async () => {
		const outcome = await runCodetasterCheck(successfulProcess(), 'codetaster', '/repo', 'origin/main');

		assert.strictEqual(outcome.kind, 'report');
		if (outcome.kind === 'report') {
			assert.strictEqual(outcome.report.head.commit, 'b'.repeat(40));
			assert.deepStrictEqual(outcome.report.sampled, validReport.sampled);
		}
	});

	it('reports a missing executable', async () => {
		const message = await errorMessageFrom(new FakeCodetasterProcess({ kind: 'failedToStart', message: 'spawn codetaster ENOENT' }));

		assert.match(message, /codetaster\.executablePath/);
		assert.match(message, /ENOENT/);
	});

	it('reports a non-zero exit with its stderr, e.g. a missing [review] config', async () => {
		const message = await errorMessageFrom(new FakeCodetasterProcess(exitedWith(1, '', 'Error: no [review] section\n')));

		assert.match(message, /exited with code 1/);
		assert.match(message, /no \[review\] section/);
	});

	it('rejects output that is not JSON', async () => {
		const message = await errorMessageFrom(new FakeCodetasterProcess(exitedWith(0, 'not json')));

		assert.match(message, /not valid JSON/);
	});

	it('rejects other schema versions', async () => {
		const message = await errorMessageFrom(new FakeCodetasterProcess(exitedWith(0, JSON.stringify({ ...validReport, schema_version: 1 }))));

		assert.match(message, /schema_version 1/);
	});

	it('rejects a report without the three file lists', async () => {
		const { sampled: _sampled, ...withoutSampled } = validReport;

		const message = await errorMessageFrom(new FakeCodetasterProcess(exitedWith(0, JSON.stringify(withoutSampled))));

		assert.match(message, /"sampled"/);
	});
});

function checkedOutPullRequest(target: Partial<CheckTarget> = {}): CheckTarget {
	return { checkout: '/repo', base: 'origin/main', fileListKey: 'a.py', localHead: 'c'.repeat(40), topRatedPercentage: undefined, ...target };
}

/** The check's outcome, waiting for it if it is still running. */
async function finishedCheck(checks: CodetasterChecks, target: CheckTarget): Promise<CheckOutcome | undefined> {
	const state = checks.checkFor(target);
	if (state?.kind !== 'running') {
		return state;
	}
	await state.finished;
	const finished = checks.checkFor(target);
	assert.notStrictEqual(finished?.kind, 'running');
	return finished as CheckOutcome | undefined;
}

describe('CodetasterChecks', () => {
	it('reports a check as running until it finishes', async () => {
		const checks = new CodetasterChecks(successfulProcess(), () => 'codetaster');

		const running = checks.checkFor(checkedOutPullRequest());
		assert.strictEqual(running?.kind, 'running');
		await (running?.kind === 'running' ? running.finished : undefined);

		assert.strictEqual(checks.checkFor(checkedOutPullRequest())?.kind, 'report');
	});

	it('returns a failed check once it finishes, then re-runs it on the next request', async () => {
		const process = new FakeCodetasterProcess(exitedWith(1, '', 'Error: something went wrong\n'));
		const checks = new CodetasterChecks(process, () => 'codetaster');

		const running = checks.checkFor(checkedOutPullRequest());
		await (running?.kind === 'running' ? running.finished : undefined);

		assert.strictEqual(checks.checkFor(checkedOutPullRequest())?.kind, 'error');
		assert.strictEqual(process.calls.length, 1);
		assert.strictEqual(checks.checkFor(checkedOutPullRequest())?.kind, 'running');
		assert.strictEqual(process.calls.length, 2);
	});

	it('checks a checked-out PR against its own base', async () => {
		const process = successfulProcess();
		const checks = new CodetasterChecks(process, () => 'codetaster');

		const outcome = await finishedCheck(checks, checkedOutPullRequest({ base: 'origin/release' }));

		assert.strictEqual(outcome?.kind, 'report');
		assert.deepStrictEqual(process.calls.map(call => call.args), [['check', '/repo', '--base', 'origin/release', '--format', 'json']]);
	});

	it('does not run for a PR that is not checked out', async () => {
		const process = successfulProcess();
		const checks = new CodetasterChecks(process, () => 'codetaster');

		const outcome = await finishedCheck(checks, checkedOutPullRequest({ checkout: undefined }));

		assert.strictEqual(outcome, undefined);
		assert.strictEqual(process.calls.length, 0);
	});

	it('re-runs the check when the PR base changes', async () => {
		const process = successfulProcess();
		const checks = new CodetasterChecks(process, () => 'codetaster');

		await finishedCheck(checks, checkedOutPullRequest({ base: 'origin/main' }));
		await finishedCheck(checks, checkedOutPullRequest({ base: 'origin/release' }));

		assert.strictEqual(process.calls.length, 2);
	});

	it('reuses the check while the checkout, base and PR file list are unchanged', async () => {
		const process = successfulProcess();
		const checks = new CodetasterChecks(process, () => 'codetaster');

		await finishedCheck(checks, checkedOutPullRequest());
		await finishedCheck(checks, checkedOutPullRequest());

		assert.strictEqual(process.calls.length, 1);
	});

	it('re-runs the check when the PR file list changes', async () => {
		const process = successfulProcess();
		const checks = new CodetasterChecks(process, () => 'codetaster');

		await finishedCheck(checks, checkedOutPullRequest());
		await finishedCheck(checks, checkedOutPullRequest({ fileListKey: 'a.py,b.py' }));

		assert.strictEqual(process.calls.length, 2);
	});

	it('re-runs the check when the local HEAD commit changes, e.g. after a local commit', async () => {
		const process = successfulProcess();
		const checks = new CodetasterChecks(process, () => 'codetaster');

		await finishedCheck(checks, checkedOutPullRequest({ localHead: 'c'.repeat(40) }));
		await finishedCheck(checks, checkedOutPullRequest({ localHead: 'd'.repeat(40) }));

		assert.strictEqual(process.calls.length, 2);
	});

	it('re-runs the check when the top-rated percentage changes', async () => {
		const process = successfulProcess();
		const checks = new CodetasterChecks(process, () => 'codetaster');

		await finishedCheck(checks, checkedOutPullRequest({ topRatedPercentage: undefined }));
		await finishedCheck(checks, checkedOutPullRequest({ topRatedPercentage: 50 }));

		assert.strictEqual(process.calls.length, 2);
	});

	it('re-runs a check that failed, rather than reusing the error', async () => {
		const process = new FakeCodetasterProcess(exitedWith(1, '', 'Error: something went wrong\n'));
		const checks = new CodetasterChecks(process, () => 'codetaster');

		const first = await finishedCheck(checks, checkedOutPullRequest());
		await finishedCheck(checks, checkedOutPullRequest());

		assert.strictEqual(first?.kind, 'error');
		assert.strictEqual(process.calls.length, 2);
	});

	it('re-runs the check after a refresh, and tells listeners', async () => {
		const process = successfulProcess();
		const checks = new CodetasterChecks(process, () => 'codetaster');
		let refreshes = 0;
		checks.onDidRefresh(() => refreshes++);

		await finishedCheck(checks, checkedOutPullRequest());
		checks.refresh();
		await finishedCheck(checks, checkedOutPullRequest());

		assert.strictEqual(process.calls.length, 2);
		assert.strictEqual(refreshes, 1);
	});

	it('stops telling a listener once it is disposed', () => {
		const checks = new CodetasterChecks(successfulProcess(), () => 'codetaster');
		let refreshes = 0;
		const listener = checks.onDidRefresh(() => refreshes++);

		listener.dispose();
		checks.refresh();

		assert.strictEqual(refreshes, 0);
	});
});
