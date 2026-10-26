import * as vscode from 'vscode';
import { DimmedLines, DimmedLinesSet } from './hunkDimming';
import { PullRequestModel } from '../github/pullRequestModel';

/** How much of a dimmed line the editor background covers. */
const DIMMED_COVERAGE = '60%';

/**
 * A pane of the editor background over each dimmed line, through the CSS of an empty
 * attachment before the line, as the decoration API cannot otherwise draw above text.
 * It covers both the text and the diff's red and green backgrounds, which are drawn
 * above any background color a decoration sets. It does not catch the pointer, and the
 * cursor and the gutter are drawn above it.
 */
const DIMMED_LINE_COVER: vscode.ThemableDecorationAttachmentRenderOptions = {
	contentText: ' ',
	textDecoration: [
		'none',
		'position: absolute',
		'inset: 0',
		'pointer-events: none',
		`background-color: color-mix(in srgb, var(--vscode-editor-background) ${DIMMED_COVERAGE}, transparent)`,
	].join('; '),
};

/**
 * Dims the hunks of needs-review files that are rated below the needs-review threshold,
 * in every visible editor showing a document of their diffs. Each owner, e.g. a
 * repository, shows the lines of the pull request it has checked out, merged from every
 * file list that shows it (see `DimmedLinesSet`).
 */
export class HunkDimmingDecorations implements vscode.Disposable {
	private readonly decorationType = vscode.window.createTextEditorDecorationType({ before: DIMMED_LINE_COVER });
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
			// The cover is positioned in the line, so each line needs its own.
			// Lines past the end of the document are left out.
			const ranges = (byUri.get(document.uri.toString()) ?? [])
				.flatMap(({ firstLine, lastLine }) => linesBetween(firstLine, Math.min(lastLine, document.lineCount - 1)))
				.map(line => new vscode.Range(line, 0, line, 0));
			editor.setDecorations(this.decorationType, ranges);
		}
	}
}

function linesBetween(firstLine: number, lastLine: number): number[] {
	return Array.from({ length: Math.max(lastLine - firstLine + 1, 0) }, (_, index) => firstLine + index);
}
