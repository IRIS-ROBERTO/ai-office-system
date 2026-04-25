import { scoutInsight } from './data.js';

const description = document.querySelector('#app-description');
const thesis = document.querySelector('#market-thesis');
const metrics = document.querySelector('#metrics');
const projects = document.querySelector('#projects');
const implementation = document.querySelector('#implementation');

const potential = scoutInsight.potential || {};
const summary = scoutInsight.summary || {};

description.textContent = scoutInsight.description || 'Generated product opportunity.';
thesis.textContent = potential.pitch || scoutInsight.recommendation || 'No market thesis available.';

const metricItems = [
  ['Viability', potential.viability || 'n/a'],
  ['Score', potential.score ? `${potential.score}/100` : 'n/a'],
  ['Projects', String((scoutInsight.projects || []).length)],
];

metrics.innerHTML = metricItems.map(([label, value]) => `
  <article class="metric">
    <strong>${value}</strong>
    <span>${label}</span>
  </article>
`).join('');

projects.innerHTML = (scoutInsight.projects || []).map((project) => `
  <article class="project">
    <div>
      <strong>${project.title || project.name}</strong>
      <small>${project.source || 'source'} · grade ${project.grade || 'n/a'} · score ${project.score || 0}</small>
    </div>
    ${project.url ? `<a href="${project.url}" target="_blank" rel="noreferrer">Open</a>` : ''}
  </article>
`).join('');

[
  summary.o_que_e || 'Define the product opportunity and user problem.',
  summary.onde_usariamos || 'Map how IRIS will use the application.',
  summary.o_que_implementariamos || 'Build the first workflow and proof of value.',
  'Validate with smoke tests, security review and market feedback.',
].forEach((item) => {
  const li = document.createElement('li');
  li.textContent = item;
  implementation.appendChild(li);
});
