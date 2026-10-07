import * as vscode from 'vscode';
import { CheckReport } from './checkReport';
import { CodetasterChecks } from './codetasterCheck';
import { fileDescription, fileHover, fileReportsByPath } from './fileRatings';
import { headMismatchWarning } from './headMismatch';
import { NodeCodetasterProcess } from './nodeCodetasterProcess';
import { ratingsErrorWarning } from './ratingsError';
import { nextFileToReview, OrderedFile, reviewOrder } from './reviewOrder';
import { groupFilesByVerdict, VerdictGroup } from './verdictGroups';
import type { Repository } from '../api/api';
import { ViewedState } from '../common/comment';
import { findLocalRepoRemoteFromGitHubRef } from '../common/githubRef';
import { disposeAll } from '../common/lifecycle';
import { compareIgnoreCase } from '../common/utils';
import { FolderRepositoryManager } from '../github/folderRepositoryManager';
import { PullRequestModel } from '../github/pullRequestModel';
import { DirectoryTreeNode } from '../view/treeNodes/directoryTreeNode';
import { FileChangeNode, GitFileChangeNode, InMemFileChangeNode, RemoteFileChangeNode } from '../view/treeNodes/fileChangeNode';
import { TreeNode, TreeNodeParent } from '../view/treeNodes/treeNode';

export const CODETASTER_SETTINGS_NAMESPACE = 'codetaster';
export const EXECUTABLE_PATH_SETTING = 'executablePath';
export const TOP_RATED_PERCENTAGE_SETTING = 'topRatedPercentage';
export const REFRESH_CHECK_COMMAND = 'codetaster.refreshCheck';
export const SET_TOP_RATED_PERCENTAGE_COMMAND = 'codetaster.setTopRatedPercentage';
export const MARK_VIEWED_AND_OPEN_NEXT_COMMAND = 'codetaster.markViewedAndOpenNext';

type PullRequestFileNode = GitFileChangeNode | RemoteFileChangeNode | InMemFileChangeNode;

function configuredExecutablePath(): string {
	return vscode.workspace.getConfiguration(CODETASTER_SETTINGS_NAMESPACE).get<string>(EXECUTABLE_PATH_SETTING) || 'codetaster';
}

function configuredTopRatedPercentage(): number | undefined {
	return vscode.workspace.getConfiguration(CODETASTER_SETTINGS_NAMESPACE).get<number | null>(TOP_RATED_PERCENTAGE_SETTING) ?? undefined;
}

export const codetasterChecks = new CodetasterChecks(new NodeCodetasterProcess(), configuredExecutablePath);

interface PullRequestReviewOrder {
	readonly folderRepoManager: FolderRepositoryManager;
	readonly pullRequest: PullRequestModel;
	readonly files: readonly OrderedFile<PullRequestFileNode>[];
}

/** The checked-out PR's files in the order the file list shows them, per repository. */
const reviewOrders = new Map<FolderRepositoryManager, PullRequestReviewOrder>();

/** The review orders of PRs that are still checked out. */
function activeReviewOrders(): PullRequestReviewOrder[] {
	return [...reviewOrders.values()].filter(order => order.pullRequest.equals(order.folderRepoManager.activePullRequest));
}

function isViewed(file: PullRequestFileNode): boolean {
	return file.pullRequest.fileChangeViewedState[file.fileName] === ViewedState.VIEWED;
}

/** The URI of the file in the active editor tab, or the modified side of a diff. */
function activeTabUri(): vscode.Uri | undefined {
	const input = vscode.window.tabGroups.activeTabGroup.activeTab?.input;
	if (input instanceof vscode.TabInputTextDiff) {
		return input.modified;
	}
	if (input instanceof vscode.TabInputText) {
		return input.uri;
	}
	return undefined;
}

/** The PR file `uri` shows. Of files whose path `uri` ends with, the longest path wins. */
function fileShownAt(uri: vscode.Uri): { order: PullRequestReviewOrder, path: string } | undefined {
	let found: { order: PullRequestReviewOrder, path: string } | undefined;
	for (const order of activeReviewOrders()) {
		for (const { path } of order.files) {
			if (uri.path.endsWith(`/${path}`) && path.length > (found?.path.length ?? -1)) {
				found = { order, path };
			}
		}
	}
	return found;
}

/**
 * Marks the current PR file as viewed and opens the next file to review, in the order
 * of the codetaster file list. The current file is `node` if given, e.g. from the file
 * list, else the active editor's. Without a current file, opens the first file to review.
 */
async function markViewedAndOpenNext(node: unknown): Promise<void> {
	const tabUri = activeTabUri();
	let current: { order: PullRequestReviewOrder, path: string } | undefined;
	if (node instanceof FileChangeNode) {
		const order = activeReviewOrders().find(candidate => candidate.pullRequest.equals(node.pullRequest));
		current = order && { order, path: node.fileName };
	} else if (tabUri) {
		current = fileShownAt(tabUri);
	}
	const order = current?.order ?? activeReviewOrders()[0];
	if (!order) {
		vscode.window.showInformationMessage('codetaster: check out a pull request to review its files.');
		return;
	}
	const currentFile = order.files.find(entry => entry.path === current?.path)?.file;
	const next = nextFileToReview(order.files, current?.path, file => file === currentFile || isViewed(file));
	try {
		if (next) {
			await next.openDiff(order.folderRepoManager);
		} else {
			vscode.window.showInformationMessage('codetaster: every file to review is viewed.');
		}
		await currentFile?.markFileAsViewed(false);
	} catch (e) {
		vscode.window.showErrorMessage(`codetaster: could not move to the next file: ${e}`);
	}
}

async function setTopRatedPercentage(): Promise<void> {
	const current = configuredTopRatedPercentage();
	const input = await vscode.window.showInputBox({
		title: 'codetaster: top-rated percentage',
		prompt: 'The percentage, from 0 to 100, of changed files with the highest AI ratings that need review. Leave empty to use the project config.',
		value: current === undefined ? '' : String(current),
		validateInput: value => value.trim() === '' || /^(100|[1-9]?[0-9])$/.test(value.trim())
			? undefined
			: 'Enter a whole number from 0 to 100, or nothing.',
	});
	if (input === undefined) {
		return;
	}
	await vscode.workspace.getConfiguration(CODETASTER_SETTINGS_NAMESPACE).update(
		TOP_RATED_PERCENTAGE_SETTING,
		input.trim() === '' ? undefined : Number(input.trim()),
		vscode.ConfigurationTarget.Workspace,
	);
}

/** Where codetaster keeps the ratings file unless `[review] ratings_path` says otherwise. */
const DEFAULT_RATINGS_FILE_GLOB = '**/.codetaster/ratings.json';

const headListeners: vscode.Disposable[] = [];
const repositoriesWatchedForHead = new WeakSet<Repository>();

/** Re-runs the checks when `repository`'s HEAD commit changes, e.g. after a local commit. */
function refreshOnHeadChange(repository: Repository): void {
	if (repositoriesWatchedForHead.has(repository)) {
		return;
	}
	repositoriesWatchedForHead.add(repository);
	let head = repository.state.HEAD?.commit;
	headListeners.push(repository.state.onDidChange(() => {
		const current = repository.state.HEAD?.commit;
		if (current !== head) {
			head = current;
			codetasterChecks.refresh();
		}
	}));
}

export function registerCodetaster(context: vscode.ExtensionContext): void {
	// The ratings file is usually gitignored, so nothing else notices it change.
	const ratingsWatcher = vscode.workspace.createFileSystemWatcher(DEFAULT_RATINGS_FILE_GLOB);
	context.subscriptions.push(
		ratingsWatcher,
		ratingsWatcher.onDidCreate(() => codetasterChecks.refresh()),
		ratingsWatcher.onDidChange(() => codetasterChecks.refresh()),
		ratingsWatcher.onDidDelete(() => codetasterChecks.refresh()),
		{ dispose: () => disposeAll(headListeners) },
		vscode.commands.registerCommand(REFRESH_CHECK_COMMAND, () => codetasterChecks.refresh()),
		vscode.commands.registerCommand(SET_TOP_RATED_PERCENTAGE_COMMAND, setTopRatedPercentage),
		vscode.commands.registerCommand(MARK_VIEWED_AND_OPEN_NEXT_COMMAND, markViewedAndOpenNext),
		vscode.workspace.onDidChangeConfiguration(e => {
			if ([EXECUTABLE_PATH_SETTING, TOP_RATED_PERCENTAGE_SETTING].some(setting => e.affectsConfiguration(`${CODETASTER_SETTINGS_NAMESPACE}.${setting}`))) {
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
		this.collapsibleState = !group.files.length
			? vscode.TreeItemCollapsibleState.None
			: group.collapsed
				? vscode.TreeItemCollapsibleState.Collapsed
				: vscode.TreeItemCollapsibleState.Expanded;
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
		localHead: folderRepoManager.repository.state.HEAD?.commit,
		topRatedPercentage: configuredTopRatedPercentage(),
	});
	if (isCheckedOut) {
		refreshOnHeadChange(folderRepoManager.repository);
	}
	if (!outcome) {
		return undefined;
	}
	if (outcome.kind === 'error') {
		reviewOrders.delete(folderRepoManager);
		return [new CodetasterErrorNode(parent, outcome.message)];
	}
	// From all files, so a viewed file hidden from the list keeps its place.
	reviewOrders.set(folderRepoManager, {
		folderRepoManager,
		pullRequest,
		files: reviewOrder(groupFilesByVerdict(outcome.report, allFiles, file => file.fileName), file => file.fileName, layout),
	});
	showFileRatings(outcome.report, shownFiles);
	const groups = groupFilesByVerdict(outcome.report, shownFiles, file => file.fileName)
		.map(group => new VerdictGroupNode(parent, group, layout));
	const warnings = [
		headMismatchWarning(outcome.report.head.commit, pullRequestHead(allFiles)),
		ratingsErrorWarning(outcome.report.ratings_error),
	].filter((warning): warning is string => warning !== undefined);
	return [...warnings.map(warning => new CodetasterWarningNode(parent, warning)), ...groups];
}
