import * as vscode from 'vscode';
import { DimmedLines, DimmedLinesSet } from './hunkDimming';
import { PullRequestModel } from '../github/pullRequestModel';

/** How opaque the text of a dimmed hunk is. */
const DIMMED_OPACITY = '0.4';

/**
 * Dims the hunks of needs-review files that are rated below the needs-review threshold,
 * in every visible editor showing a document of their diffs. Each owner, e.g. a
 * repository, shows the lines of the pull request it has checked out, merged from every
 * file list that shows it (see `DimmedLinesSet`).
 */
export class HunkDimmingDecorations implements vscode.Disposable {
	private readonly decorationType = vscode.window.createTextEditorDecorationType({ opacity: DIMMED_OPACITY, isWholeLine: true });
	private readonly lines = new DimmedLinesSet<PullRequestModel, vscode.Uri>((a, b) => a.equals(b), () => this.apply());
	private readonly visibleEditorsListener = vscode.window.onDidChangeVisibleTextEditors(() => this.apply());

	show(owner: unknown, pullRequest: PullRequestModel, source: unknown, lines: readonly DimmedLines<vscode.Uri>[]): void {
		this.lines.show(owner, pullRequest, source, lines);
	}

	clearUnlessFor(owner: unknown, checkedOut: PullRequestModel | undefined): void {
		this.lines.clearUnlessFor(owner, checkedOut);
	}

	clear(owner: unknown): void {
		this.lines.clear(owner);
	}

	dispose(): void {
		this.visibleEditorsListener.dispose();
		this.decorationType.dispose();
	}

	private apply(): void {
		const byUri = this.lines.linesByUri(uri => uri.toString());
		for (const editor of vscode.window.visibleTextEditors) {
			const document = editor.document;
			// To the end of the last line, as opacity only applies to the text the range covers.
			// Lines past the end of the document are left out.
			const ranges = (byUri.get(document.uri.toString()) ?? [])
				.filter(({ firstLine }) => firstLine < document.lineCount)
				.map(({ firstLine, lastLine }) => new vscode.Range(
					firstLine, 0, Math.min(lastLine, document.lineCount - 1), Number.MAX_SAFE_INTEGER,
				))
				.map(range => document.validateRange(range));
			editor.setDecorations(this.decorationType, ranges);
		}
	}
}
