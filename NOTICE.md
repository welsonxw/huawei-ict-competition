# NOTICE

This project reuses code from **AgriTech** by Om Roy (https://github.com/omroy07/AgriTech), licensed under the MIT License:

> MIT License – Copyright (c) 2026 Om Roy
>
> Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.

## Reused parts

| File in this repo | Source in AgriTech |
|---|---|
| `ml/models/resnet9.py` | ResNet9 architecture from `Plant Disease Detection/plant-disease.ipynb` |
| `ml/labels.py` (`PLANTVILLAGE_LABELS`) | Class list from the same notebook |
| `ml/weights/plant-disease-model.pth` (downloaded, not committed) | `Plant Disease Detection/plant-disease-model.pth` |
| `ml/samples/*.JPG` | `Plant Disease Detection/test/` (PlantVillage images) |

## Third-party data

| Data | Source | Licence / terms |
|---|---|---|
| Malaysian state boundaries (`config/malaysia_states.geojson`) | geoBoundaries gbOpen MYS ADM1, © OpenStreetMap contributors | ODbL 1.0 |
| Weather forecasts (fetched at runtime) | Open-Meteo | CC BY 4.0 |
| Chilli and tomato production by state (`config/production.yaml`) | Jabatan Pertanian Malaysia (DOA), Statistik Tanaman Sayur-sayuran dan Tanaman Kontan 2023 | Cited as the official source |
