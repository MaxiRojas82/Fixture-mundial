import os
import httpx
from dotenv import load_dotenv
from src.models.prode import ProdeUser, ProdeGroup, Prediction

load_dotenv()

_API_KEY = os.getenv("FIREBASE_API_KEY", "")
_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "")
_BASE = f"https://firestore.googleapis.com/v1/projects/{_PROJECT_ID}/databases/(default)/documents"


def is_configured() -> bool:
    return bool(_API_KEY and _PROJECT_ID)


# ── Firestore serialization ───────────────────────────────────────────────────

def _v(val) -> dict:
    if isinstance(val, str):
        return {"stringValue": val}
    if isinstance(val, bool):
        return {"booleanValue": val}
    if isinstance(val, int):
        return {"integerValue": str(val)}
    if isinstance(val, list):
        return {"arrayValue": {"values": [_v(i) for i in val]}}
    if isinstance(val, dict):
        return {"mapValue": {"fields": {k: _v(vv) for k, vv in val.items()}}}
    return {"nullValue": None}


def _parse(raw: dict):
    if "stringValue" in raw:
        return raw["stringValue"]
    if "integerValue" in raw:
        return int(raw["integerValue"])
    if "booleanValue" in raw:
        return raw["booleanValue"]
    if "arrayValue" in raw:
        return [_parse(i) for i in raw["arrayValue"].get("values", [])]
    if "mapValue" in raw:
        return {k: _parse(vv) for k, vv in raw["mapValue"].get("fields", {}).items()}
    return None


def _fields(doc: dict) -> dict:
    return {k: _parse(vv) for k, vv in doc.get("fields", {}).items()}


# ── Operations ────────────────────────────────────────────────────────────────

async def save_user(user: ProdeUser) -> None:
    if not is_configured():
        return
    async with httpx.AsyncClient() as c:
        await c.patch(
            f"{_BASE}/users/{user.id}",
            params={"key": _API_KEY},
            json={"fields": {
                "displayName": _v(user.display_name),
                "groupCode": _v(user.group_code),
            }},
            timeout=5,
        )


async def save_prediction(pred: Prediction) -> None:
    if not is_configured():
        return
    async with httpx.AsyncClient() as c:
        await c.patch(
            f"{_BASE}/predictions/{pred.user_id}_{pred.match_id}",
            params={"key": _API_KEY},
            json={"fields": {
                "userId": _v(pred.user_id),
                "matchId": _v(pred.match_id),
                "homeGoals": _v(pred.home_goals),
                "awayGoals": _v(pred.away_goals),
            }},
            timeout=5,
        )


async def create_group(group: ProdeGroup) -> None:
    if not is_configured():
        return
    async with httpx.AsyncClient() as c:
        await c.patch(
            f"{_BASE}/groups/{group.code}",
            params={"key": _API_KEY},
            json={"fields": {
                "name": _v(group.name),
                "ownerId": _v(group.owner_id),
                "memberIds": _v(group.member_ids),
                "memberNames": _v(group.member_names),
            }},
            timeout=5,
        )


async def get_group(code: str) -> ProdeGroup | None:
    if not is_configured():
        return None
    async with httpx.AsyncClient() as c:
        resp = await c.get(f"{_BASE}/groups/{code}", params={"key": _API_KEY}, timeout=10)
    if resp.status_code != 200:
        return None
    d = _fields(resp.json())
    return ProdeGroup(
        code=code,
        name=d.get("name", ""),
        owner_id=d.get("ownerId", ""),
        member_ids=d.get("memberIds") or [],
        member_names=d.get("memberNames") or {},
    )


async def join_group(code: str, uid: str, display_name: str) -> ProdeGroup | None:
    group = await get_group(code)
    if group is None:
        return None
    if uid not in group.member_ids:
        group.member_ids.append(uid)
    group.member_names[uid] = display_name
    await create_group(group)
    return group


async def get_predictions_for_users(user_ids: list[str]) -> list[Prediction]:
    if not is_configured() or not user_ids:
        return []
    query = {
        "structuredQuery": {
            "from": [{"collectionId": "predictions"}],
            "where": {
                "fieldFilter": {
                    "field": {"fieldPath": "userId"},
                    "op": "IN",
                    "value": {"arrayValue": {
                        "values": [{"stringValue": uid} for uid in user_ids[:10]]
                    }},
                }
            },
        }
    }
    async with httpx.AsyncClient() as c:
        resp = await c.post(
            f"{_BASE}:runQuery",
            params={"key": _API_KEY},
            json=query,
            timeout=15,
        )
    if resp.status_code != 200:
        return []
    results = []
    for item in resp.json():
        doc = item.get("document")
        if not doc:
            continue
        d = _fields(doc)
        results.append(Prediction(
            user_id=d.get("userId", ""),
            match_id=int(d.get("matchId") or 0),
            home_goals=int(d.get("homeGoals") or 0),
            away_goals=int(d.get("awayGoals") or 0),
        ))
    return results
