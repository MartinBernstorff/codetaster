export interface ExpandableThread {
	readonly id: string;
	readonly isResolved: boolean;
	readonly comments: readonly { readonly isDraft?: boolean }[];
}

/**
 * Decides which comment threads open expanded because of draft (pending review) comments.
 * A thread with a draft is expanded whatever `commentExpandState` says, even when resolved.
 * Once its drafts are submitted it stays expanded, until its resolved state changes.
 */
export class DraftThreadExpansion {
	private readonly resolvedStateWhenDrafted = new Map<string, boolean>();

	/** Notes whether `thread` has drafts, or has been resolved or unresolved since it had them. */
	recordThreadDrafts(thread: ExpandableThread): void {
		if (thread.comments.some(comment => comment.isDraft)) {
			this.resolvedStateWhenDrafted.set(thread.id, thread.isResolved);
		} else if (this.resolvedStateWhenDrafted.get(thread.id) !== thread.isResolved) {
			this.resolvedStateWhenDrafted.delete(thread.id);
		}
	}

	isExpandedForDrafts(thread: ExpandableThread): boolean {
		return this.resolvedStateWhenDrafted.has(thread.id);
	}
}

export const draftThreadExpansion = new DraftThreadExpansion();
