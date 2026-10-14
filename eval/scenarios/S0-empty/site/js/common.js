/* 공통 스크립트: 탭 전환, 레이어 팝업 닫기, FAQ 열기 (DOM 구조는 바꾸지 않음) */
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('.tab-btns button').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var box = btn.closest('.main-tabs');
      box.querySelectorAll('.tab-btns button').forEach(function (b) { b.classList.remove('on'); });
      box.querySelectorAll('.tab-panel').forEach(function (p) { p.hidden = true; });
      btn.classList.add('on');
      box.querySelector('#' + btn.getAttribute('aria-controls')).hidden = false;
    });
  });
  document.querySelectorAll('.faq-q').forEach(function (q) {
    q.addEventListener('click', function () {
      var a = q.nextElementSibling;
      a.hidden = !a.hidden;
      q.setAttribute('aria-expanded', String(!a.hidden));
    });
  });
  document.querySelectorAll('.pop-close').forEach(function (b) {
    b.addEventListener('click', function () { b.closest('.layer-popup').style.display = 'none'; });
  });
});
