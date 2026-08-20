# Proxy agregado de demanda pré-hospitalar

O perfil usado pela API deriva da camada oficial de acidentes de trânsito com
vítimas da CET/INFOCRIM, publicada pelo GeoSampa. Ele representa somente uma
fração da possível demanda pré-hospitalar e **não contém chamados do SAMU**.

O snapshot bruto é utilizado apenas durante a preparação e não pode ser
persistido no repositório. O artefato final agrega as ocorrências em células H3
de resolução 8 e remove identificadores, endereços, coordenadas individuais,
datas e horários exatos. A posição de cada ponto exibido é a de um nó público da
malha OpenStreetMap próximo ao centro da célula, não a posição de um acidente.

Fonte e licença:

- CET/GeoSampa — Acidentes de trânsito com vítimas (INFOCRIM/RDO)
- Metadados: https://metadados.geosampa.prefeitura.sp.gov.br/geonetwork/srv/resources/datasets/597833ac-aa90-4b4b-8a48-3be0a9a8c009
- Licença: CC BY-SA 4.0
- Período observado no snapshot: 2021-02-28 a 2022-02-28

O perfil fornece pesos espaciais e horários observados. O volume absoluto de
chamados usado na simulação continua sendo uma calibração sintética explícita.

## Reconstrução

Execute a partir da raiz do repositório:

```bash
backend/.venv/Scripts/python.exe scripts/build_cet_demand_profile.py \
  --nodes data/demo/spatial/artifacts/nodes.parquet \
  --cells data/demo/spatial/artifacts/h3_cells.geojson \
  --output data/demo/demand/demand_profile.json \
  --retrieved-at 2026-08-20
```
