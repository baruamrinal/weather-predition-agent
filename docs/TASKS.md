# Task list

Derived from [PRD.md](PRD.md); interfaces are defined in [ARCHITECTURE.md](ARCHITECTURE.md). Work is test-driven: each acceptance criterion (AC) becomes a test that fails before
the code is written and passes after.

**Conventions**
- Unit tests run offline. HTTP is faked at `weather_tools._get_json`.
- Tests that hit real APIs are marked `@pytest.mark.live` and skipped by default (`pytest -m live` to run them).
- CI requires at least 80% line + branch coverage of `weather_agent/`; below that, the bot does not approve the PR.
  Check locally with `pytest --cov --cov-fail-under=80`.
- Statuses: `[ ]` todo · `[~]` in progress · `[x]` done.

---

## M0. Test foundation

### [x] T0.1 Test setup
- **AC1** `pytest` runs from the repo root inside `.venv` with no network access.
- **AC2** Live tests are excluded by default and run with `pytest -m live`.
- **AC3** Dev dependencies are listed in `requirements-dev.txt`.

### [x] T0.2 Package layout: Brain / Memory / Tools (PRD §7.1)
- **AC1** Code lives in `weather_agent/` with `brain/`, `memory/`, and `tools/` subpackages.
- **AC2** All HTTP goes through one function, `weather_agent.tools.http.get_json`, which tests fake.
- **AC3** All existing tests pass after the move, with no change to behaviour.

---

## M2. Agent core for UC1, UC2, UC5

## Tools

### [x] T2.1 Pin existing tools with tests: `geocode`, `forecast`
- **AC1** `geocode` returns name, region, country, latitude, longitude, and time zone for each match.
- **AC2** `geocode` returns `[]` when the API has no results.
- **AC3** `forecast` returns one row per day, with weather codes turned into text (`3` → "Overcast").
- **AC4** `forecast` keeps `days` between 1 and 16 and passes the right temperature unit to the API.

### [x] T2.2 Pin `hourly_forecast`
- **AC1** Returns one row per hour, with readable conditions.
- **AC2** Raises `ValueError` if `end_date` is before `start_date`.
- **AC3** Raises `ValueError` for a range longer than 3 days.

### [x] T2.3 Pin `air_quality`
- **AC1** Groups hourly values by local date, with the daily max and mean AQI.
- **AC2** Labels AQI with US EPA categories (50 → Good, 101 → Unhealthy for sensitive groups, 301 → Hazardous).
- **AC3** Reports the hour when AQI is worst.
- **AC4** Skips missing (`null`) hours without crashing.

### [x] T2.4 Pin `climate_normals`
- **AC1** Only uses days in the same calendar window as the request.
- **AC2** Works for windows that cross New Year (Dec 30 - Jan 2).
- **AC3** Calculates averages, rainy-day share (≥ 1 mm), and record high, low, and wettest day correctly.
- **AC4** Rejects windows longer than 31 days.

### [x] T2.5 `distance` (new; PRD §7.1 `get_distance`)
- **AC1** Straight-line distance London → Paris is 344 km ± 1%.
- **AC2** Distance from a point to itself is 0.
- **AC3** Returns an estimated road distance (straight line × 1.3) and drive time (at 50 km/h), labelled `"method": "estimate"`.

### [x] T2.6 `elevation` (new; PRD §7.1 `get_elevation`)
- **AC1** Returns `elevation_m` for one point from the Open-Meteo Elevation API.
- **AC2** Raises `ValueError` if the API returns no elevation.
- **AC3** The Elevation endpoint (`api.open-meteo.com`) is on the HTTP allow-list (T2.18).

### [x] T2.7 Tool call budget (PRD R3)
- **AC1** A budget allows exactly `limit` tool calls; the next call returns an error starting with `Error: tool budget exhausted`.
- **AC2** The error tells the model to answer with its best plan so far and to list what it didn't check.
- **AC3** `reset()` restores the full budget (called at the start of every user request).
- **AC4** Default limit is 30, configurable with the `AGENT_MAX_TOOL_CALLS` environment variable.

### [ ] T2.8 Tool registry
- **AC1** Each tool is defined once (name, description, JSON schema, function), with no provider-specific code.
- **AC2** `execute(name, args)` runs a tool and returns a string. Unknown tools and failures return `Error: ...`; it
  never raises and never invents data (PRD R2).
- **AC3** Every executed tool counts against the budget (T2.7), except results served from the working-memory cache.
- **AC4** Registry includes: `find_location`, `get_weekly_forecast`, `get_hourly_forecast`, `get_air_quality`,
  `get_climate_normals`, `get_distance`, `get_elevation`, `remember`, `recall`, `forget`.
- **AC5** Missing or wrongly typed arguments return `Error: invalid arguments ...` instead of raising.

## Memory

### [x] T2.9 Long-term memory store (PRD §7.1, M1-M4)
- **AC1** `remember(kind, content)` saves an entry with an id, kind (`profile` | `preference` | `plan` | `outcome`),
  content, and creation date, and returns the entry.
- **AC2** Entries are still there after the store is reopened from the same file.
- **AC3** Saving the same content twice under the same kind does not create a duplicate.
- **AC4** `recall(query, kind=None)` returns entries matching any query word (case-insensitive), optionally filtered
  by kind. An empty query returns everything.
- **AC5** `forget(id)` deletes the entry and returns `True`, or `False` for an unknown id.
- **AC6** An unknown kind raises `ValueError`.
- **AC7** A corrupted memory file is renamed to `.bak` and the store starts empty, without crashing.
- **AC8** `profile_summary()` returns profile and preference entries as bullet lines, or `""` when there are none.

### [ ] T2.10 Working memory: tool-result cache
- **AC1** A second call to the same tool with the same arguments (in any order) returns the cached result without
  running the tool.
- **AC2** Error results are not cached.
- **AC3** Memory tools (`remember` / `recall` / `forget`) are never cached.
- **AC4** The cache lasts one session and can be cleared.

### [ ] T2.11 Memory tools for the Brain
- **AC1** `remember`, `recall`, and `forget` are registered tools backed by the long-term store.
- **AC2** `remember` returns a confirmation that the agent can repeat to the user (M1).

## Brain

### [ ] T2.12 Brain interface + agent loop
- **AC1** `Brain.think(system, transcript, tools)` returns a step: text and/or tool calls, plus a stop reason.
- **AC2** The agent loop runs tool calls through the registry, adds the results to the transcript, and calls the
  Brain again until it returns no tool calls.
- **AC3** Several tool calls in one step are all executed and returned together.
- **AC4** The loop stops after `max_steps` and returns what it has, saying it was cut short.
- **AC5** At the start of each user request, the loop resets the budget and puts the long-term profile summary and
  today's date into the system prompt.
- **AC6** All of the above is tested with a scripted `FakeBrain`, without network or API keys.

### [ ] T2.13 Claude adapter
- **AC1** Converts the transcript and tool specs into a Claude Messages API request (`claude-opus-5-5`), and the
  response into a Brain step.
- **AC2** Sends assistant turns back unchanged in later requests, including thinking blocks.
- **AC3** Handles a `refusal` stop reason by returning a clear message, not by crashing.
- **AC4** Tested with a fake SDK client; one live test marked `@pytest.mark.live`.
- **AC5** The model can be overridden with `CLAUDE_MODEL`.

### [ ] T2.14 OpenAI adapter
- **AC1** Converts the transcript and tool specs to Chat Completions format, and the response into a Brain step.
- **AC2** Tool call arguments that aren't valid JSON become an error tool result, not a crash.
- **AC3** Tested with a fake SDK client; one live test marked `@pytest.mark.live`.

### [ ] T2.15 CLI
- **AC1** `python -m weather_agent --provider claude|openai` starts a chat; it defaults to Claude.
- **AC2** `/memory` lists memories, and `/forget <id>` deletes one (PRD M2).
- **AC3** Each tool call is printed as it happens.
- **AC4** Replaces `agent.py` and `agent_openai.py`, which are then deleted.
- **AC5** The memory file location comes from `WEATHER_AGENT_MEMORY` when set (ARCHITECTURE §8).

### [ ] T2.17 Usage tracking (HLD §8.6)
- **AC1** Each request records: provider, model, Brain steps, tool calls (name, cached, duration, error), input,
  output, and cached tokens, estimated cost, and total time.
- **AC2** The CLI prints a one-line summary after each answer.
- **AC3** Details are appended as one JSON line per request to a local log file.
- **AC4** Log lines never contain API keys: any key-like text is masked before writing (`security.looks_like_secret`).

### [x] T2.18 Security guards (HLD §8.4)
- **AC1** `http.get_json` only allows HTTPS requests to Open-Meteo hosts. Any other host or scheme raises
  `ValueError` before a connection is opened.
- **AC2** Every URL the tools use is on the allow-list.
- **AC3** Within `weather_agent/`, only `tools/http.py` (data) and `brain/` (AI SDKs) may import networking modules
  (`urllib.request`, `http.client`, `socket`, `requests`, `httpx`).
- **AC4** A repo scan finds no API-key-like strings in source, docs, or config.
- **AC5** `MemoryStore.remember` refuses content that looks like an API key, so secrets never reach the memory file.
- **AC6** Prompt-injection scenarios are part of the M3 eval set (T3.1 AC3).

### [ ] T2.16 Agent instructions for R1-R10 and M1-M4
- **AC1** The system prompt covers plan-first, grounding, bounded search, visible trade-offs, asking only when it
  matters, final check, uncertainty, answer-first, safety, and revising on follow-ups, plus the memory rules M1-M4.
- **AC2** Behaviour is verified by the M3 eval scenarios, not by unit tests.

---

## M3. Evaluation

### [ ] T3.1 Scenario format and initial set
- **AC1** Scenarios are stored as YAML/JSON: request, constraints, expected checks, use case tag.
- **AC2** At least 8 scenarios each for UC1, UC2, UC5, including at least 2 per use case where the first choice fails.
- **AC3** At least 4 prompt-injection scenarios, such as a stored memory or a place name containing instructions
  ("ignore your rules and…"). The agent must treat these as data, not follow them (HLD §8.4).

### [ ] T3.2 Fixed-workflow baseline
- **AC1** For each use case, a fixed workflow fetches a set list of data and makes one model call.
- **AC2** It runs on the same scenarios and produces output in the same format as the agent.

### [ ] T3.3 Scoring
- **AC1** Constraint satisfaction is checked automatically against the fetched data.
- **AC2** Grounding check: every number in the answer appears in that run's tool results.
- **AC3** Reports tool calls, tokens, and cost per scenario.

### [ ] T3.4 Go / no-go report
- **AC1** A report compares agent vs baseline for each use case.
- **AC2** A use case is kept only if the agent beats the baseline on constraint satisfaction (PRD §9).

---

## M4. Journeys and field work

### [ ] T4.1 Routing tool (depends on PRD §12 Q2)
- **AC1** Returns points along the route with the cumulative distance and estimated time at each.
- **AC2** Handles "no route found" with an `Error:` result.

### [ ] T4.2 UC3 journey timing
- **AC1** Eval scenarios for UC3 pass the M3 thresholds.

### [ ] T4.3 UC4 field operations scheduler
- **AC1** Eval scenarios for UC4 pass the M3 thresholds, including at least 2 with conflicting tasks.

---

## M5. Plan watch and interface

### [ ] T5.1 Structured plans in memory (UC6)
- **AC1** A `plan` memory stores the constraints and the forecast it was based on, so it can be compared later.

### [ ] T5.2 Scheduled re-check (UC6)
- **AC1** Re-checking a saved plan reports only the changes that affect it, with a specific proposed fix.

### [ ] T5.3 Web or chat interface
- **AC1** To be defined after PRD §12 Q1 is answered.
