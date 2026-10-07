import * as assert from 'assert';
import * as fs from 'fs';
import { describe, it } from 'mocha';
import * as path from 'path';
import { EXTENSION_ID } from '../constants';

function readExtensionJson(fileName: string): Record<string, unknown> {
	return JSON.parse(fs.readFileSync(path.join(__dirname, '..', '..', fileName), 'utf8'));
}

describe('codetaster fork identity', () => {
	it('has an extension ID distinct from upstream', () => {
		const manifest = readExtensionJson('package.json');
		assert.strictEqual(`${manifest.publisher}.${manifest.name}`, EXTENSION_ID);
		assert.notStrictEqual(EXTENSION_ID, 'GitHub.vscode-pull-request-github');
	});

	it('has a display name that marks it as the codetaster fork', () => {
		const strings = readExtensionJson('package.nls.json');
		assert.strictEqual(strings.displayName, 'GitHub Pull Requests (codetaster)');
	});
});
