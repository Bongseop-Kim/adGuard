"""문자 판정: HOMOGLYPH, JAMO, 광고성 (research/04 §5~7, 09 §7). 브라우저 없이 텍스트만 본다.

    textcheck.check("ㅋr지노 꽁머니 지급 @test_x")  → {"ad": True, "HOMOGLYPH": "...", "JAMO": "...", "norm": "카지노꽁머니지급..."}

원칙
- 기법 분류는 원문 글자로, 광고성은 정규화한 글자로 본다 (정규화하면 자모·닮은꼴 흔적이 사라진다)
- 흔한 글자(라틴·숫자)를 한글로 되돌리는 규칙은 자모 바로 옆에서만, 그리고 키워드가 새로 생길 때만 인정한다 (LH공사, 7월, 1층 오탐 방지)
- 출력 조건은 "기법 신호 AND 광고성" (호출하는 쪽에서 ad를 본다)
"""
import os
import re
import unicodedata as ud

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------- 표 ----------

CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
JUNG = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
JONG = ["", "ㄱ", "ㄲ", "ㄳ", "ㄴ", "ㄵ", "ㄶ", "ㄷ", "ㄹ", "ㄺ", "ㄻ", "ㄼ", "ㄽ", "ㄾ", "ㄿ", "ㅀ", "ㅁ", "ㅂ", "ㅄ", "ㅅ",
        "ㅆ", "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"]
VV = {("ㅗ", "ㅏ"): "ㅘ", ("ㅗ", "ㅐ"): "ㅙ", ("ㅗ", "ㅣ"): "ㅚ", ("ㅜ", "ㅓ"): "ㅝ", ("ㅜ", "ㅔ"): "ㅞ", ("ㅜ", "ㅣ"): "ㅟ",
      ("ㅡ", "ㅣ"): "ㅢ", ("ㅏ", "ㅣ"): "ㅐ", ("ㅓ", "ㅣ"): "ㅔ", ("ㅑ", "ㅣ"): "ㅒ", ("ㅕ", "ㅣ"): "ㅖ"}
CC = {("ㄱ", "ㅅ"): "ㄳ", ("ㄴ", "ㅈ"): "ㄵ", ("ㄴ", "ㅎ"): "ㄶ", ("ㄹ", "ㄱ"): "ㄺ", ("ㄹ", "ㅁ"): "ㄻ", ("ㄹ", "ㅂ"): "ㄼ",
      ("ㄹ", "ㅅ"): "ㄽ", ("ㄹ", "ㅌ"): "ㄾ", ("ㄹ", "ㅍ"): "ㄿ", ("ㄹ", "ㅎ"): "ㅀ", ("ㅂ", "ㅅ"): "ㅄ"}
# 자모 사이에 끼워 넣는 구분자·보이지 않는 글자 (research/04 §6.2, 09 §7.1)
SEP = set(" \t\n.,-_·•*/|~^✦★☆♡♥◆◇○●ㆍ‧・･∙⋅'\"`+=:;!?()[]{}<>") | {
    "​", "‌", "‍", "‎", "‏", "⁠", "﻿", "ㅤ", "ᅟ", "ᅠ", "ﾠ", "­",
    "͏", "᠎"}
INVISIBLE = {c for c in SEP if not c.isprintable() or c in "ㅤᅟᅠﾠ­"}
BIDI = re.compile("[‪-‮⁦-⁩]")
# Unicode Default_Ignorable_Code_Point (DerivedCoreProperties.txt): 화면에 안 보이는 글자. 한글 채움 문자 포함 (research/13 §3)
# 방향 제어(U+202A~202E, 2066~2069)는 unbidi가 먼저 쓰고 지운다
IGNORABLE = re.compile("[\u00ad\u034f\u061c\u115f\u1160\u17b4\u17b5\u180b-\u180f\u200b-\u200f\u202a-\u202e\u2060-\u206f"
                       "\u3164\ufe00-\ufe0f\ufeff\uffa0\U0001bca0-\U0001bca3\U0001d173-\U0001d17a\U000e0000-\U000e0fff]")
DOT = str.maketrans({"。": ".", "｡": ".", "．": "."})  # 주소의 마침표 대신 쓰는 글자 (bcc777。COM)
# NFKC·confusables가 라틴으로 안 바꾸는 장식 글자: 작은 대문자 ʙᴇᴛ, 음각·네모 원문자 🅑🅔🅣 (research/14 §3-4)
NAME_FOLD = re.compile(r"(?:LATIN LETTER SMALL CAPITAL|(?:NEGATIVE )?(?:CIRCLED|SQUARED) LATIN (?:CAPITAL|SMALL) LETTER|"
                       r"MODIFIER LETTER (?:CAPITAL|SMALL)|REGIONAL INDICATOR SYMBOL LETTER) ([A-Z])$")


def fold(c):
    """한 글자를 NFKC로, 안 되면 유니코드 이름으로 라틴 소문자에 맞춘다"""
    n = ud.normalize("NFKC", c)
    if len(n) == 1 and n.isascii() or c.isascii():
        return n
    m = NAME_FOLD.match(ud.name(c, ""))
    return m.group(1).lower() if m else n


def _conf():
    out = {}
    with open(os.path.join(HERE, "data", "confusables_ascii.tsv"), encoding="utf-8") as f:
        for line in f:
            if line[:1] != "#" and "\t" in line:
                a, b = line.rstrip("\n").split("\t")
                if not is_hangulish(a):
                    out[a] = b
    return out


def is_hangulish(c):
    o = ord(c)
    return (0xAC00 <= o <= 0xD7A3 or 0x1100 <= o <= 0x11FF or 0x3131 <= o <= 0x318E or 0xA960 <= o <= 0xA97F
            or 0xD7B0 <= o <= 0xD7FF or 0xFFA0 <= o <= 0xFFDC)


def is_jamo(c):  # 자모 글자 (ㆍ는 공문서 가운뎃점이라 뺀다)
    o = ord(c)
    return c != "ㆍ" and (0x3131 <= o <= 0x318E or 0x1100 <= o <= 0x11FF or 0xA960 <= o <= 0xA97F or 0xD7B0 <= o <= 0xD7FF
                         or 0xFFA1 <= o <= 0xFFDC)


def is_syl(c):
    return "가" <= c <= "힣"


CONF = None  # 늦게 읽는다

# 한글을 닮은 글자 → 한글 (스팸체 생성기, KOTOX iconic_dictionary(MIT), korcen(MIT), UTS #39에서 모음. research/04 §5.3, 09 §7.2)
# 라틴·숫자처럼 흔한 글자는 LOOK_ASCII로 따로 둔다: 자모 바로 옆에서만, 키워드가 새로 생길 때만 쓴다
LOOK = {
    # 음절
    "亼": "스", "卫": "고", "仝": "소", "上": "노", "丕": "조", "卟": "마", "今": "슥", "丛": "쓰", "夬": "곳", "卒": "쭈",
    "㐃": "수", "引": "뤼", "仆": "사", "止": "나", "長": "튼", "ユ": "그", "弓": "국", "朝": "조", "兆": "조", "早": "조",
    "鳥": "조", "冫": "ㅋ",
    # 자음
    "勹": "ㄱ", "ガ": "ㄱ", "カ": "ㄱ", "ｶ": "ㄱ", "つ": "ㄱ", "プ": "ㄱ", "乚": "ㄴ", "レ": "ㄴ", "じ": "ㄴ", "匸": "ㄷ",
    "亡": "ㄷ", "て": "ㄷ", "己": "ㄹ", "乙": "ㄹ", "已": "ㄹ", "巳": "ㄹ", "さ": "ㄹ", "口": "ㅁ", "□": "ㅁ", "ロ": "ㅁ",
    "ﾛ": "ㅁ", "囗": "ㅁ", "廿": "ㅂ", "甘": "ㅂ", "田": "ㅂ", "日": "ㅂ", "目": "ㅂ", "Ы": "ㅂ", "人": "ㅅ", "Λ": "ㅅ",
    "∧": "ㅅ", "ん": "ㅅ", "◎": "ㅇ", "の": "ㅇ", "久": "ㅈ", "ヌ": "ㅈ", "ズ": "ㅈ", "叉": "ㅈ", "大": "ㅊ", "え": "ㅊ",
    "刁": "ㅋ", "巨": "ㅌ", "モ": "ㅌ", "立": "ㅍ", "云": "ㅎ", "あ": "ㅎ",
    # 모음
    "ト": "ㅏ", "卜": "ㅏ", "ﾄ": "ㅏ", "Г": "ㅏ", "ł": "ㅏ", "下": "ㅑ", "亻": "ㅓ", "丬": "ㅕ", "丄": "ㅗ", "凸": "ㅗ",
    "山": "ㅗ", "┻": "ㅗ", "┴": "ㅗ", "⊥": "ㅗ", "╨": "ㅗ", "丌": "ㅠ", "一": "ㅡ", "ー": "ㅡ", "ｰ": "ㅡ", "丨": "ㅣ",
    "Й": "ㅐ", "Н": "ㅐ",
}
LOOK_ASCII = {"r": "ㅏ", "k": "ㅏ", "F": "ㅑ", "J": "ㅓ", "I": "ㅣ", "l": "ㅣ", "1": "ㅣ", "|": "ㅣ", "H": "ㅐ", "L": "ㄴ",
              "z": "ㄹ", "7": "ㄱ", "0": "ㅇ", "o": "ㅇ", "O": "ㅇ", "^": "ㅅ"}
# 숫자를 닮은 글자 (스팸체 생성기). 숫자 옆이나 닮은 글자끼리 붙어 있을 때만 숫자로 본다
LOOK_DIGIT = {"丨": "1", "己": "2", "彐": "3", "丩": "4", "丂": "5", "旧": "18"}
LEET = str.maketrans({"0": "o", "3": "e", "4": "a", "5": "s", "7": "t", "$": "s", "@": "a"})

# ---------- 광고성 사전 (research/04 §7) ----------

KW_KO = ["카지노", "바카라", "슬롯", "토토", "먹튀", "첫충", "매충", "환전", "홀덤", "파워볼", "꽁머니", "안전놀이터", "메이저사이트",
         "배팅", "베팅", "총판", "룰렛", "잭팟", "블랙잭", "사설토토", "스포츠토토", "성인", "19금", "조건만남", "출장안마", "야동", "성인방송",
         "비아그라", "시알리스", "대포통장", "법인통장", "통장임대", "통장매매", "대포폰", "작업대출", "불법대출", "무직자대출", "무직자", "급전", "카드깡", "내구제",
         "필로폰", "대마초", "마약",
         # 2군 (research/14 §3-1): 릴게임·성매매·불법 대출·중계 계열. 일반어로도 쓰는 말은 WEAK
         "릴게임", "바다이야기", "홀짝", "사다리게임", "그래프게임", "온카", "슬롯머신", "스포츠중계", "해외축구중계", "도박",
         "사설", "롤링", "유흥", "오피", "출장", "1인샵", "립카페", "키스방", "성매매", "출장마사지", "레비트라",
         "대출", "개인돈", "일수", "대리입금", "소액결제현금화", "상품권현금화", "휴대폰깡", "중계"]
# 일반어로도 쓰는 말: 연락처·코드(또는 다른 약한 말 + 행동어)가 함께 있을 때만 광고 신호 ("성인반 수강 신청 문의", "외화 환전 안내", "의회 생중계")
# 모집요강 예시 "무료 슬롯 체험 바로가기"처럼 연락처 없는 광고가 있으므로 슬롯·토토 같은 도박 용어는 WEAK에 넣지 않는다
WEAK = {"성인", "환전", "마약", "급전", "무직자", "대출", "출장", "중계", "사설", "롤링", "유흥", "오피", "도박", "일수", "spins"}
NOT_KW = ["오피스"]  # 키워드를 품은 정상 낱말
# 안내문 어미: 광고는 짧은 문구라 이런 말투를 거의 안 쓴다. 연락처·코드가 없으면 정상 안내로 본다 ("…당첨금 지급 문의는 고객센터로 하시기 바랍니다")
GUIDE = re.compile(r"바랍니다|하시기|하십시오|안내해\s*드립니다|문의하세요|확인하세요")
KW_EN = ["casino", "baccarat", "slot", "slots", "toto", "bet", "poker", "holdem", "jackpot", "roulette", "sportsbook",
         "viagra", "cialis", "gambling", "gacor", "judi", "situs", "sbobet", "spins"]
ACTION = ["가입", "코드", "지급", "이벤트", "체험", "무료", "바로가기", "충전", "보너스", "입금", "실시간", "추천", "상담", "문의",
          "접속", "주소", "신규", "혜택", "검증", "판매", "할인", "예약", "쿠폰", "시청", "알바", "고수익", "보장", "당일", "승인",
          "24시", "모집", "정품", "free", "bonus", "join", "signup", "deposit"]
NEGATIVE = ["예방", "근절", "단속", "신고", "처벌", "주의", "경고", "피해", "교육", "캠페인", "유의", "금지", "차단", "상담센터",
            "1336", "경찰", "금융감독원", "감독위원회", "보도자료"]
NORMAL_CHO = {"ㅋㅋ", "ㅎㅎ", "ㅠㅠ", "ㅜㅜ", "ㅇㅋ", "ㄱㅅ", "ㄴㄴ", "ㅇㅇ", "ㄱㄱ", "ㅂㅂ", "ㅈㅅ", "ㄷㄷ"}

CONTACT = re.compile(r"(?<![a-z0-9_.])@[a-z][a-z0-9_]{3,31}(?![a-z0-9_@.])|t\.me/\w{3,}|open\.kakao\.com/\S+|"
                     r"(?:카톡|카카오톡|라인|line|텔레|텔레그램|위챗|wechat|kakao)\s*(?:id|아이디)?\s*[:：]?\s*@?[a-z][a-z0-9_]{2,31}\b|"
                     r"(?:bit\.ly|han\.gl|me2\.do|vo\.la|t\.ly|tinyurl\.com|goo\.gl|url\.kr|is\.gd|cutt\.ly)/\w+|"
                     r"01[016789][-. ]?\d{3,4}[-. ]?\d{4}|"
                     r"(?<![\w@])[a-z0-9][a-z0-9-]{1,}\s*(?:\.|닷|점)\s*(?:com|net|kr|xyz|top|io|bet|vip|club|site|test|example|me|cc)\b",
                     re.I)
CODE = re.compile(r"코드\s*[:：]?\s*[a-z0-9]{3,}|(?:첫충|매충|충전|보너스|지급|입금)\D{0,8}\d{1,3}\s*%|\d{1,3}\s*%\s*(?:지급|보너스|충전)",
                  re.I)
GOV = re.compile(r"\.(?:go|or|ac|re|mil|ne|pe|co)\.kr$|^(?:go|or|ac|re|mil)\.kr$")  # 기관·학교 도메인은 연락처로 안 침
KW_EN_RE = re.compile(r"(?<![a-z])(?:%s)(?![a-z])" % "|".join(KW_EN), re.I)


def cho_of(word):
    return "".join(CHO[(ord(c) - 0xAC00) // 588] for c in word if is_syl(c))


KW_CHO = {cho_of(k): k for k in KW_KO if len(k) >= 2}

# ---------- 정규화 ----------


def to_compat(c):
    """첫가끝·반각 자모 → 호환 자모"""
    o = ord(c)
    if 0x1100 <= o <= 0x1112:
        return CHO[o - 0x1100]
    if 0x1161 <= o <= 0x1175:
        return JUNG[o - 0x1161]
    if 0x11A8 <= o <= 0x11C2:
        return JONG[o - 0x11A8 + 1]
    if 0xFFA0 <= o <= 0xFFDC:
        n = ud.normalize("NFKC", c)
        return n if len(n) == 1 and 0x3131 <= ord(n) <= 0x318E else (to_compat(n) if len(n) == 1 else c)
    return c


def compose(s):
    """호환 자모 열을 음절로 조합한다. 자모 사이 구분자는 건너뛴다. 반환: (문자열, 조합한 음절 수)"""
    out, i, n, made = [], 0, len(s), 0

    def nxt(j):  # j부터 구분자를 건너뛴 다음 글자 위치
        while j < n and s[j] in SEP:
            j += 1
        return j

    while i < n:
        c = s[i]
        if c in DOUBLE and i + 1 < n and s[i + 1] == c and i + 2 < n and s[i + 2] in JUNG:  # ㄱㄱㅗㅇ → 꽁 (쌍자음 풀어쓰기)
            s, n = s[:i] + DOUBLE[c] + s[i + 2:], n - 1
            c = s[i]
        if c in CHO:
            j = nxt(i + 1)
            if j < n and s[j] in JUNG:
                v, k = s[j], nxt(j + 1)
                if k < n and (v, s[k]) in VV:
                    v, k = VV[(v, s[k])], nxt(k + 1)
                t, end = "", k
                if k < n and s[k] in CHO and s[k] in JONG:
                    k2 = nxt(k + 1)
                    if not (k2 < n and s[k2] in JUNG):  # 다음이 모음이면 받침이 아니라 다음 초성
                        t, end = s[k], k2 if k2 > k + 1 else k + 1
                        if k2 < n and (t, s[k2]) in CC:
                            k3 = nxt(k2 + 1)
                            if not (k3 < n and s[k3] in JUNG):
                                t, end = CC[(t, s[k2])], k2 + 1
                        else:
                            end = k + 1
                out.append(chr(0xAC00 + (CHO.index(c) * 21 + JUNG.index(v)) * 28 + JONG.index(t)))
                made += 1
                i = end
                continue
        out.append(c)
        i += 1
    return "".join(out), made


DOUBLE = {"ㄱ": "ㄲ", "ㄷ": "ㄸ", "ㅂ": "ㅃ", "ㅅ": "ㅆ", "ㅈ": "ㅉ"}


def strip_jong(s):
    return "".join(chr(0xAC00 + (ord(c) - 0xAC00) // 28 * 28) if is_syl(c) else c for c in s)


def unbidi(s):
    """RLO(U+202E)…PDF(U+202C) 구간을 뒤집고 방향 제어 문자를 지운다 (09 §5)"""
    s = re.sub("‮([^‪-‮]*)(‬|$)", lambda m: m.group(1)[::-1], s)
    return BIDI.sub("", s)


def base(s):
    """보이지 않는 글자 제거 + NFKC + 。→. + 결합 부호 제거 + 첫가끝·반각 자모를 호환 자모로"""
    # 한글 계열은 NFKC를 거치면 자모가 음절로 미리 합쳐져 흔적이 사라지므로 자체 조합기(compose)에 맡긴다
    out = []
    for c in IGNORABLE.sub("", unbidi(s)).translate(DOT):
        if is_hangulish(c):
            out.append(to_compat(c))
        else:  # NFKC 후 결합 부호(Mn) 제거: cásínó → casino, 카̈지노 → 카지노 (09 §7.3)
            out.append(ud.normalize("NFC", "".join(x for x in ud.normalize("NFD", fold(c))
                                                   if ud.category(x) != "Mn")))
    return "".join(out)


def near(s, i, pred):
    """s[i]의 앞뒤(구분자 건너뜀) 글자 중 pred를 만족하는 게 있나"""
    for step in (-1, 1):
        j = i + step
        while 0 <= j < len(s) and s[j] in SEP and s[j] != " ":
            j += step
        if 0 <= j < len(s) and pred(s[j]):
            return True
    return False


def variants(raw):
    """(n1, n2, flags). n1: 닮은 한자·가나·숫자 되돌림, n2: + 자모 옆 라틴·숫자 되돌림. 둘 다 자모 조합 전"""
    global CONF
    if CONF is None:
        CONF = _conf()
    s = base(raw).replace("刀卜", "까")  # korcen 다중 글자 규칙 (09 §7.2)
    hangul = lambda c: is_syl(c) or 0x3131 <= ord(c) <= 0x318E  # noqa: E731
    jamo = lambda c: 0x3131 <= ord(c) <= 0x318E  # noqa: E731
    digitish = lambda c: c.isdigit() or c in LOOK_DIGIT  # noqa: E731
    n1, flags = [], set()
    for i, c in enumerate(s):
        if c in LOOK_DIGIT and (near(s, i, digitish) or near(s, i, lambda x: x == "-")):
            n1.append(LOOK_DIGIT[c])
            flags.add("digit-lookalike")
        elif c in LOOK and near(s, i, hangul):
            n1.append(LOOK[c])
            flags.add("ko-lookalike")
        elif c in CONF and not c.isascii():
            n1.append(CONF[c])
        else:
            n1.append(c)
    n1 = "".join(n1)
    n2 = re.sub(r"77(?=[ㅏ-ㅣ])", "ㄲ", n1)  # 77 + 모음 → ㄲ
    n2 = "".join(LOOK_ASCII[c] if c in LOOK_ASCII and near(n2, i, jamo) else c for i, c in enumerate(n2))
    return n1, n2, flags


def squash(s):
    return "".join(c for c in s if c not in SEP).lower()


def jong_noise(sq):
    """두 글자 키워드에 받침을 덧붙인 글자 (먺튅 → 먹튀). 덧붙인 받침이 있어야 한다 (스스로 ≠ 슬롯)"""
    out = set()
    for k in KW_KO:
        if len(k) != 2 or k in sq:
            continue
        sk = strip_jong(k)
        for i in range(len(sq) - 1):
            sub = sq[i:i + 2]
            if sub != k and strip_jong(sub) == sk and all(is_syl(c) and (ord(c) - 0xAC00) % 28 for c in sub):
                out.add(k + "(받침)")
    return out


def keywords(s):
    """정규화된 문자열에서 찾은 키워드 집합"""
    sq = squash(s)
    for w in NOT_KW:
        sq = sq.replace(w, "|")
    found = {k for k in KW_KO if k in sq}
    found |= {m.group(0).lower() for m in KW_EN_RE.finditer(s)}
    stripped = strip_jong(sq)  # 받침 노이즈 (3음절 이상 키워드만)
    found |= {k + "(받침)" for k in KW_KO if len(k) >= 3 and k not in sq and strip_jong(k) in stripped}
    return found


# ---------- 판정 ----------


def homoglyph_tokens(raw):
    """키워드 일치 없이도 인정하는 닮은꼴 토큰: 전각·수학·원문자(A), 라틴을 닮은 다른 문자 체계(B), 주소 속 。(전각 마침표)"""
    global CONF
    if CONF is None:
        CONF = _conf()
    hits = []
    for tok in re.split(r"\s+", raw):
        compat = [c for c in tok if not c.isascii() and len(fold(c)) == 1 and fold(c).isascii() and fold(c).isalnum()]
        conf = [c for c in tok if not c.isascii() and c not in compat and c in CONF]
        latin = [c for c in tok if c.isascii() and c.isalpha()]
        letters = [c for c in compat if fold(c).isalpha()]
        fwdigit = sum("０" <= c <= "９" for c in tok)  # 전각 숫자로 쓴 연락처 (０１０－…)
        if letters and (len(compat) >= 2 or latin) or re.search(r"[a-z0-9][。｡．][a-z]", tok, re.I) or fwdigit >= 3:
            hits.append(tok)
        elif conf and (len(conf) >= 2 or latin):
            hits.append(tok)
    return hits


def check(raw):
    """raw(원문) → {"ad", "HOMOGLYPH": 근거 또는 None, "JAMO": 근거 또는 None, "norm", "kw", "INVISIBLE": 추가 유형 근거 또는 None}"""
    n1, n2, flags = variants(raw)
    c1, made1 = compose(n1)
    c2, made2 = compose(n2)
    leet = [raw.lower().translate(LEET).replace("1", x) for x in "il"]
    kw_raw = keywords(base(raw))
    kw1, kw2 = keywords(c1), keywords(c2)
    kw_leet = set().union(*(keywords(x) for x in leet)) - kw_raw
    kw_all = kw1 | kw2 | kw_leet | kw_raw
    # 키워드 글자 사이에 보이지 않는 글자를 끼움 (카\u00ad지노): 4종 밖 추가 유형, 회피 의도라 광고 신호로도 센다
    # 방향 제어 문자(RLO 등)는 화면 순서 바꾸기라 여기서 빼고 남긴다 (todo/08 VISUAL_REORDER)
    kw_inv = kw_raw - keywords(base(IGNORABLE.sub(lambda m: m.group() if BIDI.match(m.group()) else "\x01", raw)))

    # 초성 약어 (ㅋㅈㄴ, ㅁㅌ): 다른 광고 신호가 있을 때만 셈
    cho = [t for t in re.split(r"[^ㄱ-ㅎ]+", c2) if len(t) >= 2 and t not in NORMAL_CHO and t in KW_CHO]

    low = c2.lower()
    contact = any(not GOV.search(m.group(0)) for x in (low, c1.lower()) for m in CONTACT.finditer(x))
    code = bool(CODE.search(low))
    sq = squash(c2)
    action = any(a in sq for a in ACTION)
    neg = any(w in t for t in re.split(r"\s+", low) for w in NEGATIVE)  # 어절 안에서만: "당첨금 지급"의 "금지" 방지
    weak = {k for k in kw_all if k.removesuffix("(받침)") in WEAK}
    # 두 글자 키워드 받침 노이즈 (먺튅): 연락처·코드가 있을 때만
    if contact or code:
        kw_all |= jong_noise(sq)
    strong = len(kw_all - weak) + (len(cho) if contact or code else 0)
    ad = strong >= 1 and (contact or code or strong + len(weak) >= 2 or action or bool(kw_inv)) or bool(weak and (contact or code)) \
        or bool(len(weak) >= 2 and action)
    if (neg or GUIDE.search(c2)) and not contact and not code:
        ad = False

    res = {"ad": ad, "HOMOGLYPH": None, "JAMO": None, "norm": c2, "kw": sorted(kw_all | {KW_CHO[t] for t in cho}),
           "INVISIBLE": "보이지 않는 글자를 지우면: " + ", ".join(sorted(kw_inv)) if kw_inv else None}

    # HOMOGLYPH
    toks = homoglyph_tokens(raw)
    if toks:
        res["HOMOGLYPH"] = "변형 문자 토큰: " + " ".join(toks)[:80]
    elif flags:
        res["HOMOGLYPH"] = "한글·숫자를 닮은 글자"
    elif kw2 - kw1:
        res["HOMOGLYPH"] = "자모 옆 라틴·숫자를 한글로 읽으면: " + ", ".join(sorted(kw2 - kw1))
    elif kw_leet:
        res["HOMOGLYPH"] = "leet 숫자를 글자로 읽으면: " + ", ".join(sorted(kw_leet))
    elif any(ud.category(x) == "Mn" for c in raw if not is_hangulish(c) for x in ud.normalize("NFD", c)) and \
            kw_raw - keywords(unbidi(raw)):
        res["HOMOGLYPH"] = "결합 부호를 지우면: " + ", ".join(sorted(kw_raw - keywords(unbidi(raw))))

    # JAMO
    has_jamo = any(is_jamo(c) for c in raw)
    kw_syl = keywords(re.sub(r"[ㄱ-ㅣ]", "", base(raw)))  # 자모를 빼고도 나오는 키워드
    if has_jamo and (made2 >= 2 or (made2 >= 1 and kw2 - kw_syl)):
        res["JAMO"] = "자모를 조합하면: " + c2[:60]
    elif cho and (contact or code):
        res["JAMO"] = "초성 약어: " + ", ".join("%s→%s" % (t, KW_CHO[t]) for t in cho)
    elif any(k.endswith("(받침)") for k in kw_all):
        res["JAMO"] = "받침을 지우면: " + ", ".join(k for k in sorted(kw_all) if k.endswith("(받침)"))
    return res


if __name__ == "__main__":  # 자체 확인: python app/textcheck.py
    H, J = "HOMOGLYPH", "JAMO"
    cases = [  # (원문, 기대 기법들, 광고여부)
        ("ｍｅｇａ－ＢＥＴ 첫충 30％ 지급", {H}, True),
        ("ㅋㅏㅈㅣㄴㅗ ㅂㅗㄴㅓㅅㅡ 코드 TESTLUCKY7", {J}, True),
        ("саsіnо 첫충 40% 가입코드 TESTVIP88", {H}, True),
        ("ⓣⓞⓣⓞ 사이트 ⓑⓔⓣ365 텔레 @test_toto365", {H}, True),
        ("亼포츠 토토 卫액 환전 텔레그램 @test_sports_kk", {H}, True),
        ("ㅋㅈㄴ ㅂㅋㄹ 입금 보너스 텔레그램 @test_bkr24", {J}, True),
        ("ㅌ.ㅗ.ㅌ.ㅗ ㅅ.ㅏ.ㅇ.ㅣ.ㅌ.ㅡ 꽁머니 지급 텔레 @test_toto_king", {J}, True),
        ("ㅋr지노 꽁머니 지급 텔레 @test_krzino", {H, J}, True),
        ("\u110f\u1161\u110c\u1175\u1102\u1169 첫충 @test_casino_16", {J}, True),  # 첫가끝 자모
        ("𝐂𝐀𝐒𝐈𝐍𝐎 첫충 @test_casino_29", {H}, True),
        ("토토 가입코드 丨己彐 @test_toto_30", {H}, True),
        ("cas1no b3t 첫충 @test_casino_31", {H}, True),
        ("ㅋ​ㅏㅈㅣㄴㅗ 첫충 @test_casino_j8", {J}, True),
        ("ㅋㅏㄹㅈㅣㄴㅗ @test_casino_j7", {J}, True),
        ("ロㅌ 안전놀이터 @test_mt_f12b", {H, J}, True),
        ("통장 임대 월 己丂0만 010-0000-丨己彐丩", {H}, True),
        ("ㅋト지노 첫충 @test_ev_23", {H, J}, True),
        ("캃짆놁 첫충 30% @test_kjn_bonus", {J}, True),
        ("ﾼￌﾼￌ 가입코드 TEST04", {J}, True),
        ("s1ot 무료체험 b3t @test_slot_05", {H}, True),
        ("𝐁𝐄𝐓𝟑𝟔𝟓 토토 가입코드 TEST88", {H}, True),
        ("ㅂ​ㅏ​ㅋ​ㅏ​ㄹ​ㅏ 실시간 @test_bkr_stat", {J}, True),
        ("카지노 바카라 텔레그램 @test_plain", set(), True),
        ("온라인바카라 † く 【￥ bcc777。COM ￥】 ぅ", {H}, True),  # 。 마침표 (research/13 §3)
        ("카\u00ad지\u00ad노\u00ad커\u00ad뮤\u00ad니\u00ad티", set(), True),  # 소프트 하이픈 삽입: 4종 아님, 광고
        ("ㄱ\u2061ㅏ 카지노 단속 안내", set(), False),
        ("\u202e노지카\u202c 가입 @test_rlo", set(), True),  # bidi는 INVISIBLE 아님 (아래에서 따로 확인)
        ("회의록。hwp 내려받기", set(), False),
        ("77ㅗㅇ머니 지급 @test_kk", {H, J}, True),  # korcen 77→ㄲ
        ("카ㆍ지ㆍ노 첫충 @test_dot", set(), True),  # ㆍ는 구분자, 자모 아님
        ("@test_flex01카지노", set(), True),  # ID 뒤에 한글이 붙어도 연락처
        ("문의 help@agency.go.kr 카지노 단속", set(), False),
        # 미끼
        ("c\u00e1s\u00edn\u00f3 첫충 @test_a1", {H}, True),  # 결합 부호
        ("\u202e노지카\u202c 첫충 @test_b", set(), True),  # bidi 재정렬은 4종 아님 (09 §5)
        ("본문 바로가기", set(), False),
        ("（주）새솔건설 株式會社 ①② Ⅱ 10μg K-water e-나라도움", set(), False),
        ("ㅋㅋㅋ 좋아요 ㅠㅠ ㄱ. ㄴ. ㄷ.", set(), False),
        ("불법도박 예방 교육 안내 1336", set(), False),
        ("대포통장 매매는 처벌됩니다", set(), False),
        ("불법 대출 무직자 가능 010-0000-1045", set(), True),
        ("불법 광고 게시물 신고 안내", set(), False),
        ("LH공사 7월 1층 문의 help@agency.go.kr 02-123-4567", set(), False),
        ("시ㆍ도 협의회", set(), False),
        ("ＡＢＣ마트 ＬＧ전자", {H}, False),
        # research/14 신규
        ("ʙᴇᴛ 365 가입코드 TEST55", {H}, True),
        ("🅑🅔🅣 365 토토 @test_neg", {H}, True),
        ("무직자대출 당일 승인 ０１０－００００－５５８２", {H}, True),
        ("ㄱㄱㅗㅇㅁㅓㄴㅣ 지급 @test_kkong", {J}, True),
        ("먺튅 검증 사이트 가입 @test_mt", {J}, True),
        ("릴게임 바다이야기 무료쿠폰 지급 텔레 @test_reel", set(), True),
        ("오피 출장 1인샵 24시 예약 010-0000-1234", set(), True),
        ("해외 스포츠중계 무료 시청 가입 bit.ly/test123", set(), True),
        ("비아그라 정품 할인 판매 카톡 test99", set(), True),
        ("Best online gambling - free spins at spin-test.example", set(), True),
        ("카톡 ID: casino77 첫충 이벤트", set(), True),
        ("성인반 수강 신청 문의", set(), False),
        ("해외 연수 참가자 외화 환전 안내: 가까운 은행에 문의하세요", set(), False),
        ("성인 독감 접종 일정 문의 1339", set(), False),
        ("오피스텔 분양 상담 문의", set(), False),
        ("도서 대출 반납 안내", set(), False),
        ("스스로 문의 @test_self", set(), False),
        ("의회 생중계 바로가기", set(), False),
        ("스포츠토토 당첨금 지급 문의는 수탁사업자 고객센터로 하시기 바랍니다.", set(), False),
    ]
    bad = 0
    for raw, want, ad in cases:
        r = check(raw)
        got = {t for t in (H, J) if r[t]}
        if got != want or r["ad"] != ad:
            bad += 1
            print("실패:", raw, "기대", want, ad, "결과", got, r["ad"], r["kw"], r["norm"])
    assert check("카\u00ad지\u00ad노\u00ad커뮤니티")["INVISIBLE"] and not check("\u202e노지카\u202c 가입 @test_rlo")["INVISIBLE"]
    print("통과" if not bad else "%d건 실패" % bad)
