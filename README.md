# research-paper-daily-push

An open-source Codex Skill for a selective daily research-paper radar. It searches stable scholarly APIs, deduplicates previous deliveries, performs transparent preliminary scoring, requires evidence review, renders a Chinese report with dual academic/plain-language term explanations, optionally pushes it to WeChat, and maintains local research memory.

The public package contains **no research topic, credentials, push history, or learned report history**. It will not search until a research profile is configured.

## Configure

1. Copy the folder to your Codex skills directory.
2. Describe the research direction in `references/research_topics.md`.
3. Fill `config/research_profile.json` following `references/profile_schema.md`, then set `configured` to `true`.
4. Optionally copy `.env.example` values into user or process environment variables. Never commit `.env` or real tokens.

## Run

```powershell
python scripts/run_daily.py collect --mode all
```

After Codex reviews the queue and produces `reviewed_articles.json`:

```powershell
python scripts/run_daily.py deliver --reviewed reviewed_articles.json --report daily-report.md --provider auto
```

Use `--skip-push --record-local-report` only after the report has actually been presented locally. A recurring schedule is intentionally not included because execution time, timezone, destination, and side-effect authorization are user-specific.

## Data and privacy

- `data/pushed_articles.json` and `data/research_memory.json` begin empty.
- Credentials are read only from environment variables.
- Delivery status JSON never stores credentials.
- Before publishing a fork, inspect the full repository and archive for reports, tokens, UIDs, local paths, personal research topics, and generated run data.

Licensed under the MIT License.
