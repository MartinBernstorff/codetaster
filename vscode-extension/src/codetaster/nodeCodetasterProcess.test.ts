import * as assert from 'assert';
import { describe, it } from 'mocha';
import * as os from 'os';
import { NodeCodetasterProcess } from './nodeCodetasterProcess';

describe('NodeCodetasterProcess', () => {
	it('returns the exit code and output of a process that ran', async () => {
		const script = 'process.stdout.write(process.cwd()); process.stderr.write("oops"); process.exit(3)';

		const outcome = await new NodeCodetasterProcess().runCodetaster(process.execPath, ['-e', script], os.tmpdir());

		assert.strictEqual(outcome.kind, 'exited');
		if (outcome.kind === 'exited') {
			assert.strictEqual(outcome.exitCode, 3);
			assert.ok(outcome.stdout.length > 0);
			assert.strictEqual(outcome.stderr, 'oops');
		}
	});

	it('reports an executable that does not exist', async () => {
		const outcome = await new NodeCodetasterProcess().runCodetaster('codetaster-does-not-exist', ['check'], os.tmpdir());

		assert.strictEqual(outcome.kind, 'failedToStart');
	});
});
