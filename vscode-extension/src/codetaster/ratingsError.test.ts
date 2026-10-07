import * as assert from 'assert';
import { describe, it } from 'mocha';
import { ratingsErrorWarning } from './ratingsError';

describe('ratingsErrorWarning', () => {
	it('is absent when the ratings file is valid or missing', () => {
		assert.strictEqual(ratingsErrorWarning(null), undefined);
	});

	it('is absent for a report without ratings_error', () => {
		assert.strictEqual(ratingsErrorWarning(undefined), undefined);
	});

	it('says every file is unrated, and why', () => {
		const error = 'invalid ratings file /repo/.codetaster/ratings.json: not json';

		assert.strictEqual(ratingsErrorWarning(error), `codetaster ignored the ratings file, so every file is unrated: ${error}`);
	});
});
