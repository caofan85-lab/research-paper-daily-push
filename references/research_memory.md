# Persistent research memory

`data/research_memory.json` stores compact evidence from reports that were actually delivered or presented. It supports continuity across daily runs; it is not model-weight training.

Update memory only after WeChat delivery succeeds, a local report is actually presented and committed, or confirmed reports are intentionally backfilled. Never learn from preliminary candidates, failed pushes, or unfinished drafts.

The next run uses a bounded memory context to detect accumulating evidence, repeated ideas, underrepresented roadmap stages, and unresolved validation questions. It must not relax the score threshold, repeat a pushed DOI, or treat report frequency as explicit user preference. Direct feedback belongs in `explicit_preferences` and takes priority over inferred signals.
