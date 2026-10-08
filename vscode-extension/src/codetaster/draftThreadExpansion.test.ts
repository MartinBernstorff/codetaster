import * as assert from 'assert';
import { describe, it } from 'mocha';
import { DraftThreadExpansion, ExpandableThread } from './draftThreadExpansion';

function thread(isResolved: boolean, ...isDraft: boolean[]): ExpandableThread {
	return { id: 'thread-1', isResolved, comments: isDraft.map(draft => ({ isDraft: draft })) };
}

describe('DraftThreadExpansion', () => {
	it('expands a thread with a draft comment', () => {
		assert.strictEqual(new DraftThreadExpansion().forcesExpanded(thread(false, false, true)), true);
	});

	it('expands a resolved thread with a draft reply', () => {
		assert.strictEqual(new DraftThreadExpansion().forcesExpanded(thread(true, false, true)), true);
	});

	it('leaves a thread without drafts to the usual rules', () => {
		assert.strictEqual(new DraftThreadExpansion().forcesExpanded(thread(false, false)), false);
	});

	it('keeps a thread expanded after its drafts are submitted', () => {
		const expansion = new DraftThreadExpansion();
		expansion.forcesExpanded(thread(true, true));
		assert.strictEqual(expansion.forcesExpanded(thread(true, false)), true);
	});

	it('hands a submitted thread back to the usual rules once it is resolved or unresolved', () => {
		const expansion = new DraftThreadExpansion();
		expansion.forcesExpanded(thread(false, true));
		expansion.forcesExpanded(thread(false, false));
		assert.strictEqual(expansion.forcesExpanded(thread(true, false)), false);
		assert.strictEqual(expansion.forcesExpanded(thread(false, false)), false);
	});
});
