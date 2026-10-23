import * as vscode from 'vscode';
import { AnnotationPlacement, AnnotationThreadSet } from './annotationThreads';
import { PullRequestModel } from '../github/pullRequestModel';

/** Not matched by upstream's `commentController =~ /^github-(browse|review)/` menus, so no reply, resolve or edit actions. */
const ANNOTATIONS_CONTROLLER_ID = 'codetaster-annotations';
const ANNOTATION_AUTHOR = 'codetaster';

/**
 * Shows the ratings file's annotations as read-only comment threads, authored by
 * "codetaster", initially expanded. They have no commenting ranges, so nothing can be
 * added to them, and they are never sent to GitHub.
 * Each owner, e.g. a repository, shows the annotations of the pull request it has
 * checked out, merged from every file list that shows it (see `AnnotationThreadSet`).
 */
export class AnnotationComments implements vscode.Disposable {
	private readonly controller = vscode.comments.createCommentController(ANNOTATIONS_CONTROLLER_ID, 'codetaster annotations');
	private readonly threads = new AnnotationThreadSet<PullRequestModel, vscode.Uri, vscode.Disposable>(
		placement => this.createThread(placement),
		uri => uri.toString(),
		(a, b) => a.equals(b),
	);

	show(owner: unknown, pullRequest: PullRequestModel, source: unknown, placements: readonly AnnotationPlacement<vscode.Uri>[]): void {
		this.threads.show(owner, pullRequest, source, placements);
	}

	clearUnlessFor(owner: unknown, checkedOut: PullRequestModel | undefined): void {
		this.threads.clearUnlessFor(owner, checkedOut);
	}

	clear(owner: unknown): void {
		this.threads.clear(owner);
	}

	dispose(): void {
		this.threads.dispose();
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
