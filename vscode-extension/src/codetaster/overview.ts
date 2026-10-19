import { OverviewReport } from './checkReport';

/** The overview page: the PR summary, then each category and its description, in the overview's order. */
export function overviewMarkdown(overview: OverviewReport): string {
	return [
		'# Summary',
		overview.summary,
		'# Categories',
		...overview.categories.flatMap(category => [`## ${category.name}`, category.description]),
	].join('\n\n') + '\n';
}
