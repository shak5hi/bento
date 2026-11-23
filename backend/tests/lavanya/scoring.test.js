// tests/lavanya/scoring.test.js
// [Lavanya] Unit tests for the scoring rules — these are pure functions, easy to test.

import { scoreSecrity } from '../../src/scoring/rules/security.js';
import { scoreTesting } from '../../src/scoring/rules/testing.js';
import { scoreDependencies } from '../../src/scoring/rules/dependencies.js';
import { scoreDeployment } from '../../src/scoring/rules/deployment.js';
import { scorePerformance } from '../../src/scoring/rules/performance.js';

const emptySnapshot = {
  commits: [],
  openIssues: [],
  ciRuns: [],
  packageJson: null,
  repoMeta: null,
};

describe('Security Rule', () => {
  it('returns 100 for a clean snapshot', () => {
    expect(scoreSecrity(emptySnapshot)).toBe(100);
  });

  it('penalises security-labelled issues', () => {
    const snapshot = {
      ...emptySnapshot,
      openIssues: [
        { id: 1, title: 'CVE-2024-1234', labels: ['security'], createdAt: '' },
        { id: 2, title: 'XSS vulnerability', labels: ['vulnerability'], createdAt: '' },
      ],
    };
    const score = scoreSecrity(snapshot);
    expect(score).toBeLessThan(100);
    expect(score).toBeGreaterThanOrEqual(0);
  });
});

describe('Testing Rule', () => {
  it('gives a bonus for a passing test script and CI', () => {
    const snapshot = {
      ...emptySnapshot,
      packageJson: { scripts: { test: 'jest' } },
      ciRuns: [
        { status: 'completed', conclusion: 'success' },
        { status: 'completed', conclusion: 'success' },
      ],
    };
    expect(scoreTesting(snapshot)).toBeGreaterThan(50);
  });

  it('penalises a failing latest CI run', () => {
    const snapshot = {
      ...emptySnapshot,
      packageJson: { scripts: { test: 'jest' } },
      ciRuns: [{ status: 'completed', conclusion: 'failure' }],
    };
    expect(scoreTesting(snapshot)).toBeLessThan(70);
  });
});

describe('Dependencies Rule', () => {
  it('returns 50 for a project with no package.json', () => {
    expect(scoreDependencies(emptySnapshot)).toBe(50);
  });

  it('penalises large dependency counts', () => {
    const bigDeps = Object.fromEntries(Array.from({ length: 110 }, (_, i) => [`dep-${i}`, '*']));
    const snapshot = { ...emptySnapshot, packageJson: { dependencies: bigDeps } };
    expect(scoreDependencies(snapshot)).toBeLessThan(100);
  });
});

describe('Deployment Rule', () => {
  it('returns 40 with no CI runs', () => {
    expect(scoreDeployment(emptySnapshot)).toBe(40);
  });

  it('rewards high CI success rate', () => {
    const snapshot = {
      ...emptySnapshot,
      ciRuns: Array.from({ length: 5 }, () => ({ status: 'completed', conclusion: 'success' })),
    };
    expect(scoreDeployment(snapshot)).toBeGreaterThan(60);
  });
});

describe('Performance Rule', () => {
  it('starts at 80 with no issues', () => {
    expect(scorePerformance(emptySnapshot)).toBe(80);
  });

  it('penalises performance-labelled issues', () => {
    const snapshot = {
      ...emptySnapshot,
      openIssues: [{ id: 1, title: 'API is slow', labels: ['performance'], createdAt: '' }],
    };
    expect(scorePerformance(snapshot)).toBeLessThan(80);
  });
});
