import * as assert from 'assert';
import { describe, it } from 'mocha';
import { changesViewContent, ChangesViewWorkspace, RepositoryReviewStatus, reviewStatusWithoutPullRequest } from './reviewStatus';

function workspace(overrides: Partial<ChangesViewWorkspace> = {}): ChangesViewWorkspace {
	return { hasFolders: true, gitInitialized: true, openRepositoryCount: 1, repositories: [], ...overrides };
}

function repository(status: RepositoryReviewStatus, name = 'codetaster') {
	return { name, status, signedIn: status.kind !== 'signedOut' };
}

describe('changesViewContent', () => {
	it('leaves a workspace without folders to the welcome message', () => {
		assert.deepStrictEqual(changesViewContent(workspace({ hasFolders: false })), { kind: 'welcome' });
	});

	it('leaves a workspace without git repositories to the welcome message', () => {
		assert.deepStrictEqual(changesViewContent(workspace({ openRepositoryCount: 0 })), { kind: 'welcome' });
	});

	it('shows the skeleton while git is still looking for repositories', () => {
		assert.deepStrictEqual(changesViewContent(workspace({ gitInitialized: false, openRepositoryCount: 0 })), { kind: 'skeleton' });
	});

	it('shows the skeleton while a repository is not yet set up', () => {
		assert.deepStrictEqual(changesViewContent(workspace()), { kind: 'skeleton' });
	});

	it('shows the skeleton while any repository is still looking for its pull request', () => {
		const repositories = [repository({ kind: 'noPullRequest', branch: 'main' }, 'a'), repository({ kind: 'loading' }, 'b')];
		assert.deepStrictEqual(changesViewContent(workspace({ openRepositoryCount: 2, repositories })), { kind: 'skeleton' });
	});

	it('leaves signing in to the welcome message when every repository needs it', () => {
		assert.deepStrictEqual(changesViewContent(workspace({ repositories: [repository({ kind: 'signedOut' })] })), { kind: 'welcome' });
	});

	it('shows the skeleton once a signed-out repository signs in', () => {
		const repositories = [{ ...repository({ kind: 'signedOut' }), signedIn: true }];
		assert.deepStrictEqual(changesViewContent(workspace({ repositories })), { kind: 'skeleton' });
	});

	it('says why there is nothing to review', () => {
		const cases: [RepositoryReviewStatus, string][] = [
			[{ kind: 'noGitHubRemote' }, 'No GitHub remote for this repository.'],
			[{ kind: 'noPullRequest', branch: 'feature' }, 'No open pull request for branch feature.'],
			[{ kind: 'noPullRequest', branch: undefined }, 'No open pull request for this branch.'],
			[{ kind: 'pullRequestClosed', number: 7 }, 'Pull request #7 is closed.'],
			[{ kind: 'pullRequestMerged', number: 7 }, 'Pull request #7 is merged.'],
			[{ kind: 'branchIgnored', branch: 'main' }, 'Branch main is in githubPullRequests.ignoredPullRequestBranches.'],
			[{ kind: 'pullRequestUnavailable', number: 7 }, 'Could not load pull request #7.'],
		];
		for (const [status, text] of cases) {
			assert.deepStrictEqual(
				changesViewContent(workspace({ repositories: [repository(status)] })),
				{ kind: 'messages', messages: [{ text, signIn: false }] },
			);
		}
	});

	it('names each repository when there are several, with a sign-in action where needed', () => {
		const repositories = [repository({ kind: 'signedOut' }, 'a'), repository({ kind: 'noPullRequest', branch: 'main' }, 'b')];
		assert.deepStrictEqual(changesViewContent(workspace({ openRepositoryCount: 2, repositories })), {
			kind: 'messages',
			messages: [
				{ text: "a: Sign in to GitHub to find this branch's pull request.", signIn: true },
				{ text: 'b: No open pull request for branch main.', signIn: false },
			],
		});
	});
});

describe('reviewStatusWithoutPullRequest', () => {
	it('blames a missing GitHub remote before signing in', () => {
		assert.deepStrictEqual(reviewStatusWithoutPullRequest({ hasGitHubRemote: false, signedIn: false, branch: 'main' }), { kind: 'noGitHubRemote' });
	});

	it('asks to sign in when the repository has a GitHub remote', () => {
		assert.deepStrictEqual(reviewStatusWithoutPullRequest({ hasGitHubRemote: true, signedIn: false, branch: 'main' }), { kind: 'signedOut' });
	});

	it('reports the branch has no pull request otherwise', () => {
		assert.deepStrictEqual(reviewStatusWithoutPullRequest({ hasGitHubRemote: true, signedIn: true, branch: 'main' }), { kind: 'noPullRequest', branch: 'main' });
	});
});
