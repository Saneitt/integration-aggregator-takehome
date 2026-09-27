import http from 'k6/http';
import { check, sleep } from 'k6';
import exec from 'k6/execution';
import { Counter, Rate, Trend } from 'k6/metrics';

const baseUrl = __ENV.BASE_URL || 'http://integration-aggregator.aggregator.svc.cluster.local:8080';
const provider = __ENV.PROVIDER || 'mock';
const tokenUser = __ENV.TOKEN_USER || 'perf-user';
const pollMs = Number(__ENV.POLL_MS || 25);
const maxPolls = Number(__ENV.MAX_POLLS || 400);

const enqueueMs = new Trend('enqueue_ms', true);
const timeToTokenMs = new Trend('time_to_token_ms', true);
const tokens = new Counter('tokens');
const failures = new Rate('failures');

export const options = {
  scenarios: {
    c1: { executor: 'constant-vus', vus: 1, duration: '30s', startTime: '0s', tags: { level: 'c1' } },
    c10: { executor: 'constant-vus', vus: 10, duration: '30s', startTime: '35s', tags: { level: 'c10' } },
    c50: { executor: 'constant-vus', vus: 50, duration: '30s', startTime: '70s', tags: { level: 'c50' } },
  },
  thresholds: {
    'failures{level:c1}': ['rate<0.05'],
    'failures{level:c10}': ['rate<0.05'],
    'failures{level:c50}': ['rate<0.05'],
    'tokens{level:c1}': ['count>0'],
    'tokens{level:c10}': ['count>0'],
    'tokens{level:c50}': ['count>0'],
    'enqueue_ms{level:c1}': ['p(95)<1000'],
    'enqueue_ms{level:c10}': ['p(95)<1000'],
    'enqueue_ms{level:c50}': ['p(95)<1500'],
    'time_to_token_ms{level:c1}': ['p(95)<10000'],
    'time_to_token_ms{level:c10}': ['p(95)<10000'],
    'time_to_token_ms{level:c50}': ['p(95)<15000'],
  },
};

export default function () {
  const level = exec.scenario.name;
  const started = Date.now();
  const accepted = http.get(`${baseUrl}/${provider}/${tokenUser}`, {
    tags: { name: 'enqueue', level },
  });
  enqueueMs.add(accepted.timings.duration, { level });
  if (!check(accepted, {
    'token request accepted asynchronously': (response) => response.status === 202 && Boolean(response.headers.Location),
  })) {
    failures.add(true, { level });
    sleep(0.5);
    return;
  }

  const location = accepted.headers.Location.startsWith('/')
    ? `${baseUrl}${accepted.headers.Location}`
    : accepted.headers.Location;
  let done = false;
  for (let poll = 0; poll < maxPolls; poll += 1) {
    const result = http.get(location, { tags: { name: 'poll', level } });
    if (result.status !== 200) break;
    const body = result.json();
    if (body.status === 'succeeded') {
      failures.add(false, { level });
      tokens.add(1, { level });
      timeToTokenMs.add(Date.now() - started, { level });
      done = true;
      break;
    }
    if (body.status === 'failed') break;
    sleep(pollMs / 1000);
  }
  if (!done) failures.add(true, { level });
  sleep(0.5);
}

function metric(metrics, name, level) {
  return metrics[`${name}{level:${level}}`]?.values || metrics[name]?.values || {};
}

function number(value, digits = 1) {
  return Number.isFinite(value) ? value.toFixed(digits) : 'n/a';
}

export function handleSummary(data) {
  const levels = ['c1', 'c10', 'c50'];
  const rows = levels.map((level) => {
    const enqueue = metric(data.metrics, 'enqueue_ms', level);
    const elapsed = metric(data.metrics, 'time_to_token_ms', level);
    const total = metric(data.metrics, 'tokens', level).count || 0;
    const failure = metric(data.metrics, 'failures', level).rate || 0;
    const seconds = 30;
    return {
      level,
      enqueue_p50_ms: enqueue.med ?? null,
      enqueue_p95_ms: enqueue['p(95)'] ?? null,
      token_p50_ms: elapsed.med ?? null,
      token_p95_ms: elapsed['p(95)'] ?? null,
      tokens: total,
      tokens_per_second: total / seconds,
      failure_rate: failure,
    };
  });
  const markdown = [
    '=====PERF-REPORT-BEGIN=====',
    '# Token retrieval performance',
    '',
    '| Level | Enqueue p50 (ms) | Enqueue p95 (ms) | Token p50 (ms) | Token p95 (ms) | Tokens/s | Failure rate |',
    '|---|---:|---:|---:|---:|---:|---:|',
    ...rows.map((r) => `| ${r.level} | ${number(r.enqueue_p50_ms)} | ${number(r.enqueue_p95_ms)} | ${number(r.token_p50_ms)} | ${number(r.token_p95_ms)} | ${number(r.tokens_per_second, 2)} | ${number(r.failure_rate * 100, 2)}% |`),
    '',
    `Polling interval: ${pollMs} ms. Each level ran for 30 seconds.`,
    '=====PERF-REPORT-END=====',
  ].join('\n');
  return {
    stdout: `${markdown}\nPERF_JSON:${JSON.stringify(rows)}\n`,
  };
}
