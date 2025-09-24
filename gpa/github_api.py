# gpa/github_api.py — Funções auxiliares para excluir arquivos via GitHub API
import json
import requests
from urllib.parse import quote
import streamlit as st

def _get_secret(name, default=None):
    # Suporta tanto chaves planas quanto bloco [github] em secrets.toml
    if name in st.secrets:
        return st.secrets.get(name, default)
    if "github" in st.secrets and name in st.secrets["github"]:
        return st.secrets["github"].get(name, default)
    return default

def gh_credentials_ok():
    token = _get_secret("GITHUB_TOKEN")
    owner = _get_secret("REPO_OWNER")
    repo = _get_secret("REPO_NAME")
    branch = _get_secret("DEFAULT_BRANCH", "main")
    if not token:
        return False, "GITHUB_TOKEN ausente"
    if not owner or not repo:
        return False, "REPO_OWNER ou REPO_NAME ausentes"
    return True, ""

def gh_credentials_summary():
    owner = _get_secret("REPO_OWNER")
    repo = _get_secret("REPO_NAME")
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
    repo = _get_secret("REPO_NAME")
    branch = _get_secret("DEFAULT_BRANCH", "main")
    return owner, repo, branch

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

def gh_delete_file_from_repo(path_rel: str, message: str = None):
    """
    Deleta um arquivo versionado no GitHub em {repo}/{path_rel}.
    Retorna (True, msg) em sucesso, (False, erro) em falha.
    """
    ok, err = gh_credentials_ok()
    if not ok:
        return False, err

    owner, repo, branch = _repo_info()
    sha, err_sha = _get_file_sha(path_rel)
    if not sha:
        return False, f"Não foi possível obter SHA: {err_sha}"

    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{quote(path_rel)}"
    payload = {
        "message": message or f"chore: remove {path_rel} via app",
        "sha": sha,
        "branch": branch,
    }
    r = requests.delete(url, headers=_headers(), data=json.dumps(payload), timeout=20)
    if r.status_code in (200, 204):
        return True, "OK"
    return False, f"Falha ao deletar ({r.status_code}): {r.text}"
