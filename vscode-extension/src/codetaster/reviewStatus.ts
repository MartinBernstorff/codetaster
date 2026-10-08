/** Where a repository's search for its branch's pull request stands, while no pull request is shown. */
export type RepositoryReviewStatus =
	| { readonly kind: 'loading' }
	| { readonly kind: 'signedOut' }
	| { readonly kind: 'noGitHubRemote' }
	| { readonly kind: 'noPullRequest', readonly branch: string | undefined }
	| { readonly kind: 'branchIgnored', readonly branch: string }
	| { readonly kind: 'pullRequestUnavailable', readonly number: number }
	| { readonly kind: 'pullRequestClosed', readonly number: number }
	| { readonly kind: 'pullRequestMerged', readonly number: number };

export interface ChangesViewWorkspace {
	readonly hasFolders: boolean;
	/** Whether git has finished looking for repositories. */
	readonly gitInitialized: boolean;
	readonly openRepositoryCount: number;
	/** The repositories set up for review so far. */
	readonly repositories: readonly {
		readonly name: string,
		readonly status: RepositoryReviewStatus,
		/** Whether the repository is signed in to GitHub now, which may be newer than its status. */
		readonly signedIn: boolean,
	}[];
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

type SettledReviewStatus = Exclude<RepositoryReviewStatus, { kind: 'loading' }>;

function statusText(status: SettledReviewStatus): string {
	switch (status.kind) {
		case 'signedOut': return "Sign in to GitHub to find this branch's pull request.";
		case 'noGitHubRemote': return 'No GitHub remote for this repository.';
		case 'noPullRequest': return status.branch ? `No open pull request for branch ${status.branch}.` : 'No open pull request for this branch.';
		case 'branchIgnored': return `Branch ${status.branch} is in githubPullRequests.ignoredPullRequestBranches.`;
		case 'pullRequestUnavailable': return `Could not load pull request #${status.number}.`;
		case 'pullRequestClosed': return `Pull request #${status.number} is closed.`;
		case 'pullRequestMerged': return `Pull request #${status.number} is merged.`;
	}
}

export function changesViewContent(workspace: ChangesViewWorkspace): ChangesViewContent {
	if (!workspace.hasFolders || (workspace.gitInitialized && workspace.openRepositoryCount === 0)) {
		return { kind: 'welcome' };
	}
	// A repository that has just signed in is looking for its pull request again.
	const statuses = workspace.repositories.map(({ name, status, signedIn }) => ({
		name,
		status: status.kind === 'signedOut' && signedIn ? { kind: 'loading' } as const : status,
	}));
	const settled: { name: string, status: SettledReviewStatus }[] = [];
	for (const { name, status } of statuses) {
		if (status.kind === 'loading') {
			return { kind: 'skeleton' };
		}
		settled.push({ name, status });
	}
	if (settled.length === 0) {
		return { kind: 'skeleton' };
	}
	if (settled.every(({ status }) => status.kind === 'signedOut')) {
		return { kind: 'welcome' };
	}
	const messages = settled.map(({ name, status }) => {
		const text = statusText(status);
		return { text: settled.length > 1 ? `${name}: ${text}` : text, signIn: status.kind === 'signedOut' };
	});
	return { kind: 'messages', messages };
}

/** Whether two statuses say the same. */
export function isSameReviewStatus(a: RepositoryReviewStatus | undefined, b: RepositoryReviewStatus): boolean {
	return JSON.stringify(a) === JSON.stringify(b);
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
