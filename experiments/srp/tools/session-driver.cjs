// Single-session supervisor. Preparation never invokes the explicit execution switch.
const fs = require('node:fs');
const { spawn } = require('node:child_process');
if (!process.argv.includes('--execute-approved-session')) {
  console.error('Execution disabled. A separately authorized benchmark session requires --execute-approved-session.');
  process.exit(2);
}
const token = fs.readFileSync('/control/driver-token', 'utf8').trim();
const prompt = fs.readFileSync('/control/task.txt', 'utf8');
if (token.length < 32 || !prompt.trim()) throw new Error('Missing session inputs');
const stdout = fs.openSync('/control/events.jsonl', 'wx', 0o600);
const stderr = fs.openSync('/control/stderr.log', 'wx', 0o600);
const start = process.hrtime.bigint(); let timedOut = false; let hardKill;
const child = spawn('codex', ['--no-daemon', 'exec', '--json', '--ignore-rules', '--color', 'never', '--model', 'gpt-6-sol', '-'], {
  cwd: '/workspace/packages/hoppscotch-backend', detached: true,
  env: { ...process.env, BENCHMARK_DRIVER_TOKEN: token }, stdio: ['pipe',stdout,stderr],
});
child.stdin.end(prompt);
const killGroup = signal => { try { process.kill(-child.pid, signal); } catch (error) { if (error.code !== 'ESRCH') throw error; } };
const deadline = setTimeout(() => { timedOut = true; killGroup('SIGTERM'); hardKill = setTimeout(() => killGroup('SIGKILL'), 10000); }, 1800000);
child.on('error', () => { clearTimeout(deadline); fs.writeFileSync('/control/termination.json', JSON.stringify({ outcome:'launcher-failure' })+'\n'); process.exitCode=1; });
child.on('exit', (code,signal) => {
  clearTimeout(deadline); clearTimeout(hardKill);
  // Stop any remaining command descendants before grading outside this container.
  killGroup('SIGKILL'); fs.closeSync(stdout);fs.closeSync(stderr);
  fs.writeFileSync('/control/termination.json', JSON.stringify({ code,signal,timed_out:timedOut,agent_budget_seconds:1800,elapsed_seconds:Number(process.hrtime.bigint()-start)/1e9 })+'\n');
  process.exitCode=timedOut?124:(code ?? 1);
});
