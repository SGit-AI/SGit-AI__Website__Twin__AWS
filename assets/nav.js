/* aws.twin.sgit.ai — nav interaction, the same component twins.sgit.ai and sgit.ai run.
   Two jobs, and only one of them needs JavaScript on desktop: hover and :focus-within
   open a dropdown in CSS alone. This handles the rest — the phone menu button, and the
   fact that a finger has no hover. If this file never loads the nav still works: every
   group label is a link to that section's own page. */
(function () {
  'use strict';
  var nav = document.querySelector('nav.site');
  if (!nav) return;
  var toggle = nav.querySelector('.nav-toggle');
  if (toggle) {
    toggle.addEventListener('click', function () {
      var open = nav.classList.toggle('open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }
  /* On a touch screen the dropdown has no hover to open it: the first tap on a group
     label opens the menu, a second follows the link. Only where a dropdown is actually
     drawn — in the collapsed phone menu the children are already visible. */
  document.addEventListener('click', function (e) {
    var link = e.target.closest && e.target.closest('nav.site .ni-has > .nl');
    var open = nav.querySelector('.ni-has.open');
    if (open && (!link || link.parentNode !== open)) open.classList.remove('open');
    if (!link || !window.matchMedia || !window.matchMedia('(hover: none)').matches) return;
    var item = link.parentNode, sub = item.querySelector('.sub');
    if (sub && window.getComputedStyle(sub).position === 'absolute'
            && !item.classList.contains('open')) {
      e.preventDefault();
      item.classList.add('open');
    }
  });
  /* Escape closes whatever is open — keyboard users get out the same way everywhere. */
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    var open = nav.querySelector('.ni-has.open');
    if (open) open.classList.remove('open');
    if (nav.classList.contains('open')) {
      nav.classList.remove('open');
      if (toggle) toggle.setAttribute('aria-expanded', 'false');
    }
  });
}());
