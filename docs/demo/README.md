# Real GitHub OAuth recording

After configuring the ignored `.env` locally, start `make port-forward` and run `asciinema rec docs/demo/github-flow.cast -c scripts/demo-github.sh`. Complete the consent page in the Windows browser when it opens. Export a sanitized text transcript to `github-flow.md`; retain only the flow and `PASS GitHub API authenticated the expected user` result. Remove authorization URLs, OAuth state, callback query strings, codes, and tokens from the recording and transcript.

Run the repository leak check and a manual review over both files before committing. Revoke the authorization under GitHub Settings → Applications → Authorized OAuth Apps after recording. The `.cast` file and transcript are intentionally absent until a real user-controlled GitHub consent flow has been performed.
