function send(type, enabled){
  return new Promise(r => chrome.runtime.sendMessage({type, enabled}, r));
}
async function refresh(){
  const r = await send('status');
  document.querySelector('#state').textContent =
    r.ok ? ('Proxy: ' + (r.cfg.enabled ? 'ON' : 'OFF') + '\n' + r.cfg.pacUrl) : r.error;
}
document.querySelector('#on').onclick = async () => { await send('set-enabled', true); refresh(); };
document.querySelector('#off').onclick = async () => { await send('set-enabled', false); refresh(); };
document.querySelector('#options').onclick = () => chrome.runtime.openOptionsPage();
refresh();
