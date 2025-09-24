import altair as alt
import pandas as pd




def grafico_tendencia_gpa_por_disciplina_turma(df: pd.DataFrame, disciplinas, turmas):
dados = df[df["Disciplina"].isin(disciplinas) & df["Turma"].isin(turmas)].copy()
# GPA médio por (Disciplina, Turma, Trimestre)
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
tooltip=["Disciplina", "Turma", "Trimestre", "GPA"]
).properties(height=400)


facet = linha.facet(column=alt.Column("Disciplina:N", title="Disciplina"))
return facet.resolve_scale(y="independent")




def grafico_tendencia_gpa_por_estudante_disciplina(df: pd.DataFrame, disciplinas, estudantes):
dados = df[df["Disciplina"].isin(disciplinas) & df["Estudante"].isin(estudantes)].copy()
linha = alt.Chart(dados).mark_line(point=True).encode(
x=alt.X("Trimestre:O", title="Trimestre"),
y=alt.Y("GPA:Q", title="GPA"),
color=alt.Color("Estudante:N", title="Estudante"),
tooltip=["Estudante", "Disciplina", "Trimestre", "GPA"]
).properties(height=400)


facet = linha.facet(column=alt.Column("Disciplina:N", title="Disciplina"))
return facet.resolve_scale(y="independent")
