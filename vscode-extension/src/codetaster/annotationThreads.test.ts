import * as assert from 'assert';
import { describe, it } from 'mocha';
import { AnnotatedFile, AnnotationPlacement, annotationPlacements, AnnotationThreadSet, placementChanges, placementKey } from './annotationThreads';
import { AnnotationReport, CheckReport, FileReport } from './checkReport';

function fileReport(path: string, annotations: readonly AnnotationReport[] | undefined): FileReport {
	return {
		path, previous_path: null, change_type: 'modified', base_probability: 0.1, sampling_probability: 0.1,
		rating: annotations === undefined ? null : { probability: 0.5, category: 'Logic', annotations },
		unrated: annotations === undefined, draw: 0.5,
	};
}

function reportWith(...files: FileReport[]): CheckReport {
	return {
		schema_version: 6,
		needs_review: false,
		base: { ref: 'main', merge_base: 'a'.repeat(40) },
		head: { commit: 'b'.repeat(40) },
		needs_review_threshold: 0.6,
		sampling: { base_probability: 0.1, base_probability_weight: 10, commented_files: 0, viewed_files: 0, effective_probability: 0.1 },
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

describe('placementChanges', () => {
	const uriKey = (uri: string) => uri;
	const kept: AnnotationPlacement<string> = { uri: 'after:a.py', line: 0, text: 'Kept.' };
	const dropped: AnnotationPlacement<string> = { uri: 'after:a.py', line: 1, text: 'Dropped.' };
	const added: AnnotationPlacement<string> = { uri: 'file:a.py', line: 0, text: 'Kept.' };

	it('adds only placements not shown yet and removes those no longer wanted', () => {
		const shown = new Set([placementKey(kept, uriKey), placementKey(dropped, uriKey)]);

		const changes = placementChanges(shown, [kept, added], uriKey);

		assert.deepStrictEqual(changes, { added: [added], removed: [placementKey(dropped, uriKey)] });
	});

	it('changes nothing when the same placements are wanted again', () => {
		const shown = new Set([placementKey(kept, uriKey)]);

		const changes = placementChanges(shown, [kept], uriKey);

		assert.deepStrictEqual(changes, { added: [], removed: [] });
	});

	it('adds a placement wanted twice, e.g. by both file lists, once', () => {
		const changes = placementChanges(new Set(), [kept, kept], uriKey);

		assert.deepStrictEqual(changes.added, [kept]);
	});
});

interface FakeThread {
	readonly placement: AnnotationPlacement<string>;
	disposed: boolean;
	dispose(): void;
}

/** An `AnnotationThreadSet` over string URIs and PR numbers, and every thread it created. */
function threadSet(): { set: AnnotationThreadSet<number, string, FakeThread>, created: FakeThread[] } {
	const created: FakeThread[] = [];
	const set = new AnnotationThreadSet<number, string, FakeThread>(
		placement => {
			const thread: FakeThread = { placement, disposed: false, dispose() { thread.disposed = true; } };
			created.push(thread);
			return thread;
		},
		uri => uri,
		(a, b) => a === b,
	);
	return { set, created };
}

function liveThreads(created: readonly FakeThread[]): AnnotationPlacement<string>[] {
	return created.filter(thread => !thread.disposed).map(thread => thread.placement);
}

describe('AnnotationThreadSet', () => {
	const owner = 'repository';
	const checkedOut = 1;
	const other = 2;
	const localFile: AnnotationPlacement<string> = { uri: 'file:a.py', line: 0, text: 'Moved.' };
	const prFile: AnnotationPlacement<string> = { uri: 'pr:a.py', line: 0, text: 'Moved.' };

	it('shows the placements of every file list of the checked-out PR', () => {
		const { set, created } = threadSet();

		set.show(owner, checkedOut, 'local', [localFile]);
		set.show(owner, checkedOut, 'pull request', [prFile]);

		assert.deepStrictEqual(liveThreads(created), [localFile, prFile]);
	});

	it('does not recreate threads when the file lists refresh in turn', () => {
		const { set, created } = threadSet();

		set.show(owner, checkedOut, 'local', [localFile]);
		set.show(owner, checkedOut, 'pull request', [prFile]);
		set.show(owner, checkedOut, 'local', [localFile]);
		set.show(owner, checkedOut, 'pull request', [prFile]);

		assert.deepStrictEqual(created.map(thread => thread.placement), [localFile, prFile]);
		assert.deepStrictEqual(liveThreads(created), [localFile, prFile]);
	});

	it('keeps the checked-out PR\'s threads when another PR\'s file list clears', () => {
		const { set, created } = threadSet();
		set.show(owner, checkedOut, 'local', [localFile]);

		set.clearUnlessFor(owner, checkedOut);

		assert.deepStrictEqual(liveThreads(created), [localFile]);
	});

	it('removes the threads once their PR is no longer checked out', () => {
		const { set, created } = threadSet();
		set.show(owner, checkedOut, 'local', [localFile]);

		set.clearUnlessFor(owner, undefined);

		assert.deepStrictEqual(liveThreads(created), []);
	});

	it('replaces another PR\'s threads, from every file list', () => {
		const { set, created } = threadSet();
		set.show(owner, other, 'local', [localFile]);
		set.show(owner, other, 'pull request', [prFile]);

		set.show(owner, checkedOut, 'local', [localFile]);

		assert.deepStrictEqual(liveThreads(created), [localFile]);
	});
});
