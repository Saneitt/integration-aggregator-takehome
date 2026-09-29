# Real GitHub OAuth demonstration

Recorded on 2026-09-29 UTC from the local WSL/minikube deployment. The operator completed real GitHub consent in the Windows browser and confirmed the callback displayed `status: connected`. The script then requested a token through the asynchronous API and used it to call GitHub's `/user` endpoint. GitHub returned the expected login.

Command: `asciinema rec -c "bash scripts/demo-github.sh"` (raw capture kept in ignored `.build/`).

Actual terminal output, with terminal control sequences removed:

```text
github provider registered (HTTP 201).
Opened the GitHub consent page in your Windows browser. Complete consent and return to this terminal.
Press Enter after the callback page has loaded: 
Token acquired (masked; 40 characters).
PASS GitHub API authenticated the expected user: Saneitt
```

The accompanying `github-flow.cast` retains these actual output lines with shortened playback delays and sanitized metadata. Browser content, consent URLs, callback parameters, OAuth state, codes, and tokens are excluded. The recording shows the terminal result; it is not a screen recording of the browser.

Reproduce with `make demo-github` after following [the runbook](../RUNBOOK.md). The script's success line is emitted only after the token-request result succeeds and GitHub returns the configured expected username.
