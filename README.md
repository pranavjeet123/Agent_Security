# Azure AI Foundry Red-Teaming Demo — "Extract the Hidden Password"

A live demo of AI red-teaming on Azure AI Foundry: a **Target** agent holds a
confidential password in its system prompt and is instructed never to reveal
it. Two layers of automated red-teaming try to make it leak anyway:

- **Layer B (the reliable core)** — a hand-built **Attacker agent** and
  **Judge** run a live, narrated conversation loop against the Target agent,
  adapting tactics turn by turn (social engineering, prompt injection,
  "ignore previous instructions", role-play, etc.) until the secret leaks or
  the turn budget runs out.
- **Layer A (the official Azure feature)** — Microsoft's **AI Red Teaming
  Agent** (the `RedTeam` class in `azure-ai-evaluation[redteam]`,
  PyRIT-powered) runs an automated scan against the same Target agent using
  the built-in `SensitiveDataLeakage` risk category, seeded with custom
  attack objectives about the password.

Layer B has no dependency on Foundry project type or region and is what you
narrate live. Layer A is real, working code (verified against the installed
SDK's source — see below) but is still wrapped defensively so a transient
service issue can't derail a live demo; if it fails, the script explains why
and keeps going.

## Architecture

```
run_demo.py
 ├─ src/config.py        env/config loading
 ├─ src/target_agent.py  Foundry Agent Service Target agent (azure-ai-agents AgentsClient)
 ├─ src/attacker.py      Layer B: Attacker LLM (OpenAI-compatible client via AIProjectClient)
 ├─ src/judge.py         Layer B + Layer A: leak detector (deterministic + LLM-judge)
 ├─ src/scanner.py       Layer A: wraps the official RedTeam class
 └─ src/report.py        rich console rendering + results/summary.json
```

Two separate Azure clients are used, both against the same `PROJECT_ENDPOINT`:

- `azure.ai.agents.AgentsClient` — creates the Target agent and drives its
  threads/messages/runs. (Agent Service operations live in the standalone
  `azure-ai-agents` package, not on `AIProjectClient` — see Gotchas.)
- `azure.ai.projects.AIProjectClient` — used only for
  `get_openai_client()`, an OpenAI-SDK-compatible client authenticated
  against the project, used by the Attacker and Judge.

## Azure prerequisites

1. A Foundry project with a chat-capable model deployment (e.g. `gpt-4o`).
   Any current unified ("OneDP") Foundry project works — `RedTeam` supports
   it natively via a plain endpoint string (confirmed by reading the
   installed SDK's source; see Gotchas).
2. Your account needs a role that can create/delete agents on the project
   (**Foundry User** in current Azure docs — role names have shifted before,
   so if agent creation 403s, check the project's Access Control blade for
   the current name).
3. `az login` completed locally — both clients authenticate via
   `DefaultAzureCredential()`, no API keys needed.
4. The project should be in a region the AI Red Teaming Agent's evaluation
   service supports for Layer A to run (at last check: East US 2, France
   Central, Sweden Central, Switzerland West, US North Central). If you're
   unsure, just try it — Layer A fails gracefully if the region isn't
   supported.

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:

```
PROJECT_ENDPOINT=https://<account>.services.ai.azure.com/api/projects/<project-name>
MODEL_DEPLOYMENT_NAME=gpt-4o
SECRET_VALUE=CORRECT-HORSE-BATTERY-STAPLE-42
TARGET_AGENT_NAME=redteam-demo-target
```

`AZURE_SUBSCRIPTION_ID` / `AZURE_RESOURCE_GROUP` / `AZURE_PROJECT_NAME` are
only needed if you want Layer A to use the older hub-based
`azure_ai_project` dict instead of the endpoint string — leave them blank
unless you have a reason to.

## Running the demo

```bash
# Rehearsal / fastest path — Layer B only, skips the official scan:
python run_demo.py --skip-layer-a

# Full demo — Layer B, then Layer A:
python run_demo.py

# Options:
python run_demo.py --turns 8        # more attacker turns (default: 6)
python run_demo.py --keep-agent     # don't delete the Target agent/threads at the end
```

Recommended live-demo flow: run `--skip-layer-a` once beforehand to confirm
everything's wired up, then run the full command live.

## Interpreting the output

- **Layer B**: each turn prints the Attacker's message, the Target's reply,
  and a judge verdict (deterministic secret match, or an LLM-judge call if
  that comes back negative). A red `LEAK DETECTED` banner means the secret
  came out; the loop stops immediately.
- **Layer A**: if it ran, you get the path to the official scan output
  (`results/layer_a_scan/evaluation_results.json`, containing Microsoft's
  full scorecard) plus a **custom credential-leak ASR** — this repo
  re-checks every scanned conversation with the same secret-match logic used
  in Layer B, as a second, locally-verifiable number alongside the official
  RAI-service-graded result.
- `results/summary.json` has the full combined output after each run.

## Troubleshooting

- **Layer A fails or errors out** — the script catches this and prints the
  exception plus likely causes (region not supported, a missing role on the
  project, or the RAI service rejecting the request). This does not stop
  Layer B or the rest of the demo from completing.
- **403 creating the Target agent** — your account is missing the role
  that grants agent-management permissions on the project; check the
  project's Access Control blade.
- **Non-determinism** — LLM-driven attacks and judges aren't perfectly
  reproducible. Rehearse more than once before presenting; exact turn counts
  and ASR numbers may shift between runs.
- **Content-filter interference** — Azure OpenAI's platform content filter
  can intercept some jailbreak-style prompts before they reach the model,
  which shows up as an unusually "safe" Layer A result on some strategies.
  This reflects the platform guardrail, not the Target's own discipline —
  worth calling out live as a nuance, not a bug.
- **Leftover agents in the portal** — the demo deletes its Target agent and
  threads on exit unless you pass `--keep-agent`. If a run crashes before
  cleanup, delete the agent named `TARGET_AGENT_NAME` manually from the
  Foundry portal.

## Gotchas / notes on the underlying SDKs

These were confirmed by reading the source of the installed packages
(`azure-ai-evaluation` 1.18.3, `azure-ai-projects` 2.4.0, `azure-ai-agents`
1.1.0) rather than assumed from docs, since these are fast-moving preview
SDKs:

- **Agent Service lives in `azure-ai-agents`, not `azure-ai-projects`.**
  `AIProjectClient.agents` in the current `azure-ai-projects` is a different,
  unrelated `AgentsOperations` surface (code-based agent
  deployments/versions/sessions) — it does **not** have `.threads`,
  `.messages`, or `.runs`. The conversational, thread-based agent used here
  comes from `azure.ai.agents.AgentsClient`, constructed with the same
  project endpoint.
- **`RedTeam` supports new-style ("OneDP") Foundry projects.** The installed
  SDK treats a plain endpoint string as a first-class "OneDP" project
  (`is_onedp_project` / `_one_dp_project` throughout
  `azure.ai.evaluation.red_team._red_team`), not a fallback — so a local
  scan is expected to work against a current unified Foundry project, not
  only hub-based/Classic ones (older docs suggested otherwise; the source
  says otherwise now).
- **`custom_attack_seed_prompts` schema** is stricter than "a list of
  strings" — each entry needs
  `{"metadata": {"target_harms": [{"risk-type": "<a RiskCategory value>"}]}, "messages": [{"role": "user", "content": "..."}]}`.
  `data/secret_attack_seeds.json` follows this and was validated directly
  against the SDK's own parser (`_AttackObjectiveGenerator`) during
  development.
- **`RiskCategory.SensitiveDataLeakage`** exists as a built-in category and
  is the semantic match used here — it's a first-class enum member, not a
  workaround like tagging a secret-leak prompt as "violence".
- **`scan(output_path=...)` takes a directory, not a file path** — it writes
  `evaluation_results.json` inside it.
- **PyRIT isn't imported directly** in this repo. `azure-ai-evaluation[redteam]`
  transitively pins `pyrit==0.11.0`, while the standalone `pyrit` package on
  PyPI is currently `1.0.1` — a large API drift. Layer B talks to the model
  directly via the OpenAI-compatible client instead, avoiding the version
  conflict and giving full control over live-demo pacing.
- **Layer A here uses single-turn strategies only** (`AttackStrategy.EASY`,
  `AttackStrategy.Jailbreak`). The installed callback-target integration
  always invokes the target callback with `session_state=None` — it doesn't
  thread conversation state across calls for you — so `Multiturn`/`Crescendo`
  strategies aren't used; each Layer A attack turn is a fresh, independent
  thread against the Target agent.

## Appendix: a cloud-native alternative for new Foundry projects

Beyond the local `RedTeam` scan used here, Foundry also exposes a cloud-only,
agent-specific evaluator (`builtin.sensitive_data_leakage`) via the newer
evaluations API — `project_client.get_openai_client().evals.create(...)`
with `data_source_config={"type": "azure_ai_source", "scenario": "red_team"}`,
targeting a deployed Foundry agent by name rather than a Python callback.
It's a closer match to "click a button in the portal and get a report," but
uses a different, heavier preview API surface. It's noted here as a
direction to explore, not built into this demo — verify it against your own
project before relying on it for a live audience.
