content = open('C:/Users/topin/PycharmProjects/statsdoc/dashboard_preview.html', encoding='utf-8').read()

old = """      ${docRows?`<div class="divider"></div>${docRows}`:''}
    </div>`"""

new = """      ${docRows?`<div class="divider"></div>${docRows}`:''}
      ${gmailRows?`
        <div style="margin-top:10px;">
          <div style="font-size:11px;font-weight:600;color:#aaa;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px;">Лучшие почты для заказа</div>
          ${gmailRows}
        </div>`:''}
    </div>`"""

print('found:', old in content)
content = content.replace(old, new, 1)
open('C:/Users/topin/PycharmProjects/statsdoc/dashboard_preview.html', 'w', encoding='utf-8').write(content)
print('OK')
