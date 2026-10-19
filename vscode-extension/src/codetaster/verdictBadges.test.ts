import * as assert from 'assert';
import { describe, it } from 'mocha';
import { verdictBadge } from './verdictBadges';

describe('verdictBadge', () => {
	it('marks needs-review files with a green N', () => {
		assert.deepStrictEqual(verdictBadge('needs-review'), { badge: 'N', tooltip: 'Needs review', color: 'charts.green' });
	});

	it('marks sampled files with a yellow S', () => {
		assert.deepStrictEqual(verdictBadge('sampled'), { badge: 'S', tooltip: 'Sampled', color: 'charts.yellow' });
	});

	it('greys out no-review files without a badge', () => {
		assert.deepStrictEqual(verdictBadge('no-review'), { tooltip: 'No review', color: 'disabledForeground' });
	});

	it('marks files not in the check with a ?', () => {
		assert.deepStrictEqual(verdictBadge('not-checked'), { badge: '?', tooltip: 'Not in codetaster check' });
	});
});
