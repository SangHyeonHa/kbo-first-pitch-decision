"""
step6_analysis.py — ⑥ 분석·시각화 담당
분석 테이블(1행 = 1타석의 초구)을 '같은 조건끼리 묶어서(groupby)' 비교한다.

Q1. 공 위치별 결정표: 한가운데·경계·바깥 초구에서 '쳤을 때 vs 지켜봤을 때' 득점 가치
Q2. 상황별 결정표: 아웃(0·1·2) × 주자(없음/1루만/득점권) = 9칸 × 공 위치
Q3. 누구 상대로: 투타 매치업, 투수별 초구 성향(존 안으로 넣는 비율), 팀, 사례 타자

신뢰구간 = 경기 단위 부트스트랩: 경기를 '뽑고 다시 넣기'로 같은 수만큼 무작위로 뽑아
평균 차이를 다시 계산하는 일을 여러 번 반복하고, 그 값들의 가운데 95% 범위를 본다.
(random.randint + for문 + sorted — 모두 수업 범위)

[수업 밖] matplotlib(그래프), open으로 csv 파일 쓰기
"""
import os
import random

import config


# ------------------------------------------------------------------ 공통 도구
def write_csv(path, rows, columns):
    """dict 리스트를 csv 파일로 저장한다. 엑셀에서 한글이 깨지지 않게 utf-8-sig."""
    with open(path, "w", encoding="utf-8-sig") as f:
        f.write(",".join(columns) + "\n")
        for r in rows:
            values = []
            for c in columns:
                v = r.get(c)
                if v is None:
                    values.append("")
                elif isinstance(v, float):
                    values.append(f"{v:.4f}")
                else:
                    values.append(str(v))
            f.write(",".join(values) + "\n")


def analysis_rows(table):
    """분석에 쓰는 초구: 번트 제외, 타석 결과가 있고, 공 위치가 있는 것."""
    return [r for r in table if r["bunt"] == 0 and r["has_result"] == 1 and r["zone"] is not None]


def summarize(rows, keys):
    """keys로 묶어서 n, 평균 득점 가치, 출루율·장타율·OPS·삼진율을 계산한다."""
    groups = {}
    for r in rows:
        k = tuple(r[x] for x in keys)
        if k not in groups:
            groups[k] = {"n": 0, "rv": 0.0, "ab": 0, "hit": 0, "tb": 0, "bb_hbp": 0, "sf": 0, "k": 0}
        g = groups[k]
        g["n"] += 1
        g["rv"] += r["rv"]
        for c in ["ab", "hit", "tb", "bb_hbp", "sf", "k"]:
            g[c] += r[c]
    out = {}
    for k, g in groups.items():
        obp_den = g["ab"] + g["bb_hbp"] + g["sf"]
        obp = (g["hit"] + g["bb_hbp"]) / obp_den if obp_den else None
        slg = g["tb"] / g["ab"] if g["ab"] else None
        out[k] = {"n": g["n"], "rv": g["rv"] / g["n"], "obp": obp, "slg": slg,
                  "ops": obp + slg if obp is not None and slg is not None else None,
                  "k_rate": g["k"] / g["n"]}
    return out


def bootstrap_diff(rows, keys, n_boot=config.N_BOOT, seed=42):
    """그룹마다 (스윙 평균 rv - 지켜봄 평균 rv)의 95% 신뢰구간. 경기 단위로 다시 뽑는다."""
    random.seed(seed)
    per_game = {}                          # 경기 → {(그룹, 스윙여부): [rv 합, 개수]}
    for r in rows:
        key = (tuple(r[x] for x in keys), r["swing"])
        if r["game_id"] not in per_game:
            per_game[r["game_id"]] = {}
        cell = per_game[r["game_id"]]
        if key not in cell:
            cell[key] = [0.0, 0]
        cell[key][0] += r["rv"]
        cell[key][1] += 1
    games = sorted(per_game)
    diffs = {}
    for b in range(n_boot):
        total = {}
        for i in range(len(games)):
            g = games[random.randint(0, len(games) - 1)]
            for key, (s, n) in per_game[g].items():
                if key not in total:
                    total[key] = [0.0, 0]
                total[key][0] += s
                total[key][1] += n
        groups = set(key[0] for key in total)
        for grp in groups:
            sw, tk = total.get((grp, 1)), total.get((grp, 0))
            if sw and tk:
                if grp not in diffs:
                    diffs[grp] = []
                diffs[grp].append(sw[0] / sw[1] - tk[0] / tk[1])
    ci = {}
    for grp, values in diffs.items():
        values = sorted(values)
        ci[grp] = (values[int(0.025 * len(values))], values[int(0.975 * len(values)) - 1])
    return ci


def verdict(n_swing, n_take, lo, hi):
    if n_swing < config.MIN_N or n_take < config.MIN_N:
        return "표본 부족"
    if lo > 0:
        return "치는 게 유리"
    if hi < 0:
        return "거르는 게 유리"
    return "차이 불확실"


def decision_rows(rows, keys):
    """keys(+zone)별로 스윙 vs 지켜봄을 나란히 놓은 결정표."""
    s = summarize(rows, keys + ["swing"])
    ci = bootstrap_diff(rows, keys)
    out = []
    for grp in sorted(set(k[:-1] for k in s)):
        sw, tk = s.get(grp + (1,)), s.get(grp + (0,))
        if sw is None or tk is None:
            continue
        lo, hi = ci.get(grp, (None, None))
        row = {k: v for k, v in zip(keys, grp)}
        row.update({
            "n_swing": sw["n"], "n_take": tk["n"], "swing_rate": sw["n"] / (sw["n"] + tk["n"]),
            "rv_swing": sw["rv"], "rv_take": tk["rv"], "diff": sw["rv"] - tk["rv"], "ci_lo": lo, "ci_hi": hi,
            "obp_swing": sw["obp"], "obp_take": tk["obp"], "ops_swing": sw["ops"], "ops_take": tk["ops"],
            "k_swing": sw["k_rate"], "k_take": tk["k_rate"],
            "verdict": verdict(sw["n"], tk["n"], lo, hi) if lo is not None else "표본 부족",
        })
        out.append(row)
    return out


# ------------------------------------------------------------------ Q3 보조 분석
def pitcher_first_pitch(table, min_n=config.MIN_N):
    """투수별 초구 성향: 존 안으로 넣는 비율, 한가운데 비율, 상대 타자의 초구 스윙률."""
    stats = {}
    for r in table:
        if r["zone"] is None or r["bunt"] == 1:
            continue
        p = r["pitcher"]
        if p not in stats:
            stats[p] = {"pitcher": p, "name": r["pitcher_name"], "team": r["pitch_team"], "throws": r["throws"], "n": 0, "in_zone": 0, "heart": 0, "swing": 0}
        st = stats[p]
        st["n"] += 1
        st["in_zone"] += r["in_zone"]
        st["heart"] += 1 if r["zone"] == "heart" else 0
        st["swing"] += r["swing"]
    out = []
    for st in stats.values():
        if st["n"] >= min_n:
            out.append({"pitcher": st["pitcher"], "name": st["name"], "team": st["team"], "throws": st["throws"], "n": st["n"],
                        "in_zone_rate": st["in_zone"] / st["n"], "heart_rate": st["heart"] / st["n"],
                        "batter_swing_rate": st["swing"] / st["n"]})
    return sorted(out, key=lambda x: x["in_zone_rate"], reverse=True)


def batter_cases(rows, min_n=150):
    """사례 타자: 초구를 min_n개 이상 받은 타자의 구역별 초구 스윙률."""
    stats = {}
    for r in rows:
        b = r["batter"]
        if b not in stats:
            stats[b] = {"batter": b, "name": r["batter_name"], "team": r["bat_team"], "n": 0}
        st = stats[b]
        st["n"] += 1
        for z in ["heart", "shadow", "out"]:
            if r["zone"] == z:
                st[z + "_n"] = st.get(z + "_n", 0) + 1
                st[z + "_sw"] = st.get(z + "_sw", 0) + r["swing"]
    out = []
    for st in stats.values():
        if st["n"] < min_n:
            continue
        row = {"batter": st["batter"], "name": st["name"], "team": st["team"], "n": st["n"]}
        for z in ["heart", "shadow", "out"]:
            n = st.get(z + "_n", 0)
            row[z + "_swing_rate"] = st.get(z + "_sw", 0) / n if n else None
        out.append(row)
    return sorted(out, key=lambda x: x["heart_swing_rate"] or 0, reverse=True)


# ------------------------------------------------------------------ 그림 (matplotlib)
ZONE_KO = {"heart": "한가운데", "shadow": "경계", "out": "바깥"}
RUN_KO = {"none": "주자 없음", "first": "1루만", "risp": "득점권"}


def setup_font(plt):
    """한글 폰트 지정. 윈도우=맑은 고딕, 맥=AppleGothic, 리눅스=Noto Sans CJK KR 중 있는 것."""
    from matplotlib import font_manager
    names = set(f.name for f in font_manager.fontManager.ttflist)
    for name in ["Malgun Gothic", "AppleGothic", "Noto Sans CJK KR", "NanumGothic"]:
        if name in names:
            plt.rcParams["font.family"] = name
            break
    plt.rcParams["axes.unicode_minus"] = False


def plot_decision(league, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    setup_font(plt)
    order = ["heart", "shadow", "out"]
    rows = {r["zone"]: r for r in league}
    fig, ax = plt.subplots(figsize=(6.2, 3.2), dpi=200)
    label_x = max(r["ci_hi"] for r in league) + 0.02     # 숫자 라벨은 오른쪽 한 줄에 맞춰 놓기
    for i, z in enumerate(order):
        r = rows[z]
        color = "#2a78d6" if r["ci_lo"] > 0 else ("#d9622b" if r["ci_hi"] < 0 else "#8a8984")
        ax.plot([r["ci_lo"], r["ci_hi"]], [i, i], color=color, lw=2.2, solid_capstyle="round")
        ax.plot(r["diff"], i, "o", color=color, ms=8, mec="white", mew=1.2)
        ax.text(label_x, i, f"{r['diff']:+.3f}점  ({r['verdict']})", va="center", fontsize=8.5, color="#222")
    ax.axvline(0, color="#52514e", lw=0.8)
    ax.set_yticks(range(3))
    ax.set_yticklabels([f"{ZONE_KO[z]}\n(스윙률 {rows[z]['swing_rate']:.0%})" for z in order], fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("치면 - 지켜보면 (타석당 득점 가치 차이, 95% 신뢰구간)", fontsize=8.5, color="#52514e")
    lo = min(r["ci_lo"] for r in league); hi = max(r["ci_hi"] for r in league)
    ax.set_xlim(lo - 0.03, hi + 0.2)
    for s in ["top", "right", "left"]:
        ax.spines[s].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color="#e4e3df", lw=0.6)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def plot_situation(situation, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    setup_font(plt)
    cell = {(r["outs"], r["runners"], r["zone"]): r for r in situation}
    fig, axes = plt.subplots(1, 3, figsize=(9, 3.4), dpi=200)
    for k, z in enumerate(["heart", "shadow", "out"]):
        ax = axes[k]
        for i, outs in enumerate([0, 1, 2]):
            for j, run in enumerate(["none", "first", "risp"]):
                r = cell.get((outs, run, z))
                if r is None:
                    continue
                v = r["verdict"]
                color = {"치는 게 유리": "#2a78d6", "거르는 게 유리": "#d9622b"}.get(v, "#efefec")
                ax.add_patch(plt.Rectangle((j, i), 0.96, 0.96, color=color))
                ink = "white" if v in ("치는 게 유리", "거르는 게 유리") else "#333"
                label = f"{r['diff']:+.2f}" if v != "표본 부족" else "표본\n부족"
                ax.text(j + 0.48, i + 0.42, label, ha="center", va="center", fontsize=9, color=ink)
                ax.text(j + 0.48, i + 0.78, f"n={r['n_swing']}/{r['n_take']}", ha="center", va="center", fontsize=6, color=ink)
        ax.set_xlim(0, 3); ax.set_ylim(3, 0)
        ax.set_xticks([0.48, 1.48, 2.48]); ax.set_xticklabels([RUN_KO[x] for x in ["none", "first", "risp"]], fontsize=8)
        ax.set_yticks([0.48, 1.48, 2.48]); ax.set_yticklabels(["무사", "1사", "2사"], fontsize=8)
        ax.set_title(f"초구가 {ZONE_KO[z]}", fontsize=10)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.tick_params(length=0)
    fig.text(0.5, 0.02, "칸 숫자 = 치면 - 지켜보면 (득점 가치)  ·  파랑 = 치는 게 유리, 주황 = 거르는 게 유리, 회색 = 차이 불확실 또는 표본 부족",
             ha="center", fontsize=8.5)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    fig.savefig(path)
    plt.close(fig)


def plot_zone_edge(edges, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    setup_font(plt)
    pts = [(v, rate) for v, n, rate in edges["x_table"] if 0.7 <= v <= 1.1]
    fig, ax = plt.subplots(figsize=(5, 2.6), dpi=200)
    ax.plot([p[0] for p in pts], [p[1] * 100 for p in pts], "-o", color="#2a78d6", ms=3, lw=1.5)
    ax.axvline(edges["x_edge"], color="#52514e", lw=0.8, ls="--")
    ax.text(edges["x_edge"] + 0.01, 55, f"경계 {edges['x_edge']:.2f} ft", fontsize=8)
    ax.set_xlabel("홈플레이트 중앙에서 좌우 거리 |x| (ft)", fontsize=8.5)
    ax.set_ylabel("스트라이크 판정률(%)", fontsize=8.5)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


# ------------------------------------------------------------------ 전체 실행
def run_all(table, edges, re24, re24_n):
    os.makedirs(config.RESULT_DIR, exist_ok=True)
    rows = analysis_rows(table)
    dec_cols = ["n_swing", "n_take", "swing_rate", "rv_swing", "rv_take", "diff", "ci_lo", "ci_hi",
                "obp_swing", "obp_take", "ops_swing", "ops_take", "k_swing", "k_take", "verdict"]

    league = decision_rows(rows, ["zone"])
    write_csv(os.path.join(config.RESULT_DIR, "Q1_decision_by_zone.csv"), league, ["zone"] + dec_cols)

    situation = decision_rows(rows, ["outs", "runners", "zone"])
    write_csv(os.path.join(config.RESULT_DIR, "Q2_decision_by_situation.csv"), situation, ["outs", "runners", "zone"] + dec_cols)

    matchup = decision_rows([r for r in rows if r["matchup"]], ["matchup", "zone"])
    write_csv(os.path.join(config.RESULT_DIR, "Q3_matchup.csv"), matchup, ["matchup", "zone"] + dec_cols)

    team = decision_rows(rows, ["pitch_team", "zone"])
    write_csv(os.path.join(config.RESULT_DIR, "Q3_vs_pitching_team.csv"), team, ["pitch_team", "zone"] + dec_cols)

    pitchers = pitcher_first_pitch(table)
    write_csv(os.path.join(config.RESULT_DIR, "Q3_pitcher_first_pitch.csv"), pitchers,
              ["pitcher", "name", "team", "throws", "n", "in_zone_rate", "heart_rate", "batter_swing_rate"])

    batters = batter_cases(rows)
    write_csv(os.path.join(config.RESULT_DIR, "Q3_batter_cases.csv"), batters,
              ["batter", "name", "team", "n", "heart_swing_rate", "shadow_swing_rate", "out_swing_rate"])

    re_rows = [{"base_out": k, "re": re24[k], "n": re24_n[k]} for k in sorted(re24)]
    write_csv(os.path.join(config.RESULT_DIR, "RE24.csv"), re_rows, ["base_out", "re", "n"])

    plot_decision(league, os.path.join(config.RESULT_DIR, "fig1_decision_by_zone.png"))
    plot_situation(situation, os.path.join(config.RESULT_DIR, "fig2_decision_by_situation.png"))
    plot_zone_edge(edges, os.path.join(config.RESULT_DIR, "fig3_zone_edge.png"))
    return league, situation, matchup, pitchers
