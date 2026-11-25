import fs from "node:fs/promises";
const LOG = process.argv[2] + "\\clear-capture.log";
// 完場瞬間把畫面上所有可見按鈕/面板抓下來，找「獎勵格子」真正的 id。
const probe = '(function(){var C=window.__CHEAT;if(!C)return "無";'
  + 'var els=[].slice.call(document.querySelectorAll("button,div[onclick],a")).filter(function(e){return e.offsetParent!==null});'
  + 'var t=els.map(function(e){return (e.id||e.getAttribute("onclick")||"").slice(0,26)+":"+(e.textContent||"").replace(/\s+/g,"").slice(0,14)}).filter(function(x){return x.length>2});'
  + 'var pn=[].slice.call(document.querySelectorAll("div")).filter(function(d){return d.offsetParent!==null&&/獎勵|領取|結算|通關/.test(d.textContent||"")&&d.children.length<=6});'
  + 'return JSON.stringify({w:C.dbg.who().slice(2),phase:C.farm.phase,done:C.farm.done,pick:C.lastPick,'
  + 't:(document.getElementById("timeT")||{}).textContent||"",btns:t.slice(0,26),pn:pn.slice(0,3).map(function(d){return (d.id||"")+"|"+(d.textContent||"").replace(/\s+/g,"").slice(0,50)})})})()';
async function evalp(id) {
  return new Promise((res) => {
    const ws = new WebSocket("ws://127.0.0.1:9222/devtools/page/" + id);
    const t = setTimeout(() => { try { ws.close(); } catch (e) {} res("timeout"); }, 12000);
    ws.onopen = () => ws.send(JSON.stringify({ id: 1, method: "Runtime.evaluate", params: { expression: probe, returnByValue: true } }));
    ws.onmessage = (m) => { const x = JSON.parse(m.data); if (x.id === 1) { clearTimeout(t); try { ws.close(); } catch (e) {} res(x.exceptionDetails ? "EXC" : String(x.result?.result?.value)); } };
    ws.onerror = () => { clearTimeout(t); res("wserr"); };
  });
}
const prevPhase = {}, until = {};
const END = Date.now() + 25 * 60 * 1000;
while (Date.now() < END) {
  try {
    const list = await (await fetch("http://127.0.0.1:9222/json/list")).json();
    for (const p of list.filter((t) => t.type === "page" && t.url.includes("l1stw.com"))) {
      const s = await evalp(p.id);
      let o; try { o = JSON.parse(s); } catch (e) { continue; }
      const now = Date.now();
      if (prevPhase[o.w] && prevPhase[o.w] !== o.phase && /settle|finish|dead/.test(o.phase)) until[o.w] = now + 22000;
      prevPhase[o.w] = o.phase;
      if (until[o.w] && now < until[o.w]) {
        const line = new Date().toISOString().slice(11, 19) + "." + String(now % 1000).padStart(3, "0") + " " + o.w + " " + o.phase + " done=" + o.done + " t=" + o.t + " | " + o.pick + "\n  pn=" + JSON.stringify(o.pn) + "\n  btns=" + o.btns.join(" / ") + "\n";
        await fs.appendFile(LOG, line);
      }
    }
  } catch (e) { await fs.appendFile(LOG, "ERR " + e.message + "\n"); }
  await new Promise((r) => setTimeout(r, 400));
}
await fs.appendFile(LOG, "=== 擷取結束\n");
