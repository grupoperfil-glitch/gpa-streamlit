import os
import io
import time
import pandas as pd
import numpy as np
import streamlit as st


from gpa.config import (
DIRETORIO_DADOS_PADRAO,
ESQUEMA_PADRAO,
ROTULOS_PADRAO_P1,
ROTULOS_PADRAO_CONCLUSIVA,
tabela_gpa_padrao,
)
from gpa.io import (
leitura_robusta,
garantir_diretorio,
converter_decimal,
)
from gpa.processamento import (
calcular_media_por_trimestre,
aplicar_mapeamento_gpa,
)
from gpa.graficos import (
grafico_tendencia_gpa_por_disciplina_turma,
grafico_tendencia_gpa_por_estudante_disciplina,
)


st.set_page_config(page_title="Conversor de Notas → GPA", layout="wide")


st.title("Conversor de Notas → GPA (Streamlit)")
st.caption("Se suas notas usam vírgula decimal, a aplicação converte automaticamente.")


# -------------------------
# 1) Upload
# -------------------------
st.header("1) Envie o arquivo de notas (CSV/XLSX)")
arquivo = st.file_uploader("Selecione um arquivo CSV/XLSX", type=["csv", "xlsx", "xls"])


# -------------------------
# 2) Mapeamento de esquema & rótulos
# -------------------------
st.header("2) Mapeie as colunas do seu arquivo")


amostra_colunas = ["Nome", "Turma", "DescrMateria", "DescrAvaliacao", "Nota", "Trimestre"]
if arquivo is not None:
df_preview = leitura_robusta(arquivo, nrows=200)
amostra_colunas = list(df_preview.columns)
st.dataframe(df_preview.head(20), use_container_width=True)
else:
st.info("Faça upload de um arquivo para visualizar as colunas detectadas.")


esquema = ESQUEMA_PADRAO.copy()


c1, c2, c3 = st.columns(3)
with c1:
coluna_nome = st.selectbox("Coluna de Nome do Estudante", amostra_colunas, index=amostra_colunas.index(esquema["student"]) if esquema["student"] in amostra_colunas else 0)
coluna_turma = st.selectbox("Coluna de Turma", amostra_colunas, index=amostra_colunas.index(esquema["turma"]) if esquema["turma"] in amostra_colunas else 0)
with c2:
coluna_disc = st.selectbox("Coluna de Disciplina", amostra_colunas, index=amostra_colunas.index(esquema["discipline"]) if esquema["discipline"] in amostra_colunas else 0)
coluna_avaliacao = st.selectbox("Coluna de Tipo de Avaliação", amostra_colunas, index=amostra_colunas.index(esquema["assessment"]) if esquema["assessment"] in amostra_colunas else 0)
with c3:
st.info("Carregue e processe um arquivo para ver os gráficos.")
