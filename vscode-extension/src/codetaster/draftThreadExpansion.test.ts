import * as assert from 'assert';
import { describe, it } from 'mocha';
import { DraftThreadExpansion, ExpandableThread } from './draftThreadExpansion';

function threadWith(state: { resolved: boolean, drafts: boolean }): ExpandableThread {
	return { id: 'thread-1', isResolved: state.resolved, comments: [{ isDraft: false }, { isDraft: state.drafts }] };
}

function isExpandedAfter(expansion: DraftThreadExpansion, thread: ExpandableThread): boolean {
	expansion.recordThreadDrafts(thread);
	return expansion.isExpandedForDrafts(thread);
}

describe('DraftThreadExpansion', () => {
	it('expands a thread with a draft comment', () => {
		assert.strictEqual(isExpandedAfter(new DraftThreadExpansion(), threadWith({ resolved: false, drafts: true })), true);
	});

	it('expands a resolved thread with a draft reply', () => {
		assert.strictEqual(isExpandedAfter(new DraftThreadExpansion(), threadWith({ resolved: true, drafts: true })), true);
	});

	it('leaves a thread without drafts to the usual rules', () => {
		assert.strictEqual(isExpandedAfter(new DraftThreadExpansion(), threadWith({ resolved: false, drafts: false })), false);
	});

	it('keeps a thread expanded after its drafts are submitted', () => {
		const expansion = new DraftThreadExpansion();
		expansion.recordThreadDrafts(threadWith({ resolved: true, drafts: true }));

		assert.strictEqual(isExpandedAfter(expansion, threadWith({ resolved: true, drafts: false })), true);
	});

	it('hands a submitted thread back to the usual rules once it is resolved', () => {
		const expansion = new DraftThreadExpansion();
		expansion.recordThreadDrafts(threadWith({ resolved: false, drafts: true }));

		assert.strictEqual(isExpandedAfter(expansion, threadWith({ resolved: true, drafts: false })), false);
	});
});
