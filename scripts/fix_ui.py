
f = 'backend/static/index.html'
with open(f, 'rb') as fh:
    data = fh.read()

# 1. Replace alerts function header - add test button
old_alerts_bytes = (
    b'function alerts(){return `<div class="page-head"><div><div class="eyebrow">ALERTS \xc2\xb7 MONITORING</div>'
    b'<h1>\xd9\x85\xd8\xb1\xda\xa9\xd8\xb2 \xd9\x87\xd8\xb4\xd8\xaf\xd8\xa7\xd8\xb1\xd9\x87\xd8\xa7</h1>'
    b'<div class="page-desc">\xd9\x87\xd8\xb4\xd8\xaf\xd8\xa7\xd8\xb1\xd9\x87\xd8\xa7\xdb\x8c \xd9\x81\xd8\xb9\xd8\xa7\xd9\x84\xd8\x8c \xd9\x82\xd9\x88\xd8\xa7\xd8\xb9\xd8\xaf \xd9\x88 \xd9\x88\xd8\xb6\xd8\xb9\xdb\x8c\xd8\xaa \xd8\xaa\xd8\xa3\xdb\x8c\xdb\x8c\xd8\xaf.</div>'
    b'</div><div class="head-actions"><button class="btn ghost" data-action="refresh">\xe2\x9f\xb3 \xd8\xaa\xd8\xa7\xd8\xb2\xd9\x87\xe2\x80\x8c\xd8\xb3\xd8\xa7\xd8\xb2\xdb\x8c</button>'
    b'</div></div><div id="alertsLive"></div>`}'
)
new_alerts_bytes = (
    b'function alerts(){return `<div class="page-head"><div><div class="eyebrow">ALERTS \xc2\xb7 MONITORING</div>'
    b'<h1>\xd9\x85\xd8\xb1\xda\xa9\xd8\xb2 \xd9\x87\xd8\xb4\xd8\xaf\xd8\xa7\xd8\xb1\xd9\x87\xd8\xa7</h1>'
    b'<div class="page-desc">\xd9\x87\xd8\xb4\xd8\xaf\xd8\xa7\xd8\xb1\xd9\x87\xd8\xa7\xdb\x8c \xd9\x81\xd8\xb9\xd8\xa7\xd9\x84\xd8\x8c \xd9\x82\xd9\x88\xd8\xa7\xd8\xb9\xd8\xaf \xd9\x88 \xd9\x88\xd8\xb6\xd8\xb9\xdb\x8c\xd8\xaa \xd8\xaa\xd8\xa3\xdb\x8c\xdb\x8c\xd8\xaf.</div>'
    b'</div><div class="head-actions">'
    b'<button class="btn primary" type="button" onclick="sendTestAlert(\'telegram\')">&#x2709; Test Telegram</button>'
    b'<button class="btn ghost" data-action="refresh">\xe2\x9f\xb3 \xd8\xaa\xd8\xa7\xd8\xb2\xd9\x87\xe2\x80\x8c\xd8\xb3\xd8\xa7\xd8\xb2\xdb\x8c</button>'
    b'</div></div><div id="alertsLive"></div>`}'
)

if old_alerts_bytes in data:
    data = data.replace(old_alerts_bytes, new_alerts_bytes, 1)
    print('OK: alerts header updated (test button added)')
else:
    print('WARN: old alerts header not found')
    idx = data.find(b'function alerts(){return')
    if idx >= 0:
        print(repr(data[idx:idx+250]))

# 2. Add sendTestAlert function BEFORE loadAlerts
send_test_fn = (
    b"async function sendTestAlert(channel){"
    b"const btn=document.querySelector('button[onclick*=sendTestAlert]');"
    b"const orig=btn?btn.textContent:'';"
    b"if(btn)btn.disabled=true;"
    b"const out=document.getElementById('alertsLive');"
    b"if(out)out.innerHTML='<p class=muted>Sending test alert...</p>';"
    b"try{"
    b"const r=await api('POST','/api/alerts/test-deliver/'+channel,{timeout:30000});"
    b"const ok=r.status==='sent'||(r.dry_run===false&&r.attempts>=1);"
    b"const icon=ok?'&#x2705;':'&#x274c';"
    b"const cls=ok?'alert-success':'alert-error';"
    b"const detail='Channel='+r.channel+' | Status='+r.status+' | Attempts='+r.attempts+(r.last_error?' | Error='+r.last_error:'');"
    b"if(out)out.innerHTML='<div class=alert-strip style=margin-bottom:10px;padding:8px 12px;border-radius:8px class='+cls+'>'"
    b"+icon+' <b>'+(r.dry_run?'Dry Run':'Sent')+'</b>: '+detail+'</div>';"
    b"await new Promise(res=>setTimeout(res,2000));"
    b"loadAlerts();"
    b"}catch(e){"
    b"const msg=(e&&e.message)||'Unknown';"
    b"if(out)out.innerHTML='<p class=muted style=color:#ff657f>Error: '+msg+'</p>';"
    b"}finally{"
    b"if(btn){btn.disabled=false;btn.textContent=orig;}"
    b"}"
    b"}"
)

old_load_alerts = b'async function loadAlerts(){'
if old_load_alerts in data:
    data = data.replace(old_load_alerts, send_test_fn + old_load_alerts, 1)
    print('OK: sendTestAlert function added')
else:
    print('WARN: loadAlerts not found')

# 3. Add alerts/messaging section in loadSettings after app settings form
old_settings_save = b"const save=document.getElementById('settingsSave');"
alerts_section = (
    b"\n   // Alert channel status section\n"
    b"html += '<section class=\"panel\" style=\"margin-bottom:10px\"><div class=\"panel-pad\"><div class=\"panel-head\"><div><div class=\"panel-title\">Alert Channels</div><div class=\"panel-sub\">Telegram & Email delivery status</div></div></div><div class=\"table-wrap\"><table><thead><tr><th>Channel</th><th>Active</th><th>Status</th><th>Test</th></tr></thead><tbody>';"
    b"html += '<tr><td>Telegram</td><td id=\"gi-tg-active\"><span class=\"s-muted\">-</span></td><td><span class=\"s-muted\">check env</span></td><td><button class=\"btn small\" onclick=\"sendTestAlert(\\'telegram\\')\">Test</button></td></tr>';"
    b"html += '<tr><td>Email (SMTP)</td><td id=\"gi-email-active\"><span class=\"s-muted\">-</span></td><td><span class=\"s-muted\">check env</span></td><td><button class=\"btn small\" onclick=\"sendTestAlert(\\'email\\')\">Test</button></td></tr>';"
    b"html += '</tbody></table></div><div style=font-size:10px;color:#54779d;margin-top:8px>Active status is read from env vars. Telegram requires TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID. Email requires SMTP_HOST + SMTP_TO.</div></div></section>';\n"
)

if old_settings_save in data:
    data = data.replace(old_settings_save, alerts_section + old_settings_save, 1)
    print('OK: alerts section added to Settings')
else:
    print('WARN: settingsSave element not found')

with open(f, 'wb') as fh:
    fh.write(data)
print('done')