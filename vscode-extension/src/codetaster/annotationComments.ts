import * as vscode from 'vscode';
import { AnnotationPlacement } from './annotationThreads';

/** Not matched by upstream's `commentController =~ /^github-(browse|review)/` menus, so no reply, resolve or edit actions. */
const ANNOTATIONS_CONTROLLER_ID = 'codetaster-annotations';
const ANNOTATION_AUTHOR = 'codetaster';

interface ShownAnnotations {
	/** Identifies the placements shown, so unchanged ones are not recreated. */
	readonly key: string;
	readonly threads: vscode.Disposable[];
}

/**
 * Shows the ratings file's annotations as read-only comment threads, authored by
 * "codetaster", initially expanded. They have no commenting ranges, so nothing can be
 * added to them, and they are never sent to GitHub.
 * Each owner, e.g. a repository's PR file list, shows its own set of annotations.
 */
export class AnnotationComments implements vscode.Disposable {
	private readonly controller = vscode.comments.createCommentController(ANNOTATIONS_CONTROLLER_ID, 'codetaster annotations');
	private readonly shown = new Map<unknown, ShownAnnotations>();

	/**
	 * Replaces `owner`'s threads with `placements`. Does nothing if they are unchanged,
	 * so a thread the user collapsed stays collapsed across file list refreshes.
	 */
	show(owner: unknown, placements: readonly AnnotationPlacement<vscode.Uri>[]): void {
		const key = JSON.stringify(placements.map(({ uri, line, text }) => [uri.toString(), line, text]));
		if (this.shown.get(owner)?.key === key) {
			return;
		}
		this.clear(owner);
		if (!placements.length) {
			return;
		}
		this.shown.set(owner, { key, threads: placements.map(placement => this.createThread(placement)) });
	}

	clear(owner: unknown): void {
		this.shown.get(owner)?.threads.forEach(thread => thread.dispose());
		this.shown.delete(owner);
	}

	dispose(): void {
		[...this.shown.keys()].forEach(owner => this.clear(owner));
		this.controller.dispose();
	}

	private createThread({ uri, line, text }: AnnotationPlacement<vscode.Uri>): vscode.Disposable {
		const comment: vscode.Comment = {
			body: new vscode.MarkdownString(text),
			mode: vscode.CommentMode.Preview,
			author: { name: ANNOTATION_AUTHOR },
		};
		const thread = this.controller.createCommentThread(uri, new vscode.Range(line, 0, line, 0), [comment]);
		thread.canReply = false;
		thread.label = 'codetaster annotation';
		thread.collapsibleState = vscode.CommentThreadCollapsibleState.Expanded;
		return thread;
	}
}
