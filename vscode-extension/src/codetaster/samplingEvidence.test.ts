import * as assert from 'assert';
import { describe, it } from 'mocha';
import { CheckReport, FileReport, SamplingReport } from './checkReport';
import { countSamplingEvidence, reviewablePaths, ReviewablePathsSeen, ReviewThreadAuthorship, samplingDescription } from './samplingEvidence';

const VIEWER = 'reviewer';

function fakeFileReport(path: string): FileReport {
	return {
		path, previous_path: null, change_type: 'modified', base_probability: 0.1, sampling_probability: 0.1,
		rating: null, unrated: true, draw: 0.5,
	};
}

function fakeSampling(sampling: Partial<SamplingReport> = {}): SamplingReport {
	return { base_probability: 0.1, base_probability_weight: 10, commented_files: 0, viewed_files: 0, effective_probability: 0.1, ...sampling };
}

function fakeCheckReport(lists: { needsReview?: string[], sampled?: string[], noReview?: string[] }): CheckReport {
	return {
		schema_version: 6,
		needs_review: true,
		base: { ref: 'main', merge_base: 'a'.repeat(40) },
		head: { commit: 'b'.repeat(40) },
		needs_review_threshold: 0.6,
		sampling: fakeSampling(),
		'needs-review': (lists.needsReview ?? []).map(fakeFileReport),
		sampled: (lists.sampled ?? []).map(fakeFileReport),
		'no-review': (lists.noReview ?? []).map(fakeFileReport),
	};
}

function threadBy(authorLogin: string | undefined, path: string): ReviewThreadAuthorship {
	return { path, authorLogin };
}

describe('reviewablePaths', () => {
	it('lists the needs-review and sampled files, not the no-review ones', () => {
		const report = fakeCheckReport({ needsReview: ['a.py'], sampled: ['b.py'], noReview: ['c.py'] });

		assert.deepStrictEqual(reviewablePaths(report), ['a.py', 'b.py']);
	});
});

describe('countSamplingEvidence', () => {
	it('counts a reviewable file with a thread by the viewer as commented', () => {
		const evidence = countSamplingEvidence({
			reviewablePaths: ['a.py'],
			threads: [threadBy(VIEWER, 'a.py')],
			viewedPaths: new Set(),
			viewerLogin: VIEWER,
		});

		assert.deepStrictEqual(evidence, { commentedFiles: 1, viewedFiles: 0 });
	});

	it('counts several threads on one file once', () => {
		const evidence = countSamplingEvidence({
			reviewablePaths: ['a.py'],
			threads: [threadBy(VIEWER, 'a.py'), threadBy(VIEWER, 'a.py')],
			viewedPaths: new Set(['a.py']),
			viewerLogin: VIEWER,
		});

		assert.deepStrictEqual(evidence, { commentedFiles: 1, viewedFiles: 0 });
	});

	it('ignores threads by others and on files that are not reviewable', () => {
		const evidence = countSamplingEvidence({
			reviewablePaths: ['a.py'],
			threads: [threadBy('someone-else', 'a.py'), threadBy(undefined, 'a.py'), threadBy(VIEWER, 'other.py')],
			viewedPaths: new Set(),
			viewerLogin: VIEWER,
		});

		assert.deepStrictEqual(evidence, { commentedFiles: 0, viewedFiles: 0 });
	});

	it('counts a viewed reviewable file without a thread by the viewer as viewed', () => {
		const evidence = countSamplingEvidence({
			reviewablePaths: ['a.py', 'b.py'],
			threads: [threadBy('someone-else', 'a.py')],
			viewedPaths: new Set(['a.py', 'not-reviewable.py']),
			viewerLogin: VIEWER,
		});

		assert.deepStrictEqual(evidence, { commentedFiles: 0, viewedFiles: 1 });
	});
});

describe('ReviewablePathsSeen', () => {
	it('keeps a file that stops being reviewable, so its evidence keeps counting', () => {
		const seen = new ReviewablePathsSeen<object>();
		const pullRequest = {};

		seen.record(pullRequest, ['a.py']);
		const paths = seen.record(pullRequest, ['b.py']);

		assert.deepStrictEqual([...paths].sort(), ['a.py', 'b.py']);
	});

	it('starts fresh for each pull request', () => {
		const seen = new ReviewablePathsSeen<object>();

		seen.record({}, ['a.py']);
		const paths = seen.record({}, ['b.py']);

		assert.deepStrictEqual([...paths], ['b.py']);
	});
});

describe('samplingDescription', () => {
	it('shows only the base probability without evidence', () => {
		assert.strictEqual(samplingDescription(fakeSampling()), 'Sampling 10%');
	});

	it('shows only the base probability when viewed files keep it at the floor', () => {
		const sampling = fakeSampling({ viewed_files: 5, effective_probability: 0.1 });

		assert.strictEqual(samplingDescription(sampling), 'Sampling 10%');
	});

	it('shows how the evidence changed the probability', () => {
		const sampling = fakeSampling({ commented_files: 1, viewed_files: 5, effective_probability: 0.125 });

		assert.strictEqual(samplingDescription(sampling), 'Sampling 10% → 13% (1 commented, 5 viewed)');
	});

	it('keeps two significant digits of a small probability', () => {
		const sampling = fakeSampling({ base_probability: 0.005, effective_probability: 0.005 });

		assert.strictEqual(samplingDescription(sampling), 'Sampling 0.5%');
	});
});
