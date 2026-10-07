import * as vscode from 'vscode';
import { CheckReport } from './checkReport';
import { CodetasterChecks } from './codetasterCheck';
import { fileDescription, fileHover, fileReportsByPath } from './fileRatings';
import { headMismatchWarning } from './headMismatch';
import { NodeCodetasterProcess } from './nodeCodetasterProcess';
import { ratingsErrorWarning } from './ratingsError';
import { groupFilesByVerdict, VerdictGroup } from './verdictGroups';
import { findLocalRepoRemoteFromGitHubRef } from '../common/githubRef';
import { disposeAll } from '../common/lifecycle';
import { compareIgnoreCase } from '../common/utils';
import { FolderRepositoryManager } from '../github/folderRepositoryManager';
import { PullRequestModel } from '../github/pullRequestModel';
import { DirectoryTreeNode } from '../view/treeNodes/directoryTreeNode';
import { GitFileChangeNode, InMemFileChangeNode, RemoteFileChangeNode } from '../view/treeNodes/fileChangeNode';
import { TreeNode, TreeNodeParent } from '../view/treeNodes/treeNode';

export const CODETASTER_SETTINGS_NAMESPACE = 'codetaster';
export const EXECUTABLE_PATH_SETTING = 'executablePath';
export const REFRESH_CHECK_COMMAND = 'codetaster.refreshCheck';

type PullRequestFileNode = GitFileChangeNode | RemoteFileChangeNode | InMemFileChangeNode;

function configuredExecutablePath(): string {
	return vscode.workspace.getConfiguration(CODETASTER_SETTINGS_NAMESPACE).get<string>(EXECUTABLE_PATH_SETTING) || 'codetaster';
}

export const codetasterChecks = new CodetasterChecks(new NodeCodetasterProcess(), configuredExecutablePath);

export function registerCodetaster(context: vscode.ExtensionContext): void {
	context.subscriptions.push(
		vscode.commands.registerCommand(REFRESH_CHECK_COMMAND, () => codetasterChecks.refresh()),
		vscode.workspace.onDidChangeConfiguration(e => {
			if (e.affectsConfiguration(`${CODETASTER_SETTINGS_NAMESPACE}.${EXECUTABLE_PATH_SETTING}`)) {
				codetasterChecks.refresh();
			}
		}),
	);
}

/** Lays out files as upstream's PR file lists do, for the `fileListLayout` setting. */
function fileListNodes(parent: TreeNode, files: readonly PullRequestFileNode[], layout: string | undefined): TreeNode[] {
	if (layout === 'tree') {
		const dirNode = new DirectoryTreeNode(parent, '');
		files.forEach(file => dirNode.addFile(file));
		dirNode.finalize();
		if (dirNode.label !== '') {
			return [dirNode];
		}
		// Nothing changed at the root: pull the children up to the parent.
		dirNode._children.forEach(child => { child.parent = parent; });
		return dirNode._children;
	}
	const sorted = [...files].sort((a, b) => compareIgnoreCase(a.fileChangeResourceUri.toString(), b.fileChangeResourceUri.toString()));
	// Keep parent pointers aligned with the rendered tree, so reveal/getParent work.
	sorted.forEach(file => { file.parent = parent; });
	return sorted;
}

export class VerdictGroupNode extends TreeNode implements vscode.TreeItem {
	public collapsibleState: vscode.TreeItemCollapsibleState;
	public readonly contextValue: string;

	constructor(parent: TreeNodeParent, group: VerdictGroup<PullRequestFileNode>, layout: string | undefined) {
		super(parent);
		this.label = group.label;
		this.contextValue = `codetaster:verdictGroup:${group.verdict}`;
		this._children = fileListNodes(this, group.files, layout);
		this.collapsibleState = group.files.length
			? vscode.TreeItemCollapsibleState.Expanded
			: vscode.TreeItemCollapsibleState.None;
	}

	getTreeItem(): vscode.TreeItem {
		return this;
	}

	override async getChildren(): Promise<TreeNode[]> {
		return this._children ?? [];
	}

	override dispose(): void {
		super.dispose();
		disposeAll(this._children ?? []);
	}
}

export class CodetasterErrorNode extends TreeNode implements vscode.TreeItem {
	public readonly iconPath = new vscode.ThemeIcon('error', new vscode.ThemeColor('errorForeground'));
	public readonly tooltip: string;

	constructor(parent: TreeNodeParent, message: string) {
		super(parent);
		this.label = `codetaster: ${message}`;
		this.tooltip = message;
	}

	getTreeItem(): vscode.TreeItem {
		return this;
	}
}

interface UpstreamFileNodeItem {
	readonly tooltip: string;
	readonly description: string | boolean | undefined;
}

/** Each file node's tooltip and description as upstream set them, before codetaster's. */
const upstreamFileNodeItems = new WeakMap<PullRequestFileNode, UpstreamFileNodeItem>();

function upstreamFileNodeItem(file: PullRequestFileNode): UpstreamFileNodeItem {
	let item = upstreamFileNodeItems.get(file);
	if (!item) {
		item = { tooltip: file.tooltip, description: file.description };
		upstreamFileNodeItems.set(file, item);
	}
	return item;
}

function directoryOf(fileName: string): string {
	const separator = fileName.lastIndexOf('/');
	return separator === -1 ? '' : fileName.slice(0, separator);
}

/**
 * Shows each file's codetaster probability and AI reason on hover, and marks unrated
 * files in their description. Nodes can be reused across check runs, so this starts
 * from upstream's values each time.
 */
function showFileRatings(report: CheckReport, files: readonly PullRequestFileNode[]): void {
	const reports = fileReportsByPath(report);
	for (const file of files) {
		const upstream = upstreamFileNodeItem(file);
		const fileReport = reports.get(file.fileName);
		// Upstream's `tooltip` is a getter; an own property shadows it without editing upstream.
		Object.defineProperty(file, 'tooltip', {
			value: fileHover(upstream.tooltip, fileReport),
			configurable: true,
			enumerable: true,
			writable: true,
		});
		file.description = fileDescription(upstream.description, directoryOf(file.fileName), fileReport);
	}
}

export class CodetasterWarningNode extends TreeNode implements vscode.TreeItem {
	public readonly iconPath = new vscode.ThemeIcon('warning', new vscode.ThemeColor('problemsWarningIcon.foreground'));
	public readonly tooltip: string;

	constructor(parent: TreeNodeParent, message: string) {
		super(parent);
		this.label = message;
		this.tooltip = message;
	}

	getTreeItem(): vscode.TreeItem {
		return this;
	}
}

function pullRequestHead(files: readonly PullRequestFileNode[]): string | undefined {
	return files[0]?.pullRequest.head?.sha;
}

function fileListKey(files: readonly PullRequestFileNode[]): string {
	return JSON.stringify([pullRequestHead(files) ?? '', files.map(file => file.fileName).sort()]);
}

/** The PR's base branch as the checkout knows it: the remote-tracking branch, if a remote points at the base repository. */
function baseRevision(folderRepoManager: FolderRepositoryManager, pullRequest: PullRequestModel): string {
	const remote = findLocalRepoRemoteFromGitHubRef(folderRepoManager.repository, pullRequest.base);
	return remote ? `${remote.name}/${pullRequest.base.ref}` : pullRequest.base.ref;
}

/**
 * The children of a PR file list if the PR is checked out: one node per codetaster
 * verdict group, each holding its files in the configured layout, or an error and no
 * files if the check fails. Warnings precede the groups when the check ran on a
 * different commit than the PR head, or ignored an invalid ratings file. Undefined if the PR is not checked out, so the
 * caller shows upstream's file list.
 * `allFiles` is the PR's whole file list, which decides when the check re-runs;
 * `shownFiles` are the ones to show, e.g. without viewed files.
 */
export async function codetasterFileNodes(
	parent: TreeNode,
	folderRepoManager: FolderRepositoryManager,
	pullRequest: PullRequestModel,
	allFiles: readonly PullRequestFileNode[],
	shownFiles: readonly PullRequestFileNode[],
	layout: string | undefined,
): Promise<TreeNode[] | undefined> {
	const isCheckedOut = pullRequest.equals(folderRepoManager.activePullRequest);
	const outcome = await codetasterChecks.checkFor({
		checkout: isCheckedOut ? folderRepoManager.repository.rootUri.fsPath : undefined,
		base: baseRevision(folderRepoManager, pullRequest),
		fileListKey: fileListKey(allFiles),
	});
	if (!outcome) {
		return undefined;
	}
	if (outcome.kind === 'error') {
		return [new CodetasterErrorNode(parent, outcome.message)];
	}
	showFileRatings(outcome.report, shownFiles);
	const groups = groupFilesByVerdict(outcome.report, shownFiles, file => file.fileName)
		.map(group => new VerdictGroupNode(parent, group, layout));
	const warnings = [
		headMismatchWarning(outcome.report.head.commit, pullRequestHead(allFiles)),
		ratingsErrorWarning(outcome.report.ratings_error),
	].filter((warning): warning is string => warning !== undefined);
	return [...warnings.map(warning => new CodetasterWarningNode(parent, warning)), ...groups];
}
