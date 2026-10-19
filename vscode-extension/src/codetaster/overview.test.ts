import * as assert from 'assert';
import { describe, it } from 'mocha';
import { OverviewReport } from './checkReport';
import { overviewMarkdown } from './overview';

describe('overviewMarkdown', () => {
	it('shows the summary, then each category and its description in the overview\'s order', () => {
		const overview: OverviewReport = {
			summary: 'Retries payments. See *Retry*.',
			categories: [
				{ name: 'Retry', description: 'Retries on timeout.' },
				{ name: 'Tests', description: 'Covers retries.' },
			],
		};

		assert.strictEqual(
			overviewMarkdown(overview),
			'# Summary\n\nRetries payments. See *Retry*.\n\n# Categories\n\n## Retry\n\nRetries on timeout.\n\n## Tests\n\nCovers retries.\n',
		);
	});
});
