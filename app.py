# app.py — Aplicação Streamlit (PT-BR) para converter Notas → GPA e gerenciar exclusões
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
from gpa.github_api import (  # opcional: exclusão no GitHub
    gh_credentials_ok,
    gh_delete_file_from_repo,
    gh_credentials_summary,
)

# -------------------------
# Configuração da página
# -------------------------
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
# 3) Tabela de conversão e ESCALA
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

st.subheader("Escala das suas notas/médias")
escala_sel = st.radio(
    "Como estão as notas no arquivo?",
    ["Auto (detectar)", "0–10", "0–100"],
    horizontal=True,
    index=0,
)
escala_param = "auto" if "Auto" in escala_sel else ("0-10" if escala_sel == "0–10" else "0-100")

# -------------------------
# 4) Processar & Salvar
# -------------------------
st.header("4) Processar e salvar dados")
diretorio_salvar = st.text_input("Pasta para salvar dados (no repositório)", value=DIRETORIO_DADOS_PADRAO)
st.caption("Todos os dados ficarão em ./data (por padrão).")

if st.button("Processar arquivo", type="primary", disabled=(arquivo is None)):
    garantir_diretorio(diretorio_salvar)
    try:
        arquivo.seek(0)
    except Exception:
        pass

    df = leitura_robusta(arquivo)

    # Normalização de nota (vírgula → ponto)
    if coluna_nota in df.columns:
        df[coluna_nota] = converter_decimal(df[coluna_nota])

    # Determinar Trimestre
    if coluna_trimestre_opt != "<nenhuma>" and coluna_trimestre_opt in df.columns:
        df["Trimestre"] = df[coluna_trimestre_opt]
    else:
        df["Trimestre"] = trimestre_constante

    # Renomear colunas principais
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

    # 2) Aplicar mapeamento Média → GPA (com padronização de escala)
    gpa_df = aplicar_mapeamento_gpa(medias, tabela_map, escala=escala_param)

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
# 5) Gerenciar dados (Excluir)
# -------------------------
st.header("5) Gerenciar dados (Excluir)")

def listar_arquivos(pasta: str):
    if not os.path.isdir(pasta):
        return []
    full = [os.path.join(pasta, f) for f in os.listdir(pasta)]
    return sorted([p for p in full if os.path.isfile(p)])

col_g, col_info = st.columns([2, 1])
with col_g:
    st.write(f"Diretório atual: `{diretorio_salvar}`")
    arquivos = listar_arquivos(diretorio_salvar)

    if not arquivos:
        st.info("Nenhum arquivo encontrado em `./data`. Processe um arquivo para gerar resultados.")
    else:
        infos = []
        for p in arquivos:
            try:
                size = os.path.getsize(p)
                mtime = os.path.getmtime(p)
            except Exception:
                size, mtime = None, None
            infos.append({
                "arquivo": os.path.basename(p),
                "caminho": p,
                "tamanho_bytes": size,
                "modificado_em": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime)) if mtime else "",
            })
        df_infos = pd.DataFrame(infos)
        st.dataframe(df_infos, use_container_width=True, hide_index=True)

        opcoes = [os.path.basename(p) for p in arquivos]
        selecao = st.multiselect("Selecione arquivos para excluir", opcoes, default=[])

        excluir_github = st.checkbox("Excluir também do GitHub (se configurado em Secrets)", value=False)
        gh_ok, gh_err = gh_credentials_ok()
        if excluir_github:
            if gh_ok:
                st.success(f"GitHub Secrets OK — {gh_credentials_summary()}")
            else:
                st.warning(f"Secrets do GitHub ausentes/incompletos: {gh_err}")

        if st.button("Excluir selecionados", type="secondary", disabled=(len(selecao) == 0)):
            sucesso_local = 0
            sucesso_gh = 0
            for nome_arq in selecao:
                full_path = os.path.join(diretorio_salvar, nome_arq)
                if not os.path.abspath(full_path).startswith(os.path.abspath(diretorio_salvar) + os.sep):
                    st.error(f"Bloqueado (fora da pasta de dados): {full_path}")
                    continue
                try:
                    os.remove(full_path)
                    sucesso_local += 1
                    st.success(f"Excluído localmente: {full_path}")
                except FileNotFoundError:
                    st.warning(f"Arquivo já não existe localmente: {full_path}")
                except Exception as e:
                    st.error(f"Falha ao excluir localmente {full_path}: {e}")
                if excluir_github and gh_ok:
                    rel_path = os.path.relpath(full_path, start=".")
                    ok, status_msg = gh_delete_file_from_repo(rel_path, message=f"chore: remove {rel_path} via app")
                    if ok:
                        sucesso_gh += 1
                        st.success(f"Excluído do GitHub: {rel_path}")
                    else:
                        st.error(f"Falha ao excluir do GitHub {rel_path}: {status_msg}")
            st.info(f"Resumo: {sucesso_local} excluído(s) localmente; {sucesso_gh} excluído(s) no GitHub.")

with col_info:
    st.markdown("**Observações:**")
    st.markdown("- A exclusão local remove o arquivo **desta instância** do app (armazenamento efêmero).")
    st.markdown("- A exclusão no **GitHub** requer Secrets válidos e o arquivo **estar versionado** no repositório.")
    st.markdown("- Caminhos fora da pasta de dados são **bloqueados** por segurança.")

st.divider()

# -------------------------
# 6) Dashboard
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
