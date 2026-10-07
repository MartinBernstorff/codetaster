import * as assert from 'assert';
import { describe, it } from 'mocha';
import { headMismatchWarning } from './headMismatch';

const checkedHead = 'a'.repeat(7) + '1'.repeat(33);
const pullRequestHead = 'b'.repeat(7) + '2'.repeat(33);

describe('headMismatchWarning', () => {
	it('is absent when the check ran on the PR head', () => {
		assert.strictEqual(headMismatchWarning(checkedHead, checkedHead), undefined);
	});

	it('ignores letter case when comparing the commits', () => {
		assert.strictEqual(headMismatchWarning(checkedHead.toUpperCase(), checkedHead), undefined);
	});

	it('is absent when the PR head is unknown', () => {
		assert.strictEqual(headMismatchWarning(checkedHead, undefined), undefined);
	});

	it('names both commits by short SHA when the check ran on a different commit', () => {
		assert.strictEqual(
			headMismatchWarning(checkedHead, pullRequestHead),
			'codetaster grouped files for aaaaaaa, not the PR head bbbbbbb',
		);
	});
});
