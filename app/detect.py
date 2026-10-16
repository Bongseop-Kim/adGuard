"""탐지 4종: 페이지의 모든 프레임에서 숨김(OFFSCREEN·TRANSPARENT)과 변형(HOMOGLYPH·JAMO)을 찾는다.

    findings = await analyze(page, url)   # crawler.crawl(url, analyze)에 넘긴다
    → [{"location", "technique", "evidence_text", "reason"}]

근거: docs/research/04-정확도-판정규칙.md, 09-보완-탐지기술.md
- 후보 = 텍스트를 직접 가진 요소. 숨김은 CSS 속성 대조가 아니라 "글자가 실제로 그려진 박스"로 판정한다
  (텍스트 노드 rect, 조상 클리핑 교차, 누적 opacity, 조상 배경 합성 + WCAG 대비 1.25)
- 배경이 이미지·그라데이션이라 계산이 안 되면 글자만 visibility:hidden으로 바꿔 찍은 스크린샷과 비교한다
- 출력 = (숨김 또는 변형 신호) AND 광고성. 기법마다 1건
"""
import asyncio
import json
import re
import struct
import zlib

import textcheck

LIB_JS = r"""
() => {
if (window.__adg) return;
const SKIP = new Set(['SCRIPT', 'STYLE', 'TEMPLATE', 'NOSCRIPT', 'TITLE', 'HEAD', 'META', 'LINK', 'OPTION']);
const INLINE = new Set(['SPAN', 'B', 'I', 'U', 'S', 'EM', 'STRONG', 'A', 'FONT', 'SMALL', 'MARK', 'SUB', 'SUP', 'INS', 'DEL', 'Q', 'CITE', 'KBD', 'CODE']);
const up = e => e.parentElement || (e.parentNode && e.parentNode.host) || null;  // Shadow DOM 경계를 넘는 부모
const cs = e => getComputedStyle(e);
const rgba = s => {
  const m = /rgba?\(([^)]*)\)/.exec(s || ''); if (!m) return null;
  const p = m[1].split(/[\s,\/]+/).filter(Boolean).map(x => x.endsWith('%') ? parseFloat(x) / 100 : parseFloat(x));
  return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1];
};
const lum = c => { const f = v => { v /= 255; return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
                   return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
const over = (top, bot) => { const a = top[3]; return [0, 1, 2].map(i => top[i] * a + bot[i] * (1 - a)).concat([1]); };
const contrast = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
const fop = f => { let v = 1; for (const m of (f || '').matchAll(/opacity\(([\d.]+)(%?)\)/g)) v *= m[2] ? m[1] / 100 : +m[1]; return v; };

function textNodes(e) { return [...e.childNodes].filter(n => n.nodeType === 3 && n.nodeValue.trim()); }
// 직속 글자가 없으면(글자가 자식 요소에 나뉜 부모) 자손 글자 노드로 본다
function textsOf(e) {
  const own = textNodes(e);
  if (own.length) return own;
  const out = [], w = document.createTreeWalker(e, NodeFilter.SHOW_TEXT);
  while (w.nextNode()) if (w.currentNode.nodeValue.trim()) out.push(w.currentNode);
  return out;
}
function rectsOf(e, box) {
  if (box) return [e.getBoundingClientRect()];
  const out = [];
  for (const t of textsOf(e)) { const r = document.createRange(); r.selectNodeContents(t); out.push(...r.getClientRects()); }
  if (!out.length && (e.tagName === 'INPUT' || e.tagName === 'TEXTAREA')) out.push(e.getBoundingClientRect());
  return out;
}
// clip-path가 그리는 영역을 0으로 만드는가 (inset 50% 이상, 반지름 0인 원·타원, 넓이 0인 다각형)
function clipPathZero(v, b) {
  if (!v || v === 'none') return false;
  let m = /inset\(([^)]*)\)/.exec(v);
  if (m) { const p = m[1].split(/\s+/).map(x => x.endsWith('%') ? parseFloat(x) / 100 : parseFloat(x) / Math.max(1, Math.min(b.width, b.height)));
           const [t, r = t, bo = t, l = r] = p; return t + bo >= 1 || l + r >= 1; }
  if (/^(circle|ellipse)\(\s*0(px|%)?(\s|\)|\s*0)/.test(v)) return true;
  m = /polygon\(([^)]*)\)/.exec(v);
  if (m) { const pts = m[1].split(',').map(s => s.trim()); return new Set(pts).size <= 1; }
  return false;
}

// 요소의 숨김 신호. box=true면 글자 대신 요소 박스로 본다 (iframe 요소용)
function signals(e, box) {
  const off = [], tr = [];
  let root = null, diff = false, marquee = false;
  const s0 = cs(e), svg = e instanceof SVGElement;
  const rendered = e.checkVisibility ? e.checkVisibility() : !!e.getClientRects().length;
  if (!rendered) {
    off.push('렌더링 안 됨(display:none 등)');
    for (let n = e; n; n = up(n)) if (n.nodeType === 1 && (cs(n).display === 'none' || n.hidden)) { root = n; break; }
  }
  if (!box && parseFloat(s0.fontSize) <= 1) off.push('font-size ' + s0.fontSize);
  // 자기 자신의 content-visibility:hidden (hidden="until-found" 포함): checkVisibility()는 조상 것만 본다
  if (rendered && s0.contentVisibility === 'hidden') off.push('content-visibility:hidden' + (e.getAttribute('hidden') === 'until-found' ? ' (hidden=until-found)' : ''));
  if (rendered) {
    const rs = rectsOf(e, box).filter(r => r.width > 0 || r.height > 0);
    const sx = scrollX, sy = scrollY;
    const docW = Math.max(document.documentElement.scrollWidth, innerWidth);
    if (!rs.length) off.push('글자 박스 없음');
    else {
      const maxH = Math.max(...rs.map(r => r.height)), sumW = rs.reduce((a, r) => a + r.width, 0);
      const chars = textsOf(e).reduce((a, t) => a + t.nodeValue.trim().length, 0) || 1;
      if (maxH <= 1 || sumW <= 1) off.push('글자 박스 크기 0');
      else if (box ? (maxH < 2 || sumW < 2) : (maxH < 3 || sumW / chars < 1.5)) off.push('글자 박스가 읽을 수 없게 작음');
      if (rs.every(r => r.right + sx <= 0 || r.bottom + sy <= 0 || r.left + sx >= docW)) off.push('문서 밖 좌표');
      // 오른쪽·아래로 보낸 글 (right:-9999px): 문서 폭이 같이 늘어나 좌표로는 못 잡는다. left:-9999px의 대칭
      for (let n = e; n && n.nodeType === 1 && n !== document.body; n = up(n)) {
        const s = cs(n);
        if (s.position !== 'absolute' && s.position !== 'fixed') continue;
        if (parseFloat(s.right) <= -1000 || parseFloat(s.bottom) <= -1000) { off.push('right/bottom ' + s.right + ' ' + s.bottom); }
        break;
      }
      // 조상 클리핑: overflow, clip, clip-path. absolute는 정적 조상의 overflow에 안 잘리고, fixed는 조상에 안 잘린다
      let L = -1e9, T = -1e9, R = 1e9, B = 1e9, abs = false, fixed = false, zero = null;
      for (let n = e; n && n.nodeType === 1 && n !== document.documentElement && n !== document.body; n = up(n)) {
        const s = cs(n), b = n.getBoundingClientRect();
        let skip = false;
        if (n !== e) { if (fixed) break; if (abs && s.position === 'static' && s.transform === 'none') skip = true; else abs = false; }
        if (!skip && (s.overflowX !== 'visible' || s.overflowY !== 'visible') && !(n === e && box)) {
          const l = b.left + n.clientLeft, t = b.top + n.clientTop;
          if (n.clientWidth < 2 || n.clientHeight < 2) { zero = n; break; }  // 크기 0 상자는 스크롤 확장보다 먼저 (09 §1)
          const w = /auto|scroll/.test(s.overflowX) ? n.scrollWidth : n.clientWidth;
          const h = /auto|scroll/.test(s.overflowY) ? n.scrollHeight : n.clientHeight;
          if (s.overflowX !== 'visible') { L = Math.max(L, l); R = Math.min(R, l + w); }
          if (s.overflowY !== 'visible') { T = Math.max(T, t); B = Math.min(B, t + h); }
        }
        if ((s.position === 'absolute' || s.position === 'fixed') && s.clip && s.clip !== 'auto') {
          const m = /rect\(([^)]*)\)/.exec(s.clip);
          if (m) { const p = m[1].split(/[\s,]+/).map(x => x === 'auto' ? null : parseFloat(x));
                   T = Math.max(T, b.top + (p[0] ?? 0)); R = Math.min(R, b.left + (p[1] ?? b.width));
                   B = Math.min(B, b.top + (p[2] ?? b.height)); L = Math.max(L, b.left + (p[3] ?? 0)); }
        }
        if (clipPathZero(s.clipPath, b)) { zero = n; break; }
        if (s.position === 'fixed') fixed = true;
        if (s.position === 'absolute') abs = true;
      }
      if (zero) off.push('크기 0 상자에 잘림');
      else {
        // 한 줄이라도 높이 35% 이상, 폭 2px 이상 보이면 보임 (line-clamp 미리보기 오탐 방지, 09 §2)
        const vis = rs.some(r => Math.min(r.bottom, B) - Math.max(r.top, T) >= r.height * 0.35 &&
                                 Math.min(r.right, R) - Math.max(r.left, L) >= 2);
        if (!vis && !off.includes('문서 밖 좌표')) off.push('조상 상자에 잘림');
      }
    }
    if (e.closest('marquee')) marquee = true;
  }
  // TRANSPARENT: 투명도는 조상까지 곱한다
  if (s0.visibility !== 'visible') tr.push('visibility:' + s0.visibility);
  let op = 1, blend = false, bgUnknown = false;
  for (let n = e; n && n.nodeType === 1; n = up(n)) {
    const s = cs(n); op *= parseFloat(s.opacity) * fop(s.filter);
    if (s.mixBlendMode !== 'normal' || (s.filter !== 'none' && !/^(opacity\([^)]*\)\s*)+$/.test(s.filter))) blend = true;
  }
  if (op < 0.1) tr.push('누적 opacity ' + op.toFixed(2));
  if (!box) {
    let fill = svg ? rgba(s0.fill) : (rgba(s0.webkitTextFillColor) || rgba(s0.color));
    if (svg && fill) fill[3] *= parseFloat(s0.fillOpacity);
    const deco = (s0.textShadow !== 'none') || parseFloat(s0.webkitTextStrokeWidth) > 0;
    const clipText = /text/.test(s0.webkitBackgroundClip || s0.backgroundClip || '') && s0.backgroundImage !== 'none';
    let bg = [255, 255, 255, 1]; const layers = [];
    for (let n = e; n && n.nodeType === 1; n = up(n)) {
      const s = cs(n);
      if (s.backgroundImage !== 'none' && !(n === e && clipText)) { bgUnknown = true; break; }
      const c = rgba(s.backgroundColor); if (c && c[3] > 0) { layers.push(c); if (c[3] >= 1) break; }
    }
    for (const c of layers.reverse()) bg = over(c, bg);
    if (clipText) diff = true;
    else if (fill && fill[3] < 0.1 && !deco) tr.push('글자색 투명(' + (svg ? s0.fill : s0.webkitTextFillColor) + ')');
    else if (fill && !deco && !bgUnknown) {
      const cr = contrast(over(fill, bg), bg);
      if (cr < 1.25) tr.push('글자색과 배경 대비 ' + cr.toFixed(2));
    }
    if ((bgUnknown || blend) && rendered && !tr.length && !off.length) diff = true;
  }
  return { off, tr, root, diff, marquee };
}

// 광고성 판정용 글자열: 이 요소 기준으로 숨긴 자손(display:none, font-size≤1)은 빼고, ::before/::after를 붙이고,
// flex·grid 자식은 화면 순서로, bidi-override rtl은 뒤집는다 (09 §5)
function vtext(e) {
  const s = cs(e);
  const pseudo = p => { const c = getComputedStyle(e, p).content; return c && c !== 'none' && c !== 'normal' ? c.replace(/^["']|["']$/g, '') : ''; };
  if (e.tagName === 'INPUT') return e.value || '';
  let kids = [...e.childNodes];
  if (/flex|grid/.test(s.display)) {  // 화면 좌표 순서 (글자 노드는 Range로 위치를 잰다)
    const pos = k => { if (k.nodeType === 1) return k.getBoundingClientRect();
                       const r = document.createRange(); r.selectNodeContents(k); return r.getBoundingClientRect(); };
    const at = new Map(kids.map(k => [k, pos(k)]));
    kids.sort((a, b) => (at.get(a).top - at.get(b).top) || (at.get(a).left - at.get(b).left));
  }
  let t = pseudo('::before');
  for (const k of kids) {
    if (k.nodeType === 3) t += k.nodeValue;
    else if (k.nodeType === 1 && !SKIP.has(k.tagName)) {
      const ks = cs(k);
      if (ks.display === 'none' || parseFloat(ks.fontSize) <= 1) continue;
      t += vtext(k);
    }
  }
  t += pseudo('::after');
  if (s.unicodeBidi === 'bidi-override' && s.direction === 'rtl') t = [...t].reverse().join('');
  return t;
}

// ---------- location ----------
const STATE = new Set(['active', 'on', 'open', 'show', 'hover', 'focus', 'selected', 'current', 'visible', 'in', 'fade']);
const HASH = /^(css|sc|jsx|emotion|styled|svelte)-|^_[\w-]{5,}$|_[a-zA-Z0-9]{5}$|[bcdfghjklmnpqrstvwxz]{4,}|\d[^\d]*\d[^\d]*\d|[a-z]\d+[a-z]+\d|\d[a-z]+\d+[a-z]|^(?=[a-z0-9]*\d[a-z])[a-z0-9]{4,8}$|^(is|has|ng|aos|swiper-slide|slick)-/i;
const stable = c => c.length > 1 && !STATE.has(c) && !HASH.test(c);
const q = s => s.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
function nth(n) { let i = 1; for (let p = n.previousElementSibling; p; p = p.previousElementSibling) if (p.localName === n.localName) i++; return ':nth-of-type(' + i + ')'; }
function seg(n) {
  const c = [...n.classList].find(stable);
  if (c) return n.localName + '.' + CSS.escape(c);
  if (n.id && !HASH.test(n.id)) return n.localName + '#' + CSS.escape(n.id);
  return n.localName + nth(n);
}
// 상위 요소부터 ' > '로 잇는다. 자동 삽입되는 tbody·thead는 건너뛰고 자손 결합자(공백)로 잇는다 (04 §8.3)
function selectorIn(e) {
  const root = e.getRootNode();
  const parts = [];  // [세그먼트, 다음과의 결합자]
  const join = () => parts.map((p, i) => p[0] + (i < parts.length - 1 ? p[1] : '')).join('');
  const one = sel => { try { const r = root.querySelectorAll(sel); return r.length === 1 && r[0] === e; } catch (x) { return false; } };
  let joiner = ' > ';
  for (let n = e; n && n.nodeType === 1 && n.localName !== 'html'; n = n.parentElement) {
    if (/^(tbody|thead|tfoot)$/.test(n.localName) && n.parentElement && n.parentElement.localName === 'table') { joiner = ' '; continue; }
    const s = seg(n);
    parts.unshift([s, joiner]); joiner = ' > ';
    if (one(join())) return join();
    if (!/:nth-of-type/.test(s)) { parts[0][0] = s + nth(n); if (one(join())) return join(); parts[0][0] = s; }
  }
  // 마지막 수단: 모든 단계에 순번
  let n = e;
  for (const p of parts.slice().reverse()) {
    while (n && /^(tbody|thead|tfoot)$/.test(n.localName)) n = n.parentElement;
    if (n && !/:nth-of-type|\[src=/.test(p[0])) p[0] += nth(n);
    n = n && n.parentElement;
  }
  return join();
}
// Shadow DOM 안이면 호스트 경로 >>> 안쪽 경로
function locate(e) {
  const r = e.getRootNode();
  const inner = selectorIn(e);
  return r instanceof ShadowRoot ? locate(r.host) + ' >>> ' + inner : inner;
}

function collect(all_) {  // all_: 상위 iframe이 숨겨져 있으면 자기 신호가 없어도 후보로
  const all = [];
  const visit = root => { for (const e of root.querySelectorAll('*')) { all.push(e); if (e.shadowRoot) visit(e.shadowRoot); } };
  visit(document);
  const C = window.__adg.C = [], out = [];
  const shown = new Map();  // 요소 → 숨김 신호 없음 (보이는 글자열을 만들 때 쓴다)
  // 숨김 신호가 없어도 연락처가 있으면 문자 판정을 한다 (보이는 받침 노이즈 "먺튅 … @id")
  const contactish = /@[a-z][a-z0-9_]{3}|t\.me\/|open\.kakao|01[016789][-. ]?\d{3,4}[-. ]?\d{4}|bit\.ly\//i;
  const KW = new RegExp(__KW__, 'i');  // 광고 사전 낱말 (보이는 광고 VISIBLE_AD 후보)
  const odd = /[^\x00-\x7f가-힣\s -¿‐-‧‰-⁞　-〿]|[a-z][0-9]|[0-9][a-z]|[­͏ᅟᅠ᠋-᠏​-‏⁠-⁯ㅤ︀-️﻿ﾠ]/i;
  for (const e of all) {
    if (SKIP.has(e.tagName) || e.closest('script,style,template,noscript,head')) continue;
    let own = textNodes(e).map(t => t.nodeValue).join(' ');
    if ((e.tagName === 'INPUT' && /^(text|search|email|url|tel|)$/.test(e.type || '') && e.value) ) own = e.value;
    let block = false;
    if (!own.trim()) {
      // 글자 노드가 없는 부모: 자손 글자를 합쳐 판정 (research/14 §3-2). span으로 쪼갠 글자(ㅋㅏ|ㅈㅣ|ㄴㅗ)나,
      // 숨김을 만든 상자 안에 글자가 여러 요소로 나뉜 경우(<strong>카지노</strong><a>가입 @id</a>)
      const kids = [...e.children], txt = e.textContent.trim();
      if (!txt || txt.length > 300 || kids.length < 2 || kids.length > 8) continue;
      block = kids.every(k => !k.children.length && INLINE.has(k.tagName)) ? 'inline' : 'hide';
    }
    const raw = (e.tagName === 'INPUT' ? e.value : e.textContent).replace(/\s+/g, ' ').trim();
    const sg = signals(e, false);
    if (block === 'hide') {  // 숨김이 이 상자에서 시작될 때만 (부모가 보일 때). 부모 신호는 숨겨진 상자만 잰다
      if (!(sg.off.length || sg.tr.length)) continue;
      const p = up(e), sp = p && p.nodeType === 1 ? signals(p, false) : null;
      if (sp && (sp.off.length || sp.tr.length)) continue;
    }
    shown.set(e, !sg.off.length && !sg.tr.length && !sg.diff);
    if (!all_ && !sg.off.length && !sg.tr.length && !sg.diff && !sg.marquee && !odd.test(raw) && !contactish.test(raw) && !KW.test(raw.replace(/\s+/g, ''))) continue;
    const vt = vtext(e).replace(/\s+/g, ' ').trim();
    const i = C.push(e) - 1;
    e.__adgI = i;
    let anc = null;
    for (let n = up(e); n; n = up(n)) if (n.__adgI !== undefined && C[n.__adgI] === n) { anc = n.__adgI; break; }
    let rootSame = null;
    if (sg.root && sg.root !== e && sg.root.textContent.replace(/\s+/g, '') === e.textContent.replace(/\s+/g, '')) rootSame = C.push(sg.root) - 1;
    out.push({ i, anc, block, raw: raw.slice(0, 500), text: vt.slice(0, 500), off: sg.off, tr: sg.tr, diff: sg.diff, marquee: sg.marquee, root: rootSame });
  }
  // 숨긴 글이 같은 페이지에 그대로 보이면 광고를 감추려는 숨김이 아니다: 접근성 제목(그누보드 #hd_h1), 댓글 수정 폼 등 (research/13 §1)
  // ponytail: 보이는 쪽 글만 본다. 화면 어디에도 없는 sr-only 광고는 그대로 검출. iframe이 숨겨져 있으면(all_) 따지지 않음
  if (!all_) {
    let vis = '';
    const w = document.createTreeWalker(document, NodeFilter.SHOW_TEXT);
    while (w.nextNode()) { const p = w.currentNode.parentElement; if (p && shown.get(p)) vis += w.currentNode.nodeValue; }
    vis = vis.replace(/\s+/g, '');
    for (const o of out) {  // 제목 형식("글 제목 > 게시판 | 사이트")이면 조각마다 본다
      const parts = o.raw.split(/\s[>|·:\-–—]\s/).map(x => x.replace(/\s+/g, '')).filter(Boolean);
      if ((o.off.length || o.tr.length) && parts.join('').length >= 6 && parts.every(x => vis.includes(x))) o.dup = true;
    }
  }
  return out;
}

// 스크린샷 차분 준비: 직속 텍스트 노드를 span으로 감싸고 그 span만 visibility:hidden (09 §3)
function hideText(i, on) {
  const e = window.__adg.C[i];
  if (!e.__adgWrapped) {
    for (const t of textNodes(e)) { const s = document.createElement('span'); s.setAttribute('data-adg-w', ''); t.replaceWith(s); s.appendChild(t); }
    e.__adgWrapped = true;
  }
  for (const s of e.querySelectorAll(':scope > span[data-adg-w]')) s.style.visibility = on ? 'hidden' : '';
}
// marquee 상자 안에 들어온 글자 면적 비율
function marqueeSeen(i) {
  const e = window.__adg.C[i], m = e.closest('marquee').getBoundingClientRect();
  let all = 0, seen = 0;
  for (const r of rectsOf(e, false)) {
    all += r.width * r.height;
    seen += Math.max(0, Math.min(r.right, m.right) - Math.max(r.left, m.left)) * Math.max(0, Math.min(r.bottom, m.bottom) - Math.max(r.top, m.top));
  }
  return all ? seen / all : 0;
}
// iframe 단계: iframe[src="절대URL"]. src 속성은 상대 경로일 수 있어 CSS로는 못 세므로 .src끼리 비교한다.
// 같은 src가 여럿이면 상위 경로를 붙이고, src가 없으면(srcdoc 등) 일반 경로 (04 §8.4)
function frameSeg(e) {
  const r = e.getRootNode();
  if (!e.getAttribute('src')) return locate(e);
  const s = 'iframe[src="' + q(e.src) + '"]';
  const same = [...r.querySelectorAll('iframe')].filter(x => x.src === e.src);
  const pre = r instanceof ShadowRoot ? locate(r.host) + ' >>> ' : '';
  return pre + (same.length === 1 ? s : selectorIn(e.parentElement) + ' > ' + s);
}
window.__adg = { C: [], collect, signals, locate, hideText, marqueeSeen, frameSeg };
}
"""


STYLE_JS = r"""
i => {
  const e = window.__adg.C[i], s = getComputedStyle(e), out = {};
  for (const k of ['display', 'visibility', 'opacity', 'position', 'left', 'top', 'font-size', 'color',
                   'background-color', 'overflow', 'clip', 'clip-path', 'transform', 'text-indent', 'width', 'height'])
    out[k] = s.getPropertyValue(k);
  const h = e.outerHTML;
  return { html: h.length > 800 ? h.slice(0, 800) + ' …' : h, style: out };
}
"""


LIB_JS = LIB_JS.replace("__KW__", json.dumps("|".join(re.escape(k) for k in textcheck.KW_KO + textcheck.KW_EN if k not in textcheck.WEAK)))


async def ev(target, js, arg=None, sec=10):
    try:
        return await asyncio.wait_for(target.evaluate(js, arg), sec)
    except Exception:
        return None


def png_rgb(data):
    """Playwright PNG(8비트, 비인터레이스) → (폭, 높이, 바이트열 RGB(A)). 표준 라이브러리만 쓴다"""
    w, h, depth, ctype = struct.unpack(">IIBB", data[16:26])
    bpp = {2: 3, 6: 4}[ctype]
    raw, pos, idat = b"", 8, []
    while pos < len(data):
        n, t = struct.unpack(">I4s", data[pos:pos + 8])
        if t == b"IDAT":
            idat.append(data[pos + 8:pos + 8 + n])
        pos += 12 + n
    raw = zlib.decompress(b"".join(idat))
    stride, out, prev = w * bpp, bytearray(), bytearray(w * bpp)
    for y in range(h):
        f, line = raw[y * (stride + 1)], bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for x in range(stride):
            a = line[x - bpp] if x >= bpp else 0
            b, c = prev[x], prev[x - bpp] if x >= bpp else 0
            if f == 1:
                line[x] = (line[x] + a) & 255
            elif f == 2:
                line[x] = (line[x] + b) & 255
            elif f == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        out += line
        prev = line
    return w, h, bpp, bytes(out)


async def text_invisible(page, frame, i):
    """글자만 숨긴 스크린샷과 차이가 거의 없으면 안 보이는 글자 (차이 > 24인 픽셀이 글자 면적의 1% 미만)"""
    h = await frame.evaluate_handle("i => window.__adg.C[i]", i)
    try:
        await asyncio.wait_for(h.scroll_into_view_if_needed(timeout=2000), 3)
        box = await h.bounding_box()
        if not box or box["width"] < 1 or box["height"] < 1:
            return False
        clip = {k: box[k] for k in ("x", "y", "width", "height")}
        a = await page.screenshot(clip=clip, animations="disabled", caret="hide", timeout=5000)
        await ev(frame, "i => window.__adg.hideText(i, true)", i)
        b = await page.screenshot(clip=clip, animations="disabled", caret="hide", timeout=5000)
        await ev(frame, "i => window.__adg.hideText(i, false)", i)
        (w, hh, bpp, pa), (_, _, _, pb) = png_rgb(a), png_rgb(b)
        changed = sum(1 for k in range(0, len(pa), bpp) if max(abs(pa[k + j] - pb[k + j]) for j in range(3)) > 24)
        return changed < max(1, w * hh * 0.01)
    except Exception:
        return False
    finally:
        await h.dispose()


async def analyze(page, url):
    """crawler가 부르는 페이지 분석. 프레임을 위에서부터 내려가며 location 접두어와 숨김 상속을 넘긴다"""
    found = []

    async def walk(frame, prefix, inherit):
        await ev(frame, LIB_JS)
        hidden = bool(inherit["OFFSCREEN"] or inherit["TRANSPARENT"])
        cands = await ev(frame, "a => window.__adg.collect(a)", hidden, sec=20) or []
        hits = {}  # 후보 인덱스 → 그 후보에서 낸 기법들
        for c in cands:
            hits[c["i"]] = await judge(frame, prefix, inherit, c)
        # 같은 기법이 자손에서도 나왔으면 부모 것은 뺀다: 광고는 가장 안쪽 요소 (04 §4.3)
        # 숨김을 만든 상자(block "hide")는 광고 자손이 2개 이상일 때만 뺀다: 광고 여럿을 감싼 상자는 자식만, 광고 하나를 감싼 숨김 상자는 둘 다 (S1 tag-cloud, S2 s-wrap1)
        by_i = {c["i"]: c for c in cands}
        under = {}
        for c in cands:
            a = c["anc"]
            while a is not None:
                for k in hits.get(a, {}):
                    if k in hits[c["i"]]:
                        under.setdefault((a, k), set()).add(c["i"])
                a = by_i[a]["anc"] if a in by_i else None
        # span 조각(inline) 부모는 자손 하나라도 검출되면 뺀다: 조각 하나가 이미 광고면 합친 글이 아니라 따로 쓴 글이다
        for (a, k), kids in under.items():
            if by_i[a].get("block") != "hide" or len(kids) >= 2:
                hits[a][k]["drop"] = True
        # 보이는 부모 글에 숨긴 자식 광고가 섞였으면(보이는 문단 + 투명 span) 부모는 VISIBLE_AD가 아니다: 광고는 자식
        for c in cands:
            if not hits[c["i"]]:
                continue
            a = c["anc"]
            while a is not None:
                if "VISIBLE_AD" in hits.get(a, {}):
                    hits[a]["VISIBLE_AD"]["drop"] = True
                a = by_i[a]["anc"] if a in by_i else None
        for c in cands:
            if c.get("block") == "inline" and hits[c["i"]]:
                a = c["i"]
                if any(hits.get(d["i"]) for d in cands if d["anc"] == a):
                    for f in hits[a].values():
                        f["drop"] = True
        for child in frame.child_frames:
            try:
                fe = await asyncio.wait_for(child.frame_element(), 3)
                seg = await asyncio.wait_for(fe.evaluate("e => window.__adg.frameSeg(e)"), 3)
                sg = await asyncio.wait_for(fe.evaluate("e => window.__adg.signals(e, true)"), 3)
            except Exception:
                continue
            inh = {"OFFSCREEN": inherit["OFFSCREEN"] + ["iframe: " + x for x in sg["off"]],
                   "TRANSPARENT": inherit["TRANSPARENT"] + ["iframe: " + x for x in sg["tr"]]}
            await walk(child, prefix + seg + " >>> ", inh)

    async def judge(frame, prefix, inherit, c):
        t = textcheck.check(c["text"])
        if not t["ad"] or c.get("dup"):  # dup: 같은 글이 화면에 보인다. 보이는 쪽에서 판정한다
            return {}
        tech = {}
        off, tr = c["off"] + inherit["OFFSCREEN"], c["tr"] + inherit["TRANSPARENT"]
        if c["marquee"] and not off:
            seen = []
            for _ in range(8):  # 흐르는 글자: 2.4초 동안 한 번도 상자 안에 안 들어오면 숨김 (09 §4)
                seen.append(await ev(frame, "i => window.__adg.marqueeSeen(i)", c["i"]) or 0)
                if seen[-1] >= 0.05:
                    break
                await asyncio.sleep(0.3)
            if max(seen) < 0.05:
                off = ["marquee가 글자를 상자 밖으로만 움직임"]
        if off:
            tech["OFFSCREEN"] = "; ".join(off)
        if tr:
            tech["TRANSPARENT"] = "; ".join(tr)
        shot = None  # 스크린샷 비교 결과: True 안 보임, False 보임
        if not tr and c["diff"] and not off and not c.get("block"):
            shot = await text_invisible(page, frame, c["i"])
            if shot:
                tech["TRANSPARENT"] = "배경 위에서 글자가 보이지 않음(스크린샷 비교)"
        for k in ("HOMOGLYPH", "JAMO"):
            if t[k]:
                tech[k] = t[k]
        # 4종 밖 추가 유형 VISIBLE_AD: 숨김·변형 없이 그냥 보이는 광고. 연락처·코드까지 있을 때만 (안내문 오탐 방지)
        visible = not tech and not off and not tr and (not c["diff"] or shot is False)
        if visible and t["contact"]:
            tech["VISIBLE_AD"] = "숨김·변형 없이 보이는 광고 (" + ", ".join(t["kw"]) + ")"
        if not tech and not t["INVISIBLE"]:
            return {}
        loc = await ev(frame, "i => window.__adg.locate(window.__adg.C[i])", c["i"])
        if not loc:
            return {}
        # 보고서 근거(R5)용: HTML 조각과 숨김에 관계된 계산된 스타일. result.json에는 안 들어간다
        more = await ev(frame, STYLE_JS, c["i"]) or {}
        mine = {}
        for k, why in tech.items():
            mine[k] = {"location": prefix + loc, "technique": k, "evidence_text": c["raw"], "reason": why,
                       "norm": t["norm"], "kw": t["kw"], **more}
            if k == "VISIBLE_AD":  # result_extra.json으로만 (모집요강 붙임4, technique "ETC")
                mine[k].update(technique="ETC", extra_finding="VISIBLE_AD")
            found.append(mine[k])
        if t["INVISIBLE"]:  # 4종 밖 추가 유형: result_extra.json으로만 나간다 (모집요강 붙임4, technique "ETC")
            found.append({"location": prefix + loc, "technique": "ETC", "extra_finding": "INVISIBLE_CHAR",
                          "evidence_text": c["raw"], "reason": t["INVISIBLE"], "norm": t["norm"], "kw": t["kw"], **more})
        # 숨김 루트가 광고만 감싸고 있으면 루트도 낸다 (04 §4.3)
        if c["root"] is not None and "OFFSCREEN" in tech:
            rloc = await ev(frame, "i => window.__adg.locate(window.__adg.C[i])", c["root"])
            if rloc:
                found.append({"location": prefix + rloc, "technique": "OFFSCREEN", "evidence_text": c["raw"],
                              "reason": "광고만 감싼 숨김 상위 요소"})
        return mine

    await walk(page.main_frame, "", {"OFFSCREEN": [], "TRANSPARENT": []})
    seen, out = set(), []
    for f in found:
        k = (f["location"], f["technique"])
        if k not in seen and not f.get("drop"):
            seen.add(k)
            out.append(f)
    return out
