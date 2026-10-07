import * as assert from 'assert';
import { describe, it } from 'mocha';
import { CheckReport, FileReport } from './checkReport';
import { fileDescription, fileHover, fileReportsByPath } from './fileRatings';

function ratedFileReport(path: string, probability: number, reason: string): FileReport {
	return {
		path, previous_path: null, change_type: 'modified', base_probability: 0.1,
		rating: { probability, reason }, unrated: false, draw: 0.5,
	};
}

function unratedFileReport(path: string): FileReport {
	return {
		path, previous_path: null, change_type: 'modified', base_probability: 0.1,
		rating: null, unrated: true, draw: 0.5,
	};
}

describe('fileHover', () => {
	it('shows a rated file\'s AI rating and reason', () => {
		const hover = fileHover('/repo/src/a.py', ratedFileReport('src/a.py', 0.8, 'Changes the retry logic.'));

		assert.strictEqual(hover, '/repo/src/a.py\n\nAI rating: 80%\nAI reason: Changes the retry logic.');
	});

	it('marks an unrated file', () => {
		const hover = fileHover('/repo/src/a.py', unratedFileReport('src/a.py'));

		assert.strictEqual(hover, '/repo/src/a.py\n\nUnrated: no AI rating matches this version of the file.');
	});

	it('keeps fractional percentages instead of rounding them to 0%', () => {
		const hover = fileHover('a.py', ratedFileReport('a.py', 0.005, 'Reason.'));

		assert.match(hover, /AI rating: 0\.5%/);
	});

	it('says when the check did not list the file', () => {
		assert.strictEqual(fileHover('/repo/a.py', undefined), '/repo/a.py\n\nNot in the codetaster check.');
	});
});

describe('fileDescription', () => {
	it('leaves a rated file\'s description as it was', () => {
		const rated = ratedFileReport('src/a.py', 0.8, 'Reason.');

		assert.strictEqual(fileDescription(true, 'src', rated), true);
		assert.strictEqual(fileDescription('', 'src', rated), '');
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

describe('fileReportsByPath', () => {
	it('finds each file\'s report, whichever list it is in', () => {
		const needsReview = ratedFileReport('a.py', 0.8, 'Reason.');
		const sampled = unratedFileReport('b.py');
		const noReview = unratedFileReport('c.py');
		const report: CheckReport = {
			schema_version: 3,
			needs_review: true,
			base: { ref: 'main', merge_base: 'a'.repeat(40) },
			head: { commit: 'b'.repeat(40) },
			top_rated_percentage: 20,
			'needs-review': [needsReview],
			sampled: [sampled],
			'no-review': [noReview],
		};

		const byPath = fileReportsByPath(report);

		assert.deepStrictEqual([...byPath.entries()], [['a.py', needsReview], ['b.py', sampled], ['c.py', noReview]]);
	});
});
