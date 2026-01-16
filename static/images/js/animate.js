const observer=new IntersectionObserver((entries)=>{for(const e of entries){if(e.isIntersecting){e.target.classList.add('is-visible');if(e.target.classList.contains('skills__group')){e.target.classList.add('is-expanded')}}}},{threshold:0.15});
document.querySelectorAll('.reveal').forEach(el=>observer.observe(el));
const skillDetails={
  'Python':'Backend APIs, automation, and ML in SmartKart and Career-F-Crawler.',
  'JavaScript':'Interactive UIs and sorting animations in Sorting Visualizer.',
  'C++':'Competitive programming and DSA problem solving.',
  'C':'Systems programming fundamentals and low-level concepts.',
  'SQL':'Writing queries and designing schemas for SmartKart and MyPrepSpot.',
  'HTML':'Building semantic layouts for all portfolio projects.',
  'CSS':'Custom responsive styling and hover animations.',
  'Django':'Backend for SmartKart and MyPrepSpot platforms.',
  'Flask':'Backend for Career-F-Crawler analytics.',
  'React.js':'Dashboards and SPA frontends for SmartKart and MyPrepSpot.',
  'Tailwind CSS':'Utility-first styling for dashboards and landing pages.',
  'Bootstrap':'Quick prototyping of responsive layouts.',
  'PostgreSQL':'Primary relational database for structured project data.',
  'MySQL':'Relational database used in academic and personal projects.',
  'SQLite':'Lightweight DB for smaller applications and prototypes.',
  'MongoDB':'Document database for flexible data models.',
  'Pandas':'Data wrangling in ML pipelines.',
  'NumPy':'Numerical operations in ML and DS work.',
  'Scikit-learn':'ML models and recommendation engines.',
  'Seaborn':'Statistical visualizations.',
  'Matplotlib':'Custom plots and graphs.',
  'Git':'Version control for all codebases.',
  'GitHub':'Hosting and collaborating on projects.',
  'VS Code':'Primary development editor.',
  'Linux':'Server environments and command-line workflows.'
};
document.querySelectorAll('.chip').forEach(ch=>{
  const key=ch.textContent.trim();
  ch.dataset.title=skillDetails[key]||key;
});

// Tilt effect for project cards (desktop only)
const isTouch='ontouchstart' in window||navigator.maxTouchPoints>0;
if(!isTouch){
  document.querySelectorAll('.card').forEach(card=>{
    card.classList.add('card--tilt');
    card.addEventListener('mousemove',(ev)=>{
      const r=card.getBoundingClientRect();
      const cx=ev.clientX - r.left - r.width/2;
      const cy=ev.clientY - r.top - r.height/2;
      const rx=(cy/r.height)*4;
      const ry=-(cx/r.width)*4;
      card.style.transform=`perspective(600px) rotateX(${rx}deg) rotateY(${ry}deg)`;
    });
    card.addEventListener('mouseleave',()=>{card.style.transform='';});
  });
}
// Project card "See more" toggles
document.querySelectorAll('[data-project-toggle]').forEach(btn=>{
  btn.addEventListener('click',()=>{
    const card=btn.closest('.card');
    if(card){card.classList.toggle('is-open');}
  });
});

// Subtle parallax on hero intro
const hero=document.querySelector('.hero__intro--left')||document.querySelector('.hero__intro--center');
if(hero){
  window.addEventListener('scroll',()=>{
    const y=window.scrollY*0.08;
    hero.style.transform=`translateY(${y}px)`;
  });
}

// Per-letter reveal for hero name
const nameEl=document.querySelector('.hero__outline--animated');
if(nameEl){
  const text=nameEl.textContent.trim();
  nameEl.textContent='';
  const frag=document.createDocumentFragment();
  [...text].forEach((ch,idx)=>{
    const span=document.createElement('span');
    span.textContent=ch;
    span.style.display='inline-block';
    span.style.opacity='0';
    span.style.transform='translateY(12px)';
    span.style.transition='opacity .4s ease, transform .4s ease';
    frag.appendChild(span);
    setTimeout(()=>{span.style.opacity='1';span.style.transform='translateY(0)'}, idx*50);
  });
  nameEl.appendChild(frag);
  nameEl.addEventListener('mouseenter',()=>{
    const letters=[...nameEl.childNodes].filter(n=>n.nodeType===1);
    letters.forEach(l=>{l.style.opacity='0';l.style.transform='translateY(12px)'});
    letters.forEach((l,idx)=>setTimeout(()=>{l.style.opacity='1';l.style.transform='translateY(0)'}, idx*45));
  });
}

// Typed effect for tagline
const taglineEl=document.querySelector('.hero__tagline');
if(taglineEl){
  const full=taglineEl.textContent;
  taglineEl.textContent='';
  let i=0;
  const tick=()=>{if(i<=full.length){taglineEl.textContent=full.slice(0,i);i++;setTimeout(tick,18)}};
  tick();
}

// Roles rotator (typewriter)
const rolesEl=document.getElementById('roles-typed');
if(rolesEl){
  const roles=(rolesEl.dataset.roles||'').split('|').filter(Boolean);
  let idx=0, pos=0, deleting=false;
  const speed=40, pause=800;
  const step=()=>{
    const word=roles[idx]||'';
    if(!deleting){
      pos++;
      rolesEl.textContent=word.slice(0,pos);
      if(pos>=word.length){deleting=true;setTimeout(step,pause);return}
    }else{
      pos--;
      rolesEl.textContent=word.slice(0,pos);
      if(pos<=0){deleting=false;idx=(idx+1)%roles.length}
    }
    setTimeout(step,speed);
  };
  step();
}
// Contact form AJAX submit
window.submitContact = function(form){
  const status=document.getElementById('contact-status');
  status.textContent='Sending...';
  fetch('/contact',{method:'POST',body:new FormData(form)})
    .then(r=>r.json())
    .then(d=>{
      status.textContent=d.ok?'Message sent successfully!':'Failed to send message.';
      if(d.stored){status.textContent+=' (Saved locally)'}
      form.reset();
      setTimeout(()=>{status.textContent=''}, 5000);
    })
    .catch(()=>{status.textContent='Failed to send message.'});
  return false;
};
