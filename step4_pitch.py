"""
step4_pitch.py — ④ 투구·존 담당
1) 투구 테이블: 1행 = 1투구. 투구 '전' 카운트·주자·아웃을 붙인다.
   (원본 카운트는 '직후' 값이라, 투구 전 카운트 = 같은 타석의 직전 투구의 직후 값. 첫 공은 0-0)
2) 공 높이(pz) 계산: 원본에는 좌우 위치(px)만 있고 높이는 없어서 궤적으로 계산한다.
   공은 y방향(투수→포수)으로 등가속도 운동:  y(t) = y0 + vy0·t + ½·ay·t²
   y(t) = 홈플레이트 위치(plate_y)가 되는 시간 t를 근의 공식으로 구하고,
   그 t를 z(t) = z0 + vz0·t + ½·az·t² 에 넣으면 홈플레이트를 지날 때의 높이가 나온다.
3) 존 경계 찾기: 타자가 '지켜본 공'의 판정(볼/스트라이크)으로 경계를 데이터에서 찾는다.
4) 존 3구역 분류: 한가운데(heart) / 경계(shadow) / 바깥(out)
"""
import math

import config
from step3_pa import base_state, bat_score


def compute_plate_z(t):
    """궤적 값 dict → 홈플레이트 통과 높이(ft). 값이 없으면 None."""
    keys = ["y0", "vy0", "ay", "z0", "vz0", "az", "plate_y"]
    for k in keys:
        if t.get(k) is None:
            return None
    a = 0.5 * t["ay"]
    b = t["vy0"]
    c = t["y0"] - t["plate_y"]
    d = b * b - 4 * a * c                 # 판별식
    if d < 0 or a == 0:
        return None
    roots = [(-b + math.sqrt(d)) / (2 * a), (-b - math.sqrt(d)) / (2 * a)]
    positive = [r for r in roots if r > 0]
    if not positive:
        return None
    time = min(positive)                   # 양수인 근 중 작은 것 = 처음 도달하는 시각
    return t["z0"] + t["vz0"] * time + 0.5 * t["az"] * time * time


def build_pitch_table(game_id, events, tracking, pas):
    """pa_no가 붙은 이벤트 리스트 → 투구 테이블."""
    pa_by_no = {pa["pa_no"]: pa for pa in pas}
    pitches = []
    prev = None                            # 같은 경기의 직전 이벤트(종류 상관없음)
    last_count = {}                        # 타석 번호 → 직전 투구 직후 카운트
    for e in events:
        if e["type"] == 1 and prev is not None:
            pa = pa_by_no[e["pa_no"]]
            balls, strikes = last_count.get(e["pa_no"], (0, 0))
            t = tracking.get(e["pts_id"], {})
            pitches.append({
                "game_id": game_id, "pa_id": pa["pa_id"], "pitch_num": e["pitch_num"],
                "pitch_result": e["pitch_result"], "pitch_type": e["pitch_type"],
                "count_before": f"{balls}-{strikes}",
                "base_out_before": base_state(prev) + "_" + str(prev["outs_after"]),
                "runs_to_end": pa["half_end_score"] - bat_score(prev),
                "half_complete": pa["half_complete"],
                "px": t.get("px"), "pz": compute_plate_z(t),
                "top": t.get("top"), "bot": t.get("bot"), "stance": t.get("stance"),
            })
            last_count[e["pa_no"]] = (e["balls_after"], e["strikes_after"])
        prev = e
    return pitches


def zone_height(p):
    """존 중앙을 0, 존 위끝을 +1, 아래끝을 -1로 맞춘 '정규화 높이'. 타자마다 키가 달라서 필요하다."""
    mid = (p["top"] + p["bot"]) / 2
    half = (p["top"] - p["bot"]) / 2
    return (p["pz"] - mid) / half


def has_location(p):
    return p["px"] is not None and p["pz"] is not None and p["top"] is not None and p["bot"] is not None


def find_edge(pairs, step):
    """(위치, 스트라이크 여부) 쌍들을 step 크기 구간으로 나눠 구간별 스트라이크 비율을 구하고,
    비율이 처음으로 0.5 아래로 떨어지는 구간의 시작값을 경계로 돌려준다."""
    count = {}
    strike = {}
    for value, is_strike in pairs:
        b = int(value / step)              # 구간 번호
        count[b] = count.get(b, 0) + 1
        strike[b] = strike.get(b, 0) + is_strike
    table = []
    for b in sorted(count):
        table.append((b * step, count[b], strike[b] / count[b]))
    start = int(0.6 / step)                # 존 안쪽 확실한 구간부터 찾기 시작
    for value, n, rate in table:
        if value >= start * step and n >= 20 and rate < 0.5:
            return round(value, 3), table
    return None, table


def calibrate_zone(pitches):
    """지켜본 공(B: 볼, T: 루킹 스트라이크)만 써서 존 경계 3개를 데이터로 찾는다."""
    side, up, down = [], [], []
    for p in pitches:
        if p["pitch_result"] not in ("B", "T") or not has_location(p):
            continue
        is_strike = 1 if p["pitch_result"] == "T" else 0
        zn = zone_height(p)
        if abs(zn) < 0.5:                  # 높이가 존 가운데인 공 → 좌우 경계 찾기
            side.append((abs(p["px"]), is_strike))
        if abs(p["px"]) < 0.4:             # 좌우가 가운데인 공 → 위·아래 경계 찾기
            if zn > 0:
                up.append((zn, is_strike))
            else:
                down.append((-zn, is_strike))
    x_edge, x_table = find_edge(side, 0.01)
    z_top, _ = find_edge(up, 0.025)
    z_bot, _ = find_edge(down, 0.025)
    return {"x_edge": x_edge, "z_top": z_top, "z_bot": -z_bot, "x_table": x_table}


def add_zone(pitches, edges, ball=config.BALL_FT):
    """각 투구에 edge_dist(존 경계에서 바깥으로 몇 ft인지, 안쪽이면 음수)와 구역을 붙인다."""
    for p in pitches:
        if not has_location(p):
            p["edge_dist"], p["in_zone"], p["zone"] = None, None, None
            continue
        mid = (p["top"] + p["bot"]) / 2
        half = (p["top"] - p["bot"]) / 2
        over_side = abs(p["px"]) - edges["x_edge"]
        over_top = p["pz"] - (mid + edges["z_top"] * half)
        over_bottom = (mid + edges["z_bot"] * half) - p["pz"]
        d = max(over_side, over_top, over_bottom)
        p["edge_dist"] = d
        p["in_zone"] = 1 if d <= 0 else 0
        if d < -ball:
            p["zone"] = "heart"            # 경계 안쪽으로 공 1개 넘게
        elif d <= ball:
            p["zone"] = "shadow"           # 경계 ± 공 1개
        else:
            p["zone"] = "out"              # 그보다 바깥
