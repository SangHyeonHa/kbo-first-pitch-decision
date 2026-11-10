"""
step5_value.py — ⑤ 기준표·분석 테이블 담당
1) 기대득점표(RE24): 주자 8가지 × 아웃 3가지 = 24상황마다 '이닝 끝까지 평균 몇 점 났나'
   = 상황의 '시세'. 끝까지 진행된 이닝(half_complete)만 쓴다.
2) 득점 가치(run value): 시세 변화 + 실제로 난 점수
   rv = 끝 상황 시세 - 시작 상황 시세 + 타석 중 득점   (이닝이 끝나면 끝 시세 = 0)
3) 분석 테이블: 1행 = 1타석의 초구. 누가·누구 상대·상황·공 위치·결정·결과를 한 줄에.
"""

ON_BASE = ["1B", "2B", "3B", "HR", "BB", "HBP"]
HITS = ["1B", "2B", "3B", "HR"]
BASES = {"1B": 1, "2B": 2, "3B": 3, "HR": 4}
NOT_AB = ["BB", "HBP", "SF", "SH", "OTHER", "NONE"]   # 타수에서 빠지는 결과


def build_re24(pas):
    """{'000_0': 0.49, ...} 와 칸별 표본 수를 함께 돌려준다."""
    total, count = {}, {}
    for pa in pas:
        if not pa["half_complete"]:
            continue
        key = pa["base_out"]
        total[key] = total.get(key, 0) + pa["runs_to_end"]
        count[key] = count.get(key, 0) + 1
    re24 = {}
    for key in total:
        re24[key] = total[key] / count[key]
    return re24, count


def add_run_value(pas, re24):
    for pa in pas:
        start = re24.get(pa["base_out"], 0)
        end = 0 if pa["end_base_out"] == "END" else re24.get(pa["end_base_out"], 0)
        pa["rv"] = end - start + pa["runs_in_pa"]


def runner_group(base):
    """24상황 → 3묶음: 주자 없음 / 1루만 / 득점권(2루나 3루에 주자)"""
    if base == "000":
        return "none"
    if base == "100":
        return "first"
    return "risp"


def build_first_pitch_table(pitches, pas, players):
    """pitch_num == 1 인 투구 + 그 타석 정보 → 분석 테이블."""
    pa_by_id = {pa["pa_id"]: pa for pa in pas}
    rows = []
    for p in pitches:
        if p["pitch_num"] != 1:
            continue
        pa = pa_by_id[p["pa_id"]]
        bat_side = p["stance"]
        pitcher_hand = players.get(pa["pitcher"], {}).get("throws")
        if bat_side in ("L", "R") and pitcher_hand in ("L", "R"):
            matchup = "same" if bat_side == pitcher_hand else "opp"
        else:
            matchup = None
        res = pa["result"]
        rows.append({
            # 식별
            "game_id": pa["game_id"], "pa_id": pa["pa_id"],
            # 누가 / 누구 상대
            "batter": pa["batter"], "batter_name": players.get(pa["batter"], {}).get("name"), "bat_team": pa["bat_team"], "bat_side": bat_side,
            "pitcher": pa["pitcher"], "pitcher_name": players.get(pa["pitcher"], {}).get("name"), "pitch_team": pa["pitch_team"], "throws": pitcher_hand, "matchup": matchup,
            # 상황 (공 오기 전)
            "inn": pa["inn"], "outs": pa["outs_start"], "base": pa["base_start"],
            "runners": runner_group(pa["base_start"]), "score_diff": pa["score_diff"],
            # 공 (결정 순간)
            "px": p["px"], "pz": p["pz"], "zone": p["zone"], "in_zone": p["in_zone"], "pitch_type": p["pitch_type"],
            # 결정
            "pitch_result": p["pitch_result"],
            "swing": 1 if p["pitch_result"] in ("S", "F", "H") else 0,
            "bunt": 1 if p["pitch_result"] in ("W", "V") else 0,
            # 결과 (타석 끝까지)
            "result": res, "has_result": 1 if res != "NONE" else 0,
            "on_base": 1 if res in ON_BASE else 0,
            "ab": 0 if res in NOT_AB else 1,
            "hit": 1 if res in HITS else 0,
            "tb": BASES.get(res, 0),
            "bb_hbp": 1 if res in ("BB", "HBP") else 0,
            "sf": 1 if res == "SF" else 0,
            "k": 1 if res == "K" else 0,
            "rv": pa["rv"],
        })
    return rows
