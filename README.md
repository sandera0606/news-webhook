# news-webhook

A small, **forkable** GitHub Actions cron that pulls news from PubMed and RSS feeds, summarizes the top articles per topic with an LLM, and posts a digest to a Discord webhook.

Out of the box it ships with two topics:
- **biology** — PubMed search for CRISPR / gene therapy / mRNA / biotech + Nature's biotechnology feed
- **ai** — arXiv `cs.AI` + `cs.LG` + TechCrunch AI

Each topic has its own schedule (`daily`, `weekly`, `weekdays`, `weekends`) and article cap. The default LLM is **Gemini Flash** (free tier), but Anthropic / OpenAI / Groq are drop-in alternatives.

## Quickstart (fork → running digest in ~10 minutes)

1. **Fork this repo.**
2. **Create a Discord webhook** in the channel you want digests in: *Edit Channel → Integrations → Webhooks → New Webhook → Copy URL*.
3. **Get an LLM API key** — easiest free option is Google's [AI Studio](https://aistudio.google.com/apikey) (Gemini).
4. **Add repo secrets** at *Settings → Secrets and variables → Actions → New repository secret*:
   - `DISCORD_WEBHOOK_URL` — your webhook URL from step 2
   - `GEMINI_API_KEY` — your key from step 3
   - `NCBI_EMAIL` — your email (NCBI asks for one; gets you a higher PubMed rate limit)
5. **Set up `config.yaml`** — pick one:
   - **Edit the existing `config.yaml`** in place (ships with a combined biology + AI topic running on weekdays).
   - **Or delete it and start fresh**: `del config.yaml` then `copy config.example.yaml config.yaml` and edit. The example file has biology and AI as two separate topics with different schedules — a good starting point if you want them delivered separately.
6. **Enable Actions** on your fork: *Actions → I understand my workflows, go ahead and enable them*.
7. **Test it**: *Actions → news digest → Run workflow* (you can tick `dry_run` to skip posting on the first run).

That's it. After step 6, the cron runs daily at 13:00 UTC and posts to your channel.

## Configuration (`config.yaml`)

The repo ships with two files:

- **`config.yaml`** — the active config the workflow reads. Out of the box it's a single combined **biology + AI** topic running on weekdays.
- **`config.example.yaml`** — a template with biology and AI as **two separate topics** (different schedules, different article caps). Useful if you want them delivered as separate Discord messages.

Either edit `config.yaml` in place, or replace it with the example:

```powershell
del config.yaml
copy config.example.yaml config.yaml
```

The schema is small:

```yaml
llm:
  provider: gemini             # gemini | anthropic | openai | groq
  model: gemini-2.0-flash
  api_key_env: GEMINI_API_KEY

topics:
  - name: biology
    frequency: daily           # daily | weekly | weekdays | weekends
    max_articles: 5
    enrich_fulltext: true      # try PubMed Central for open-access full text
    sources:
      - type: pubmed
        query: '(CRISPR[tiab] OR "gene therapy"[tiab]) AND ("last 7 days"[dp])'
      - type: rss
        url: https://www.nature.com/subjects/biotechnology.rss
```

### Relevance gating (optional, per topic)

If you set `relevance_check: true` on a topic, the LLM is asked to pick up to
`max_articles` candidates that match your `relevance_criteria`. If nothing
qualifies, the topic stays silent for the day — no post is sent.

```yaml
- name: ai
  max_articles: 1
  relevance_check: true
  relevance_criteria: |
    A genuinely notable AI development — strong new model, real-world impact,
    or significant industry news. Skip incremental benchmark bumps and
    marketing pieces.
```

Without `relevance_check`, the picker simply takes the first `max_articles`
fresh items in source order (so put your best-curated source first).

### Frequency semantics

Evaluated against the cron firing day in **UTC**:

| Value      | Runs on               |
|------------|-----------------------|
| `daily`    | every day             |
| `weekly`   | Mondays               |
| `weekdays` | Mon–Fri               |
| `weekends` | Sat–Sun               |

Each topic only fires when its frequency matches. The cron itself runs daily; the code decides whether each topic is due.

### Writing PubMed queries

PubMed query syntax: https://pubmed.ncbi.nlm.nih.gov/help/

Useful tags:
- `[tiab]` — title/abstract
- `[mesh]` — MeSH term
- `[dp]` — date of publication, e.g. `"last 7 days"[dp]`, `"2024"[dp]`
- `[au]` — author
- `[journal]` — journal name

### Adding an RSS source

Just append another `- type: rss` block:

```yaml
- type: rss
  url: https://export.arxiv.org/rss/q-bio
```

ArXiv categories list: https://arxiv.org/category_taxonomy

## Swapping the LLM provider

1. Pick a provider supported in [`src/news_webhook/llm/`](./src/news_webhook/llm/): `gemini`, `anthropic`, `openai`, `groq`.
2. In `config.yaml`, set `llm.provider`, `llm.model`, and `llm.api_key_env`.
3. Add the matching API key as a GitHub repo secret (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or `GROQ_API_KEY`).
4. **Set the repo variable `LLM_EXTRA`** (*Settings → Secrets and variables → Actions → Variables → New variable*) to one of `gemini` / `anthropic` / `openai` / `groq` so CI installs the right SDK. Defaults to `gemini` if unset.

Examples:

```yaml
# Anthropic — paid, very high quality, ~$0.001/summary on Haiku
llm:
  provider: anthropic
  model: claude-haiku-4-5-20251001
  api_key_env: ANTHROPIC_API_KEY
```

```yaml
# Groq — free, fast Llama-3 inference
llm:
  provider: groq
  model: llama-3.1-70b-versatile
  api_key_env: GROQ_API_KEY
```

### Adding a new provider

1. Create `src/news_webhook/llm/<name>.py` implementing the `LLMProvider` protocol (one method: `summarize(text, *, style) -> str`).
2. Register it in `get_provider()` in [`llm/base.py`](./src/news_webhook/llm/base.py).
3. Add the SDK as an optional dependency in [`pyproject.toml`](./pyproject.toml) under `[project.optional-dependencies]`.

Each existing provider file is ~25 lines — copy one as a template.

## Paywalled papers

The workflow does **not** automate institutional SSO / EZproxy logins — that's fragile and usually violates publisher ToS. Instead, it uses two legal open-access paths:

- **PubMed Central** — when a PubMed article has an OA counterpart in PMC, the enrichment step pulls the full text directly. Enable per-topic with `enrich_fulltext: true`.
- **Unpaywall** (optional) — set `UNPAYWALL_EMAIL` as a secret to enable lookups for legal OA versions of paywalled DOIs.

For most digest-style summaries, the **abstract is enough** — full-text mostly helps for technical depth on a specific paper. Start with abstracts and only enable enrichment if your summaries feel shallow.

## Running locally

```powershell
git clone <your fork>
cd news-webhook
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[gemini]"

# Copy the env template and fill in your keys — .env is auto-loaded.
copy .env.example .env
notepad .env

# Preview without posting
python -m news_webhook.run --dry-run --topic biology

# Force a topic to run regardless of frequency
python -m news_webhook.run --topic ai

# Pretend today is Saturday to test weekend topics
python -m news_webhook.run --today 2026-05-23 --dry-run
```

## CLI flags

| Flag | What it does |
|------|--------------|
| `--config PATH` | use a different config file (default `config.yaml`) |
| `--state PATH` | use a different seen.json location (default `state/seen.json`) |
| `--topic NAME` | run only this topic; repeatable. Bypasses the frequency check. |
| `--dry-run` | print the Discord payload as JSON; don't POST and don't update state |
| `--today YYYY-MM-DD` | override "today" for testing frequency logic |
| `-v` | verbose logs |

## How dedup works

`state/seen.json` stores `{topic: {article_id: date_seen}}`. The workflow commits it back to the repo after each successful run. Entries older than 60 days are pruned automatically. To wipe and restart, delete the file or clear individual entries.

## Project layout

```
src/news_webhook/
  run.py              # CLI entrypoint; orchestrates one digest run
  config.py           # pydantic config models
  scheduler.py        # is_due(frequency, today)
  state.py            # seen.json reader/writer
  discord.py          # webhook embed builder + POST
  sources/
    base.py           # Article dataclass
    pubmed.py         # NCBI E-utilities (esearch + efetch)
    rss.py            # feedparser wrapper
    enrich.py         # Unpaywall + PMC OA full-text
  llm/
    base.py           # LLMProvider protocol + get_provider()
    gemini.py
    anthropic.py
    openai.py
    groq.py
```

## What this isn't

- **Not a Discord bot.** Webhooks are outbound-only — you can't `/news subscribe` from inside Discord. To configure topics, edit `config.yaml` and commit.
- **Not a publisher-paywall bypass.** Use PMC + Unpaywall for legal OA, abstracts for the rest.
- **Not a real-time alerter.** It's a digest. If you want push alerts on new papers, look at NCBI's "My NCBI" email alerts or a dedicated tool like Stork.

## License

MIT. Fork freely.
