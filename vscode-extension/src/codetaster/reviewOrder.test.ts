import * as assert from 'assert';
import { describe, it } from 'mocha';
import { CategoryGroup, FileVerdict } from './categoryGroups';
import { nextFileToReview, OrderedFile, reviewOrder } from './reviewOrder';

function group(...files: [string, FileVerdict][]): CategoryGroup<string> {
	return { kind: 'category', label: 'Category', files: files.map(([file, verdict]) => ({ file, verdict })), collapsed: false };
}

function ordered(...entries: [string, FileVerdict][]): OrderedFile<string>[] {
	return entries.map(([path, verdict]) => ({ file: path, path, verdict }));
}

function viewedAmong(...viewed: string[]): (file: string) => boolean {
	return file => viewed.includes(file);
}

describe('reviewOrder', () => {
	it('lists files group by group, sorted by path within each group', () => {
		const groups = [group(['b.py', 'sampled'], ['a.py', 'sampled']), group(['c.py', 'sampled'])];

		const order = reviewOrder(groups, file => file, 'flat', 'fileList');

		assert.deepStrictEqual(order.map(entry => entry.path), ['a.py', 'b.py', 'c.py']);
	});

	it('puts directories before files in tree layout', () => {
		const groups = [group(['z.py', 'sampled'], ['src/b.py', 'sampled'], ['src/lib/a.py', 'sampled'])];

		const order = reviewOrder(groups, file => file, 'tree', 'fileList');

		assert.deepStrictEqual(order.map(entry => entry.path), ['src/lib/a.py', 'src/b.py', 'z.py']);
	});

	const mixedVerdicts = [
		group(['missing.py', 'not-checked']),
		group(['a.py', 'no-review'], ['b.py', 'sampled'], ['c.py', 'needs-review']),
		group(['d.py', 'sampled'], ['e.py', 'needs-review']),
	];

	it('lists files in the order shown, whatever their verdict, in file list order', () => {
		const order = reviewOrder(mixedVerdicts, file => file, 'flat', 'fileList');

		assert.deepStrictEqual(order.map(entry => entry.path), ['missing.py', 'a.py', 'b.py', 'c.py', 'd.py', 'e.py']);
	});

	it('lists files not in the check, then needs-review, sampled and no-review files, each in the order shown, in priority order', () => {
		const order = reviewOrder(mixedVerdicts, file => file, 'flat', 'priority');

		assert.deepStrictEqual(order.map(entry => [entry.path, entry.verdict]), [
			['missing.py', 'not-checked'],
			['c.py', 'needs-review'], ['e.py', 'needs-review'],
			['b.py', 'sampled'], ['d.py', 'sampled'],
			['a.py', 'no-review'],
		]);
	});
});

describe('nextFileToReview', () => {
	it('picks the next unviewed file after the current one', () => {
		const files = ordered(['a.py', 'needs-review'], ['b.py', 'needs-review'], ['c.py', 'sampled']);

		assert.strictEqual(nextFileToReview(files, 'a.py', viewedAmong('a.py', 'b.py'), 'fileList'), 'c.py');
	});

	it('wraps around to unviewed files before the current one', () => {
		const files = ordered(['a.py', 'needs-review'], ['b.py', 'sampled']);

		assert.strictEqual(nextFileToReview(files, 'b.py', viewedAmong('b.py'), 'fileList'), 'a.py');
	});

	it('starts at the first unviewed file without a current file', () => {
		const files = ordered(['a.py', 'needs-review'], ['b.py', 'sampled']);

		assert.strictEqual(nextFileToReview(files, undefined, viewedAmong('a.py'), 'fileList'), 'b.py');
	});

	it('visits no-review files in file list order', () => {
		const files = ordered(['a.py', 'needs-review'], ['b.py', 'no-review'], ['c.py', 'needs-review']);

		assert.strictEqual(nextFileToReview(files, 'a.py', viewedAmong('a.py'), 'fileList'), 'b.py');
	});

	it('skips no-review files in priority order', () => {
		const files = ordered(['a.py', 'needs-review'], ['b.py', 'no-review']);

		assert.strictEqual(nextFileToReview(files, 'a.py', viewedAmong('a.py'), 'priority'), undefined);
	});

	it('includes no-review files in priority order when the current file is one', () => {
		const files = ordered(['a.py', 'no-review'], ['b.py', 'no-review']);

		assert.strictEqual(nextFileToReview(files, 'a.py', viewedAmong('a.py'), 'priority'), 'b.py');
	});

	it('never picks the current file', () => {
		const files = ordered(['a.py', 'needs-review']);

		assert.strictEqual(nextFileToReview(files, 'a.py', viewedAmong(), 'fileList'), undefined);
	});
});
