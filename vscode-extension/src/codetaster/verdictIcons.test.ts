import * as assert from 'assert';
import { describe, it } from 'mocha';
import { ThemeIconSpec, verdictIconPath } from './verdictIcons';

const FILE_ICON = 'file-type-icon';

function iconFor(verdict: Parameters<typeof verdictIconPath>[0]): string | ThemeIconSpec {
	return verdictIconPath<string | ThemeIconSpec>(verdict, FILE_ICON, spec => spec);
}

describe('verdictIconPath', () => {
	it('replaces a needs-review file\'s icon with a green circle', () => {
		assert.deepStrictEqual(iconFor('needs-review'), { id: 'circle-filled', color: 'charts.green' });
	});

	it('replaces a sampled file\'s icon with a yellow circle', () => {
		assert.deepStrictEqual(iconFor('sampled'), { id: 'circle-filled', color: 'charts.yellow' });
	});

	it('keeps a no-review file\'s own icon', () => {
		assert.strictEqual(iconFor('no-review'), FILE_ICON);
	});

	it('replaces the icon of a file not in the check with an uncoloured question mark', () => {
		assert.deepStrictEqual(iconFor('not-checked'), { id: 'question' });
	});
});
