# -*- coding: utf-8 -*-
"""테스트용 광고 문구 모음 (eval/README.md "테스트용 광고 문구 방침").

범주 키워드 1~2개 + 가짜 연락처(@test_, .test/.example, 010-0000-, TEST 코드)만 쓴다.
"""

# 첫가끝 자모(U+1100~)로 쓴 '카지노'
CONJOINING_KAJINO = "카지노"
# 반각 자모(U+FFA0~)로 쓴 '토토' (ㅌㅗㅌㅗ)
HALFWIDTH_TOTO = "ﾼￌﾼￌ"
# 자모 사이에 U+200B를 넣은 '바카라'
ZWSP_BAKARA = "​".join("ㅂㅏㅋㅏㄹㅏ")
# 수학용 굵은 영숫자 'BET365'
MATH_BET = "".join(chr(0x1D400 + ord(c) - 65) for c in "BET") + "".join(chr(0x1D7CE + int(d)) for d in "365")

AD = {
    # 공지사항 게시판
    "n1002": "온라인 카지노 첫충 이벤트 @test_casino_01",
    "n1009": "대포통장 법인통장 매입 @test_bank_02",
    "n1137": "먹튀검증 토토사이트 @test_toto_03",
    "n1088": MATH_BET + " 토토 가입코드 TEST88",
    "n1045": "불법 대출 무직자 가능 010-0000-1045",
    "n1201": "s1ot 무료체험 b3t @test_slot_05",
    "n1176": "성인 출장 광고 @test_adult_06",
    "n1150": "마약 광고 @test_drug_07",
    "n1033": "바카라 첫충 10% 가입코드 TEST33",
    "n1240": "토토 총판 모집 @test_toto_12",
    "n1111": "성인용품 최저가 shop.test",
    "n1066": "사설토토 리딩방 @test_pick_14",
    "n1260": "홀덤 환전 가입코드 TEST60",
    "n1190_extra": "토토사이트 추천 가입코드 TEST777",
    # 고시·공고(POST) 게시판
    "e7": "파워볼 픽 제공 @test_pb_07",
    "e19": "통장 임대 월 己丂0만 010-0000-丨己彐丩",
    "e12_title": CONJOINING_KAJINO + " 첫충 이벤트 @test_kjn_12",
    # 행사
    "ev7": "라이브 바카라 가입머니 @test_live_07",
    "ev23": "ㅋト지노 첫충 @test_ev_23",
    "ev32": "ㅋr지노 이벤트 @test_ev_32",
    # 기타 페이지
    "report4": HALFWIDTH_TOTO + " 가입코드 TEST04",
    "stats": ZWSP_BAKARA + " 실시간 @test_bkr_stat",
    "srcdoc": "성인 출장 @test_home_24",
    "shadow_open": "슬롯 첫충 @test_shadow_open",
    "shadow_closed": "토토 가입코드 TESTCL",
    "vision": "카지노 환전 @test_vision",
    # 옛 게시판(EUC-KR)
    "old12": "카지노 슬롯 무료머니 TEST1212",
    "old8_extra": "카지노 무료머니 casino.example",
}
