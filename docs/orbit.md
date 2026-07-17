# GitLab Orbit

DevPilot can treat GitLab Orbit as an important discovery process before it
launches Executors. Orbit gives the coordinator a point-in-time knowledge graph
for questions like what depends on a file, which code paths are related, what
merge requests touched an area, and which pipelines or security findings are
connected to a change.

Orbit is optional. Enable it per project when the target repository or GitLab
group has been indexed.

## Orbit Local

Install Orbit Local and index the project:

```powershell
irm https://gitlab.com/gitlab-org/orbit/knowledge-graph/-/raw/main/install.ps1 | iex
orbit index .
```

Then enable it in `devpilot.yaml` or `research_config.yaml`:

```yaml
orbit:
  enabled: true
  mode: local
  command: orbit
  database_path: ~/.orbit/graph.duckdb
```

When enabled, DevPilot adds Orbit guidance to the coordinator prompt and checks
that the Orbit command and local graph are present. Missing Orbit is a warning
by default so ordinary local research runs do not break.

Make Orbit mandatory for GitLab-backed work:

```yaml
orbit:
  enabled: true
  mode: local
  required: true
```

With `required: true`, preflight fails if Orbit is missing or the local graph
has not been built.

## Orbit Remote

For GitLab.com Premium or Ultimate groups with Orbit Remote enabled:

```yaml
orbit:
  enabled: true
  mode: remote
  command: glab
  remote_group: my-top-level-group
  required: true
```

Remote mode tells the coordinator to use Orbit for SDLC context such as merge
requests, pipelines, jobs, reviewers, work items, security findings, and
cross-project dependencies.

## How DevPilot Uses Orbit

When `orbit.enabled` is true, the coordinator is instructed to:

- Prefer Orbit for graph-shaped questions before broad text search.
- Use Orbit evidence during OBSERVE and IDEATE before spending Executor cycles.
- Treat Orbit results as point-in-time evidence from the last index cycle.
- Continue with normal code tools when Orbit is best-effort and unavailable.
- Stop and ask for indexing/configuration when Orbit is required and unavailable.

Orbit does not replace experiments. It makes DevPilot's first pass sharper:
fewer blind edits, better dependency awareness, and more useful hypotheses.
