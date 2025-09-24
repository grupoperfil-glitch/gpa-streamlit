import pandas as pd


DIRETORIO_DADOS_PADRAO = "./data"


# Padrões de mapeamento (pode ajustar na UI)
ESQUEMA_PADRAO = {
"student": "Nome",
"turma": "Turma",
"discipline": "DescrMateria",
"assessment": "DescrAvaliacao",
"grade": "Nota",
"trimester": None,
}


# Rótulos comuns em exports escolares
ROTULOS_PADRAO_P1 = ["P1", "Progressiva I", "Prova 1"]
ROTULOS_PADRAO_CONCLUSIVA = ["Conclusiva", "CF", "Prova Final"]




def tabela_gpa_padrao():
"""Tabela padrão de Média→GPA (ajustável na interface). Faixas inclusivas [min, max]."""
dados = [
{"min": 9.0, "max": 10.0, "gpa": 4.0},
{"min": 8.5, "max": 8.9, "gpa": 3.7},
{"min": 8.0, "max": 8.4, "gpa": 3.5},
{"min": 7.5, "max": 7.9, "gpa": 3.3},
{"min": 7.0, "max": 7.4, "gpa": 3.0},
{"min": 6.5, "max": 6.9, "gpa": 2.7},
{"min": 6.0, "max": 6.4, "gpa": 2.3},
{"min": 5.5, "max": 5.9, "gpa": 2.0},
{"min": 5.0, "max": 5.4, "gpa": 1.7},
{"min": 4.0, "max": 4.9, "gpa": 1.0},
{"min": 0.0, "max": 3.9, "gpa": 0.0},
]
return pd.DataFrame(dados, columns=["min", "max", "gpa"]).sort_values(["min", "max"]).reset_index(drop=True)
