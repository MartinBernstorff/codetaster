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

	forcesExpanded(thread: ExpandableThread): boolean {
		if (thread.comments.some(comment => comment.isDraft)) {
			this.resolvedStateWhenDrafted.set(thread.id, thread.isResolved);
			return true;
		}
		if (this.resolvedStateWhenDrafted.get(thread.id) === thread.isResolved) {
			return true;
		}
		this.resolvedStateWhenDrafted.delete(thread.id);
		return false;
	}
}

export const draftThreadExpansion = new DraftThreadExpansion();
