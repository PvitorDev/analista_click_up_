from fastapi import Depends, HTTPException

from app.auth import require_session
from app.db import fetch_one


def require_profile_access(pessoa_id: str, session: dict = Depends(require_session)) -> dict:
    """Guard do Bloco D. Aplicar em toda rota de perfil individual."""
    person = fetch_one("SELECT * FROM members WHERE clickup_id = %s", (str(pessoa_id),))
    if not person:
        raise HTTPException(status_code=404, detail="Não encontrado")
    if str(session["clickup_user_id"]) == str(pessoa_id):
        return session
    if session.get("role") == "admin":
        return session
    raise HTTPException(status_code=403, detail="Acesso negado")
