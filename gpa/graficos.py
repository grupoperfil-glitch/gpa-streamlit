import altair as alt
import pandas as pd

def grafico_tendencia_gpa_por_disciplina_turma(df: pd.DataFrame, disciplinas, turmas):
    """Linha por turma (facet por disciplina), GPA médio por trimestre."""
    dados = df[df["Disciplina"].isin(disciplinas) & df["Turma"].isin(turmas)].copy()
    grp = (
        dados
        .groupby(["Disciplina", "Turma", "Trimestre"], dropna=False)["GPA"]
        .mean()
        .reset_index()
    )
    linha = alt.Chart(grp).mark_line(point=True).encode(
        x=alt.X("Trimestre:O", title="Trimestre"),
        y=alt.Y("GPA:Q", title="GPA médio"),
        color=alt.Color("Turma:N", title="Turma"),
        tooltip=["Disciplina", "Turma", "Trimestre", "GPA"],
    ).properties(height=400)
    facet = linha.facet(column=alt.Column("Disciplina:N", title="Disciplina"))
    return facet.resolve_scale(y="independent")

def grafico_tendencia_gpa_por_estudante_disciplina(df: pd.DataFrame, disciplinas, estudantes):
    """Linha por estudante (facet por disciplina), GPA por trimestre."""
    dados = df[df["Disciplina"].isin(disciplinas) & df["Estudante"].isin(estudantes)].copy()
    linha = alt.Chart(dados).mark_line(point=True).encode(
        x=alt.X("Trimestre:O", title="Trimestre"),
        y=alt.Y("GPA:Q", title="GPA"),
        color=alt.Color("Estudante:N", title="Estudante"),
        tooltip=["Estudante", "Disciplina", "Trimestre", "GPA"],
    ).properties(height=400)
    facet = linha.facet(column=alt.Column("Disciplina:N", title="Disciplina"))
    return facet.resolve_scale(y="independent")

def grafico_gpa_individual_estudante_disciplinas(df: pd.DataFrame, estudante: str, disciplinas):
    """
    Um estudante, várias disciplinas: linhas coloridas por disciplina, GPA vs Trimestre.
    Requer colunas: Estudante, Disciplina, Trimestre, GPA (e opcional Turma para tooltip).
    """
    dados = df[(df["Estudante"] == estudante) & (df["Disciplina"].isin(disciplinas))].copy()
    if dados.empty:
        # Mensagem amigável quando não há dados
        return alt.Chart(pd.DataFrame({"msg": ["Sem dados para os filtros atuais."]})) \
                 .mark_text(size=16) \
                 .encode(text="msg")
    chart = alt.Chart(dados).mark_line(point=True).encode(
        x=alt.X("Trimestre:O", title="Trimestre"),
        y=alt.Y("GPA:Q", title="GPA"),
        color=alt.Color("Disciplina:N", title="Disciplina"),
        tooltip=["Estudante", "Turma", "Disciplina", "Trimestre", "GPA"],
    ).properties(height=420)
    return chart
