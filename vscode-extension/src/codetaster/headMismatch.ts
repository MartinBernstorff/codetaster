function shortSha(commit: string): string {
	return commit.slice(0, 7);
}

/**
 * A warning when codetaster checked a different commit than the PR's head, e.g. when
 * the sidebar lists a PR that is not the one checked out. Absent when the commits match
 * or the PR head is unknown.
 */
export function headMismatchWarning(checkedHead: string, pullRequestHead: string | undefined): string | undefined {
	if (pullRequestHead === undefined || checkedHead.toLowerCase() === pullRequestHead.toLowerCase()) {
		return undefined;
	}
	return `codetaster grouped files for ${shortSha(checkedHead)}, not the PR head ${shortSha(pullRequestHead)}`;
}
