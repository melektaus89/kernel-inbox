# Contributing

Kernel Inbox is a local, read-only mailing-list reader. Keep changes focused and preserve loopback-only serving, text-only archive rendering, and existing browser storage keys.

1. Fork and clone the repository, then follow the README setup steps.
2. Create a branch for your change.
3. Run `npm test`, `npm run typecheck`, and `npm run build`.
4. Open a pull request explaining the problem, behavior change, and verification.

Parser changes should include a small synthetic archive fixture in `test_server.py`, covering both accepted data and malformed input. Tests must work offline. Avoid committing cached mail, personal settings, or generated builds.

For bugs, include the feed, public archive URL if relevant, expected and actual behavior, and Python/Node versions. Do not include private browser data. Archive downtime and truncated upstream headers are known limitations; distinguish these from parser failures.
