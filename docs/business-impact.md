# Business impact

This section describes what the platform is for. The counts below are from the seeded demonstration grid, not from a utility's production history. `data/processed/impact_snapshot.json` is rewritten every time bootstrap runs.

## Decisions the platform supports

**Reduce outages.** The outage model ranks assets for the next month. Crews use the ranking with the composite score, not instead of it. A high probability on an asset that is already critical is a candidate for switching plans and a field visit. A high probability on a young, maintained asset is a prompt to check the weather and load assumptions before rolling a truck.

**Improve reliability.** Health scores separate "old but maintained" from "old and failing." The incident explorer shows whether the last 90 days were weather, equipment, vegetation, or overload, which changes the work type.

**Plan maintenance.** The backlog is explicit: high score, at most one completed job in a year. That list is the preventive program, not a dump of every asset.

**Forecast demand.** The 90-day forecast is a location-level energy view for generation and import planning. It is a statistical forecast with climatological temperature, and the page says so.

**Brief leadership.** The executive page and the analyst answer the same four questions operators actually ask: where the risk sits, what failed, what to maintain, and what demand is coming.

## How to read the demonstration

Use the snapshot file after bootstrap for the current counts of assets, open incidents, critical assets, and the 90-day demand delta. Those numbers move only when the generator or the score changes. They are the right figures to put in a portfolio walkthrough, with the sentence "seeded demonstration grid" next to them.
