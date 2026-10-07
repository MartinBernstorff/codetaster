import * as assert from 'assert';
import { describe, it } from 'mocha';
import { CheckReport, FileReport } from './checkReport';
import { groupFilesByVerdict } from './verdictGroups';

interface FakeFile {
	readonly fileName: string;
}

function fakeFileReport(path: string): FileReport {
	return { path, previous_path: null, change_type: 'modified', base_probability: 0.1, rating: null, unrated: true, probability: 0.1, draw: 0.5 };
}

function fakeCheckReport(groups: { needsReview?: string[], sampled?: string[], noReview?: string[] }): CheckReport {
	return {
		schema_version: 2,
		needs_review: false,
		base: { ref: 'main', merge_base: 'a'.repeat(40) },
		head: { commit: 'b'.repeat(40) },
		'needs-review': (groups.needsReview ?? []).map(fakeFileReport),
		sampled: (groups.sampled ?? []).map(fakeFileReport),
		'no-review': (groups.noReview ?? []).map(fakeFileReport),
	};
}

function filesNamed(...names: string[]): FakeFile[] {
	return names.map(fileName => ({ fileName }));
}

function groupFakeFiles(report: CheckReport, files: FakeFile[]) {
	return groupFilesByVerdict(report, files, file => file.fileName);
}

describe('groupFilesByVerdict', () => {
	it('puts each PR file in the group the check put its path in', () => {
		const report = fakeCheckReport({ needsReview: ['a.py'], sampled: ['b.py'], noReview: ['c.py'] });
		const [a, b, c] = filesNamed('a.py', 'b.py', 'c.py');

		const groups = groupFakeFiles(report, [c, b, a]);

		assert.deepStrictEqual(groups.map(group => group.files), [[a], [b], [c]]);
	});

	it('labels the three groups in urgency order with their file counts', () => {
		const report = fakeCheckReport({ sampled: ['b.py', 'src/d.py'], noReview: ['c.py'] });

		const groups = groupFakeFiles(report, filesNamed('b.py', 'src/d.py', 'c.py'));

		assert.deepStrictEqual(groups.map(group => group.label), ['Needs review (0)', 'Sampled (2)', 'No review (1)']);
		assert.deepStrictEqual(groups.map(group => group.verdict), ['needs-review', 'sampled', 'no-review']);
	});

	it('ignores files the check lists but the PR does not', () => {
		const report = fakeCheckReport({ needsReview: ['only-local.py'], noReview: ['c.py'] });

		const groups = groupFakeFiles(report, filesNamed('c.py'));

		assert.deepStrictEqual(groups.map(group => group.files.length), [0, 0, 1]);
	});

	it('shows PR files the check did not list in a fourth group, so none are hidden', () => {
		const report = fakeCheckReport({ noReview: ['c.py'] });
		const [c, missing] = filesNamed('c.py', 'missing.py');

		const groups = groupFakeFiles(report, [c, missing]);

		assert.strictEqual(groups.length, 4);
		assert.strictEqual(groups[3].verdict, 'not-checked');
		assert.strictEqual(groups[3].label, 'Not in codetaster check (1)');
		assert.deepStrictEqual(groups[3].files, [missing]);
	});

	it('partitions the PR files: every file is in exactly one group', () => {
		const report = fakeCheckReport({ needsReview: ['a.py'], sampled: ['b.py'], noReview: ['c.py'] });
		const files = filesNamed('a.py', 'b.py', 'c.py', 'd.py');

		const grouped = groupFakeFiles(report, files).flatMap(group => group.files);

		assert.strictEqual(grouped.length, files.length);
		assert.deepStrictEqual(new Set(grouped), new Set(files));
	});
});
