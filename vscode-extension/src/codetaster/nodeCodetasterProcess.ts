import * as childProcess from 'child_process';
import { Readable } from 'stream';
import { CodetasterProcess, ProcessOutcome } from './codetasterCheck';

/** Runs codetaster as a local process. In the web extension host, child_process is empty and every run fails to start. */
export class NodeCodetasterProcess implements CodetasterProcess {
	runCodetaster(executable: string, args: readonly string[], cwd: string): Promise<ProcessOutcome> {
		return new Promise(resolve => {
			const stdout: Buffer[] = [];
			const stderr: Buffer[] = [];
			let child: childProcess.ChildProcessByStdio<null, Readable, Readable>;
			try {
				child = childProcess.spawn(executable, args, { cwd, stdio: ['ignore', 'pipe', 'pipe'] });
			} catch (error) {
				resolve({ kind: 'failedToStart', message: error instanceof Error ? error.message : String(error) });
				return;
			}
			child.stdout.on('data', (chunk: Buffer) => stdout.push(chunk));
			child.stderr.on('data', (chunk: Buffer) => stderr.push(chunk));
			// A failed spawn emits 'error' and may then emit 'close'; the first event wins.
			child.on('error', error => resolve({ kind: 'failedToStart', message: error.message }));
			child.on('close', (exitCode, signal) => resolve({
				kind: 'exited',
				exitCode: exitCode ?? -1,
				stdout: Buffer.concat(stdout).toString('utf8'),
				stderr: Buffer.concat(stderr).toString('utf8') + (signal ? `Killed by ${signal}.` : ''),
			}));
		});
	}
}
