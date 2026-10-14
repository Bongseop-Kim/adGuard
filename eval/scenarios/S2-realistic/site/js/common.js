(function(){
  document.querySelectorAll('.gnb-item').forEach(function(it){
    it.addEventListener('focusin',function(){it.classList.add('open')});
    it.addEventListener('focusout',function(){it.classList.remove('open')});
  });
  var f=document.querySelector('.btn-family');
  if(f)f.addEventListener('click',function(){var p=f.parentNode;p.classList.toggle('open');f.setAttribute('aria-expanded',p.classList.contains('open'))});
  document.querySelectorAll('[data-tab]').forEach(function(b){
    b.addEventListener('click',function(e){e.preventDefault();
      document.querySelectorAll('.tab-panel').forEach(function(p){p.classList.remove('on')});
      var t=document.getElementById(b.getAttribute('data-tab'));if(t)t.classList.add('on')});
  });
  document.querySelectorAll('.faq-item dt button').forEach(function(b){
    b.addEventListener('click',function(){b.parentNode.parentNode.classList.toggle('open')});
  });
})();
