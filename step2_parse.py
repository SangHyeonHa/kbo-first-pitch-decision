"""
step2_parse.py — ② 파싱 담당
경기 원본 JSON(이닝별 응답 리스트)을 '표'로 바꾼다. 표 = 행(dict)들의 리스트.

원본 구조 (W07의 중첩 dict·list와 같다):
  payload["result"]["textRelayData"]["textRelays"]  ← 타석(블록) 리스트
      relay["textOptions"]  ← 이벤트(투구·타석결과·교체 …) 리스트
      relay["ptsOptions"]   ← 투구 추적값(위치·궤적) 리스트
  relay["inn"] = 이닝, relay["homeOrAway"] = "0"(초, 원정 공격) / "1"(말, 홈 공격)

★ 주의: currentGameState(볼카운트·아웃·주자·점수)는 '그 이벤트 직후' 상태다.
   그래서 이름에 _after 를 붙여 둔다.

[수업 밖] open/with + json.load (파일을 읽어 dict/list로 만들기)
"""
import json

import config


def load_raw(path):
    """원본 JSON 파일 하나를 읽어 리스트(이닝별 응답들)로 돌려준다."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def to_int(value):
    """None·빈 문자열은 0, 나머지는 정수로."""
    if value is None or value == "":
        return 0
    return int(value)


def parse_events(payloads):
    """1행 = 1이벤트. 같은 seqno(이벤트 번호)가 여러 응답에 겹칠 수 있어서 set으로 중복을 거른다."""
    events = []
    seen = set()
    for payload in payloads:
        data = payload["result"]["textRelayData"]
        for relay in data.get("textRelays", []):
            for opt in relay.get("textOptions", []):
                if opt["seqno"] in seen:
                    continue
                seen.add(opt["seqno"])
                state = opt.get("currentGameState") or {}
                events.append({
                    "game_id": data["gameId"],
                    "seqno": opt["seqno"],
                    "inn": to_int(relay["inn"]),
                    "half": to_int(relay["homeOrAway"]),
                    "type": opt.get("type"),
                    "text": opt.get("text") or "",
                    "pitch_num": opt.get("pitchNum"),
                    "pitch_result": opt.get("pitchResult"),
                    "pitch_type": opt.get("stuff"),
                    "pts_id": opt.get("ptsPitchId"),
                    "batter": state.get("batter"),
                    "pitcher": state.get("pitcher"),
                    "balls_after": to_int(state.get("ball")),
                    "strikes_after": to_int(state.get("strike")),
                    "outs_after": to_int(state.get("out")),
                    "base1": str(state.get("base1", "0")),
                    "base2": str(state.get("base2", "0")),
                    "base3": str(state.get("base3", "0")),
                    "home_score": to_int(state.get("homeScore")),
                    "away_score": to_int(state.get("awayScore")),
                })
    return sorted(events, key=lambda e: e["seqno"])


def parse_tracking(payloads):
    """투구 추적값. {투구 ID: {px, 궤적 값들, 존 위아래, 타석 방향}} 형태의 dict로 돌려준다."""
    tracking = {}
    for payload in payloads:
        for relay in payload["result"]["textRelayData"].get("textRelays", []):
            for p in relay.get("ptsOptions", []):
                tracking[p["pitchId"]] = {
                    "px": p.get("crossPlateX"), "plate_y": p.get("crossPlateY"),
                    "top": p.get("topSz"), "bot": p.get("bottomSz"),
                    "y0": p.get("y0"), "vy0": p.get("vy0"), "ay": p.get("ay"),
                    "z0": p.get("z0"), "vz0": p.get("vz0"), "az": p.get("az"),
                    "stance": p.get("stance"),
                }
    return tracking


def parse_players(payloads):
    """선수 코드 → {"name": 이름, "throws": 던지는 손 "R"/"L"}.
    hitType이 "우투좌타"처럼 오니까 첫 글자(우/좌)만 본다."""
    players = {}
    for payload in payloads:
        data = payload["result"]["textRelayData"]
        for side in ["homeLineup", "awayLineup", "homeEntry", "awayEntry"]:
            group = data.get(side) or {}
            for role in ["batter", "pitcher"]:
                for player in group.get(role) or []:
                    code = player.get("pcode")
                    if not code:
                        continue
                    hit_type = player.get("hitType") or player.get("hittype") or ""
                    throws = None
                    if hit_type[:1] == "우":
                        throws = "R"
                    elif hit_type[:1] == "좌":
                        throws = "L"
                    players[code] = {"name": player.get("name") or "", "throws": throws}
    return players


def game_date(game_id):
    """game_id = 날짜8 + 원정2 + 홈2 + '0' + 연도4  →  'YYYY-MM-DD'"""
    return game_id[:4] + "-" + game_id[4:6] + "-" + game_id[6:8]
