import fs from 'node:fs';

const required = [
  'index.html',
  'src/styles.css',
  'src/app.js',
  'src/data.js',
  'docs/ARCHITECTURE.md',
  'docs/RUNBOOK.md',
  'docs/MARKET_BRIEF.md',
  'security/SECURITY_REVIEW.md',
];

for (const file of required) {
  if (!fs.existsSync(file)) {
    throw new Error(`Missing required file: ${file}`);
  }
}

const html = fs.readFileSync('index.html', 'utf8');
const app = fs.readFileSync('src/app.js', 'utf8');
if (!html.includes('src/styles.css') || !html.includes('src/app.js')) {
  throw new Error('HTML asset references are incomplete');
}
if (!app.includes('document.querySelector')) {
  throw new Error('App does not bind to DOM');
}

console.log('application-factory-smoke: passed');
