content = open('C:/Users/topin/PycharmProjects/statsdoc/dashboard_v5_4.html', encoding='utf-8').read()

old = 'render();\n</script>'

buyers_js = r"""render();

// BUYERS
function verCol(p){return p>=80?'#3a7d15':p>=60?'#9a5c08':'#c02020';}

function renderBuyers(){
  const data=BUYERS_DATA;
  if(!data||data.length===0){
    document.getElementById('buyer-cards').innerHTML='<div class="empty-state">Нет данных — запустите скрипт обновления</div>';
    return;
  }
  const totAccounts=data.reduce((s,b)=>s+b.total,0);
  const totPassed=data.reduce((s,b)=>s+b.passed,0);
  const totFailed=data.reduce((s,b)=>s+b.failed,0);
  const totQueued=data.reduce((s,b)=>s+b.queued,0);
  const totVna=data.reduce((s,b)=>s+b.vna,0);
  const avgPct=totVna>0?Math.round(totPassed/totVna*100):0;

  document.getElementById('buyers-metrics').innerHTML=`
    <div class="metric"><div class="metric-label">Баеров</div><div class="metric-value">${data.length}</div></div>
    <div class="metric"><div class="metric-label">Аккаунтов выдано</div><div class="metric-value">${totAccounts.toLocaleString()}</div></div>
    <div class="metric">
      <div class="metric-label">Прошли верификацию</div>
      <div class="metric-value" style="color:${verCol(avgPct)}">${avgPct}%</div>
      <div class="metric-hint" style="margin-top:4px;">
        <div style="display:flex;justify-content:space-between;"><span>прошли</span><span style="font-weight:500;">${totPassed}</span></div>
        <div style="display:flex;justify-content:space-between;"><span>на замену</span><span style="font-weight:500;">${totFailed}</span></div>
        <div style="display:flex;justify-content:space-between;"><span>в очереди</span><span style="font-weight:500;">${totQueued}</span></div>
      </div>
    </div>
    <div class="metric">
      <div class="metric-label">На замену</div>
      <div class="metric-value" style="color:#c02020">${totFailed}</div>
      <div class="metric-hint" style="margin-top:4px;">${totVna>0?Math.round(totFailed/totVna*100):0}% от верифицированных</div>
    </div>`;

  document.getElementById('buyer-cards').innerHTML=data.map(b=>{
    const t=b.total;
    const pPass=t>0?Math.round(b.passed/t*100):0;
    const pFail=t>0?Math.round(b.failed/t*100):0;
    const pQueue=t>0?Math.round(b.queued/t*100):0;
    const pOther=t>0?Math.round((b.others+b.no_status)/t*100):0;
    const clr=verCol(b.success_pct);
    const docRows=(b.by_doc||[]).map(d=>{
      const dc=verCol(d.success_pct);
      return `<div class="buyer-doc-row">
        <span class="buyer-doc-name">${d.doc}</span>
        <span style="display:flex;align-items:center;gap:8px;">
          ${d.passed>0?`<span class="stag stag-pass">прошли: ${d.passed}</span>`:''}
          ${d.failed>0?`<span class="stag stag-fail">замена: ${d.failed}</span>`:''}
          ${d.queued>0?`<span class="stag stag-queue">очередь: ${d.queued}</span>`:''}
          ${d.vna>0?`<span style="font-weight:600;color:${dc};min-width:40px;text-align:right;">${d.success_pct}%</span>`:''}
        </span>
      </div>`;
    }).join('');
    return `<div class="buyer-card">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:4px;">
        <div class="buyer-name">${b.buyer}</div>
        <span class="buyer-pct" style="color:${clr}">${b.success_pct}%</span>
      </div>
      <div class="buyer-total">${t} аккаунтов выдано</div>
      <div class="buyer-stack">
        <div style="width:${pPass}%;background:#3a7d15;"></div>
        <div style="width:${pFail}%;background:#c02020;"></div>
        <div style="width:${pQueue}%;background:#185FA5;"></div>
        <div style="width:${pOther}%;background:#534AB7;"></div>
      </div>
      <div class="buyer-tags">
        ${b.passed>0?`<span class="stag stag-pass">прошли: ${b.passed}</span>`:''}
        ${b.failed>0?`<span class="stag stag-fail">на замену: ${b.failed}</span>`:''}
        ${b.queued>0?`<span class="stag stag-queue">в очереди: ${b.queued}</span>`:''}
        ${b.others>0?`<span class="stag stag-other">прочие: ${b.others}</span>`:''}
      </div>
      ${docRows?`<div class="divider"></div>${docRows}`:''}
    </div>`;
  }).join('');
}

// TABS
function switchTab(name){
  document.querySelectorAll('.tab-btn').forEach((b,i)=>{
    b.classList.toggle('active',['purchases','buyers'][i]===name);
  });
  document.getElementById('tab-purchases').classList.toggle('active',name==='purchases');
  document.getElementById('tab-buyers').classList.toggle('active',name==='buyers');
  if(name==='buyers') renderBuyers();
}

renderBuyers();
</script>"""

print('found:', old in content)
content = content.replace(old, buyers_js, 1)
open('C:/Users/topin/PycharmProjects/statsdoc/dashboard_v5_4.html', 'w', encoding='utf-8').write(content)
print('OK, len:', len(content))
