"""
check_naver.py — 네이버 문자중계 API 연결 확인 (수집 전에 한 번만 실행)
  python check_naver.py
main.py collect 와 똑같은 함수(step1_collect.get_json)로 일정·경기·문자중계를 하나씩 요청해 본다.
"""
import config
import step1_collect

print("보내는 헤더:", config.HEADERS)
schedule = step1_collect.fetch_games_of_day("2025-03-22")
print("1. 일정(2025-03-22):", "실패" if schedule is None else f"성공, 정규시즌 경기 {len(schedule)}개 {[g['game_id'] for g in schedule][:2]}")
info = step1_collect.get_json(config.GAME_URL.format(game_id="20250322HHKT02025"))
print("2. 경기 정보:", "실패" if info is None else "성공, 마지막 이닝 = " + str(info["result"]["game"].get("currentInning")))
relay = step1_collect.get_json(config.RELAY_URL.format(game_id="20250322HHKT02025"), {"inning": 1},
                              referer="https://m.sports.naver.com/game/20250322HHKT02025/relay")
if relay is None:
    print("3. 1회 문자중계: 실패")
else:
    n = len(relay["result"]["textRelayData"].get("textRelays", []))
    print("3. 1회 문자중계: 성공, 타석 블록", n, "개")
    print("→ 셋 다 성공이면 python main.py collect 를 실행하세요.")
