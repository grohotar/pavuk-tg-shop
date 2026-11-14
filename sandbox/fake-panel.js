// Fake Remnawave panel API (v3 shape) for the sandbox. No dependencies, Node 18+.
// State: panel_state.json next to this file (written by seed.py). Oформление: subpage_configs.json (copy of prod app-data.json).
//   local:   node sandbox/fake-panel.js                    -> 127.0.0.1:3999
//   hosting: APP_IP/APP_PORT from the hosting, PANEL_KEY required for every request
// Env: PANEL_KEY (Bearer for /api, ?key= for /frame), MINIAPP_URL (for /frame), APP_IP, APP_PORT
const http = require('http')
const fs = require('fs')
const path = require('path')
const crypto = require('crypto')

const DIR = __dirname
const STATE = path.join(DIR, 'panel_state.json')
const SUBPAGES = JSON.parse(fs.readFileSync(path.join(DIR, 'subpage_configs.json'), 'utf8'))
const SUBPAGE_FOR_USERS = 'c0ed1012-999a-484a-afab-a7b167c4b520'
const PUBLIC_SUB = 'https://sub.sandbox.invalid/sub'
const NODES = ['Финляндия', 'Нидерланды', 'Польша', 'Германия', 'Эстония', 'Турция', 'США', 'Казахстан']
const KEY = process.env.PANEL_KEY || ''
const PUBLIC_URL = (process.env.PUBLIC_URL || 'http://127.0.0.1:3999').replace(/\/$/, '')
const MINIAPP_URL = (process.env.MINIAPP_URL || 'http://127.0.0.1:3020').replace(/\/$/, '')

const load = () => (fs.existsSync(STATE) ? JSON.parse(fs.readFileSync(STATE, 'utf8')) : { users: [], devices: {} })
const save = (s) => fs.writeFileSync(STATE, JSON.stringify(s, null, 1))
const nowIso = () => new Date().toISOString()
const rid = (n) => crypto.randomBytes(n).toString('base64url').slice(0, 16)

function view(u0) {
    const u = { ...u0 }
    if (u.status === 'ACTIVE' && u.expireAt < nowIso()) u.status = 'EXPIRED'
    u.subscriptionUrl = `${PUBLIC_SUB}/${u.shortUuid}`
    u.activeInternalSquads = (u.activeInternalSquads || []).map((x) => (typeof x === 'string' ? { uuid: x, name: 'Default-Squad' } : x))
    u.vlessUuid ??= u.uuid
    u.userTraffic = { firstConnectedAt: u.createdAt, lastConnectedNodeUuid: null, ...(u.userTraffic || {}) }
    const defs = { externalSquadUuid: null, trojanPassword: 'sandbox', ssPassword: 'sandbox', lastTriggeredThreshold: 0,
        subRevokedAt: null, lastTrafficResetAt: null, email: null, description: null, tag: null, hwidDeviceLimit: 0,
        updatedAt: u.createdAt }
    for (const [k, v] of Object.entries(defs)) if (!(k in u)) u[k] = v
    return u
}

function human(b) {
    const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB']
    let i = 0
    while (b >= 1024 && i < units.length - 1) { b /= 1024; i++ }
    return i === 0 ? `${b} B` : `${b.toFixed(2)} ${units[i]}`
}

const find = (s, ref) => s.users.find((u) => String(u.id) === String(ref) || u.uuid === String(ref))
const byShort = (short) => load().users.find((u) => u.shortUuid === short)

// ---- browser preview: fake Telegram client around the real mini app (no app code changes) ----
const THEME = { bg_color: '#17212b', text_color: '#f5f5f5', button_color: '#5288c1', button_text_color: '#ffffff',
    secondary_bg_color: '#232e3c', hint_color: '#708499', link_color: '#6ab3f3', accent_text_color: '#6ab2f2',
    section_bg_color: '#17212b', header_bg_color: '#17212b', subtitle_text_color: '#708499',
    destructive_text_color: '#ec3942', section_header_text_color: '#6ab3f3' }

// Telegram WebApp initData signed like Telegram does; the mini app accepts the key 'sandbox-local'.
function initData(tgId, key = 'sandbox-local') {
    const f = { auth_date: String(Math.floor(Date.now() / 1000)),
        user: JSON.stringify({ id: tgId, first_name: 'Sandbox', language_code: 'ru' }), signature: '' }
    const secret = crypto.createHmac('sha256', 'WebAppData').update(key).digest()
    const dcs = Object.keys(f).sort().map((k) => `${k}=${f[k]}`).join('\n')
    f.hash = crypto.createHmac('sha256', secret).update(dcs).digest('hex')
    return new URLSearchParams(f).toString()
}

function frameHtml(tg, q) {
    const lp = new URLSearchParams({ tgWebAppData: initData(tg), tgWebAppVersion: '8.0', tgWebAppPlatform: 'tdesktop',
        tgWebAppThemeParams: JSON.stringify(THEME) })
    return `<!doctype html><meta charset=utf-8><title>Mini app ${tg}</title>
<style>body{margin:0;background:#0e1621;display:flex;justify-content:center;font:13px sans-serif;color:#8a9}
iframe{width:390px;height:780px;border:0;margin:12px;border-radius:18px;background:#17212b}
div{position:fixed;left:8px;top:8px}</style>
<div>user ${tg} &middot; <a style=color:#6ab3f3 href="/frame${q}">все пользователи</a></div>
<iframe id=f src="${MINIAPP_URL}/#${lp}"></iframe>
<script>
const f=document.getElementById('f'),theme=${JSON.stringify(THEME)},z={top:0,bottom:0,left:0,right:0};
const send=(t,d)=>f.contentWindow.postMessage(JSON.stringify({eventType:t,eventData:d}),'*');
addEventListener('message',e=>{let m;try{m=JSON.parse(e.data)}catch{return}
 const t=m.eventType,d=m.eventData||{};
 if(t==='web_app_request_theme')send('theme_changed',{theme_params:theme});
 else if(t==='web_app_request_viewport')send('viewport_changed',{height:f.clientHeight,width:f.clientWidth,is_expanded:true,is_state_stable:true});
 else if(t==='web_app_request_safe_area')send('safe_area_changed',z);
 else if(t==='web_app_request_content_safe_area')send('content_safe_area_changed',z);
 else if(t==='web_app_open_link')open(d.url);
 else if(t==='web_app_open_tg_link')open('https://t.me'+d.path_full);
 else console.log('tg event',t,d);});
</script>`
}

// ---- routes ----
const ok = (data, status = 200) => [status, { response: data }]
const notFound = () => [404, { message: 'User not found', errorCode: 'A062' }]

async function route(method, p, q, body) {
    let m
    const s = load()
    if (method === 'GET' && p === '/api/system/metadata') return ok({ version: '3.3.2' })
    if (method === 'GET' && p === '/api/users') {
        const start = +(q.get('start') || 0), size = +(q.get('size') || 100)
        return ok({ users: s.users.slice(start, start + size).map(view), total: s.users.length })
    }
    if (method === 'GET' && p === '/api/users/stream') {
        const tg = q.get('telegramId'), email = q.get('email')
        const res = s.users.filter((u) => (tg && String(u.telegramId) === tg) || (email && u.email === email)).map(view)
        return ok({ users: res.slice(0, +(q.get('size') || 50)), nextCursor: null, hasMore: false })
    }
    if (method === 'GET' && p === '/api/subscription-page-configs/')
        return ok({ total: Object.keys(SUBPAGES).length, configs: Object.keys(SUBPAGES).map((k, i) =>
            ({ uuid: k, viewPosition: i, name: k.startsWith('0000') ? 'Default' : `config${i}`, config: null })) })
    if (method === 'GET' && (m = p.match(/^\/api\/subscription-page-configs\/([^/]+)$/))) {
        if (!(m[1] in SUBPAGES)) return [404, { message: 'Not found' }]
        return ok({ uuid: m[1], viewPosition: Object.keys(SUBPAGES).indexOf(m[1]), name: m[1], config: SUBPAGES[m[1]] })
    }
    if (method === 'GET' && (m = p.match(/^\/api\/subscriptions\/subpage-config\/([^/]+)$/)))
        return byShort(m[1]) ? ok({ subpageConfigUuid: SUBPAGE_FOR_USERS, webpageAllowed: true }) : notFound()
    if (method === 'GET' && (m = p.match(/^\/api\/sub\/([^/]+)\/info$/))) {
        const raw = byShort(m[1])
        if (!raw) return notFound()
        const u = view(raw)
        const used = u.userTraffic.usedTrafficBytes || 0, life = u.userTraffic.lifetimeUsedTrafficBytes || 0, lim = u.trafficLimitBytes
        return ok({ isFound: true,
            user: { shortUuid: u.shortUuid, daysLeft: Math.max(0, Math.floor((new Date(u.expireAt) - Date.now()) / 864e5)),
                trafficUsed: human(used), trafficLimit: lim ? human(lim) : '0', lifetimeTrafficUsed: human(life),
                trafficUsedBytes: String(used), trafficLimitBytes: String(lim), lifetimeTrafficUsedBytes: String(life),
                username: u.username, expiresAt: u.expireAt, isActive: u.status === 'ACTIVE', userStatus: u.status,
                trafficLimitStrategy: u.trafficLimitStrategy },
            links: NODES.map((n, i) => `vless://${u.vlessUuid}@192.0.2.${i + 1}:443?security=reality&type=tcp#${encodeURIComponent(n)}`),
            ssConfLinks: {}, subscriptionUrl: u.subscriptionUrl })
    }
    if (method === 'GET' && (m = p.match(/^\/api\/users\/by-username\/([^/]+)$/))) {
        const u = s.users.find((x) => x.username === decodeURIComponent(m[1]))
        return u ? ok(view(u)) : notFound()
    }
    if (method === 'GET' && (m = p.match(/^\/api\/users\/([^/]+)$/))) {
        const u = find(s, m[1])
        return u ? ok(view(u)) : notFound()
    }
    if (method === 'POST' && p === '/api/users') {
        if (s.users.some((u) => u.username === body.username)) return [400, { message: 'Username already exists', errorCode: 'A019' }]
        const u = { id: Math.max(0, ...s.users.map((x) => x.id)) + 1, uuid: crypto.randomUUID(), shortUuid: rid(12),
            createdAt: nowIso(), userTraffic: { usedTrafficBytes: 0, lifetimeUsedTrafficBytes: 0, onlineAt: null },
            activeInternalSquads: [], ...body }
        s.users.push(u); save(s)
        return ok(view(u), 201)
    }
    if (method === 'PATCH' && p === '/api/users') {
        const ref = body.id ?? body.uuid
        delete body.id; delete body.uuid
        const u = find(s, ref)
        if (!u) return notFound()
        Object.assign(u, body); save(s)
        return ok(view(u))
    }
    if (method === 'POST' && (m = p.match(/^\/api\/users\/([^/]+)\/actions\/([^/]+)$/))) {
        const u = find(s, m[1])
        if (!u) return notFound()
        if (m[2] === 'enable' || m[2] === 'disable') u.status = m[2] === 'enable' ? 'ACTIVE' : 'DISABLED'
        else if (m[2] === 'revoke') u.shortUuid = rid(12)
        save(s)
        return ok(view(u))
    }
    if (method === 'DELETE' && (m = p.match(/^\/api\/users\/([^/]+)$/))) {
        const u = find(s, m[1])
        if (!u) return notFound()
        s.users.splice(s.users.indexOf(u), 1); save(s)
        return ok({ isDeleted: true })
    }
    if (method === 'GET' && (m = p.match(/^\/api\/hwid\/devices\/([^/]+)$/))) {
        const d = s.devices[m[1]] || []
        return ok({ total: d.length, devices: d })
    }
    if (method === 'POST' && p === '/api/hwid/devices/delete') {
        const ref = String(body.userId ?? body.userUuid)
        const d = (s.devices[ref] || []).filter((x) => x.hwid !== body.hwid)
        s.devices[ref] = d; save(s)
        return ok({ total: d.length, devices: d })
    }
    if (method === 'GET' && p === '/api/system/stats') {
        const us = s.users.map(view)
        const counts = Object.fromEntries(['ACTIVE', 'DISABLED', 'EXPIRED', 'LIMITED'].map((k) => [k, us.filter((u) => u.status === k).length]))
        return ok({ users: { totalUsers: us.length, statusCounts: counts },
            onlineStats: { onlineNow: Math.floor(counts.ACTIVE / 3), lastDay: counts.ACTIVE, lastWeek: us.length },
            memory: { total: 4 * 2 ** 30, used: Math.floor(2.3 * 2 ** 30) }, nodes: { totalOnline: NODES.length } })
    }
    if (method === 'GET' && p === '/api/system/stats/bandwidth')
        return ok({ bandwidthLastSevenDays: { current: '1.84 TiB' }, bandwidthLast30Days: { current: '7.31 TiB' } })
    if (method === 'GET' && p === '/api/system/stats/nodes')
        return ok({ lastSevenDays: NODES.map((n) => ({ nodeName: n, totalBytes: 0 })) })
    return [404, { message: 'Cannot ' + method + ' ' + p }]
}

const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, 'http://x')
    const p = url.pathname
    try {
        if (p.startsWith('/frame')) {
            if (KEY && url.searchParams.get('key') !== KEY) { res.writeHead(403); return res.end('forbidden') }
            const q = KEY ? `?key=${encodeURIComponent(KEY)}` : ''
            let html
            const m = p.match(/^\/frame\/(\d+)$/)
            if (m) html = frameHtml(+m[1], q)
            else html = `<meta charset=utf-8><body style='background:#0e1621;color:#ccc;font:14px sans-serif'><h3>Открыть мини-апп как пользователь</h3><ul>` +
                load().users.map((u) => `<li><a style=color:#6ab3f3 href="/frame/${u.telegramId}${q}">${u.telegramId}</a> ${view(u).status} до ${u.expireAt.slice(0, 10)}</li>`).join('') + '</ul>'
            res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' })
            return res.end(html)
        }
        // ---- fake Platega (PLATEGA_API_BASE_URL points here) ----
        if (p.startsWith('/transaction/') || p.startsWith('/subscription/') || p === '/sandbox/platega-events') {
            if (KEY && req.headers['x-secret'] !== KEY) { res.writeHead(401); return res.end('{}') }
            let raw = ''
            for await (const c of req) raw += c
            const [st, out] = plategaApi(req.method, p, raw ? JSON.parse(raw) : {})
            res.writeHead(st, { 'Content-Type': 'application/json' })
            return res.end(JSON.stringify(out))
        }
        if (p.startsWith('/pay/') || p === '/platega') {
            let raw = ''
            for await (const c of req) raw += c
            const form = Object.fromEntries(new URLSearchParams(raw))
            if (p === '/platega' && KEY && url.searchParams.get('key') !== KEY) { res.writeHead(403); return res.end('forbidden') }
            res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' })
            return res.end(plategaPage(req.method, p, form, url))
        }
        if (p.startsWith('/sub/')) { res.writeHead(200, { 'Content-Type': 'text/plain' }); return res.end('sandbox: fake subscription, no real servers here\n') }
        if (KEY && req.headers.authorization !== `Bearer ${KEY}`) {
            res.writeHead(401, { 'Content-Type': 'application/json' })
            return res.end(JSON.stringify({ message: 'Unauthorized' }))
        }
        let raw = ''
        for await (const c of req) raw += c
        const [status, data] = await route(req.method, p, url.searchParams, raw ? JSON.parse(raw) : {})
        res.writeHead(status, { 'Content-Type': 'application/json' })
        res.end(JSON.stringify(data))
    } catch (e) {
        console.error(req.method, p, e)
        res.writeHead(500, { 'Content-Type': 'application/json' })
        res.end(JSON.stringify({ message: String(e) }))
    }
})

// ---------- fake Platega: payments, autopay subscriptions, callbacks queue ----------
// Callbacks go to a queue; the sandbox bot (polling mode) pulls GET /sandbox/platega-events every 2 s
// and feeds them to PlategaService.process_callback, the same code the prod webhook runs.
const PG = { tx: {}, subs: {}, events: [] }
const addMonths = (d, m) => { const x = new Date(d); x.setUTCMonth(x.getUTCMonth() + m); return x.toISOString() }
function pgEvent(e) { PG.events.push(Object.fromEntries(Object.entries(e).filter(([, v]) => v !== undefined))) }
function pgCharge(sub, ok) {
    const id = crypto.randomUUID()
    if (ok) {
        sub.nextChargeAt = addMonths(sub.nextChargeAt || nowIso(), sub.months)
        pgEvent({ id, amount: sub.amount, currency: 'RUB', status: 'CONFIRMED', paymentMethod: 6, payload: sub.payload,
            subscriptionId: sub.id, nextChargeAt: sub.nextChargeAt })
    } else {
        sub.status = 'PastDue'
        pgEvent({ id, amount: sub.amount, currency: 'RUB', status: 'CANCELED', paymentMethod: 6, payload: sub.payload, subscriptionId: sub.id })
        pgEvent({ id: sub.id, amount: sub.amount, currency: 'RUB', status: 'SUBSCRIPTION_PAST_DUE', payload: sub.payload, subscriptionId: sub.id })
    }
}
function plategaApi(method, p, body) {
    if (p === '/sandbox/platega-events') { const e = PG.events; PG.events = []; return [200, e] }
    if (method === 'POST' && p === '/transaction/process') {
        const id = crypto.randomUUID(), d = body.paymentDetails || {}
        if (body.paymentMethod === 6) {
            PG.subs[id] = { id, amount: +d.amount, months: +d.intervalCount || 1, status: 'PendingAgreement', payload: body.payload || '',
                description: body.description || 'Пополнение', nextChargeAt: null }
            return [200, { paymentMethod: 'Subscription', transactionId: id, redirect: `${PUBLIC_URL}/pay/sub/${id}`, status: 'PENDING' }]
        }
        PG.tx[id] = { id, amount: +d.amount, method: body.paymentMethod, payload: body.payload || '', status: 'PENDING' }
        return [200, { transactionId: id, status: 'PENDING', redirect: `${PUBLIC_URL}/pay/${id}`, expiresIn: '00:15:00' }]
    }
    let m = p.match(/^\/transaction\/([\w-]+)$/)
    if (m) return PG.tx[m[1]] ? [200, { id: m[1], status: PG.tx[m[1]].status, payload: PG.tx[m[1]].payload }] : [404, { message: 'Transaction not found.' }]
    m = p.match(/^\/subscription\/([\w-]+)\/cancel$/)
    if (m && method === 'POST') {
        const sub = PG.subs[m[1]]
        if (!sub) return [404, { message: 'not found' }]
        if (sub.status !== 'Cancelled') {
            sub.status = 'Cancelled'
            pgEvent({ id: sub.id, amount: sub.amount, currency: 'RUB', status: 'SUBSCRIPTION_CANCELLED', payload: sub.payload, subscriptionId: sub.id })
        }
        return [200, { subscriptionId: sub.id, status: 'cancelled' }]
    }
    m = p.match(/^\/subscription\/([\w-]+)$/)
    if (m) return PG.subs[m[1]] ? [200, PG.subs[m[1]]] : [404, { message: 'not found' }]
    return [404, { message: 'unknown' }]
}
const PAGE = (body) => `<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">` +
    `<body style="font:16px -apple-system,sans-serif;max-width:440px;margin:24px auto;padding:0 16px;color:#222">` +
    `<p style="color:#b00;font-size:13px">Песочница: это имитация Platega, деньги не списываются.</p>${body}</body>`
const BTN = (label, name, color = '#2f6fed') =>
    `<button name=act value=${name} style="display:block;width:100%;padding:14px;margin:8px 0;border:0;border-radius:10px;background:${color};color:#fff;font-size:16px">${label}</button>`
const DONE = PAGE('<h3>Готово</h3><p>Вернитесь в Telegram — бот пришлёт сообщение через пару секунд.</p>')
function plategaPage(method, p, form, url) {
    let m = p.match(/^\/pay\/sub\/([\w-]+)$/)
    if (m) {
        const sub = PG.subs[m[1]]
        if (!sub) return PAGE('<h3>Подписка не найдена</h3><p>Песочница перезапускалась — оформите заново в боте.</p>')
        if (method === 'POST' && sub.status === 'PendingAgreement') {
            sub.status = 'Active'
            pgEvent({ id: sub.id, amount: sub.amount, currency: 'RUB', status: 'SUBSCRIPTION_ACTIVATED', payload: sub.payload,
                subscriptionId: sub.id, nextChargeAt: addMonths(nowIso(), sub.months) })
            pgCharge(sub, true)
            return DONE
        }
        if (sub.status !== 'PendingAgreement') return PAGE('<h3>Подписка уже оформлена</h3>')
        const every = sub.months === 1 ? 'раз в месяц' : `раз в ${sub.months} мес.`
        return PAGE(`<h3>Оформить подписку</h3><p style="color:#666">Мерчант: Pipun VPN · ${sub.description}</p>` +
            `<p><b>${sub.amount} ₽</b> ${every}, автоматическое продление</p><form method=post>` +
            `<input name=email type=email required placeholder="Email *" style="width:100%;padding:12px;font-size:16px;box-sizing:border-box">` +
            `<label style="display:block;margin:12px 0"><input type=checkbox required> Соглашаюсь на автоматические списания ${sub.amount} ₽ ${every}.</label>` +
            BTN('Оформить подписку', 'ok') + '</form>')
    }
    m = p.match(/^\/pay\/([\w-]+)$/)
    if (m) {
        const tx = PG.tx[m[1]]
        if (!tx) return PAGE('<h3>Платёж не найден</h3><p>Песочница перезапускалась — создайте платёж заново в боте.</p>')
        if (method === 'POST' && tx.status === 'PENDING') {
            tx.status = form.act === 'ok' ? 'CONFIRMED' : 'CANCELED'
            pgEvent({ id: tx.id, amount: tx.amount, currency: 'RUB', status: tx.status, paymentMethod: tx.method, payload: tx.payload })
            return DONE
        }
        if (tx.status !== 'PENDING') return PAGE(`<h3>Платёж уже ${tx.status === 'CONFIRMED' ? 'оплачен' : 'отменён'}</h3>`)
        return PAGE(`<h3>Оплата ${tx.amount} ₽</h3><p>${tx.method === 11 ? 'Карта МИР' : 'СБП (QR-код)'}</p><form method=post>` +
            BTN(`Оплатить ${tx.amount} ₽`, 'ok') + BTN('Отказаться', 'no', '#888') + '</form>')
    }
    // /platega?key=… : sandbox control page for autopay subscriptions
    const sub = PG.subs[form.id]
    if (method === 'POST' && sub) {
        if (form.act === 'charge' && sub.status !== 'Cancelled') { sub.status = 'Active'; pgCharge(sub, true) }
        if (form.act === 'fail' && sub.status !== 'Cancelled') pgCharge(sub, false)
        if (form.act === 'cancel' && sub.status !== 'Cancelled') {
            sub.status = 'Cancelled'
            pgEvent({ id: sub.id, amount: sub.amount, currency: 'RUB', status: 'SUBSCRIPTION_CANCELLED', payload: sub.payload, subscriptionId: sub.id })
        }
    }
    const rows = Object.values(PG.subs).reverse().map((s) => `<div style="border:1px solid #ddd;border-radius:10px;padding:12px;margin:12px 0">` +
        `<b>${s.amount} ₽ / ${s.months} мес.</b> · ${s.status}<br><small>${s.payload}<br>следующее списание: ${s.nextChargeAt || '—'}</small>` +
        (s.status === 'Cancelled' || s.status === 'PendingAgreement' ? '' : `<form method=post><input type=hidden name=id value=${s.id}>` +
            BTN('Следующее списание (успешно)', 'charge') + BTN('Списание не прошло', 'fail', '#c77700') + BTN('Клиент отменил в банке', 'cancel', '#b00') + '</form>') +
        '</div>').join('')
    return PAGE(`<h3>Автопродления (Platega)</h3>${rows || '<p>Пока нет. Оформите в боте: Купить → срок → СБП с автопродлением.</p>'}`)
}

function start() {
    const port = +(process.env.APP_PORT || 3999), host = process.env.APP_IP || '127.0.0.1'
    server.listen(port, host, () => console.log(`fake panel on ${host}:${port}${KEY ? ' (key required)' : ''}`))
    process.on('SIGTERM', () => server.close(() => process.exit(0)))
}
if (require.main === module) start()
module.exports = { initData, view, start }
