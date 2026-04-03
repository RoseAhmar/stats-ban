content = open('C:/Users/topin/PycharmProjects/statsdoc/dashboard_preview.html', encoding='utf-8').read()

# 1. Переименовать вкладку + добавить сортировку
old1 = """    <button class="tab-btn active" onclick="switchTab('purchases')">Закупки</button>
    <button class="tab-btn" onclick="switchTab('buyers')">Баеры</button>"""
new1 = """    <button class="tab-btn active" onclick="switchTab('purchases')">Закупки</button>
    <button class="tab-btn" onclick="switchTab('buyers')">Баера</button>"""
content = content.replace(old1, new1, 1)

# 2. Добавить контролы сортировки баеров + убрать кол-во баеров, починить метрику
old2 = """  document.getElementById('buyers-metrics').innerHTML=`
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
    </div>`;"""

new2 = """  document.getElementById('buyers-metrics').innerHTML=`
    <div class="metric"><div class="metric-label">Аккаунтов выдано</div><div class="metric-value">${totAccounts.toLocaleString()}</div></div>
    <div class="metric">
      <div class="metric-label">Верификация</div>
      <div class="metric-value" style="color:${verCol(avgPct)}">${avgPct}%</div>
      <div class="metric-hint" style="margin-top:4px;">
        из <b>${totVna.toLocaleString()}</b> дошедших до верификации
        <div style="margin-top:4px;display:flex;justify-content:space-between;"><span>прошли</span><span style="font-weight:500;">${totPassed}</span></div>
        <div style="display:flex;justify-content:space-between;"><span>на замену</span><span style="font-weight:500;">${totFailed}</span></div>
        <div style="display:flex;justify-content:space-between;"><span>в очереди</span><span style="font-weight:500;">${totQueued}</span></div>
        <div style="display:flex;justify-content:space-between;color:#bbb;"><span>ещё не верифицированы</span><span style="font-weight:500;">${totAccounts-totVna-totQueued}</span></div>
      </div>
    </div>
    <div class="metric">
      <div class="metric-label">На замену</div>
      <div class="metric-value" style="color:#c02020">${totFailed}</div>
      <div class="metric-hint" style="margin-top:4px;">${totVna>0?Math.round(totFailed/totVna*100):0}% от дошедших до верификации</div>
    </div>`;"""
content = content.replace(old2, new2, 1)

# 3. Добавить сортировку перед карточками
old3 = """  document.getElementById('buyer-cards').innerHTML=data.map(b=>{"""
new3 = """  const bsort = document.getElementById('buyer-sort') ? document.getElementById('buyer-sort').value : 'total';
  const sortedData = [...data].sort((a,b)=>{
    if(bsort==='ver_desc') return b.success_pct - a.success_pct;
    if(bsort==='ver_asc') return a.success_pct - b.success_pct;
    if(bsort==='name') return a.buyer.localeCompare(b.buyer);
    return b.total - a.total; // default: по кол-ву
  });
  document.getElementById('buyer-cards').innerHTML=sortedData.map(b=>{"""
content = content.replace(old3, new3, 1)

# 4. Добавить контрол сортировки в HTML (перед buyer-cards div)
old4 = """    <div class="section-label" style="margin-top:1.5rem;">Карточки баеров</div>
    <div class="buyer-cards" id="buyer-cards"></div>"""
new4 = """    <div style="display:flex;justify-content:space-between;align-items:center;margin-top:1.5rem;margin-bottom:1rem;">
      <div class="section-label" style="margin:0;">Карточки баеров</div>
      <div style="display:flex;align-items:center;gap:8px;">
        <label style="font-size:13px;color:#888780;font-weight:500;">Сортировка:</label>
        <select id="buyer-sort" onchange="renderBuyers()" style="font-size:13px;font-family:Inter,sans-serif;padding:5px 10px;border:1px solid rgba(0,0,0,0.15);border-radius:8px;background:#f7f7f5;color:#1c1c1a;cursor:pointer;outline:none;">
          <option value="total">По кол-ву аккаунтов</option>
          <option value="ver_desc">Верификация ↓ (лучшие)</option>
          <option value="ver_asc">Верификация ↑ (худшие)</option>
          <option value="name">По имени</option>
        </select>
      </div>
    </div>
    <div class="buyer-cards" id="buyer-cards"></div>"""
content = content.replace(old4, new4, 1)

open('C:/Users/topin/PycharmProjects/statsdoc/dashboard_preview.html', 'w', encoding='utf-8').write(content)
print('OK')
