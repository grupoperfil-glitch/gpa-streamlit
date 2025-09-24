# gpa-streamlit
Conversor de Notas → GPA
# Streamlit — Conversor de Notas → GPA


Aplicação **Streamlit** para converter exports de notas brasileiras em **GPA** no padrão dos EUA, salvar resultados por **trimestre** em `./data` e visualizar tendências por **disciplina×turma** e por **estudante×disciplina**.


## ✨ Funcionalidades
- Upload de CSV/XLSX com leitura robusta (delimitador e encoding)
- Mapeamento de colunas (Estudante, Turma, Disciplina, Avaliação, Nota, Trimestre)
- Reconhecimento flexível de rótulos **P1** e **Conclusiva**
- Média por trimestre: **(P1 + Conclusiva)/2**
- Tabela **Média→GPA** editável na interface
- Persistência local em `./data` dentro do repositório
- Dashboards:
- Tendência de GPA **por disciplina × turma**
- Tendência de GPA **por estudante × disciplina**


## 🚀 Como executar
```bash
pip install -r requirements.txt
streamlit run app.py
