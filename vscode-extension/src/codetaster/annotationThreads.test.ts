import * as assert from 'assert';
import { describe, it } from 'mocha';
import { AnnotatedFile, annotationPlacements } from './annotationThreads';
import { AnnotationReport, CheckReport, FileReport } from './checkReport';

function fileReport(path: string, annotations: readonly AnnotationReport[] | undefined): FileReport {
	return {
		path, previous_path: null, change_type: 'modified', base_probability: 0.1,
		rating: annotations === undefined ? null : { probability: 0.5, category: 'Logic', annotations },
		unrated: annotations === undefined, draw: 0.5,
	};
}

function reportWith(...files: FileReport[]): CheckReport {
	return {
		schema_version: 5,
		needs_review: false,
		base: { ref: 'main', merge_base: 'a'.repeat(40) },
		head: { commit: 'b'.repeat(40) },
		needs_review_threshold: 0.6,
		'needs-review': [],
		sampled: [],
		'no-review': files,
	};
}

function bothSides(path: string): AnnotatedFile<string> {
	return { path, beforeUri: `before:${path}`, afterUri: `after:${path}` };
}

describe('annotationPlacements', () => {
	it('places each annotation on its side\'s document, at its line counted from 0', () => {
		const report = reportWith(fileReport('a.py', [
			{ side: 'after', line: 3, text: 'Moved from `old.py`.' },
			{ side: 'before', line: 1, text: 'Was here.' },
		]));

		const placements = annotationPlacements(report, [bothSides('a.py')]);

		assert.deepStrictEqual(placements, [
			{ uri: 'after:a.py', line: 2, text: 'Moved from `old.py`.' },
			{ uri: 'before:a.py', line: 0, text: 'Was here.' },
		]);
	});

	it('places nothing for an unrated file, whose rating no longer applies', () => {
		const report = reportWith(fileReport('a.py', undefined));

		assert.deepStrictEqual(annotationPlacements(report, [bothSides('a.py')]), []);
	});

	it('skips an annotation on a side the file does not have', () => {
		const report = reportWith(fileReport('added.py', [{ side: 'before', line: 1, text: 'Nothing before.' }]));

		const placements = annotationPlacements(report, [{ path: 'added.py', beforeUri: undefined, afterUri: 'after:added.py' }]);

		assert.deepStrictEqual(placements, []);
	});

	it('skips files the PR file list does not show', () => {
		const report = reportWith(fileReport('a.py', [{ side: 'after', line: 1, text: 'Note.' }]));

		assert.deepStrictEqual(annotationPlacements(report, [bothSides('b.py')]), []);
	});
});
