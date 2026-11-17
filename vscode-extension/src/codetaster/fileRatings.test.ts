import * as assert from 'assert';
import { describe, it } from 'mocha';
import { CheckReport, FileReport } from './checkReport';
import { fileDescription, fileHover, fileReportsByPath, fileStatus } from './fileRatings';

function ratedFileReport(path: string, probability: number): FileReport {
	return {
		path, previous_path: null, change_type: 'modified', base_probability: 0.1, sampling_probability: 0.1,
		rating: { probability, category: 'Logic', annotations: [] }, unrated: false, draw: 0.5,
	};
}

function unratedFileReport(path: string): FileReport {
	return {
		path, previous_path: null, change_type: 'modified', base_probability: 0.1, sampling_probability: 0.1,
		rating: null, unrated: true, draw: 0.5,
	};
}

describe('fileHover', () => {
	it('states a rated file\'s verdict and AI rating', () => {
		const hover = fileHover('/repo/src/a.py', 'needs-review', ratedFileReport('src/a.py', 0.8));

		assert.strictEqual(hover, '/repo/src/a.py\n\nVerdict: Needs review\nAI rating: 80%');
	});

	it('states an unrated file\'s verdict and marks it unrated', () => {
		const hover = fileHover('/repo/src/a.py', 'sampled', unratedFileReport('src/a.py'));

		assert.strictEqual(hover, '/repo/src/a.py\n\nVerdict: Sampled\nUnrated: no AI rating matches this version of the file.');
	});

	it('states a no-review verdict', () => {
		assert.match(fileHover('a.py', 'no-review', ratedFileReport('a.py', 0.1)), /\nVerdict: No review\n/);
	});

	it('keeps fractional percentages instead of rounding them to 0%', () => {
		const hover = fileHover('a.py', 'no-review', ratedFileReport('a.py', 0.005));

		assert.match(hover, /AI rating: 0\.5%/);
	});

	it('says when the check did not list the file', () => {
		assert.strictEqual(fileHover('/repo/a.py', 'not-checked', undefined), '/repo/a.py\n\nVerdict: Not in codetaster check');
	});
});

describe('fileDescription', () => {
	it('leads a rated file\'s description with its AI rating', () => {
		const rated = ratedFileReport('src/a.py', 0.8);

		assert.strictEqual(fileDescription(true, 'src', rated), '80% · src');
		assert.strictEqual(fileDescription('', 'src', rated), '80%');
	});

	it('leaves the description of a file the check did not list as it was', () => {
		assert.strictEqual(fileDescription(true, 'src', undefined), true);
	});

	it('marks an unrated file in tree layout, where the description is empty', () => {
		assert.strictEqual(fileDescription('', 'src', unratedFileReport('src/a.py')), 'unrated');
	});

	it('marks an unrated file in flat layout and keeps its directory, which upstream derives from `true`', () => {
		assert.strictEqual(fileDescription(true, 'src/lib', unratedFileReport('src/lib/a.py')), 'unrated · src/lib');
		assert.strictEqual(fileDescription(true, '', unratedFileReport('a.py')), 'unrated');
	});

	it('marks an unrated file whose description is already text', () => {
		assert.strictEqual(fileDescription('src/lib', 'src/lib', unratedFileReport('src/lib/a.py')), 'unrated · src/lib');
	});
});

describe('fileStatus', () => {
	it('shows the file\'s place in the review order, its verdict and AI rating', () => {
		const status = fileStatus(3, 10, 'needs-review', ratedFileReport('a.py', 0.86));

		assert.strictEqual(status.text, 'codetaster 3/10 · Needs review · 86%');
		assert.match(status.tooltip, /^Read closely/);
	});

	it('marks an unrated file', () => {
		assert.strictEqual(fileStatus(1, 2, 'sampled', unratedFileReport('a.py')).text, 'codetaster 1/2 · Sampled · unrated');
	});

	it('shows only the verdict of a file the check did not list', () => {
		assert.strictEqual(fileStatus(1, 1, 'not-checked', undefined).text, 'codetaster 1/1 · Not in codetaster check');
	});
});

describe('fileReportsByPath', () => {
	it('finds each file\'s report, whichever list it is in', () => {
		const needsReview = ratedFileReport('a.py', 0.8);
		const sampled = unratedFileReport('b.py');
		const noReview = unratedFileReport('c.py');
		const report: CheckReport = {
			schema_version: 6,
			needs_review: true,
			base: { ref: 'main', merge_base: 'a'.repeat(40) },
			head: { commit: 'b'.repeat(40) },
			needs_review_threshold: 0.6,
			sampling: { base_probability: 0.1, base_probability_weight: 10, commented_files: 0, viewed_files: 0, effective_probability: 0.1 },
			'needs-review': [needsReview],
			sampled: [sampled],
			'no-review': [noReview],
		};

		const byPath = fileReportsByPath(report);

		assert.deepStrictEqual([...byPath.entries()], [['a.py', needsReview], ['b.py', sampled], ['c.py', noReview]]);
	});
});
