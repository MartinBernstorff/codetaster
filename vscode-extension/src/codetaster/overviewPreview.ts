import * as vscode from 'vscode';
import { OverviewReport } from './checkReport';
import { overviewMarkdown } from './overview';
import { TreeNode, TreeNodeParent } from '../view/treeNodes/treeNode';

const OVERVIEW_SCHEME = 'codetaster-overview';
export const OPEN_OVERVIEW_COMMAND = 'codetaster.openOverview';

/** Serves each PR's overview page, as Markdown, from the latest check report. */
class OverviewDocuments implements vscode.TextDocumentContentProvider {
	private readonly _pages = new Map<string, string>();
	private readonly _onDidChange = new vscode.EventEmitter<vscode.Uri>();
	readonly onDidChange = this._onDidChange.event;

	provideTextDocumentContent(uri: vscode.Uri): string {
		return this._pages.get(uri.toString()) ?? '';
	}

	/** Shows `overview` at `uri`, updating an open preview if it changed. */
	show(uri: vscode.Uri, overview: OverviewReport): void {
		const page = overviewMarkdown(overview);
		if (this._pages.get(uri.toString()) !== page) {
			this._pages.set(uri.toString(), page);
			this._onDidChange.fire(uri);
		}
	}

	dispose(): void {
		this._onDidChange.dispose();
	}
}

const overviewDocuments = new OverviewDocuments();

/** Overview pages already opened this session, so each opens by itself only once. */
const openedOverviews = new Set<string>();

/** The overview page of PR `pullRequestNumber` in the checkout at `checkout`. */
function overviewUri(checkout: string, pullRequestNumber: number): vscode.Uri {
	return vscode.Uri.from({ scheme: OVERVIEW_SCHEME, path: `/PR #${pullRequestNumber} overview.md`, query: checkout });
}

async function openOverview(uri: vscode.Uri): Promise<void> {
	await vscode.commands.executeCommand('markdown.showPreview', uri);
}

export function registerOverviewPreview(context: vscode.ExtensionContext): void {
	context.subscriptions.push(
		overviewDocuments,
		vscode.workspace.registerTextDocumentContentProvider(OVERVIEW_SCHEME, overviewDocuments),
		vscode.commands.registerCommand(OPEN_OVERVIEW_COMMAND, openOverview),
	);
}

/** Opens the PR summary and the category descriptions. */
export class CodetasterSummaryNode extends TreeNode implements vscode.TreeItem {
	public readonly iconPath = new vscode.ThemeIcon('book');
	public readonly tooltip: vscode.MarkdownString;
	public readonly command: vscode.Command;

	constructor(parent: TreeNodeParent, uri: vscode.Uri, overview: OverviewReport) {
		super(parent);
		this.label = 'Summary';
		this.tooltip = new vscode.MarkdownString(overview.summary);
		this.command = { title: 'Open Summary', command: OPEN_OVERVIEW_COMMAND, arguments: [uri] };
	}

	getTreeItem(): vscode.TreeItem {
		return this;
	}
}

/**
 * The node for the overview of PR `pullRequestNumber`. Updates its page, and opens it
 * the first time this session that the PR has an overview.
 */
export function summaryNode(parent: TreeNodeParent, checkout: string, pullRequestNumber: number, overview: OverviewReport): CodetasterSummaryNode {
	const uri = overviewUri(checkout, pullRequestNumber);
	overviewDocuments.show(uri, overview);
	if (!openedOverviews.has(uri.toString())) {
		openedOverviews.add(uri.toString());
		void openOverview(uri);
	}
	return new CodetasterSummaryNode(parent, uri, overview);
}
