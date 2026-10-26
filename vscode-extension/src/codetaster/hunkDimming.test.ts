import * as assert from 'assert';
import { describe, it } from 'mocha';
import { AnnotatedFile } from './annotationThreads';
import { CheckReport, FileReport, HunkReport } from './checkReport';
import { dimmedLines, DimmedLines, DimmedLinesSet } from './hunkDimming';

const THRESHOLD = 0.6;

function fileReport(path: string, hunks: readonly HunkReport[]): FileReport {
	const probability = Math.max(...hunks.map(hunk => hunk.probability));
	return {
		path, previous_path: null, change_type: 'modified', base_probability: 0.1, sampling_probability: 0.1,
		rating: { probability, category: 'Logic', hunks, annotations: [] },
		unrated: false, draw: 0.5,
	};
}

function reportWith(lists: Partial<Pick<CheckReport, 'needs-review' | 'sampled' | 'no-review'>>): CheckReport {
	return {
		schema_version: 6,
		needs_review: true,
		base: { ref: 'main', merge_base: 'a'.repeat(40) },
		head: { commit: 'b'.repeat(40) },
		needs_review_threshold: THRESHOLD,
		sampling: { base_probability: 0.1, base_probability_weight: 10, commented_files: 0, viewed_files: 0, effective_probability: 0.1 },
		'needs-review': [],
		sampled: [],
		'no-review': [],
		...lists,
	};
}

function bothSides(path: string): AnnotatedFile<string> {
	return { path, beforeUri: `before:${path}`, afterUri: `after:${path}` };
}

const reviewed: HunkReport = { before: { start: 15, count: 1 }, after: { start: 15, count: 8 }, probability: 0.8 };

describe('dimmedLines', () => {
	it('dims a needs-review file\'s hunks rated below the threshold, on both sides, counting from 0', () => {
		const below: HunkReport = { before: { start: 4, count: 2 }, after: { start: 4, count: 1 }, probability: 0.1 };
		const report = reportWith({ 'needs-review': [fileReport('a.py', [below, reviewed])] });

		const lines = dimmedLines(report, [bothSides('a.py')]);

		assert.deepStrictEqual(lines, [
			{ uri: 'before:a.py', firstLine: 3, lastLine: 4 },
			{ uri: 'after:a.py', firstLine: 3, lastLine: 3 },
		]);
	});

	it('does not dim a hunk rated at the threshold', () => {
		const atThreshold: HunkReport = { ...reviewed, probability: THRESHOLD };
		const report = reportWith({ 'needs-review': [fileReport('a.py', [atThreshold])] });

		assert.deepStrictEqual(dimmedLines(report, [bothSides('a.py')]), []);
	});

	it('dims nothing on a side where the hunk has no lines', () => {
		const insertion: HunkReport = { before: { start: 3, count: 0 }, after: { start: 4, count: 2 }, probability: 0.1 };
		const report = reportWith({ 'needs-review': [fileReport('a.py', [insertion, reviewed])] });

		assert.deepStrictEqual(dimmedLines(report, [bothSides('a.py')]), [{ uri: 'after:a.py', firstLine: 3, lastLine: 4 }]);
	});

	it('dims nothing for a hunk for the whole change', () => {
		const wholeChange: HunkReport = { before: null, after: null, probability: 0.1 };
		const report = reportWith({ 'needs-review': [fileReport('a.py', [wholeChange, reviewed])] });

		assert.deepStrictEqual(dimmedLines(report, [bothSides('a.py')]), []);
	});

	it('dims nothing in sampled and no-review files', () => {
		const below: HunkReport = { ...reviewed, probability: 0.1 };
		const report = reportWith({ sampled: [fileReport('a.py', [below])], 'no-review': [fileReport('b.py', [below])] });

		assert.deepStrictEqual(dimmedLines(report, [bothSides('a.py'), bothSides('b.py')]), []);
	});

	it('skips a side the file does not have', () => {
		const below: HunkReport = { before: { start: 0, count: 0 }, after: { start: 1, count: 3 }, probability: 0.1 };
		const report = reportWith({ 'needs-review': [fileReport('added.py', [below, reviewed])] });

		const lines = dimmedLines(report, [{ path: 'added.py', beforeUri: undefined, afterUri: 'after:added.py' }]);

		assert.deepStrictEqual(lines, [{ uri: 'after:added.py', firstLine: 0, lastLine: 2 }]);
	});
});

describe('DimmedLinesSet', () => {
	const first: DimmedLines<string> = { uri: 'after:a.py', firstLine: 0, lastLine: 1 };
	const second: DimmedLines<string> = { uri: 'after:a.py', firstLine: 5, lastLine: 5 };

	function newSet(): { set: DimmedLinesSet<string, string>, changes: { count: number } } {
		const changes = { count: 0 };
		return { set: new DimmedLinesSet<string, string>((a, b) => a === b, () => changes.count++), changes };
	}

	it('merges the lines of every source showing the pull request', () => {
		const { set } = newSet();

		set.show('repo', 'pr-1', 'tree', [first]);
		set.show('repo', 'pr-1', 'list', [second]);

		assert.deepStrictEqual(set.linesByUri(uri => uri), new Map([['after:a.py', [first, second]]]));
	});

	it('drops the lines of another pull request of the same owner', () => {
		const { set } = newSet();

		set.show('repo', 'pr-1', 'tree', [first]);
		set.show('repo', 'pr-2', 'tree', [second]);

		assert.deepStrictEqual(set.linesByUri(uri => uri), new Map([['after:a.py', [second]]]));
	});

	it('keeps the lines of the checked-out pull request on clearUnlessFor', () => {
		const { set } = newSet();
		set.show('repo', 'pr-1', 'tree', [first]);

		set.clearUnlessFor('repo', 'pr-1');

		assert.deepStrictEqual(set.linesByUri(uri => uri), new Map([['after:a.py', [first]]]));
	});

	it('removes the lines of a pull request that is no longer checked out', () => {
		const { set } = newSet();
		set.show('repo', 'pr-1', 'tree', [first]);

		set.clearUnlessFor('repo', undefined);

		assert.deepStrictEqual(set.linesByUri(uri => uri), new Map());
	});

	it('reports a change when lines are shown or cleared, not when there was nothing to clear', () => {
		const { set, changes } = newSet();

		set.show('repo', 'pr-1', 'tree', [first]);
		set.clear('repo');
		set.clear('repo');

		const expectedChanges = 2;
		assert.strictEqual(changes.count, expectedChanges);
	});
});
