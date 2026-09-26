# Values that must come from official sources

Nothing in this list may be invented. Until filled, the app runs on clearly flagged placeholders.

| Value | File | Source to use | Status |
|---|---|---|---|
| Fertiliser prices (RM/kg) | `config/fertiliser_products.yaml` → `price_rm_per_kg` | DOA / FAMA / retailer survey, with date | TODO |
| Chilli N, P₂O₅, K₂O per growth stage (kg/ha) | `config/crop_requirements.yaml` | DOA Pakej Teknologi Cili | TODO (placeholder numbers) |
| Tomato N, P₂O₅, K₂O per growth stage (kg/ha) | `config/crop_requirements.yaml` | DOA Pakej Teknologi Tomato | TODO (placeholder numbers) |
| Tomato pH range | `config/crop_requirements.yaml` | DOA Pakej Teknologi Tomato | TODO |
| Soil level factors | `config/crop_requirements.yaml` → `soil_level_factor` | DOA soil-test guidance | TODO (placeholder) |
| Retail bag sizes | `config/thresholds.yaml` → `fertiliser.bag_sizes_kg` | Retailer survey | TODO verify |
| Disease parameters not given in the brief | `config/disease_profiles.yaml` (`TODO` markers) | DOA / MARDI / literature | TODO |
| Regional production (t) | added in Phase 5 | DOSM / DOA Statistik Tanaman | TODO |
| Damage coefficients | added in Phase 5 | Literature / DOA | TODO |
| National supply-risk thresholds | `config/thresholds.yaml` → `national.supply_bands` | Project decision + source | TODO |
