import * as assert from 'assert';
import { describe, it } from 'mocha';
import { CategoryGroup, groupFilesByCategory, needsReviewRuleDescription } from './categoryGroups';
import { CheckReport, FileReport } from './checkReport';

interface FakeFile {
	readonly fileName: string;
}

/** A file the check rated in `category`, or left unrated without one. */
function fakeFileReport(path: string, category: string | undefined): FileReport {
	return {
		path, previous_path: null, change_type: 'modified', base_probability: 0.1, sampling_probability: 0.1,
		rating: category === undefined ? null : { probability: 0.5, category, annotations: [] },
		unrated: category === undefined, draw: 0.5,
	};
}

type FakeVerdictFiles = Record<string, string | undefined>;

function fakeCheckReport(verdicts: { needsReview?: FakeVerdictFiles, sampled?: FakeVerdictFiles, noReview?: FakeVerdictFiles }): CheckReport {
	const fileReports = (files: FakeVerdictFiles = {}) => Object.entries(files).map(([path, category]) => fakeFileReport(path, category));
	return {
		schema_version: 6,
		needs_review: false,
		base: { ref: 'main', merge_base: 'a'.repeat(40) },
		head: { commit: 'b'.repeat(40) },
		needs_review_threshold: 0.6,
		sampling: { base_probability: 0.1, base_probability_weight: 10, commented_files: 0, viewed_files: 0, effective_probability: 0.1 },
		'needs-review': fileReports(verdicts.needsReview),
		sampled: fileReports(verdicts.sampled),
		'no-review': fileReports(verdicts.noReview),
	};
}

function filesNamed(...names: string[]): FakeFile[] {
	return names.map(fileName => ({ fileName }));
}

function groupFakeFiles(report: CheckReport, files: FakeFile[]): CategoryGroup<FakeFile>[] {
	return groupFilesByCategory(report, files, file => file.fileName);
}

describe('groupFilesByCategory', () => {
	it('puts each PR file in the group of its category, with the verdict the check gave it', () => {
		const report = fakeCheckReport({ needsReview: { 'a.py': 'Logic' }, sampled: { 'b.py': 'Tests' }, noReview: { 'c.py': 'Logic' } });
		const [a, b, c] = filesNamed('a.py', 'b.py', 'c.py');

		const groups = groupFakeFiles(report, [c, b, a]);

		assert.deepStrictEqual(groups.map(group => [group.label, group.files]), [
			['Logic (2)', [{ file: c, verdict: 'no-review' }, { file: a, verdict: 'needs-review' }]],
			['Tests (1)', [{ file: b, verdict: 'sampled' }]],
		]);
	});

	it('sorts categories alphabetically, comparing numbers by value', () => {
		const report = fakeCheckReport({ sampled: { 'a.py': '10. Docs', 'b.py': '2. Logic', 'c.py': 'b', 'd.py': 'A' } });

		const groups = groupFakeFiles(report, filesNamed('a.py', 'b.py', 'c.py', 'd.py'));

		assert.deepStrictEqual(groups.map(group => group.label), ['2. Logic (1)', '10. Docs (1)', 'A (1)', 'b (1)']);
	});

	it('orders categories as the overview lists them, then any it does not list by name', () => {
		const report = {
			...fakeCheckReport({ sampled: { 'a.py': 'A', 'b.py': 'B', 'c.py': 'C', 'd.py': 'D' } }),
			overview: { summary: 'Summary.', categories: [{ name: 'C', description: 'C.' }, { name: 'A', description: 'A.' }] },
		};

		const groups = groupFakeFiles(report, filesNamed('a.py', 'b.py', 'c.py', 'd.py'));

		assert.deepStrictEqual(groups.map(group => group.label), ['C (1)', 'A (1)', 'B (1)', 'D (1)']);
	});

	it('explains the groups outside the categories, and leaves categories to the overview', () => {
		const report = fakeCheckReport({ needsReview: { 'a.py': undefined }, sampled: { 'b.py': 'Z' } });

		const groups = groupFakeFiles(report, filesNamed('a.py', 'b.py', 'missing.py'));

		assert.deepStrictEqual(groups.map(group => [group.kind, group.tooltip !== undefined]), [
			['not-checked', true], ['category', false], ['unrated', true],
		]);
	});

	it('shows PR files the check did not list in a group before the categories, so none are hidden', () => {
		const report = fakeCheckReport({ noReview: { 'c.py': 'A' } });
		const [c, missing] = filesNamed('c.py', 'missing.py');

		const groups = groupFakeFiles(report, [c, missing]);

		assert.deepStrictEqual(groups.map(group => [group.kind, group.label]), [['not-checked', 'Not in codetaster check (1)'], ['category', 'A (1)']]);
		assert.deepStrictEqual(groups[0].files, [{ file: missing, verdict: 'not-checked' }]);
	});

	it('shows files the check listed without a rating in a group after the categories', () => {
		const report = fakeCheckReport({ needsReview: { 'a.py': undefined }, sampled: { 'b.py': 'Z' } });
		const [a, b] = filesNamed('a.py', 'b.py');

		const groups = groupFakeFiles(report, [a, b]);

		assert.deepStrictEqual(groups.map(group => [group.kind, group.label]), [['category', 'Z (1)'], ['unrated', 'Unrated (1)']]);
		assert.deepStrictEqual(groups[1].files, [{ file: a, verdict: 'needs-review' }]);
	});

	it('leaves out the not-checked and unrated groups when they are empty', () => {
		const report = fakeCheckReport({ sampled: { 'b.py': 'Z' } });

		const groups = groupFakeFiles(report, filesNamed('b.py'));

		assert.deepStrictEqual(groups.map(group => group.kind), ['category']);
	});

	it('collapses only groups whose files all need no review', () => {
		const report = fakeCheckReport({
			needsReview: { 'a.py': 'Mixed' },
			noReview: { 'b.py': 'Mixed', 'c.py': 'Quiet', 'd.py': undefined },
		});

		const groups = groupFakeFiles(report, filesNamed('a.py', 'b.py', 'c.py', 'd.py', 'missing.py'));

		assert.deepStrictEqual(groups.map(group => [group.label, group.collapsed]), [
			['Not in codetaster check (1)', false], ['Mixed (2)', false], ['Quiet (1)', true], ['Unrated (1)', true],
		]);
	});

	it('ignores files the check lists but the PR does not', () => {
		const report = fakeCheckReport({ needsReview: { 'only-local.py': 'A' }, noReview: { 'c.py': 'B' } });

		const groups = groupFakeFiles(report, filesNamed('c.py'));

		assert.deepStrictEqual(groups.map(group => group.label), ['B (1)']);
	});

	it('partitions the PR files: every file is in exactly one group', () => {
		const report = fakeCheckReport({ needsReview: { 'a.py': 'A' }, sampled: { 'b.py': undefined }, noReview: { 'c.py': 'B' } });
		const files = filesNamed('a.py', 'b.py', 'c.py', 'd.py');

		const grouped = groupFakeFiles(report, files).flatMap(group => group.files.map(entry => entry.file));

		assert.strictEqual(grouped.length, files.length);
		assert.deepStrictEqual(new Set(grouped), new Set(files));
	});
});

describe('needsReviewRuleDescription', () => {
	it('says which rating a file needs review at', () => {
		assert.strictEqual(needsReviewRuleDescription(fakeCheckReport({})), 'needs review = rating ≥ 0.6');
	});
});
