/** Where a repository's search for its branch's pull request stands, while no pull request is shown. */
export type RepositoryReviewStatus =
	| { readonly kind: 'loading' }
	| { readonly kind: 'signedOut' }
	| { readonly kind: 'noGitHubRemote' }
	| { readonly kind: 'noPullRequest', readonly branch: string | undefined }
	| { readonly kind: 'pullRequestClosed', readonly number: number }
	| { readonly kind: 'pullRequestMerged', readonly number: number };

export interface ChangesViewWorkspace {
	readonly hasFolders: boolean;
	/** Whether git has finished looking for repositories. */
	readonly gitInitialized: boolean;
	readonly openRepositoryCount: number;
	/** The repositories set up for review so far. */
	readonly repositories: readonly { readonly name: string, readonly status: RepositoryReviewStatus }[];
}

export interface ChangesViewMessage {
	readonly text: string;
	/** Whether the message offers to sign in to GitHub. */
	readonly signIn: boolean;
}

/**
 * What the changes view shows while no pull request is in it. The welcome content in
 * package.json explains the workspace-wide cases: no folder, no git repository, and
 * signed out of GitHub.
 */
export type ChangesViewContent =
	| { readonly kind: 'skeleton' }
	| { readonly kind: 'messages', readonly messages: readonly ChangesViewMessage[] }
	| { readonly kind: 'welcome' };

function statusText(status: Exclude<RepositoryReviewStatus, { kind: 'loading' }>): string {
	switch (status.kind) {
		case 'signedOut': return "Sign in to GitHub to find this branch's pull request.";
		case 'noGitHubRemote': return 'No GitHub remote for this repository.';
		case 'noPullRequest': return status.branch ? `No open pull request for branch ${status.branch}.` : 'No open pull request for this branch.';
		case 'pullRequestClosed': return `Pull request #${status.number} is closed.`;
		case 'pullRequestMerged': return `Pull request #${status.number} is merged.`;
	}
}

export function changesViewContent(workspace: ChangesViewWorkspace): ChangesViewContent {
	if (!workspace.hasFolders || (workspace.gitInitialized && workspace.openRepositoryCount === 0)) {
		return { kind: 'welcome' };
	}
	const { repositories } = workspace;
	if (repositories.length === 0 || repositories.some(repository => repository.status.kind === 'loading')) {
		return { kind: 'skeleton' };
	}
	if (repositories.every(repository => repository.status.kind === 'signedOut')) {
		return { kind: 'welcome' };
	}
	const messages = repositories.map(({ name, status }) => {
		const text = statusText(status as Exclude<RepositoryReviewStatus, { kind: 'loading' }>);
		return { text: repositories.length > 1 ? `${name}: ${text}` : text, signIn: status.kind === 'signedOut' };
	});
	return { kind: 'messages', messages };
}

/** Why a repository whose branch has no pull request shows none. */
export function reviewStatusWithoutPullRequest(repository: { hasGitHubRemote: boolean, signedIn: boolean, branch: string | undefined }): RepositoryReviewStatus {
	if (!repository.hasGitHubRemote) {
		return { kind: 'noGitHubRemote' };
	}
	if (!repository.signedIn) {
		return { kind: 'signedOut' };
	}
	return { kind: 'noPullRequest', branch: repository.branch };
}
