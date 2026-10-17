import json,sys,re,urllib.parse
H="127.0.0.1:8180"
EXP={"R01":"/f1/view?id=301","R02":"/f2/view?nttId=303","R03":"/f3/view?no=302","R04":"/f4/view?no=201","R05":"/spa/","R06":"/app/post/7",
"R07":"/c7/view?id=1","R08":"/c8/view?id=1","R09":"/t9/","R10":"/m10/list","R11":"/v11/preview?file=notice.hwp","R13":"/d13/view?id=2",
"R14":"/cal/event?id=9","R15":"/slow/view?id=1","R16":"/err/ok","R17":"/map/target","R18":"/btn/target","R19":"/dh/target","R20":"/sel/target",
"R21":"/ext/ok","R23":"/공지/글 보기?번호=5","R24":"/bh/sub/target.html","R25":"/mr/target","R26":"/jsr/target_page","R27":"/nest/",
"R28":"/sess/view?id=1","R29":"/secret/","R30":"/only/sitemap-page.html","R31":"/ln/2","R33":"/pop/view_n7","R39":"/hov/target",
"R40":"/ev/view?no=12","R41":"/fp/view?id=22",
"R42":"/ib/list?id=free&page=2","R44":"/aeb/t44","R45":"/aeb/t45","R46":"/lx/list","R47":"/cn/view?id=3","R48":"/late/","R49":"/enc/view?q=a%20b&path=x%2Fy&flag"}
if "--big" in sys.argv: EXP={k:v for k,v in [("R12_5","/big/view?id=5"),("R12_1500","/big/view?id=1500"),("R12_2995","/big/view?id=2995")]}
def n(u):
    s=urllib.parse.urlsplit(urllib.parse.unquote(u)); return s.path.rstrip("/")+"?"+"&".join(sorted(s.query.split("&")))
res=json.load(open(sys.argv[1]))
got={}
for f in res["findings"]:
    for m in re.findall(r"@test_(r\w+)",f["evidence_text"]):
        got.setdefault(m.upper(),set()).add((f["url"],f["technique"],f["location"]))
hit=0
for k,v in EXP.items():
    g=got.get(k,set()); urls={u for u,_,_ in g}
    ok=any(n(u)==n("http://"+H+v) for u in urls)
    hit+=ok
    print("%-9s %-4s %s"%(k,"OK" if ok else ("URL?" if g else "MISS"), sorted(g)[:2] if g and not ok else ""))
for k in sorted(set(got)-set(EXP)): print("EXTRA",k,sorted(got[k]))
# R49는 문자열 그대로 비교: %20·%2F·값 없는 flag가 바뀌면 안 된다 (todo/12 결정 6)
raw={u for u,_,_ in got.get("R49",set())}
print("R49 원래 표기", "OK" if "http://"+H+EXP["R49"] in raw else "FAIL %s" % sorted(raw))
print("hit %d/%d elapsed %s findings %d"%(hit,len(EXP),res["meta"]["elapsed_sec"],len(res["findings"])))
