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
| Regional production (t) | `config/production.yaml` | DOA Statistik Tanaman Sayur-sayuran dan Tanaman Kontan 2023 | Filled (Phase 5) |
| Damage coefficients | added in Phase 5 | Literature / DOA | TODO |
| National supply-risk thresholds | `config/thresholds.yaml` → `national.supply_bands` | Project decision + source | TODO |

## Risk engine (Phase 4)

| Value | File | Needed source |
|---|---|---|
| Risk bands (Medium > 1.0, High ≥ 2.0) | `config/thresholds.yaml` `risk.bands` | Validate with DOA outbreak records |
| Rule window / full fraction | `config/thresholds.yaml` `risk.rule` | DOA / MARDI disease epidemiology |
| Whitefly vector proxy thresholds | `config/thresholds.yaml` `risk.vector_proxy` | DOA / MARDI entomology |
| Hutton criteria for Malaysia | `config/disease_profiles.yaml` `tomato:late_blight` | Local recalibration (UK rule) |
| TOM-CAST table verification | `config/tomcast_table.yaml` | Pitblado (1992) original |

## National dashboard (Phase 5)

| Value | File | Status / needed source |
|---|---|---|
| Regional production (chilli, tomato) | `config/production.yaml` | **Filled** from DOA Statistik Tanaman Sayur-sayuran dan Tanaman Kontan 2023, Jadual 2-1 |
| Damage coefficients per disease | `config/damage_functions.yaml` | TODO – DOA/MARDI yield-loss studies (linear placeholder) |
| Supply bands (Watch 2%, High 5%) | `config/thresholds.yaml` `national.supply_bands` | TODO – agree with FAMA/KPKM |
| Minimum scans per state (20) | `config/thresholds.yaml` `national.min_scans` | Engineering default |

## Farm monitor (Phase 9)

| Value | File | Status / needed source |
|---|---|---|
| Soil-moisture target band per crop (25–40 %) | `config/iot.yaml` `targets` | TODO – DOA/MARDI Pakej Teknologi Cili / Tomato, calibrated to the sensor used |
| EC (nutrient) target band per crop | `config/iot.yaml` `targets` | TODO – DOA/MARDI fertigation guidance |
| Air temperature and humidity bands | `config/iot.yaml` `targets` | TODO – DOA/MARDI |
| Leaf-wet alert (≥ 6 h) | `config/iot.yaml` `leaf_wet_alert_hours` | Engineering default, aligned with `rh_hours` in disease profiles |
| Offline after 45 min, low battery 20 % | `config/iot.yaml` | Engineering default |
| Simulator soil constants (root zone, field capacity, ET) | `config/iot.yaml` `simulator` | Engineering default – only drives the "Simulated device" |
