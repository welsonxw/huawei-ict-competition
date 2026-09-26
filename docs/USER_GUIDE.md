# User guide

Switch between **BM** and **EN** at any time with the toggle at the top right.

## Farmers

1. **Log in** with the username and password your extension officer or team gave you.
2. **Scan tab**
   - Pick your plot and crop (chilli or tomato), then take or choose a clear photo of **one leaf in daylight**.
   - You get the diagnosis, how sure the model is, the top 3 possibilities and a **heatmap** showing where the model looked.
   - If the model is not sure, you see "Not sure – please retake the photo" and an expert will check the scan.
   - **What to do next** gives 3–5 steps that take the next 48 hours of weather into account (for example, wait until leaves are dry before spraying).
   - **Ask the assistant** explains the result in simple words. Always follow the pesticide label for doses.
   - **Fertiliser planner** suggests up to two products and amounts for your plot size and growth stage, and liming advice if the soil pH is low. Values marked as placeholders are not for field use yet.
3. **Outbreak map**: risk in your area today, in 3 days and in 5 days. Medium or High needs recent reports nearby, not just wet weather.
4. **National dashboard**: which states may lose the most harvest in the next two weeks.

## Experts

Experts see everything farmers see, plus the **Expert review queue** at the bottom of the Scan tab:

- Each card shows the photo, the model's guess with confidence and the top 3.
- **Confirm** if the model is right, or pick the correct label and press **Correct to**.
- Confirmed labels replace the model's label on the map and dashboard.
- **Export training set** downloads a zip with one folder per disease for retraining:
  ```bash
  unzip training-set-chilli-*.zip -d data/exports/training-set
  python -m ml.train --data data/chilli --extra data/exports/training-set/chilli --version v2
  ```
  The **Model v1 → v2** panel then shows the new accuracy.

## Demo data

When the **"Simulated scenario – not real data"** banner is shown, the outbreak and dashboard numbers come from generated demo scans, not real farms.

## Admins

- Create accounts: `flask create-user NAME --role farmer|expert` (inside the backend container: `docker compose exec backend flask create-user ...`).
- Load or clear demo data: `flask seed-demo` / `flask seed-demo --clear`.
- Deployment: see `docs/DEPLOY_HUAWEI_CLOUD.md`.

## Farm game

The **Farm game** tab is a Stardew-style farm for teaching the scan → action-plan loop.

- Move with the arrow keys/WASD or the on-screen pad; press Space/E (or **Act**) to till, plant, water, harvest or scan the tile in front of you. Refill water at the pond. Sleep at the house door to end the day.
- Each night, the chance a plant gets sick comes from `GET /api/game/outlook`, which reads the real risk engine bands (Low/Medium/High) for the chosen farm location. Game day 1 uses today's risk, day 4 the +3-day forecast and day 6 the +5-day forecast, then the week repeats. Rain in the real 48 h forecast waters the field.
- Scanning a sick plant shows the real TaniGuard action plan for that disease and weather; the matching treatment cures it. Untreated plants die after 3 days and spread to neighbours.
- With **Risk data: Simulated scenario** the page shows the "Simulated scenario – not real data" banner, like the outbreak map.
- Growth times, coins and infection chances are game rules, not agronomic data. Progress is saved in the browser only; nothing is written to the database.
