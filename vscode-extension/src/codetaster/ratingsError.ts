/**
 * A warning when codetaster ignored an invalid ratings file, from the report's
 * `ratings_error`. Absent when the file is valid or missing.
 */
export function ratingsErrorWarning(ratingsError: string | null | undefined): string | undefined {
	if (ratingsError === null || ratingsError === undefined) {
		return undefined;
	}
	return `codetaster ignored the ratings file, so every file is unrated: ${ratingsError}`;
}
