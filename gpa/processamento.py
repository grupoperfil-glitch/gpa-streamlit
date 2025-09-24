import pandas as pd
import numpy as np
from typing import List




def calcular_media_por_trimestre(df: pd.DataFrame, rotulos_p1: List[str], rotulos_conclusiva: List[str]) -> pd.DataFrame:
"""Calcula Média por (Estudante, Turma, Disciplina, Trimestre) como (P1+Conclusiva)/2.
df deve conter: Estudante, Turma, Disciplina, Avaliacao, Nota, Trimestre
rotulos_*: listas de strings para identificar 'P1' e 'Conclusiva' (case-insensitive, contém)
"""
trab = df.copy()


def classificar(av: str) -> str:
s = str(av).strip().lower()
if any(lbl.lower() in s for lbl in rotulos_p1):
return "P1"
if any(lbl.lower() in s for lbl in rotulos_conclusiva):
return "Conclusiva"
return "Outro"


trab["_tipo"] = trab["Avaliacao"].apply(classificar)


# Manter apenas P1 e Conclusiva
trab = trab[trab["_tipo"].isin(["P1", "Conclusiva"])]


# Em caso de duplicatas, tirar média por tipo
agg = (
trab
.groupby(["Estudante", "Turma", "Disciplina", "Trimestre", "_tipo"], dropna=False)["Nota"]
.mean()
.unstack("_tipo")
.reset_index()
)


# Média
agg["Media"] = (agg.get("P1") + agg.get("Conclusiva")) / 2.0


return agg[["Estudante", "Turma", "Disciplina", "Trimestre", "P1", "Conclusiva", "Media"]]




def aplicar_mapeamento_gpa(df_medias: pd.DataFrame, tabela_map: pd.DataFrame) -> pd.DataFrame:
"""Aplica tabela de Média→GPA (faixas inclusivas [min, max]).
tabela_map deve ter colunas: min, max, gpa
"""
mapa = tabela_map.sort_values(["min", "max"]).reset_index(drop=True)


def media_para_gpa(x: float) -> float:
if pd.isna(x):
return np.nan
linha = mapa[(mapa["min"] <= x) & (x <= mapa["max"])].head(1)
if not linha.empty:
return float(linha.iloc[0]["gpa"])
return np.nan


out = df_medias.copy()
out["GPA"] = out["Media"].apply(media_para_gpa)
return out
