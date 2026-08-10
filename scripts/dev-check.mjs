#!/usr/bin/env node
/** Quick preflight: required tooling versions for local development. */
import { execSync } from 'node:child_process';

const checks = [
  ['node', 'node -v'],
  ['npm', 'npm -v'],
  ['python', 'python --version'],
];

let ok = true;
for (const [name, cmd] of checks) {
  try {
    const out = execSync(cmd, { encoding: 'utf8' }).trim();
    console.log(`✓ ${name}: ${out}`);
  } catch {
    console.error(`✗ ${name}: not found`);
    ok = false;
  }
}

try {
  const out = execSync('docker --version', { encoding: 'utf8' }).trim();
  console.log(`✓ docker: ${out}`);
} catch {
  console.warn('⚠ docker: not found (optional for pure local API/web; required for full stack)');
}

process.exit(ok ? 0 : 1);
