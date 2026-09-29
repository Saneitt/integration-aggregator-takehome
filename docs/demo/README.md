# Real GitHub OAuth demonstration

The [transcript](github-flow.md) and [terminal recording](github-flow.cast) capture the successful real GitHub flow recorded on 2026-09-29 UTC. The browser consent was completed by the operator. The script confirmed the returned credential worked against GitHub's `/user` API.

The capture includes only actual terminal output, with terminal control sequences removed, metadata sanitized, and playback delays shortened. It excludes browser URLs, callback parameters, codes, state, and credentials.

To repeat it, follow [the runbook](../RUNBOOK.md). Record raw output under ignored `.build/`, inspect and sanitize it before copying evidence into this directory, and run the repository secret scan before committing. Revoke the GitHub authorization after each demonstration under **Settings → Applications → Authorized OAuth Apps**.
