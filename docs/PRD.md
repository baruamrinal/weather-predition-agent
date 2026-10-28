# PRD: Weather Planning Agent

| | |
|---|---|
| **Status** | Draft v2 for review |
| **Last updated** | 2026-10-28 |
| **Repo** | `weather-predition-agent` |

## 1. Summary

An agent that plans **around** the weather. The user brings a goal with constraints, such as a trip, a journey, an
event, or farm work. The agent works out which places, dates, and hours to check, gathers that data step by step,
compares the options, and returns a plan, plus a backup when the forecast is uncertain.

Forecast numbers always come from professional weather models through tools. The agent's job is deciding **what to
look at next** and **what it means for the plan**.

## 2. Design principle: the agent test

This product only includes use cases that a single API call or a fixed workflow cannot handle well. A use case
qualifies when it meets **at least two** of these conditions:

| # | Condition | What it means |
|---|---|---|
| **T1** | **Next steps depend on results** | What to fetch next depends on what was just found (e.g. Saturday is wet, so check Sunday and Monday) |
| **T2** | **Open search space** | Places, dates, or times to check aren't given; the agent generates candidates and narrows them down |
| **T3** | **Competing constraints** | Several requirements pull against each other and need trade-offs (dry *and* cool *and* within 4 h drive) |
| **T4** | **Re-planning** | A plan has to be revised when new data contradicts it |
| **T5** | **Clarification mid-task** | The agent may need to ask the user something it only discovers partway through |

### Fails the test (out of scope for the agent)

These are handled better by a direct lookup or a short script. They are **not** agent features.

| Request | Why it doesn't need an agent |
|---|---|
| "7-day forecast for Kolkata" | One geocode call + one forecast call. Steps are always the same |
| "Current AQI in Delhi" | Single call |
| "Is this week's rain normal for Kolkata?" | Fixed workflow: forecast + 10-year history for the same dates, then compare |
| "Compare tomorrow in Goa vs Pune" | Fixed workflow: the same two calls per place, then compare. Places are given |

## 3. Problem

Real plans involve **several places, several days, and conditions that depend on each other**. Weather apps show one
place at a time. To plan a mountain trip, a drive through the ghats, or a spraying schedule, a person has to check many
locations and hours, keep the constraints in their head, and redo it all when the forecast changes. It is slow and
easy to get wrong.

## 4. Goals and non-goals

**Goals**
- Turn a goal with constraints into a concrete, weather-checked plan with reasons and a backup.
- Explore options on its own (places, dates, departure times) within a set budget of tool calls.
- Show its work: what it checked, what it ruled out, and why.
- Every number traceable to a tool result. No made-up forecasts, distances, or travel times.
- Run on Claude or OpenAI using the same tool layer.

**Non-goals (v1)**
- Training our own forecasting model.
- Official severe-weather warnings. The agent refers users to local authorities.
- Booking travel or acting in the real world. The agent advises; the user acts.

## 5. Target users

| Persona | Goal type |
|---|---|
| **Traveller** | Multi-stop trip where activities depend on conditions |
| **Weekend planner** | "Somewhere nice nearby", where the destination is the open question |
| **Driver / rider** | Long journey through weather-sensitive terrain (ghats, hills, coast) |
| **Small farmer / gardener** | Several weather-dependent tasks to fit into one week |
| **Event organiser** | Outdoor event needing a go/no-go call, plus backup date and venue options |

## 6. Core use cases

### UC1. Weather-aware trip itinerary

> "I'm in Sikkim Nov 2-7, based in Gangtok. I want one trek (needs a dry, clear day), one day at Tsomgo Lake, and a
> monastery day. Arrange the days so the weather fits each activity."

- **Agent test:** T1, T3, T4, T5
- **Why not a workflow:** each activity is at a different place and altitude, so the locations to check depend on the
  activities. Assigning activities to days means comparing options. If no day is clear enough for the trek, the agent
  must look at nearby alternatives or ask whether the trek can move.
- **Agent loop:** pick a location for each activity → fetch daily forecasts → find candidate days → check hourly data
  for the best windows (the trek needs a clear morning) → assign days → check for conflicts → plan + backup day.
- **Output:** a day-by-day itinerary with the reason for each placement, the best time of day, a packing note, and the
  backup if the forecast changes.

### UC2. "Find me somewhere"

> "We want to go camping this weekend within about 4 hours' drive of Bangalore. Dry, nights not below 12 °C, low wind."

- **Agent test:** T1, T2, T3
- **Why not a workflow:** the destination is the unknown. The agent proposes candidates, checks them, drops the ones
  that fail, and widens or narrows the search depending on how many pass.
- **Agent loop:** generate 6-10 candidate places → check distance → fetch forecasts → filter on the constraints → if
  fewer than two pass, relax the least important constraint *and say so*, or search further out → rank.
- **Output:** the top 2-3 places, how each meets the constraints, trade-offs, and the best night.

### UC3. Journey timing along a route

> "Driving Bangalore → Madikeri on Saturday. When should I leave to miss heavy rain on the ghat section?"

- **Agent test:** T1, T2, T3
- **Why not a workflow:** the weather has to be checked **where the car will be, at the time it will be there**. The
  agent picks points along the route, estimates arrival times for each possible departure time, and checks the hourly
  forecast at each point. Which departure times to test depends on what earlier checks found.
- **Agent loop:** split the route into points → estimate arrival times → for each candidate departure time, check
  hourly rain, visibility, and wind at each point → pick the safest departure time → note the riskiest stretch.
- **Output:** the recommended departure time, a timeline of conditions along the route, and the riskiest stretch and hour.

### UC4. Field operations scheduler

> "This week I need to: spray pesticide (6 dry hours after, wind under 15 km/h), irrigate twice unless more than
> 10 mm of rain falls, and harvest onions (needs 2 dry days in a row). Farm near Nashik."

- **Agent test:** T1, T3, T4
- **Why not a workflow:** the tasks interact. Rain that cancels irrigation might also block the harvest window, and
  spraying must not fall right before rain. The agent has to search for windows that work for all tasks together.
- **Agent loop:** fetch daily + hourly data → find feasible windows per task → resolve conflicts (harvest first,
  since its window is rarest) → schedule irrigation around the rain total → re-check the spray window → produce the
  schedule.
- **Output:** a task calendar with time windows, the reason for each, and what to check again mid-week.

### UC5. Outdoor event with backups

> "Outdoor reception for 150 people in Jaipur, Saturday 5-10 pm. Do we need a tent? If Saturday looks bad, what are
> our options?"

- **Agent test:** T1, T3, T4, T5
- **Why not a workflow:** whether to look further depends on the first answer. If Saturday is fine, the agent stops.
  If not, it checks nearby dates, alternative hours, and air quality or heat. It may ask whether the date or venue can
  change before going further.
- **Output:** a go / tent / move recommendation with thresholds ("book a tent if rain chance goes above 40% on
  Thursday's check"), plus the backup options.

### UC6 (later). Plan watch and re-plan

> "Keep an eye on my Sikkim plan and tell me if anything needs to change."

- **Agent test:** T1, T4
- Saves a plan from UC1-UC5, re-checks it on a schedule, and proposes specific changes when the forecast shifts.
  Needs plan storage and scheduling (M5).

## 7. Functional requirements

### 7.1 Architecture: Brain, Memory, Tools

```
            ┌──────────────────────── Agent loop ────────────────────────┐
 user ───►  │  BRAIN (AI model)  ◄──── context ────  MEMORY             │
            │   plans, decides,                       • working: chat,   │
            │   explains          ── remember ─────►    current plan,    │
            │        │                                  data cache       │
            │        │ tool calls (within budget)     • long-term:       │
            │        ▼                                  profile, prefs,  │
            │  TOOLS: weather · hourly · air quality ·  saved plans      │
            │  history · distance · elevation · memory tools             │
            └────────────────────────────────────────────────────────────┘
```

| Component | Responsibility | Design |
|---|---|---|
| **Brain** | Breaks the goal into steps, picks tools, weighs trade-offs, writes the answer | One `Brain` interface with Claude and OpenAI adapters. The agent loop doesn't know which provider is behind it. A scripted fake brain makes the loop unit-testable |
| **Working memory** | Everything for the current request: conversation, the plan being built, data already fetched | Session transcript + a cache of tool results. Repeating an identical lookup is free and doesn't use up the budget |
| **Long-term memory** | What the agent knows about the user across sessions | Local JSON store (provider-independent). The brain reads and writes it through memory tools. The profile summary is loaded at the start of each session |
| **Tools** | All facts and calculations | Defined once and shared by both providers. Each one is budgeted, returns errors as text, and never invents data |

**What goes into long-term memory**

| Kind | Example | Used for |
|---|---|---|
| Profile | "Lives in Pune", "prefers °F" | Default location and units, without asking |
| Preferences and limits | "Doesn't run above 30 °C", "Son has asthma: keep AQI under 100" | Applied automatically as constraints in UC1-UC5 |
| Saved plans | "Sikkim trip Nov 2-7: trek on Nov 4" | Follow-ups in later sessions; UC6 plan watch |
| Outcomes | "Nov 4 trek: forecast said clear, it rained after 2 pm" | Adds caution to similar plans later |

**Memory rules**
- **M1.** The agent saves only what is useful for future plans, and **says so when it saves something** ("I'll
  remember that your son has asthma").
- **M2.** The user can list, correct, and delete memories (`/memory`, `/forget`, or by asking).
- **M3.** Stored memories are applied as constraints but stated in the answer ("keeping AQI under 100 for your son").
  A memory never overrides what the user says in the current request.
- **M4.** Stored locally only. Nothing is shared between users.

### 7.2 Tools

| Tool | Purpose | Source | Status |
|---|---|---|---|
| `find_location` | Name to coordinates, with alternatives | Open-Meteo Geocoding | Built |
| `get_weekly_forecast` | Daily forecast, 1-16 days | Open-Meteo Forecast | Built |
| `get_hourly_forecast` | Hour-by-hour data for up to 3 days | Open-Meteo Forecast | Written, live-tested, not yet connected to the agents |
| `get_air_quality` | AQI and PM2.5, daily worst and average | Open-Meteo Air Quality | Written, live-tested, not yet connected to the agents |
| `get_climate_normals` | 10-year averages and records for given dates (context for "unusual") | Open-Meteo Archive | Written, live-tested, not yet connected to the agents |
| `get_distance` | Straight-line distance and estimated drive time between two points | Computed in code | Planned |
| `get_route` | Road route as points with times along the way, for UC3 | Routing service, TBD (see §12) | Planned |
| `get_elevation` | Altitude for a point (mountain plans; temperatures drop with height) | Open-Meteo Elevation | Planned |
| `remember` | Save a profile fact, preference, plan, or outcome | Long-term memory | Planned |
| `recall` | Search long-term memory | Long-term memory | Planned |
| `forget` | Delete a memory | Long-term memory | Planned |

All distances, times, averages, and AQI categories are computed in code, never estimated by the model.

### 7.3 Agent behaviour

- **R1. Plan first.** For a multi-step goal, state the plan in one or two lines before calling tools.
- **R2. Grounding.** Every number in the answer comes from a tool result in the same session.
- **R3. Bounded search.** At most 30 tool calls per request (configurable). When the budget runs out, return the best
  plan so far and say what wasn't checked.
- **R4. Visible trade-offs.** When a constraint has to be relaxed, say which one and by how much.
- **R5. Ask only when it matters.** Ask a question only if the answer would change the plan. Otherwise make a
  reasonable assumption and state it.
- **R6. Check the final plan.** Before answering, re-check the plan against the data it relied on.
- **R7. Uncertainty.** Mark any part of the plan that relies on days 5+ as less certain, and say when to check again.
- **R8. Answer first.** Lead with the plan, then the reasons, then the details. Include a short "checked and ruled
  out" list.
- **R9. Safety.** For dangerous conditions (heavy rain on hill roads, extreme heat, hazardous AQI), say so plainly and
  point to official sources.
- **R10. Follow-ups.** "What if we skip the trek?" revises the existing plan instead of starting over.

## 8. Non-functional requirements

| Area | Requirement |
|---|---|
| Latency | UC1-UC5 answered in under 60 s, with progress shown while the agent works |
| Cost | Track tokens and tool calls per request; report cost per completed plan |
| Providers | Claude (`claude-opus-5-5`) and OpenAI (configurable) share one tool layer |
| Reliability | Retry failed tool calls once; a failure must never produce invented data |
| Privacy | Long-term memory is a local file the user can view and delete; the agent announces every save (M1-M4) |
| Interface | v1: CLI, showing tool activity. Later: web or chat app |

## 9. Evaluation: proving the agent earns its place

- **Eval set:** 8-10 scenarios per use case (40-50 total), including cases where the first choice fails and the agent
  must go further.
- **Baseline:** a fixed workflow for each use case (fetch a fixed set of data, then make one model call). The agent
  must beat it on plan quality, or the use case is dropped.
- **Metrics:**
  - **Constraint satisfaction:** does the plan meet the user's constraints according to the fetched data? (≥ 90%)
  - **Grounding:** numbers match tool output (100%)
  - **Search quality:** did it find the best option that exists in the data? (checked against a brute-force run)
  - **Efficiency:** tool calls and cost per completed plan
  - **Honesty:** relaxed constraints and uncertainty are disclosed when they apply

## 10. Risks

| Risk | Mitigation |
|---|---|
| Agent loops or over-explores, so cost goes up | R3 budget; efficiency metric in evals |
| Made-up places, distances, or travel times | Distance, route, and elevation tools; R2 grounding check |
| Forecast uncertainty adds up across multi-day plans | R7; backup options; recommended re-check dates; UC6 |
| **Open-Meteo free tier: non-commercial only**, with rate limits (searches call it many times) | Fine for personal use; budget per request; paid plan if offered commercially |
| Routing service limits or licence | Decide the provider in §12 before building UC3 |
| Users treat the plan as a safety guarantee | R9; clear disclaimer on hazardous conditions |

## 11. Milestones

| Milestone | Scope | Status |
|---|---|---|
| **M1** | CLI agent for single-place forecasts (Claude + OpenAI) | Done (single-place forecasts now count as a direct lookup, not an agent feature) |
| **M2** | Brain interface + adapters; working and long-term memory; full tool registry with budget; agent instructions for R1-R10 and M1-M4; **UC1, UC2, UC5** | In progress |
| **M3** | Eval set + fixed-workflow baseline + scoring | Planned |
| **M4** | Routing tool + **UC3**; **UC4** | Planned |
| **M5** | Scheduled re-checks of saved plans (**UC6**); web or chat interface | Proposed |

## 12. Open questions

1. **Personal or offered to others?** This decides the Open-Meteo licence (free vs paid) and hosting.
2. **Routing provider for UC3:** the free public OSRM server (light use only), self-hosted OSRM, or a paid API?
3. **Candidate places for UC2:** use the model's knowledge (verified by geocoding and distance), or a places database
   such as OpenStreetMap?
4. **Primary provider:** Claude, OpenAI, or keep both?
5. **Memory location:** a local JSON file (default: `~/.weather_agent/memory.json`) is enough for one user on one
   machine. A web or chat interface with several users would need a database.
6. **Which use case to build first?** Suggested: UC1 (trip itinerary). It uses the most agent behaviours with tools
   that already exist.
