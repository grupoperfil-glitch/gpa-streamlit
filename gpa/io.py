# gpa/io.py — Leitura robusta de CSV/XLSX com detecção de encoding e delimitador
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


def _detectar_codificacao(bruto: bytes) -> str:
    """Tenta detectar encoding com chardet; se falhar, retorna 'utf-8'."""
    if chardet is None:
        return "utf-8"
    try:
        res = chardet.detect(bruto) or {}
        enc = res.get("encoding")
        if enc:
            return enc
    except Exception:
        pass
    return "utf-8"


def _try_read_csv_from_bytes(bruto: bytes, nrows: Optional[int] = None) -> Optional[pd.DataFrame]:
    """
    Tenta ler CSV a partir de bytes usando:
      - múltiplos encodings: UTF-8/UTF-8-SIG (prioridade), detectado, latin-1, cp1252
      - múltiplos separadores: ';', ',', '\\t', e auto (sep=None)
    Último recurso: encoding_errors='ignore' para não quebrar por caracteres inválidos.
    """
    enc_detect = _detectar_codificacao(bruto)
    enc_candidates = []
    # Preferimos UTF-8 primeiro para evitar mojibake quando chardet "chuta" cp1252
    for e in ["utf-8", "utf-8-sig", enc_detect, "latin-1", "cp1252"]:
        if e and e.lower() not in [x.lower() for x in enc_candidates]:
            enc_candidates.append(e)

    seps = [";", ",", "\t", None]  # None => auto-detecção (engine='python')

    # 1) Tenta combinações encoding × sep
    for enc in enc_candidates:
        for sep in seps:
            try:
                df = pd.read_csv(
                    io.BytesIO(bruto),
                    sep=sep,
                    nrows=nrows,
                    encoding=enc,
                    engine="python",  # necessário para sep=None (sniffer)
                )
                # Heurística mínima: pelo menos 2 colunas
                if df.shape[1] >= 2:
                    return df
            except Exception:
                continue

    # 2) Último recurso: ignora erros de decodificação
    try:
        df = pd.read_csv(
            io.BytesIO(bruto),
            sep=None,
            nrows=nrows,
            engine="python",
            encoding="utf-8",
            encoding_errors="ignore",  # pandas >= 1.4
        )
        return df
    except Exception:
        return None


def leitura_robusta(arquivo_ou_buffer, nrows: Optional[int] = None) -> pd.DataFrame:
    """
    Lê CSV/XLS/XLSX com tratamento de encoding e delimitador.
    - Se for CSV: tenta múltiplos encodings e separadores; último recurso ignora erros.
    - Se for Excel: tenta via openpyxl.
    - Mantém compatibilidade com nrows para pré-visualização.
    """
    bruto = None
    # Captura bytes se for um buffer/file-like
    try:
        if hasattr(arquivo_ou_buffer, "read"):
            bruto = arquivo_ou_buffer.read()
        elif isinstance(arquivo_ou_buffer, (bytes, bytearray)):
            bruto = bytes(arquivo_ou_buffer)
    except Exception:
        bruto = None

    # 1) Se temos bytes, tentar como CSV primeiro
    if bruto is not None:
        df_csv = _try_read_csv_from_bytes(bruto, nrows=nrows)
        if df_csv is not None:
            return df_csv

        # 2) Tentar Excel a partir dos bytes
        try:
            return pd.read_excel(io.BytesIO(bruto), nrows=nrows, engine="openpyxl")
        except Exception:
            pass

        # 3) Último fallback CSV com ignore (caso extremo)
        df_ignore = _try_read_csv_from_bytes(bruto, nrows=nrows)
        if df_ignore is not None:
            return df_ignore

        raise ValueError("Não foi possível ler o arquivo (CSV/Excel) — verifique encoding e formato.")

    # 4) Caso não sejam bytes (ex.: caminho no disco)
    enc_candidates = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]
    seps = [";", ",", "\t", None]
    for enc in enc_candidates:
        for sep in seps:
            try:
                df = pd.read_csv(arquivo_ou_buffer, sep=sep, nrows=nrows, encoding=enc, engine="python")
                if df.shape[1] >= 2:
                    return df
            except Exception:
                continue

    try:
        return pd.read_excel(arquivo_ou_buffer, nrows=nrows, engine="openpyxl")
    except Exception:
        pass

    try:
        return pd.read_csv(
            arquivo_ou_buffer,
            sep=None,
            nrows=nrows,
            engine="python",
            encoding="utf-8",
            encoding_errors="ignore",
        )
    except Exception as e:
        raise ValueError(f"Não foi possível ler o arquivo. Último erro: {e}")


def converter_decimal(serie: pd.Series) -> pd.Series:
    """
    Converte strings com vírgula decimal para float.
    Remove separador de milhar e troca vírgula por ponto.
    """
    s = serie.astype(str).str.strip()
    s = s.str.replace("\u00a0", " ")
    s = s.str.replace(".", "", regex=False)      # remove milhares (ponto)
    s = s.str.replace(",", ".", regex=False)     # vírgula → ponto
    return pd.to_numeric(s, errors="coerce")
