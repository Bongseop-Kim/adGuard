/* 가온시설관리공단 공통 스크립트 */
(function () {
  // GNB 키보드 접근 시 하위 메뉴 열기
  document.querySelectorAll('.gnb > ul > li > a').forEach(function (a) {
    a.addEventListener('focus', function () { a.parentNode.classList.add('on'); });
    a.addEventListener('blur', function () { a.parentNode.classList.remove('on'); });
  });
  // 탭
  document.querySelectorAll('.tab-menu a[data-tab]').forEach(function (a) {
    a.addEventListener('click', function (e) {
      e.preventDefault();
      document.querySelectorAll('.tab-menu li').forEach(function (li) { li.classList.remove('on'); });
      document.querySelectorAll('.tab-cont .tab-panel').forEach(function (p) { p.classList.remove('on'); });
      a.parentNode.classList.add('on');
      var p = document.querySelector('.tab-cont .' + a.getAttribute('data-tab'));
      if (p) p.classList.add('on');
    });
  });
  // FAQ 아코디언
  document.querySelectorAll('.faq-list dt a').forEach(function (a) {
    a.addEventListener('click', function (e) {
      e.preventDefault();
      var dd = a.parentNode.nextElementSibling;
      if (dd) dd.classList.toggle('open');
    });
  });
  // 레이어 팝업 닫기
  document.querySelectorAll('.layer-popup .btn-close').forEach(function (b) {
    b.addEventListener('click', function () { b.closest('.layer-popup').classList.remove('open'); });
  });
})();
