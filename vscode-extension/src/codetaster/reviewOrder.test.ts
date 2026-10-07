import * as assert from 'assert';
import { describe, it } from 'mocha';
import { nextFileToReview, OrderedFile, reviewOrder } from './reviewOrder';
import { GroupVerdict, VerdictGroup } from './verdictGroups';

function group(verdict: GroupVerdict, ...files: string[]): VerdictGroup<string> {
	return { verdict, label: verdict, files, collapsed: false };
}

function ordered(...entries: [string, GroupVerdict][]): OrderedFile<string>[] {
	return entries.map(([path, verdict]) => ({ file: path, path, verdict }));
}

function viewedAmong(...viewed: string[]): (file: string) => boolean {
	return file => viewed.includes(file);
}

describe('reviewOrder', () => {
	it('lists files group by group, sorted by path within each group', () => {
		const groups = [group('needs-review', 'b.py', 'a.py'), group('sampled', 'c.py')];

		const order = reviewOrder(groups, file => file, 'flat');

		assert.deepStrictEqual(order.map(entry => [entry.path, entry.verdict]), [['a.py', 'needs-review'], ['b.py', 'needs-review'], ['c.py', 'sampled']]);
	});

	it('puts directories before files in tree layout', () => {
		const groups = [group('needs-review', 'z.py', 'src/b.py', 'src/lib/a.py')];

		const order = reviewOrder(groups, file => file, 'tree');

		assert.deepStrictEqual(order.map(entry => entry.path), ['src/lib/a.py', 'src/b.py', 'z.py']);
	});
});

describe('nextFileToReview', () => {
	it('picks the next unviewed file after the current one', () => {
		const files = ordered(['a.py', 'needs-review'], ['b.py', 'needs-review'], ['c.py', 'sampled']);

		assert.strictEqual(nextFileToReview(files, 'a.py', viewedAmong('a.py', 'b.py')), 'c.py');
	});

	it('wraps around to unviewed files before the current one', () => {
		const files = ordered(['a.py', 'needs-review'], ['b.py', 'sampled']);

		assert.strictEqual(nextFileToReview(files, 'b.py', viewedAmong('b.py')), 'a.py');
	});

	it('starts at the first unviewed file without a current file', () => {
		const files = ordered(['a.py', 'needs-review'], ['b.py', 'sampled']);

		assert.strictEqual(nextFileToReview(files, undefined, viewedAmong('a.py')), 'b.py');
	});

	it('skips no-review files', () => {
		const files = ordered(['a.py', 'needs-review'], ['b.py', 'no-review']);

		assert.strictEqual(nextFileToReview(files, 'a.py', viewedAmong('a.py')), undefined);
	});

	it('includes no-review files when the current file is one', () => {
		const files = ordered(['a.py', 'no-review'], ['b.py', 'no-review']);

		assert.strictEqual(nextFileToReview(files, 'a.py', viewedAmong('a.py')), 'b.py');
	});

	it('never picks the current file', () => {
		const files = ordered(['a.py', 'needs-review']);

		assert.strictEqual(nextFileToReview(files, 'a.py', viewedAmong()), undefined);
	});
});
