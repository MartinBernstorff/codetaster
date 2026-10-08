import * as vscode from 'vscode';
import { changesViewContent, RepositoryReviewStatus, reviewStatusWithoutPullRequest } from './reviewStatus';
import { codetasterSkeletonNodes } from './verdictGroupNodes';
import { GitApiImpl } from '../api/api1';
import { FolderRepositoryManager, ReposManagerState } from '../github/folderRepositoryManager';
import { RepositoriesManager } from '../github/repositoriesManager';
import { TreeNode, TreeNodeParent } from '../view/treeNodes/treeNode';

/** Each repository's review status, as its review manager last reported it. */
const reviewStatuses = new WeakMap<FolderRepositoryManager, RepositoryReviewStatus>();

export function setReviewStatus(folderRepoManager: FolderRepositoryManager, status: RepositoryReviewStatus): void {
	reviewStatuses.set(folderRepoManager, status);
}

/** Why `folderRepoManager`'s branch shows no pull request: no GitHub remote, signed out, or none found. */
export async function reviewStatusWithoutPullRequestFor(folderRepoManager: FolderRepositoryManager): Promise<RepositoryReviewStatus> {
	return reviewStatusWithoutPullRequest({
		hasGitHubRemote: (await folderRepoManager.getAllGitHubRemotes()).length > 0,
		signedIn: folderRepoManager.state !== ReposManagerState.NeedsAuthentication,
		branch: folderRepoManager.repository.state.HEAD?.name,
	});
}

export class CodetasterMessageNode extends TreeNode implements vscode.TreeItem {
	public readonly iconPath: vscode.ThemeIcon;
	public readonly command: vscode.Command | undefined;

	constructor(parent: TreeNodeParent, text: string, signIn: boolean) {
		super(parent);
		this.label = text;
		this.iconPath = new vscode.ThemeIcon(signIn ? 'sign-in' : 'info');
		this.command = signIn ? { title: 'Sign in', command: 'pr.signin' } : undefined;
	}

	getTreeItem(): vscode.TreeItem {
		return this;
	}
}

function repositoryName(folderRepoManager: FolderRepositoryManager): string {
	return folderRepoManager.repository.rootUri.path.split('/').pop() ?? folderRepoManager.repository.rootUri.path;
}

/**
 * The changes view's children while it shows no pull request: the verdict groups'
 * skeleton while pull requests are looked up, then why there is nothing to review.
 * Empty when the view's welcome content explains it instead.
 */
export function codetasterNoPullRequestNodes(parent: TreeNodeParent, git: GitApiImpl, reposManager: RepositoriesManager): TreeNode[] {
	const content = changesViewContent({
		hasFolders: (vscode.workspace.workspaceFolders?.length ?? 0) > 0,
		gitInitialized: git.state === 'initialized',
		openRepositoryCount: git.repositories.length,
		repositories: reposManager.folderManagers.map(folderRepoManager => ({
			name: repositoryName(folderRepoManager),
			status: reviewStatuses.get(folderRepoManager) ?? { kind: 'loading' },
		})),
	});
	switch (content.kind) {
		case 'skeleton': return codetasterSkeletonNodes(parent);
		case 'messages': return content.messages.map(message => new CodetasterMessageNode(parent, message.text, message.signIn));
		case 'welcome': return [];
	}
}
