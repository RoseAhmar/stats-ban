content = open('C:/Users/topin/PycharmProjects/statsdoc/dashboard_preview.html', encoding='utf-8').read()

old = """const docRows=(b.by_doc||[]).map(d=>{
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
    }).join('');"""

new = """const docRows=(b.by_doc||[]).map(d=>{
      const dc=verCol(d.success_pct);
      const banEntries=Object.entries(d.bans||{});
      const banTip=banEntries.length?banEntries.map(([k,v])=>k+': '+v).join('\n'):'нет данных';
      const failedTag=d.failed>0?`<span class="stag stag-fail" style="cursor:default;position:relative;" title="${banTip}">замена: ${d.failed} ⓘ</span>`:'';
      return `<div class="buyer-doc-row">
        <span class="buyer-doc-name">${d.doc}</span>
        <span style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
          ${d.passed>0?`<span class="stag stag-pass">прошли: ${d.passed}</span>`:''}
          ${failedTag}
          ${d.queued>0?`<span class="stag stag-queue">очередь: ${d.queued}</span>`:''}
          ${d.vna>0?`<span style="font-weight:600;color:${dc};min-width:40px;text-align:right;">${d.success_pct}%</span>`:''}
        </span>
      </div>`;
    }).join('');
    const gmailRows=(b.by_gmail||[]).filter(g=>g.vna>0).slice(0,5).map(g=>{
      const gc=verCol(g.success_pct);
      const bar=g.vna>0?Math.round(g.passed/g.vna*100):0;
      return `<div class="buyer-doc-row">
        <span class="buyer-doc-name" style="font-weight:500;">${g.gmail}</span>
        <span style="display:flex;align-items:center;gap:8px;">
          <span style="font-size:11px;color:#aaa;">${g.vna} акк.</span>
          <span style="font-weight:600;color:${gc};">${g.success_pct}%</span>
        </span>
      </div>`;
    }).join('');"""

print('found:', old in content)
content = content.replace(old, new, 1)
open('C:/Users/topin/PycharmProjects/statsdoc/dashboard_preview.html', 'w', encoding='utf-8').write(content)
print('OK')
