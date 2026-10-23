import { CheckReport } from './checkReport';
import { fileReportsByPath } from './fileRatings';

/**
 * A PR file and the documents its diff shows, as URIs of type `Uri`. A side is
 * undefined if the file has no such version: no before for an added file, no after
 * for a deleted one.
 */
export interface AnnotatedFile<Uri> {
	readonly path: string;
	readonly beforeUri: Uri | undefined;
	readonly afterUri: Uri | undefined;
}

/** Where to show an annotation as a comment thread. */
export interface AnnotationPlacement<Uri> {
	readonly uri: Uri;
	/** Counting from 0, as editors do. */
	readonly line: number;
	/** Markdown. */
	readonly text: string;
}

/**
 * The annotations of each file's rating, placed on the document of their side.
 * An unrated file, whose rating is for another version, has none. Annotations on a
 * side the file does not have, or on files `files` leaves out, are skipped.
 */
export function annotationPlacements<Uri>(report: CheckReport, files: readonly AnnotatedFile<Uri>[]): AnnotationPlacement<Uri>[] {
	const reports = fileReportsByPath(report);
	return files.flatMap(file => (reports.get(file.path)?.rating?.annotations ?? []).flatMap(annotation => {
		const uri = annotation.side === 'before' ? file.beforeUri : file.afterUri;
		return uri === undefined ? [] : [{ uri, line: annotation.line - 1, text: annotation.text }];
	}));
}
