# gpa/github_api.py — utilitários GitHub (listar, baixar, enviar e excluir arquivos)
import os
import json
import base64
import requests
from urllib.parse import quote
import streamlit as st

# -------- Secrets helpers --------
def _get_secret(name, default=None):
    # Suporta chaves planas ou bloco [github] em secrets.toml
    if name in st.secrets:
        return st.secrets.get(name, default)
    if "github" in st.secrets and name in st.secrets["github"]:
        return st.secrets["github"].get(name, default)
    return default

def gh_credentials_ok():
    token = _get_secret("GITHUB_TOKEN")
    owner = _get_secret("REPO_OWNER")
    repo  = _get_secret("REPO_NAME")
    if not token:
        return False, "GITHUB_TOKEN ausente"
    if not owner or not repo:
        return False, "REPO_OWNER ou REPO_NAME ausentes"
    return True, ""

def gh_credentials_summary():
    owner = _get_secret("REPO_OWNER")
    repo  = _get_secret("REPO_NAME")
    branch = _get_secret("DEFAULT_BRANCH", "main")
    if not owner or not repo:
        return "repositório não configurado"
    return f"{owner}/{repo}@{branch}"

def _headers():
    token = _get_secret("GITHUB_TOKEN")
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

def _repo_info():
    owner = _get_secret("REPO_OWNER")
    repo  = _get_secret("REPO_NAME")
    branch = _get_secret("DEFAULT_BRANCH", "main")
    return owner, repo, branch

# -------- Listar / SHA / Download / Upload / Delete --------
def _get_file_sha(path_rel: str):
    owner, repo, branch = _repo_info()
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{quote(path_rel)}"
    r = requests.get(url, headers=_headers(), params={"ref": branch}, timeout=20)
    if r.status_code == 200:
        try:
            return r.json().get("sha"), None
        except Exception as e:
            return None, f"Erro parseando resposta SHA: {e}"
    elif r.status_code == 404:
        return None, "Arquivo não encontrado no repositório"
    else:
        return None, f"Falha ao obter SHA ({r.status_code}): {r.text}"

def gh_list_dir(path_rel: str):
    """Lista itens (arquivos/pastas) em um diretório do repo."""
    owner, repo, branch = _repo_info()
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{quote(path_rel)}"
    r = requests.get(url, headers=_headers(), params={"ref": branch}, timeout=20)
    if r.status_code == 200:
        items = r.json()
        if isinstance(items, dict):
            items = [items]
        out = []
        for it in items:
            out.append({
                "name": it.get("name"),
                "path": it.get("path"),
                "type": it.get("type"),
                "sha": it.get("sha"),
                "size": it.get("size"),
            })
        return True, out
    elif r.status_code == 404:
        return False, f"Diretório {path_rel} não encontrado"
    return False, f"Falha ao listar ({r.status_code}): {r.text}"

def gh_download_file_to_local(path_rel: str, local_path: str):
    """Baixa um arquivo (base64) do repo para o caminho local."""
    owner, repo, branch = _repo_info()
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{quote(path_rel)}"
    r = requests.get(url, headers=_headers(), params={"ref": branch}, timeout=30)
    if r.status_code != 200:
        return False, f"Falha ao obter conteúdo ({r.status_code}): {r.text}"
    data = r.json()
    if data.get("encoding") != "base64":
        return False, "Conteúdo não está em base64"
    content_b64 = data.get("content", "")
    try:
        raw = base64.b64decode(content_b64)
    except Exception as e:
        return False, f"Erro ao decodificar base64: {e}"
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    with open(local_path, "wb") as f:
        f.write(raw)
    return True, "OK"

def gh_upload_file_from_local(local_path: str, path_rel: str = None, message: str = None):
    """Envia/atualiza um arquivo local para o repo (PUT contents API)."""
    if not os.path.isfile(local_path):
        return False, f"Arquivo local não encontrado: {local_path}"
    ok, err = gh_credentials_ok()
    if not ok:
        return False, err
    owner, repo, branch = _repo_info()
    if path_rel is None:
        path_rel = local_path.replace("\\", "/").lstrip("./")
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{quote(path_rel)}"

    with open(local_path, "rb") as f:
        raw = f.read()
    content_b64 = base64.b64encode(raw).decode("utf-8")

    sha, _ = _get_file_sha(path_rel)  # se existir, faz update
    payload = {
        "message": message or f"chore: add/update {path_rel} via app",
        "content": content_b64,
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha

    r = requests.put(url, headers=_headers(), data=json.dumps(payload), timeout=30)
    if r.status_code in (200, 201):
        return True, "OK"
    return False, f"Falha ao enviar ({r.status_code}): {r.text}"

def gh_delete_file_from_repo(path_rel: str, message: str = None):
    """Exclui arquivo versionado no GitHub."""
    ok, err = gh_credentials_ok()
    if not ok:
        return False, err
    owner, repo, branch = _repo_info()
    sha, err_sha = _get_file_sha(path_rel)
    if not sha:
        return False, f"Não foi possível obter SHA: {err_sha}"
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{quote(path_rel)}"
    payload = {"message": message or f"chore: remove {path_rel} via app", "sha": sha, "branch": branch}
    r = requests.delete(url, headers=_headers(), data=json.dumps(payload), timeout=20)
    if r.status_code in (200, 204):
        return True, "OK"
    return False, f"Falha ao deletar ({r.status_code}): {r.text}"
