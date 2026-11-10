"""
step3_pa.py — ③ 타석 담당
이벤트 리스트를 '타석(PA)' 단위로 묶어 타석 테이블을 만든다. 1행 = 1타석.

규칙
1) type 8(타자 소개)이 나오면 새 타석이 시작된다.
2) 유령 타석 제거: 같은 타자를 두 번 소개하는 경우가 있어서, 투구(1)도 타석결과(13·23)도
   없는 '타석'은 버린다.
3) 타석 시작 상태 = 타자 소개 줄의 _after 값 (소개 직후 = 첫 공 던지기 전)
4) 같은 하프이닝의 다음 타석 시작 상태 = 이번 타석이 끝난 상태. 다음 타석이 없으면 이닝 종료("END").
5) half_complete: 3아웃으로 끝났고 '9회 이후 말 공격'이 아닌 이닝만 기대득점 계산에 쓴다.
   (끝내기로 끝난 이닝은 남은 득점 기회가 잘려서 평균을 왜곡한다)
"""


def base_state(e):
    """주자 상황을 '1루2루3루' 3자리 문자열로. 예) 1·3루 → '101'. 주자 없으면 선수코드 자리에 '0'."""
    code = ""
    for base in ["base1", "base2", "base3"]:
        code += "0" if e[base] in ("0", "", "None") else "1"
    return code


def bat_score(e):
    """공격팀 점수: 초(half 0)는 원정팀, 말(half 1)은 홈팀이 공격한다."""
    return e["away_score"] if e["half"] == 0 else e["home_score"]


def opp_score(e):
    return e["home_score"] if e["half"] == 0 else e["away_score"]


def assign_pa_numbers(events):
    """각 이벤트에 타석 번호 pa_no를 붙인다. 첫 타자 소개 전 이벤트와 유령 타석 소개 줄은 버린다."""
    # 1차: 타자 소개마다 임시 번호
    temp = 0
    for e in events:
        if e["type"] == 8:
            temp += 1
        e["tmp"] = temp
    # 진짜 타석 = 투구나 타석결과가 하나라도 있는 임시 번호
    real = set()
    for e in events:
        if e["tmp"] > 0 and e["type"] in (1, 13, 23):
            real.add(e["tmp"])
    # 2차: 유령 타석의 소개 줄을 빼고 번호를 다시 매긴다
    result = []
    pa_no = 0
    for e in events:
        if e["tmp"] == 0:
            continue
        if e["type"] == 8 and e["tmp"] not in real:
            continue
        if e["type"] == 8:
            pa_no += 1
        if pa_no == 0:
            continue
        e["pa_no"] = pa_no
        result.append(e)
    return result


def classify_result(text):
    """타석 결과 문장에서 결과 종류를 뽑는다. 순서가 중요하다(예: '희생플라이 아웃'은 '아웃'보다 먼저)."""
    rules = [
        ("고의4구", "BB"), ("볼넷", "BB"), ("몸에 맞는 볼", "HBP"),
        ("홈런", "HR"), ("3루타", "3B"), ("2루타", "2B"),
        ("1루타", "1B"), ("내야안타", "1B"), ("번트안타", "1B"),
        ("희생플라이", "SF"), ("희생번트", "SH"),
        ("삼진", "K"), ("낫 아웃", "K"),
        ("실책으로 출루", "ROE"), ("출루", "FC"),
        ("아웃", "OUT"),
    ]
    for keyword, code in rules:
        if keyword in text:
            return code
    return "OTHER"


def build_pa_table(game_id, events):
    """pa_no가 붙은 이벤트 리스트 → 타석 테이블(dict 리스트)."""
    half_last = {}                       # 하프이닝별 마지막 이벤트
    for e in events:
        half_last[(e["inn"], e["half"])] = e
    away, home = game_id[8:10], game_id[10:12]

    pas = []
    by_no = {}
    for e in events:
        if e["type"] == 8:
            last = half_last[(e["inn"], e["half"])]
            pa = {
                "game_id": game_id, "pa_id": f"{game_id}_{e['pa_no']:03d}", "pa_no": e["pa_no"],
                "inn": e["inn"], "half": e["half"],
                "batter": e["batter"], "pitcher": e["pitcher"],
                "bat_team": away if e["half"] == 0 else home,
                "pitch_team": home if e["half"] == 0 else away,
                "outs_start": e["outs_after"], "base_start": base_state(e),
                "base_out": base_state(e) + "_" + str(e["outs_after"]),
                "score_start": bat_score(e), "score_diff": bat_score(e) - opp_score(e),
                "half_end_score": bat_score(last),
                "half_complete": last["outs_after"] == 3 and not (e["inn"] >= 9 and e["half"] == 1),
                "result": "NONE", "result_text": "",
            }
            pas.append(pa)
            by_no[e["pa_no"]] = pa
        elif e["type"] in (13, 23):
            pa = by_no.get(e["pa_no"])
            if pa is not None:           # 타석 결과(마지막 것)를 기록
                text = e["text"].split(":", 1)[-1].strip()
                pa["result"] = classify_result(text)
                pa["result_text"] = text

    # 다음 타석 시작 상태 = 이번 타석 끝 상태 (같은 하프이닝 안에서만)
    for i in range(len(pas)):
        pa = pas[i]
        nxt = pas[i + 1] if i + 1 < len(pas) else None
        same_half = nxt is not None and (nxt["inn"], nxt["half"]) == (pa["inn"], pa["half"])
        if same_half:
            pa["end_base_out"] = nxt["base_out"]
            pa["runs_in_pa"] = nxt["score_start"] - pa["score_start"]
        else:
            pa["end_base_out"] = "END"
            pa["runs_in_pa"] = pa["half_end_score"] - pa["score_start"]
        pa["runs_to_end"] = pa["half_end_score"] - pa["score_start"]
    return pas
