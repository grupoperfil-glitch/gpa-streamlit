# app.py — Aplicação Streamlit (PT-BR)
# - Upload em lote (vários arquivos)
# - Processa e salva em ./data
# - Opcional: envia cópia para GitHub
# - Dashboard carrega TODOS os processados (./data) e oferece sincronizar do GitHub
# - Filtros globais + Tabela sempre aparente + Gráficos comparativos

import os
import re
import io
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

# Imports dos gráficos com fallback seguro (evita quebra se commit parcial ocorrer)
try:
    from gpa.graficos import (
        grafico_tendencia_gpa_por_disciplina_turma,
        grafico_tendencia_gpa_por_estudante_disciplina,
        grafico_gpa_individual_estudante_disciplinas,
    )
    _GRAFICO_INDIVIDUAL_OK = True
except ImportError as _e:
    from gpa.graficos import (
        grafico_tendencia_gpa_por_disciplina_turma,
        grafico_tendencia_gpa_por_estudante_disciplina,
    )
    grafico_gpa_individual_estudante_disciplinas = None
    _GRAFICO_INDIVIDUAL_OK = False
    _GRAFICOS_IMPORT_ERROR = str(_e)

from gpa.github_api import (
    gh_credentials_ok,
    gh_credentials_summary,
    gh_upload_file_from_local,
    gh_list_dir,
    gh_download_file_to_local,
    gh_delete_file_from_repo,
)

# -------------------------
# Configuração da página
# -------------------------
st.set_page_config(page_title="Conversor de Notas → GPA", layout="wide")
st.title("Conversor de Notas → GPA (Streamlit)")
st.caption("Se suas notas usam vírgula decimal, a aplicação converte automaticamente.")

# -------------------------
# 0) Helpers
# -------------------------
def extrair_serie(txt: str) -> str:
    """Extrai 'Série' a partir do texto de Turma (ex.: '6º ano A' -> '6º ano')."""
    if not isinstance(txt, str):
        return ""
    s = txt.lower().replace("º", "").strip()
    m = re.search(r"(\d{1,2})\s*ano", s)
    if m:
        return f"{int(m.group(1))}º ano"
    m = re.search(r"^(\d{1,2})", s)  # '9a', '1b', etc.
    if m:
        return f"{int(m.group(1))}º ano"
    return txt

def listar_arquivos(pasta: str):
    if not os.path.isdir(pasta):
        return []
    full = [os.path.join(pasta, f) for f in os.listdir(pasta)]
    return sorted([p for p in full if os.path.isfile(p)])

def listar_processados_locais(pasta: str):
    return [
        p for p in listar_arquivos(pasta)
        if os.path.basename(p).startswith("processado_") and p.endswith(".csv")
    ]

def carregar_todos_processados(pasta: str) -> pd.DataFrame:
    """Concatena todos os CSVs processados da pasta."""
    files = listar_processados_locais(pasta)
    if not files:
        return pd.DataFrame()
    dfs = []
    for f in files:
        try:
            dfs.append(pd.read_csv(f))
        except Exception as e:
            st.warning(f"Falha ao ler {os.path.basename(f)}: {e}")
    if not dfs:
        return pd.DataFrame()
    out = pd.concat(dfs, ignore_index=True)
    # Garantias mínimas de colunas e padronização
    expected = ["Estudante", "Turma", "Disciplina", "Trimestre", "P1", "Conclusiva", "Media", "GPA"]
    for c in expected:
        if c not in out.columns:
            out[c] = pd.NA
    # MediaPadronizada pode não existir em arquivos antigos → derivar
    if "MediaPadronizada" not in out.columns:
        out["MediaPadronizada"] = out["Media"].apply(lambda x: (x/10.0) if pd.notna(x) and x > 10 else x)
    return out

# -------------------------
# 1) Upload (agora em lote)
# -------------------------
st.header("1) Envie o(s) arquivo(s) de notas (CSV/XLSX)")
arquivos = st.file_uploader(
    "Selecione um ou vários arquivos CSV/XLSX",
    type=["csv", "xlsx", "xls"],
    accept_multiple_files=True
)

# -------------------------
# 2) Mapeamento de esquema & rótulos (baseado no primeiro arquivo)
# -------------------------
st.header("2) Mapeie as colunas do seu arquivo")

amostra_colunas = ["Nome", "Turma", "DescrMateria", "DescrAvaliacao", "Nota", "Trimestre"]
if arquivos:
    # Usa o primeiro arquivo para deduzir colunas
    f0 = arquivos[0]
    df_preview = leitura_robusta(f0, nrows=200)
    amostra_colunas = list(df_preview.columns)
    st.caption(f"Prévia do primeiro arquivo: **{f0.name}**")
    st.dataframe(df_preview.head(20), use_container_width=True)
else:
    st.info("Faça upload de pelo menos um arquivo para visualizar as colunas detectadas.")

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
        "Se não houver coluna, selecione o trimestre para os arquivos",
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
    "Como estão as notas nos arquivos?",
    ["Auto (detectar)", "0–10", "0–100"],
    horizontal=True,
    index=0,
)
escala_param = "auto" if "Auto" in escala_sel else ("0-10" if escala_sel == "0–10" else "0-100")

# Salvar cópia no GitHub após processar?
gh_ok_flag, gh_err_msg = gh_credentials_ok()
salvar_no_github_flag = st.checkbox(
    "Salvar uma cópia no GitHub após processar (requer Secrets configurados)",
    value=False,
    help="Envia cada CSV gerado para a pasta data/ do repositório via GitHub API.",
)

# -------------------------
# 4) Processar & Salvar (em lote)
# -------------------------
st.header("4) Processar e salvar dados")
diretorio_salvar = st.text_input("Pasta para salvar dados (no repositório)", value=DIRETORIO_DADOS_PADRAO)
st.caption("Todos os dados ficarão em ./data (por padrão).")

if st.button("Processar arquivo(s)", type="primary", disabled=(not arquivos)):
    garantir_diretorio(diretorio_salvar)
    total_ok = 0
    enviados_gh = 0
    for f in arquivos:
        # reposiciona ponteiro e lê
        try:
            f.seek(0)
        except Exception:
            pass
        df = leitura_robusta(f)

        # Normalização de nota (vírgula → ponto)
        if coluna_nota in df.columns:
            df[coluna_nota] = converter_decimal(df[coluna_nota])

        # Determinar Trimestre
        if coluna_trimestre_opt != "<nenhuma>" and coluna_trimestre_opt in df.columns:
            df["Trimestre"] = df[coluna_trimestre_opt]
        else:
            df["Trimestre"] = trimestre_constante

        # Renomear colunas principais
        try:
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
        except Exception as e:
            st.error(f"[{f.name}] Falha ao padronizar colunas: {e}")
            continue

        # 1) Média por trimestre = (P1 + Conclusiva)/2
        medias = calcular_media_por_trimestre(
            df,
            rotulos_p1=rotulos_p1,
            rotulos_conclusiva=rotulos_conclusiva,
        )

        # 2) Aplicar mapeamento Média → GPA (com padronização de escala)
        gpa_df = aplicar_mapeamento_gpa(medias, tabela_map, escala=escala_param)

        # 3) Persistir dados localmente
        ts = time.strftime("%Y%m%d-%H%M%S")
        nome_base = os.path.splitext(f.name)[0] if hasattr(f, "name") else "arquivo"
        caminho_saida = os.path.join(diretorio_salvar, f"processado_{nome_base}_{ts}.csv")
        try:
            gpa_df.to_csv(caminho_saida, index=False, encoding="utf-8-sig")
            total_ok += 1
            st.success(f"[{f.name}] Salvo em {caminho_saida}")
        except Exception as e:
            st.error(f"[{f.name}] Falha ao salvar: {e}")
            continue

        # 4) (Opcional) enviar cópia ao GitHub
        if salvar_no_github_flag:
            if gh_ok_flag:
                rel_path = os.path.relpath(caminho_saida, start=".").replace("\\", "/")
                ok_up, msg_up = gh_upload_file_from_local(
                    caminho_saida,
                    path_rel=rel_path,
                    message=f"feat: adiciona {rel_path} (processado via app)"
                )
                if ok_up:
                    enviados_gh += 1
                    st.info(f"[{f.name}] Cópia enviada ao GitHub: {rel_path}")
                else:
                    st.error(f"[{f.name}] Falha ao enviar ao GitHub: {msg_up}")
            else:
                st.warning(f"[{f.name}] Secrets do GitHub ausentes/incompletos: {gh_err_msg}")

    st.info(f"Resumo do processamento: {total_ok} arquivo(s) salvo(s) localmente; {enviados_gh} enviado(s) ao GitHub.")
    # Atualiza seleção para último processado mais recente
    st.session_state["_ultimo_arquivo_processado"] = None

st.divider()

# -------------------------
# 5) Gerenciar dados (Excluir)
# -------------------------
st.header("5) Gerenciar dados (Excluir)")

col_g, col_info = st.columns([2, 1])
with col_g:
    st.write(f"Diretório atual: `{diretorio_salvar}`")
    arquivos_locais = listar_arquivos(diretorio_salvar)

    if not arquivos_locais:
        st.info("Nenhum arquivo encontrado em `./data`. Processe arquivos para gerar resultados.")
    else:
        infos = []
        for p in arquivos_locais:
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

        opcoes = [os.path.basename(p) for p in arquivos_locais]
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
                    rel_path = os.path.relpath(full_path, start=".").replace("\\", "/")
                    ok, status_msg = gh_delete_file_from_repo(rel_path, message=f"chore: remove {rel_path} via app")
                    if ok:
                        sucesso_gh += 1
                        st.success(f"Excluído do GitHub: {rel_path}")
                    else:
                        st.error(f"Falha ao excluir do GitHub {rel_path}: {status_msg}")
            st.info(f"Resumo: {sucesso_local} excluído(s) localmente; {sucesso_gh} excluído(s) no GitHub.")

with col_info:
    st.markdown("**Observações:**")
    st.markdown("- A exclusão local remove o arquivo **desta instância** (armazenamento efêmero).")
    st.markdown("- A exclusão no **GitHub** requer Secrets válidos e o arquivo **estar versionado**.")
    st.markdown("- Caminhos fora da pasta de dados são **bloqueados** por segurança.")

st.divider()

# -------------------------
# 6) Dashboard (multi-arquivo + filtros globais + tabela sempre aparente)
# -------------------------
st.header("Dashboard com filtros globais e comparação entre turmas")

# 6.0) Sincronizar tudo do GitHub → ./data (opcional)
gh_ok2, gh_err2 = gh_credentials_ok()
with st.expander("Sincronização com GitHub (opcional)"):
    if gh_ok2:
        st.caption(f"Conectado a: {gh_credentials_summary()}")
        if st.button("Sincronizar TODOS os 'processado_*.csv' do GitHub para ./data"):
            ok, itens = gh_list_dir("data")
            if ok and isinstance(itens, list):
                nomes_gh = [i["name"] for i in itens if i.get("type") == "file"
                            and i.get("name", "").startswith("processado_")
                            and i.get("name", "").endswith(".csv")]
                baixados = 0
                for nome in nomes_gh:
                    rel_path = f"data/{nome}"
                    local_dest = os.path.join("data", nome)
                    if not os.path.exists(local_dest):  # evita baixar duplicado
                        okb, msg = gh_download_file_to_local(rel_path, local_dest)
                        if okb:
                            baixados += 1
                        else:
                            st.error(f"Erro ao baixar {rel_path}: {msg}")
                st.success(f"Sincronização concluída. Baixados {baixados} arquivo(s).")
            else:
                st.error(f"Falha ao listar pasta data/ no GitHub: {itens}")
    else:
        st.info("Configure os Secrets do GitHub para habilitar sincronização (GITHUB_TOKEN, REPO_OWNER, REPO_NAME, DEFAULT_BRANCH).")

# 6.1) Carregar todos os processados locais
dados_all = carregar_todos_processados(diretorio_salvar)
if dados_all.empty:
    st.info("Nenhum arquivo processado encontrado em ./data. Processe ou sincronize do GitHub.")
else:
    # Derivar Série
    dados_all["Serie"] = dados_all["Turma"].astype(str).apply(extrair_serie)

    # ---- Filtros globais ----
    fcol1, fcol2, fcol3 = st.columns(3)
    with fcol1:
        series_disp = sorted([s for s in dados_all["Serie"].dropna().unique() if str(s).strip() != ""])
        serie_sel = st.multiselect("Série", series_disp, default=series_disp)
    with fcol2:
        turmas_disp = sorted(dados_all.query("Serie in @serie_sel")["Turma"].dropna().unique()) if serie_sel else []
        turma_sel = st.multiselect("Turma", turmas_disp, default=turmas_disp)
    with fcol3:
        trimestres_disp = sorted(dados_all.query("Serie in @serie_sel and Turma in @turma_sel")["Trimestre"].dropna().unique()) if turma_sel else []
        trim_sel = st.multiselect("Trimestre", trimestres_disp, default=trimestres_disp)

    fcol4, fcol5 = st.columns(2)
    with fcol4:
        disc_disp = sorted(dados_all.query(
            "Serie in @serie_sel and Turma in @turma_sel and Trimestre in @trim_sel"
        )["Disciplina"].dropna().unique()) if trim_sel else []
        disc_sel = st.multiselect("Disciplina", disc_disp, default=disc_disp)
    with fcol5:
        est_disp = sorted(dados_all.query(
            "Serie in @serie_sel and Turma in @turma_sel and Trimestre in @trim_sel and Disciplina in @disc_sel"
        )["Estudante"].dropna().unique()) if disc_sel else []
        est_sel = st.multiselect("Estudante", est_disp, default=est_disp[: min(20, len(est_disp))])

    # Aplicar filtros
    dados_filtrados = dados_all.copy()
    if serie_sel:
        dados_filtrados = dados_filtrados[dados_filtrados["Serie"].isin(serie_sel)]
    if turma_sel:
        dados_filtrados = dados_filtrados[dados_filtrados["Turma"].isin(turma_sel)]
    if trim_sel:
        dados_filtrados = dados_filtrados[dados_filtrados["Trimestre"].isin(trim_sel)]
    if disc_sel:
        dados_filtrados = dados_filtrados[dados_filtrados["Disciplina"].isin(disc_sel)]
    if est_sel:
        dados_filtrados = dados_filtrados[dados_filtrados["Estudante"].isin(est_sel)]

    # ---- Tabela sempre aparente ----
    st.subheader("Tabela (Série/Turma/Estudante/Disciplina/Trimestre, P1, Conclusiva, Média, GPA)")
    tabela_cols = ["Serie", "Turma", "Estudante", "Disciplina", "Trimestre", "P1", "Conclusiva", "Media", "GPA"]
    tabela_view = dados_filtrados[tabela_cols].sort_values(["Serie", "Turma", "Estudante", "Disciplina", "Trimestre"])
    st.dataframe(tabela_view, use_container_width=True, hide_index=True)

    # Download da tabela filtrada
    csv_bytes = tabela_view.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button("Baixar tabela filtrada (CSV)", data=csv_bytes, file_name="gpa_filtrado.csv", mime="text/csv")

    st.divider()

    # ---- Gráficos (usam os dados filtrados) ----
    aba1, aba2 = st.tabs([
        "Comparação por disciplina × turma (GPA médio por trimestre)",
        "Tendência por estudante × disciplina (GPA)",
    ])

    with aba1:
        if not disc_sel or not turma_sel:
            st.info("Selecione pelo menos uma disciplina e uma turma para visualizar.")
        else:
            fig1 = grafico_tendencia_gpa_por_disciplina_turma(dados_filtrados, disciplinas=disc_sel, turmas=turma_sel)
            st.altair_chart(fig1, use_container_width=True)

    with aba2:
        if not disc_sel or not est_sel:
            st.info("Selecione pelo menos uma disciplina e um estudante para visualizar.")
        else:
            fig2 = grafico_tendencia_gpa_por_estudante_disciplina(dados_filtrados, disciplinas=disc_sel, estudantes=est_sel)
            st.altair_chart(fig2, use_container_width=True)

    # Aba 3 (individual) – se a função existir
    if _GRAFICO_INDIVIDUAL_OK and grafico_gpa_individual_estudante_disciplinas:
        aba3 = st.tabs(["GPA individual (série→turma→estudante)"])[0]
        with aba3:
            if not serie_sel or not turma_sel:
                st.info("Selecione pelo menos uma Série e uma Turma.")
            else:
                dados_ind = dados_filtrados.copy()
                series_loc = sorted(set(serie_sel))
                serie_escolha = st.selectbox("Série (para visão individual)", series_loc, index=0)
                turmas_loc = sorted(dados_ind.query("Serie == @serie_escolha")["Turma"].dropna().unique())
                turma_escolha = st.selectbox("Turma (para visão individual)", turmas_loc, index=0)
                alunos_loc = sorted(dados_ind.query(
                    "Serie == @serie_escolha and Turma == @turma_escolha"
                )["Estudante"].dropna().unique())
                if not alunos_loc:
                    st.info("Não há estudantes para os filtros selecionados.")
                else:
                    aluno_escolha = st.selectbox("Estudante", alunos_loc, index=0)
                    disps = sorted(dados_ind.query(
                        "Serie == @serie_escolha and Turma == @turma_escolha and Estudante == @aluno_escolha"
                    )["Disciplina"].dropna().unique())
                    if not disps:
                        st.info("Não há disciplinas para este estudante.")
                    else:
                        dis_sel3 = st.multiselect("Disciplinas (individual)", disps, default=disps[:min(4, len(disps))])
                        if dis_sel3:
                            dados_f = dados_ind.query(
                                "Serie == @serie_escolha and Turma == @turma_escolha and Estudante == @aluno_escolha"
                            )
                            fig3 = grafico_gpa_individual_estudante_disciplinas(dados_f, estudante=aluno_escolha, disciplinas=dis_sel3)
                            st.altair_chart(fig3, use_container_width=True)
                        else:
                            st.info("Selecione pelo menos uma disciplina.")
    else:
        st.warning("O gráfico individual não foi carregado. Verifique/atualize o arquivo 'gpa/graficos.py' no GitHub.")
