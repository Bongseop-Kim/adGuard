document.addEventListener('DOMContentLoaded',function(){
  var el=document.querySelector('.js-hide-target');
  if(el){el.style.position='absolute';el.style.left='-9999px';el.style.top='0';}
  // open shadow dom host
  var h=document.getElementById('host-open');
  if(h){var r=h.attachShadow({mode:'open'});
    r.innerHTML='<div class="card"><p class="ok">자료실 안내 위젯</p><span class="sh" style="display:inline-block;transform:scale(0);">'+h.dataset.ad+'</span></div>';}
});
