# src/scoring/

**Owner: Lavanya**

This folder contains the scoring engine and all scoring rules.

## Architecture

```
engine.js          ← reads snapshots → runs rules → writes to scores table
rules/
  security.js      ← pure function (snapshot) → 0-100
  testing.js       ← pure function (snapshot) → 0-100
  dependencies.js  ← pure function (snapshot) → 0-100
  deployment.js    ← pure function (snapshot) → 0-100
  performance.js   ← pure function (snapshot) → 0-100
```

## Category weights (overall score)

| Category | Weight |
|----------|--------|
| Security | 30% |
| Testing | 25% |
| Dependencies | 20% |
| Deployment | 15% |
| Performance | 10% |

## Rules contract

Every rule file exports a single **pure function** with this signature:

```js
/**
 * @param {object} snapshot - raw_data from the snapshots table
 * @returns {number} integer between 0 and 100
 */
export function scoreXxx(snapshot) { ... }
```

Rules must:
- Take only the snapshot object as input
- Return a number clamped to [0, 100]
- Have **no side effects** — no DB calls, no API calls
- Be independently testable with a plain object

## Adding a new rule

1. Create `rules/yourCategory.js` following the pattern above
2. Import it in `engine.js`
3. Add it to `WEIGHTS` (adjust other weights to keep the sum = 1)
4. Add a test in `tests/lavanya/`

## Calling the engine

```js
import { runScoringEngine } from './engine.js';
const scores = await runScoringEngine('project-uuid');
// → { security: 85, testing: 72, dependencies: 90, deployment: 60, performance: 80, overall: 79 }
```
