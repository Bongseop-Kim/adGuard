/* 공통 스크립트 */
var SITE = { archive: "/archive/notice", search: "/search" };
function goArchive() { location.href = SITE.archive; }
function moreCmt(id, btn) {
  btn.cpage = (btn.cpage || 1) + 1;
  fetch("/api/comments?id=" + id + "&cpage=" + btn.cpage).then(function (r) { return r.text(); }).then(function (h) {
    document.querySelector("ul.cmt-list").insertAdjacentHTML("beforeend", h);
    if (btn.cpage >= +btn.getAttribute("data-last")) btn.style.display = "none";
  });
}
