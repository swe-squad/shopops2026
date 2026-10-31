# Workspace browser regression suite

Runs three real frontend documents and two real FastAPI services with temporary SQLite databases.
OpenAI transport is replaced with an offline fixture in this directory. The catalog's HTTP transport
uses the real mock-source seed through a test-only fixture; it cannot contact a configured live data
service. Replies and catalog screens identify mock/test data. Production services never import these
fixtures. The local stock-change endpoint belongs only to this test runner.

## Run

Install frontend dependencies with `npm ci` in each frontend and backend dependencies with `make install` in each API. Then:

```sh
cd tests/workspace
npm ci
npx playwright install chromium
npm test
```

The default bundled Chromium headless shell is the regression target used by CI. For exploratory checks against installed Google Chrome:

```sh
PLAYWRIGHT_CHANNEL=chrome npm test
```

Installed Chrome's full headless mode showed an intermittent missed native click in the cross-site browser iframe during phone emulation on this machine. Enlarging its native window passed the comparison while keeping the emulated viewport unchanged. This remains a compatibility caveat, not a proven application defect. Use the default command for CI parity; keep the same interaction assertions when investigating other channels. See the [recorded diagnosis](../../plans/261031-workspace-upgrade/reports/iframe-input-diagnosis.md). Playwright documents the [different headless implementations](https://playwright.dev/docs/browsers#google-chrome--microsoft-edge).

`npm run test:headed` shows the browser; `npm run test:ui` opens Playwright's runner. Reports, failure traces and viewport screenshots are in ignored `playwright-report/` and `test-results/`.

Deterministic ports: operations 8000, chat API 8001, browser 5173, chat 5174, viewer 5175. The runner refuses occupied servers to avoid testing a personal workspace. Stop only owned processes first. Playwright manages process groups and sends SIGTERM on completion; temporary databases are removed on clean shutdown.

The [workspace CI workflow](../../.github/workflows/workspace-checks.yml) runs the suite and brand drift check for changes to participating services, canonical assets or this test tooling. It needs no secrets.

## Coverage

- Fixed parent viewport at phone/tablet/desktop/short landscape sizes.
- Separate origins, blocked parent DOM access, no viewer credentials/business requests.
- Browser tab histories/drafts, add/select/close and keyboard navigation.
- Real SSE normalization and Markdown; chat links delivered through the operations mailbox to the active tab.
- Authenticated product catalog, scoped SKU deep links, review/return evidence, question drafts,
  revision-aware stock refresh and retained data during a source outage.
- Independent reload and narrow switches preserving the other client.
- Child scrolling with pinned controls; streamed text respects reader position.
- Explicit stop/history recovery without silently resending.
- Telegram-style multiline composer, keyboard chat menu, history refresh and lock.
- Wide Markdown tables/code stay scrollable inside the phone frame.

Service tests cover exhaustive URL validation, provider lifecycle, errors and runtime configuration. This suite does not certify live OpenAI access, deployed nginx/CSP, external embedding policies, or physical device keyboards.
