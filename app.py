# app.py — Aplicação Streamlit (PT-BR) para converter Notas → GPA
# Requisitos: ver requirements.txt
# Estrutura esperada do repo:
# .
# ├─ app.py
# ├─ requirements.txt
# ├─ .streamlit/config.toml
# ├─ gpa/
# │  ├─ __init__.py
# │  ├─ config.py
# │  ├─ io.py
# │  ├─ processamento.py
# │  └─ graficos.py
# └─ data/.gitkeep

import os
import time
import pandas as pd
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

# Configuração da página
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
    # Pré-visualização (apenas primeiras linhas)
    df_preview = leitura_robusta(arquivo, nrows=200)
    amostra_colunas = list(df_preview.columns)
    st.dataframe(df_preview.head(20), use_container_width=True)
else:
    st.info("Faça upload de um arquivo para visualizar as colunas detectadas.")

# Seletores de colunas (fora do bloco if/else acima)
esquema = ESQUEMA_PADRAO.copy()

c1, c2, c3 = st.columns(3)
with c1:
    coluna_nome = st.selectbox(
        "Coluna de Nome do Estudante",
        amostra_colunas,
        index=amostra_colunas.index(esquema["student"]) if esquema["student"] in amostra_colunas else 0,
    )
    coluna_turma = st.selectbox(
        "Coluna de Turma",
        amostra_colunas,
        index=amostra_colunas.index(esquema["turma"]) if esquema["turma"] in amostra_colunas else 0,
    )
with c2:
    coluna_disc = st.selectbox(
        "Coluna de Disciplina",
        amostra_colunas,
        index=amostra_colunas.index(esquema["discipline"]) if esquema["discipline"] in amostra_colunas else 0,
    )
    coluna_avaliacao = st.selectbox(
        "Coluna de Tipo de Avaliação",
        amostra_colunas,
        index=amostra_colunas.index(esquema["assessment"]) if esquema["assessment"] in amostra_colunas else 0,
    )
with c3:
    coluna_nota = st.selectbox(
        "Coluna de Nota",
        amostra_colunas,
        index=amostra_colunas.index(esquema["grade"]) if esquema["grade"] in amostra_colunas else 0,
    )

st.subheader("Trimestre")
cc1, cc2 = st.columns(2)
with cc1:
    coluna_trimestre_opt = st.selectbox(
        "Coluna de Trimestre (se existir)",
        ["<nenhuma>"] + amostra_colunas,
        index=(amostra_colunas.index("Trimestre") + 1) if "Trimestre" in amostra_colunas else 0,
    )
with cc2:
    trimestre_constante = st.select_slider(
        "Se não houver coluna, selecione o trimestre para todo o arquivo",
        options=[1, 2, 3],
        value=1,
    )

st.subheader("Rótulos de P1 & Conclusiva")
cp1, ccon = st.columns(2)
with cp1:
    texto_p1 = st.text_input(
        "Rótulos para P1 (ex.: 'P1', 'Progressiva I')",
        value=", ".join(ROTULOS_PADRAO_P1),
    )
    rotulos_p1 = [s.strip() for s in texto_p1.split(",") if s.strip()]
with ccon:
    texto_conc = st.text_input(
        "Rótulos para Conclusiva (ex.: 'Conclusiva', 'CF')",
        value=", ".join(ROTULOS_PADRAO_CONCLUSIVA),
    )
    rotulos_conclusiva = [s.strip() for s in texto_conc.split(",") if s.strip()]

# -------------------------
# 3) Tabela de conversão Média → GPA
# -------------------------
st.header("3) Tabela de conversão de Média → GPA (edite se necessário)")

tabela_map = tabela_gpa_padrao()
tabela_map = st.data_editor(
    tabela_map,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "min": st.column_config.NumberColumn("min", step=0.1),
        "max": st.column_config.NumberColumn("max", step=0.1),
        "gpa": st.column_config.NumberColumn("gpa", step=0.1),
    },
    key="gpa_editor",
)

# -------------------------
# 4) Processar & Salvar
# -------------------------
st.header("4) Processar e salvar dados")
diretorio_salvar = st.text_input("Pasta para salvar dados (no repositório)", value=DIRETORIO_DADOS_PADRAO)
st.caption("Todos os dados ficarão em ./data (por padrão).")

if st.button("Processar arquivo", type="primary", disabled=(arquivo is None)):
    garantir_diretorio(diretorio_salvar)

    # MUITO IMPORTANTE: reposiciona o ponteiro do arquivo antes da leitura final
    try:
        arquivo.seek(0)
    except Exception:
        pass

    # Leitura completa do arquivo
    df = leitura_robusta(arquivo)

    # Normalização de nota (vírgula → ponto)
    if coluna_nota in df.columns:
        df[coluna_nota] = converter_decimal(df[coluna_nota])

    # Determinar Trimestre
    if coluna_trimestre_opt != "<nenhuma>" and coluna_trimestre_opt in df.columns:
        df["Trimestre"] = df[coluna_trimestre_opt]
    else:
        df["Trimestre"] = trimestre_constante

    # Renomear colunas principais para nomes internos padronizados
    df = df.rename(
        columns={
            coluna_nome: "Estudante",
            coluna_turma: "Turma",
            coluna_disc: "Disciplina",
            coluna_avaliacao: "Avaliacao",
            coluna_nota: "Nota",
        }
    )[
        ["Estudante", "Turma", "Disciplina", "Avaliacao", "Nota", "Trimestre"]
    ]

    # 1) Média por trimestre = (P1 + Conclusiva)/2
    medias = calcular_media_por_trimestre(
        df,
        rotulos_p1=rotulos_p1,
        rotulos_conclusiva=rotulos_conclusiva,
    )

    # 2) Aplicar mapeamento Média → GPA
    gpa_df = aplicar_mapeamento_gpa(medias, tabela_map)

    # 3) Persistir dados
    ts = time.strftime("%Y%m%d-%H%M%S")
    nome_base = os.path.splitext(arquivo.name)[0] if hasattr(arquivo, "name") else "arquivo"
    caminho_saida = os.path.join(diretorio_salvar, f"processado_{nome_base}_{ts}.csv")
    gpa_df.to_csv(caminho_saida, index=False, encoding="utf-8-sig")

    st.success(f"Arquivo processado e salvo em {caminho_saida}")
    st.dataframe(gpa_df.head(50), use_container_width=True)

    st.session_state["_ultimo_arquivo_processado"] = caminho_saida

st.divider()

# -------------------------
# Dashboard
# -------------------------
st.header("Dashboard de Tendências de GPA")

caminho_dados = st.session_state.get("_ultimo_arquivo_processado")
if caminho_dados and os.path.exists(caminho_dados):
    dados = pd.read_csv(caminho_dados)

    aba1, aba2 = st.tabs(["GPA por disciplina e turma", "GPA por estudante e disciplina"])

    with aba1:
        opcoes_disc = sorted(dados["Disciplina"].dropna().unique())
        opcoes_turma = sorted(dados["Turma"].dropna().unique())
        sel_disc = st.multiselect("Selecione disciplinas", opcoes_disc, default=opcoes_disc[:3])
        sel_turma = st.multiselect("Selecione turmas", opcoes_turma, default=opcoes_turma[:5])

        if sel_disc and sel_turma:
            fig1 = grafico_tendencia_gpa_por_disciplina_turma(dados, disciplinas=sel_disc, turmas=sel_turma)
            st.altair_chart(fig1, use_container_width=True)

    with aba2:
        opcoes_disc2 = sorted(dados["Disciplina"].dropna().unique())
        sel_disc2 = st.multiselect("Selecione disciplinas", opcoes_disc2, default=opcoes_disc2[:1], key="disc2")
        opcoes_est = sorted(dados["Estudante"].dropna().unique())
        sel_est = st.multiselect("Selecione estudantes", opcoes_est, default=opcoes_est[:10])

        if sel_disc2 and sel_est:
            fig2 = grafico_tendencia_gpa_por_estudante_disciplina(dados, disciplinas=sel_disc2, estudantes=sel_est)
            st.altair_chart(fig2, use_container_width=True)
else:
    st.info("Carregue e processe um arquivo para ver os gráficos.")
