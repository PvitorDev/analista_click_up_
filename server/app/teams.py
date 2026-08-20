"""Lista workspaces autorizados no token de serviço (GET /v2/team)."""

from app.clickup.client import service_client
from app.config import settings


def main() -> None:
    client = service_client()
    teams = client.workspaces()
    if not teams:
        print("Nenhum workspace neste token. Confira CLICKUP_API_TOKEN.")
        return
    print("Workspaces autorizados (GET /api/v2/team):")
    for team in teams:
        print(f"  {team.get('name')} → {team.get('id')}")
    configured = (settings.clickup_team_id or "").strip()
    if configured:
        print(f"\nCLICKUP_TEAM_ID no .env: {configured}")
    elif len(teams) == 1:
        print("\nSó há um workspace: o sync usa este id automaticamente.")
    else:
        print("\nHá vários workspaces. O app usa o primeiro até você trocar no menu do header.")


if __name__ == "__main__":
    main()
