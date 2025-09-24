import os
import io
import pandas as pd
from typing import Optional

try:
    import chardet
except Exception:
    chardet = None

def garantir_diretorio(caminho: str) -> None:
    os.makedirs(caminho, exist_ok=True)

def detectar_codificacao(arquivo_bytes: bytes) -> str:
    if chardet is None:
        return "utf-8"
    res = chardet.detect(arquivo_bytes)
    enc = res.get("encoding") or "utf-8"
    return enc

def leitura_robusta(arquivo_ou_buffer, nrows: Optional[int] = None) -> pd.DataFrame:
    """
    Lê CSV/XLS/XLSX com tratamento de delimitador e encoding.
    - Tenta CSV com ';' e ',' (detectando encoding)
    - Faz fallback para Excel (openpyxl)
    """
    bruto = arquivo_ou_buffer.read() if hasattr(arquivo_ou_buffer, "read") else None

    # Tentar CSV primeiro
    if bruto is not None:
        enc = detectar_codificacao(bruto)
        for sep in [";", ","]:
            try:
                df = pd.read_csv(io.BytesIO(bruto), sep=sep, nrows=nrows, encoding=enc)
                if df.shape[1] >= 3:
                    return df
            except Exception:
                pass

    # Tentar Excel
    try:
        if bruto is not None:
            return pd.read_excel(io.BytesIO(bruto), nrows=nrows, engine="openpyxl")
        else:
            return pd.read_excel(arquivo_ou_buffer, nrows=nrows, engine="openpyxl")
    except Exception:
        pass

    # Último recurso: CSV utf-8 com ';'
    if bruto is not None:
        return pd.read_csv(io.BytesIO(bruto), sep=";", nrows=nrows, encoding="utf-8", engine="python")
    else:
        return pd.read_csv(arquivo_ou_buffer, sep=";", nrows=nrows, encoding="utf-8", engine="python")

def converter_decimal(serie: pd.Series) -> pd.Series:
    """
    Converte strings com vírgula decimal para float.
    Remove separador de milhar e troca vírgula por ponto.
    """
    s = serie.astype(str).str.strip()
    s = s.str.replace("\u00a0", " ")
    s = s.str.replace(".", "", regex=False)  # remove milhares
    s = s.str.replace(",", ".", regex=False)  # vírgula → ponto
    return pd.to_numeric(s, errors="coerce")
