"""
main.py — 전체 실행
  python main.py           : data/raw 에 있는 경기 파일로 ②~⑥ 실행
  python main.py collect   : ① 수집부터 (약 2시간) → 이어서 ②~⑥ 실행
  python main.py data/raw_dev  : 다른 폴더(예: 개발용 한화 샘플)로 실행

각 단계 파일 = 조원 한 명 담당
  ① step1_collect.py   ② step2_parse.py   ③ step3_pa.py
  ④ step4_pitch.py     ⑤ step5_value.py   ⑥ step6_analysis.py
"""
import os
import sys

import config
import step1_collect
import step2_parse
import step3_pa
import step4_pitch
import step5_value
import step6_analysis


def load_all_games(raw_dir):
    """②~④: 경기 파일을 하나씩 읽어 타석·투구 테이블을 만들고 이어 붙인다."""
    all_pa, all_pitches, players = [], [], {}
    count = {"files": 0, "games": 0, "pitch_events": 0}
    for name in sorted(os.listdir(raw_dir)):
        if not name.endswith(".json"):
            continue
        count["files"] += 1
        payloads = step2_parse.load_raw(os.path.join(raw_dir, name))
        events = step2_parse.parse_events(payloads)                       # ②
        if not events:
            continue
        game_id = events[0]["game_id"]
        n_pitch = len([e for e in events if e["type"] == 1])
        if step2_parse.game_date(game_id) < config.REGULAR_START or n_pitch == 0:
            continue                                                       # 시범경기·취소 경기 제외
        count["games"] += 1
        count["pitch_events"] += n_pitch
        tracking = step2_parse.parse_tracking(payloads)
        players.update(step2_parse.parse_players(payloads))
        events = step3_pa.assign_pa_numbers(events)                       # ③
        pas = step3_pa.build_pa_table(game_id, events)
        pitches = step4_pitch.build_pitch_table(game_id, events, tracking, pas)   # ④
        all_pa += pas
        all_pitches += pitches
    return all_pa, all_pitches, players, count


def main():
    raw_dir = config.RAW_DIR
    if len(sys.argv) > 1 and sys.argv[1] == "collect":
        step1_collect.collect_season()                                     # ①
    elif len(sys.argv) > 1:
        raw_dir = sys.argv[1]

    if not os.path.isdir(raw_dir) or not os.listdir(raw_dir):
        print("경기 파일이 없습니다:", raw_dir, "→ 먼저 python main.py collect 로 수집하세요.")
        return
    pas, pitches, players, count = load_all_games(raw_dir)
    if not pas:
        print("분석할 정규시즌 경기가 없습니다.")
        return
    edges = step4_pitch.calibrate_zone(pitches)                            # ④ 존 경계
    step4_pitch.add_zone(pitches, edges)
    re24, re24_n = step5_value.build_re24(pas)                             # ⑤
    step5_value.add_run_value(pas, re24)
    table = step5_value.build_first_pitch_table(pitches, pas, players)

    os.makedirs(config.RESULT_DIR, exist_ok=True)
    step6_analysis.write_csv(os.path.join(config.RESULT_DIR, "first_pitch_table.csv"), table, list(table[0].keys()))
    league, situation, matchup, pitchers = step6_analysis.run_all(table, edges, re24, re24_n)   # ⑥

    # ---- 체크포인트: 단계마다 숫자가 상식에 맞는지 ----
    rows = step6_analysis.analysis_rows(table)
    complete = [pa["rv"] for pa in pas if pa["half_complete"]]
    print("=== 체크포인트 ===")
    print("파일", count["files"], "/ 경기", count["games"], "/ 투구 이벤트", count["pitch_events"])
    print("타석", len(pas), "/ 투구", len(pitches), "/ 초구 행", len(table),
          "/ 번트", sum(r["bunt"] for r in table), "/ 결과 없는 타석", len([r for r in table if r["has_result"] == 0]))
    print("존 경계 x=%.2f ft, 위=%.3f, 아래=%.3f" % (edges["x_edge"], edges["z_top"], edges["z_bot"]))
    print("RE24 칸 수", len(re24), "/ 무사 주자없음 %.3f, 무사 1루 %.3f, 2사 만루 %.3f"
          % (re24["000_0"], re24["100_0"], re24["111_2"]))
    print("rv 평균(끝난 이닝) %.4f  ← 0에 가까워야 정상" % (sum(complete) / len(complete)))
    print("분석 초구", len(rows), "/ 초구 스윙률 %.3f / 존 안 비율 %.3f"
          % (sum(r["swing"] for r in rows) / len(rows), sum(r["in_zone"] for r in rows) / len(rows)))
    print("=== Q1 공 위치별 결정표 ===")
    for r in sorted(league, key=lambda x: ["heart", "shadow", "out"].index(x["zone"])):
        print("%-6s 스윙률 %.2f | 치면 %+.3f (n=%d) vs 보내면 %+.3f (n=%d) | 차이 %+.3f [%+.3f, %+.3f] → %s"
              % (r["zone"], r["swing_rate"], r["rv_swing"], r["n_swing"], r["rv_take"], r["n_take"],
                 r["diff"], r["ci_lo"], r["ci_hi"], r["verdict"]))


if __name__ == "__main__":
    main()
