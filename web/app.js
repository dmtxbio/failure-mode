'use strict';
const $ = (id) => document.getElementById(id);
const escapeHTML = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const number = (value) => Number(value || 0).toLocaleString();
const statuses = {unreviewed:'Not reviewed',gap:'Open gap',addressed:'Addressed',not_applicable:'Not applicable'};
const state = {view:'overview',stats:null,taxonomy:[],letters:[],total:0,offset:0,limit:25,request:0,related:new Set(),projects:[],active:null,storage:true};
let searchTimer, toastTimer;
async function api(path) {
  const response = await fetch(path, {headers:{Accept:'application/json'}});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'The archive could not be loaded.');
  return data;
}
function notify(message) {
  $('toast').textContent = message; $('toast').hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => $('toast').hidden = true, 4200);
}
function error(message) { $('error').textContent = message; $('error').hidden = !message; }
function params() {
  const data = new URLSearchParams(new FormData($('filters')));
  for (const [key,value] of [...data]) if (!value.trim()) data.delete(key);
  data.set('sort', $('sort').value);
  return data;
}
function syncURL() {
  const query = params(); if (query.get('sort') === 'date_desc') query.delete('sort');
  const tail = query.toString();
  history.replaceState(null, '', location.pathname + (tail ? '?' + tail : '') + (location.hash || '#overview'));
}
function statusBadge(value) {return '<span class="status ' + (String(value).toLowerCase()==='unapproved' ? 'unapproved' : '') + '">' + escapeHTML(value || 'Unknown') + '</span>';}
function applications(letter) {return (letter.application_number || []).join(' · ') || 'Application not disclosed';}
function tags(categories, max = 3) {
  const all = categories || [];
  return '<div class="tags">' + all.slice(0,max).map(c => '<span class="tag">' + escapeHTML(c.label) + '</span>').join('') + (all.length > max ? '<span class="tag">+' + (all.length-max) + '</span>' : '') + (!all.length ? '<span class="tag">No candidate match</span>' : '') + '</div>';
}
function metrics(stats) {
  const activeAreas = stats.categories.filter(c=>c.count>0).length;
  const values = [[number(stats.total_letters),'Published records','Includes pending-release metadata'],[number(stats.total_applications),'Distinct applications','A program can have multiple letters'],[number(activeAreas),'Candidate review areas','Automated, unreviewed topic matches'],[number(stats.text_available),'Letters with source text','Searchable, with source provenance']];
  $('metrics').innerHTML = values.map(([value,title,note])=>'<div class="metric"><div class="metric-value">'+value+'</div><div class="metric-title">'+title+'</div><div class="metric-note">'+note+'</div></div>').join('');
}
function charts(stats) {
  const cats = [...stats.categories].filter(c=>c.count>0).sort((a,b)=>b.count-a.count).slice(0,9);
  const max = Math.max(1,...cats.map(c=>c.count));
  $('category-chart').innerHTML = cats.length ? cats.map(c=>'<button class="bar-row" data-category="'+escapeHTML(c.id)+'" title="'+escapeHTML(c.label)+': '+c.count+' letters" aria-label="Explore '+escapeHTML(c.label)+', '+c.count+' letters"><span class="bar-label">'+escapeHTML(c.label)+'</span><span class="bar-track"><span class="bar-fill" style="width:'+(c.count/max*100)+'%"></span></span><span class="bar-count">'+c.count+'</span></button>').join('') : '<div class="empty">No topic matches in this selection.</div>';
  let years = [...stats.years].sort((a,b)=>a.year-b.year);
  if (years.length > 1) {
    const byYear = new Map(years.map(y=>[Number(y.year),y.count]));
    const first = Number(years[0].year), last = Number(years[years.length-1].year);
    if(last-first<100) years = Array.from({length:last-first+1},(_,i)=>({year:first+i,count:byYear.get(first+i)||0}));
  }
  const ymax = Math.max(1,...years.map(y=>y.count));
  $('timeline').innerHTML = years.length ? years.map(y=>'<button class="year-column '+(String(y.year)===$('filter-year').value?'selected':'')+'" data-year="'+escapeHTML(y.year)+'" aria-label="'+escapeHTML(y.year)+': '+y.count+' letters" '+(!y.count?'disabled':'')+'><span class="year-count">'+y.count+'</span><span class="year-bar" style="height:'+(y.count/ymax*83)+'%"></span><span class="year-label">'+escapeHTML(String(y.year).slice(years.length>12?2:0))+'</span></button>').join('') : '<div class="empty">No letters match these filters.</div>';
}
function renderLetters() {
  $('recent-letters').innerHTML = state.letters.slice(0,3).map(l=>'<article class="letter-card"><div class="card-top"><span>'+escapeHTML(l.letter_date)+'</span>'+statusBadge(l.status)+'</div><h3>'+escapeHTML(l.company_name || 'Sponsor not disclosed')+'</h3><p class="application">'+escapeHTML(applications(l))+'</p>'+tags(l.categories,2)+'<p class="card-excerpt">'+escapeHTML(l.evidence_preview || l.text_preview || 'FDA has not released letter text for this record.')+'</p><button class="text-link" data-letter="'+escapeHTML(l.id)+'">Read the letter ↗</button></article>').join('') || '<div class="empty">No letters found. Try a broader search or reset the filters.</div>';
  $('letters-body').innerHTML = state.letters.map(l=>'<tr><td><button class="row-title" data-letter="'+escapeHTML(l.id)+'">'+escapeHTML(l.company_name || 'Sponsor not disclosed')+'</button><p class="application">'+escapeHTML(applications(l))+'</p></td><td>'+escapeHTML(l.letter_date || 'Not disclosed')+'</td><td>'+statusBadge(l.status)+'</td><td>'+tags(l.categories)+'</td><td><button class="row-arrow" data-letter="'+escapeHTML(l.id)+'" aria-label="Read letter from '+escapeHTML(l.company_name)+'">↗</button></td></tr>').join('') || '<tr><td colspan="5"><div class="empty">No letters found. Try a broader search or reset the filters.</div></td></tr>';
  $('pagination').innerHTML = '<span>'+(state.total ? (state.offset+1)+'–'+Math.min(state.offset+state.limit,state.total) : '0')+' of '+number(state.total)+' letters</span><button class="button" data-page="-1" '+(!state.offset?'disabled':'')+'>← Previous</button><button class="button" data-page="1" '+(state.offset+state.limit>=state.total?'disabled':'')+'>Next →</button>';
}
async function refresh() {
  const request = ++state.request;
  const query = params(); query.set('limit',state.limit); query.set('offset',state.offset);
  $('result-count').textContent = 'Updating selection…';
  try {
    const [stats,letters] = await Promise.all([api('/api/stats?'+query),api('/api/letters?'+query)]);
    if (request !== state.request) return;
    error(''); state.letters = letters.results; state.total = letters.total;
    metrics(stats); charts(stats); renderLetters();
    $('result-count').textContent = number(letters.total)+' of '+number(state.stats.total_letters)+' published records';
    syncURL();
  } catch (err) {if(request===state.request){error(err.message);$('result-count').textContent='Search unavailable';}}
}
function route() {
  const view = location.hash.slice(1);
  state.view = ['overview','letters','planner','data'].includes(view)?view:'overview';
  $('research-shell').hidden = !['overview','letters'].includes(state.view);
  for (const id of ['overview','letters','planner','data']) {
    $('view-'+id).hidden = id !== state.view;
    document.querySelector('[data-view="'+id+'"]').classList.toggle('active',id===state.view);
    document.querySelector('[data-view="'+id+'"]').setAttribute('aria-current',id===state.view?'page':'false');
  }
  if(state.view==='planner') renderPlanner();
}
let detailRequest=0;
async function showLetter(id) {
  const request=++detailRequest;
  const dialog=$('letter-dialog');
  $('letter-detail').innerHTML='<h2 id="letter-title">Loading source letter…</h2>';
  if(!dialog.open) dialog.showModal();
  try {
    const l=await api('/api/letters/'+encodeURIComponent(id));
    if(request!==detailRequest) return;
    const p=l.provenance || {};
    const evidence=(l.evidence || []).map(e=>'<article class="detail-evidence"><h3>'+escapeHTML(e.category_label)+' <span class="tag">Candidate mention</span></h3><blockquote>'+escapeHTML(e.excerpt)+'</blockquote><p class="microcopy">Source text characters '+escapeHTML(e.start)+'–'+escapeHTML(e.end)+' · '+escapeHTML(e.method)+'</p></article>').join('');
    const pdf = typeof l.pdf_url==='string' && l.pdf_url.startsWith('https://download.open.fda.gov/') ? '<a class="button primary" href="'+escapeHTML(l.pdf_url)+'" target="_blank" rel="noopener">Open FDA source PDF ↗</a>' : '';
    $('letter-detail').innerHTML='<h2 id="letter-title" class="detail-title">'+escapeHTML(l.company_name || 'Sponsor not disclosed')+'</h2><div class="detail-meta"><span>'+escapeHTML(applications(l))+'</span><span>'+escapeHTML(l.letter_date)+'</span>'+statusBadge(l.status)+'</div><div class="inline-actions">'+pdf+'<a class="button" href="/api/letters/'+encodeURIComponent(l.id)+'" target="_blank" rel="noopener">View source record ↗</a></div><p class="detail-note">FDA dataset status is not a verified current market status. Topic matches below need review in the full letter context.</p>'+evidence+(!evidence?'<div class="empty">'+(l.text?'No candidate topics matched. Read the full source text to review this letter.':'No topic analysis is available until source text is released.')+'</div>':'')+'<details open><summary>Full letter text</summary><div class="full-text">'+escapeHTML(l.text || (l.pdf_url ? 'Text unavailable; consult the source PDF.' : 'FDA lists this record as under review for release. Letter text and a source PDF are not available.'))+'</div></details><details><summary>Provenance & extraction</summary><p class="source-hash">Source: '+escapeHTML(p.source_url)+'<br>File: '+escapeHTML(l.file_name)+'<br>FDA dataset updated: '+escapeHTML(p.source_updated)+'<br>Fetched: '+escapeHTML(p.source_fetched_at || 'Unknown')+'<br>Indexed: '+escapeHTML(p.ingested_at)+'<br>Taxonomy: '+escapeHTML(p.taxonomy_version || state.stats.taxonomy_version)+'<br>Snapshot SHA-256: '+escapeHTML(p.source_sha256)+'</p></details>';
  } catch(err) {$('letter-detail').innerHTML='<h2 id="letter-title">Letter unavailable</h2><p>'+escapeHTML(err.message)+'</p>';}
}
const storageKey='failure-mode-workspaces-v1';
function makeProject() { return {id:crypto.randomUUID(),name:'Untitled program',stage:'Development',context:'',entries:{},updated_at:new Date().toISOString()}; }
function project() {return state.projects.find(p=>p.id===state.active);}
function readProjects() {
  try {
    const stored=JSON.parse(localStorage.getItem(storageKey) || 'null');
    if(stored && Array.isArray(stored.projects) && stored.projects.length) {
      state.projects=stored.projects.map(validateProject); state.active=state.projects.some(p=>p.id===stored.active)?stored.active:state.projects[0].id;
    }
  } catch {state.storage=false;}
  if(!state.projects.length){const p=makeProject();state.projects=[p];state.active=p.id;}
}
function validateProject(raw) {
  if(!raw || typeof raw!=='object' || Array.isArray(raw) || typeof raw.name!=='string' || !['Development','Pre-NDA/BLA','Submission'].includes(raw.stage)) throw new Error('Not a valid workspace export.');
  const p={id:typeof raw.id==='string'?raw.id:crypto.randomUUID(),name:raw.name.slice(0,200),stage:raw.stage,context:String(raw.context || '').slice(0,100000),entries:{},updated_at:raw.updated_at || new Date().toISOString()};
  const allowed=new Set(state.taxonomy.map(c=>c.id));
  for(const [id,entry] of Object.entries(raw.entries || {})) {
    if(!allowed.has(id) || !entry || typeof entry!=='object') continue;
    p.entries[id]={status:Object.hasOwn(statuses,entry.status)?entry.status:'unreviewed',notes:String(entry.notes || '').slice(0,20000),owner:String(entry.owner || '').slice(0,300),evidence:String(entry.evidence || '').slice(0,2000)};
  }
  return p;
}
function save() {
  const p=project();p.updated_at=new Date().toISOString();
  try {localStorage.setItem(storageKey,JSON.stringify({version:1,active:state.active,projects:state.projects}));state.storage=true;} catch {state.storage=false;}
  $('save-status').textContent=state.storage?'Saved locally · '+new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}):'Browser storage unavailable. Export your work before leaving.';
}
function stageCategories() {return state.taxonomy.filter(c=>!c.stages?.length || c.stages.includes(project().stage));}
function updateRelated() {
  const text=project().context.toLowerCase();
  state.related=new Set(state.taxonomy.filter(c=>(c.terms || []).some(term=>text.includes(String(term).toLowerCase())) || c.label.toLowerCase().split(/[\s/&]+/).filter(t=>t.length>4).some(term=>text.includes(term))).map(c=>c.id));
}
function renderPlanner() {
  const p=project(); if(!p)return;
  $('project-select').innerHTML=state.projects.map(x=>'<option value="'+escapeHTML(x.id)+'" '+(x.id===p.id?'selected':'')+'>'+escapeHTML(x.name || 'Untitled program')+'</option>').join('');
  $('project-name').value=p.name; $('project-stage').value=p.stage; $('project-context').value=p.context;
  updateRelated(); renderChecklist(); progress();
  if(!state.storage)$('save-status').textContent='Browser storage unavailable. Export your work before leaving.';
}
function progress() {
  const p=project(), cats=stageCategories();
  const reviewed=cats.filter(c=>(p.entries[c.id]?.status || 'unreviewed')!=='unreviewed').length;
  const gaps=cats.filter(c=>p.entries[c.id]?.status==='gap').length;
  $('planning-progress').innerHTML='<div class="progress-heading"><strong>Review progress</strong><span>'+reviewed+' / '+cats.length+'</span></div><div class="progress-track"><div class="progress-fill" style="width:'+(cats.length?reviewed/cats.length*100:0)+'%"></div></div><p class="microcopy">'+gaps+' open '+(gaps===1?'gap':'gaps')+' · Progress tracks review, not readiness.</p>';
}
function renderChecklist() {
  const p=project(); const filter=$('checklist-filter').value;
  const cats=stageCategories().filter(c=>filter==='all' || (filter==='related'?state.related.has(c.id):(p.entries[c.id]?.status || 'unreviewed')===filter));
  $('checklist').innerHTML=cats.map((c,i)=>{
    const entry=p.entries[c.id] || {status:'unreviewed',notes:'',owner:'',evidence:''};
    return '<article class="check-item" data-check="'+escapeHTML(c.id)+'"><div class="check-title"><h3><span class="check-index">'+String(i+1).padStart(2,'0')+'</span> '+escapeHTML(c.label)+'</h3><select class="check-status '+entry.status+'" aria-label="Review status for '+escapeHTML(c.label)+'" data-entry="status">'+Object.entries(statuses).map(([key,label])=>'<option value="'+key+'" '+(entry.status===key?'selected':'')+'>'+label+'</option>').join('')+'</select></div><p class="check-question">'+escapeHTML(c.question)+'</p><p class="check-description">'+escapeHTML(c.description)+'</p>'+(state.related.has(c.id)?'<span class="context-badge">TERM MATCH IN YOUR PLAN CONTEXT</span>':'')+'<div class="evidence-links"><span>'+number(c.count)+' source letters</span>'+(c.examples || []).slice(0,2).map(l=>'<button data-letter="'+escapeHTML(l.id)+'">'+escapeHTML((l.application_number || [l.company_name]).join(', '))+' ↗</button>').join('')+'<button data-explore="'+escapeHTML(c.id)+'">Explore all ↗</button></div><div class="check-fields"><label class="wide">ASSESSMENT / OPEN QUESTIONS<textarea data-entry="notes" rows="2" placeholder="What supports your assessment? What still needs work?">'+escapeHTML(entry.notes)+'</textarea></label><label>SUPPORTING EVIDENCE / DOCUMENT REFERENCE<input data-entry="evidence" value="'+escapeHTML(entry.evidence)+'" placeholder="Protocol section, report, letter ID…"></label><label>OWNER / NEXT ACTION<input data-entry="owner" value="'+escapeHTML(entry.owner)+'" placeholder="Who will resolve this, and how?"></label></div></article>';
  }).join('') || '<div class="empty">'+(filter==='related'?'No review areas matched your context. Review all areas; unmentioned concerns can still apply.':'No review areas in this selection.')+'</div>';
}
function download(content,filename,type) {
  const link=document.createElement('a'); const url=URL.createObjectURL(new Blob([content],{type}));link.href=url;link.download=filename;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),10000);
}
function exportPlan(json=false) {
  const p=project();const filename=(p.name || 'program').replace(/[^a-z0-9_-]+/gi,'-').slice(0,80);
  if(json){download(JSON.stringify({version:1,project:p},null,2),filename+'-workspace.json','application/json');return;}
  const lines=['# '+p.name+' — development review','','Stage: '+p.stage,'Exported: '+new Date().toISOString(),'FDA dataset updated: '+(state.stats.source_updated || 'unknown'),'','This is a human planning record. Candidate letter topics are unreviewed, non-exhaustive, and do not establish regulatory readiness. Status is the reviewer’s assessment.','','## Plan context','',p.context || '(None supplied)',''];
  for(const c of stageCategories()) {
    const e=p.entries[c.id] || {status:'unreviewed'};
    lines.push('## '+c.label,'','Status: '+statuses[e.status],'',c.question,'','Assessment: '+(e.notes || '(Not documented)'),'Evidence reference: '+(e.evidence || '(Not documented)'),'Owner / next action: '+(e.owner || '(Not assigned)'),'','Published letters with candidate mentions: '+c.count);
    for(const l of (c.examples || []).slice(0,2))lines.push('- '+l.company_name+' · '+applications(l)+' · '+l.letter_date+' · letter ID: '+l.id);
    lines.push('');
  }
  lines.push('Source: https://open.fda.gov/apis/transparency/completeresponseletters/');
  download(lines.join('\n'),filename+'-review.md','text/markdown');
}
function bind() {
  window.addEventListener('hashchange',route);
  $('filters').addEventListener('submit',e=>{e.preventDefault();state.offset=0;refresh();});
  $('search').addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>{state.offset=0;refresh();},280);});
  $('filters').addEventListener('change',e=>{if(e.target.tagName==='SELECT'){state.offset=0;refresh();}});
  $('filters').addEventListener('reset',()=>setTimeout(()=>{state.offset=0;refresh();},0));
  $('sort').addEventListener('change',()=>{state.offset=0;refresh();});
  $('export-csv').addEventListener('click',()=>{const q=params();q.set('format','csv');location.href='/api/export?'+q;});
  document.addEventListener('click',e=>{
    const letter=e.target.closest('[data-letter]'); if(letter){showLetter(letter.dataset.letter);return;}
    const category=e.target.closest('[data-category]'); if(category){$('filter-category').value=category.dataset.category;state.offset=0;refresh();return;}
    const year=e.target.closest('[data-year]'); if(year){$('filter-year').value=year.dataset.year;state.offset=0;refresh();return;}
    const page=e.target.closest('[data-page]'); if(page && !page.disabled){state.offset+=Number(page.dataset.page)*state.limit;refresh();return;}
    const explore=e.target.closest('[data-explore]'); if(explore){$('filters').reset();$('filter-category').value=explore.dataset.explore;state.offset=0;location.hash='letters';refresh();}
  });
  $('close-dialog').addEventListener('click',()=>$('letter-dialog').close());
  $('letter-dialog').addEventListener('click',e=>{if(e.target===$('letter-dialog')){const r=e.target.getBoundingClientRect();if(e.clientX<r.left || e.clientX>r.right || e.clientY<r.top || e.clientY>r.bottom)e.target.close();}});
  $('project-select').addEventListener('change',e=>{state.active=e.target.value;save();renderPlanner();});
  $('new-project').addEventListener('click',()=>{const p=makeProject();state.projects.push(p);state.active=p.id;$('checklist-filter').value='all';save();renderPlanner();$('project-name').focus();$('project-name').select();});
  $('project-name').addEventListener('input',e=>{project().name=e.target.value.slice(0,200);save();$('project-select').selectedOptions[0].textContent=project().name || 'Untitled program';});
  $('project-context').addEventListener('input',e=>{project().context=e.target.value;save();});
  $('project-stage').addEventListener('change',e=>{project().stage=e.target.value;save();renderChecklist();progress();});
  $('suggest-areas').addEventListener('click',()=>{updateRelated();$('checklist-filter').value='related';renderChecklist();notify(state.related.size+' related review areas found. Review the full checklist too.');});
  $('checklist-filter').addEventListener('change',renderChecklist);
  $('checklist').addEventListener('input',e=>{
    const field=e.target.dataset.entry;if(!field)return;
    const id=e.target.closest('[data-check]').dataset.check;
    const p=project();p.entries[id] ||= {status:'unreviewed',notes:'',owner:'',evidence:''};
    p.entries[id][field]=e.target.value; save(); progress();
    if(field==='status'){e.target.className='check-status '+e.target.value;if($('checklist-filter').value!=='all' && $('checklist-filter').value!=='related')renderChecklist();}
  });
  $('export-plan').addEventListener('click',()=>exportPlan());
  $('export-plan-json').addEventListener('click',()=>exportPlan(true));
  $('import-plan').addEventListener('change',async e=>{
    const file=e.target.files[0];if(!file)return;
    try {
      if(file.size>2000000)throw new Error('Workspace files must be smaller than 2 MB.');
      const raw=JSON.parse(await file.text());
      if(raw.version!==1)throw new Error('Unsupported workspace version.');
      const p=validateProject(raw.project);p.id=crypto.randomUUID();state.projects.push(p);state.active=p.id;save();renderPlanner();notify('Workspace restored as a new copy.');
    }catch(err){notify('Could not restore workspace: '+err.message);}
    e.target.value='';
  });
}
async function init() {
  try {
    const [stats,taxonomy]=await Promise.all([api('/api/stats'),api('/api/taxonomy')]);
    state.stats=stats;state.taxonomy=taxonomy.categories;
    $('nav-count').textContent=number(stats.total_letters);
    const years=stats.years.map(x=>x.year).sort((a,b)=>b-a);
    $('filter-year').innerHTML='<option value="">All years</option>'+years.map(y=>'<option>'+escapeHTML(y)+'</option>').join('');
    $('filter-category').innerHTML='<option value="">All areas</option>'+state.taxonomy.map(c=>'<option value="'+escapeHTML(c.id)+'">'+escapeHTML(c.label)+'</option>').join('');
    $('source-range').textContent=years.length?Math.min(...years)+'–'+Math.max(...years)+' · source records':'No letters ingested';
    $('source-date').textContent='FDA update '+(stats.source_updated || 'not available');
    $('data-provenance').innerHTML='<div class="provenance-list">Published letters: '+number(stats.total_letters)+'<br>Distinct applications: '+number(stats.total_applications)+'<br>FDA dataset updated: '+escapeHTML(stats.source_updated || 'Unknown')+'<br>Indexed: '+escapeHTML(stats.ingested_at || 'Not yet ingested')+'</div>';
    const initial=new URLSearchParams(location.search);
    for(const [key,value] of initial){const field=$('filters').elements.namedItem(key);if(field)field.value=value;}
    if(['date_desc','date_asc','company'].includes(initial.get('sort')))$('sort').value=initial.get('sort');
    readProjects();bind();$('loading').hidden=true;route();await refresh();
  } catch(err) {
    $('loading').hidden=true;
    error('The local archive is unavailable. Run python3 -m failure_mode.ingest, then restart the server and reload. '+err.message);
  }
}
init();
