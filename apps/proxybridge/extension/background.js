const DEFAULT_PAC = 'http://127.0.0.1:8787/proxy.pac';

async function getConfig() {
  const v = await chrome.storage.local.get({pacUrl: DEFAULT_PAC, enabled: true});
  return v;
}

async function apply(enabled) {
  const {pacUrl} = await getConfig();
  const value = enabled
    ? {mode: 'pac_script', pacScript: {url: pacUrl}}
    : {mode: 'system'};
  await chrome.proxy.settings.set({value, scope: 'regular'});
  await chrome.storage.local.set({enabled});
}

chrome.runtime.onInstalled.addListener(async () => {
  await apply(false);
});

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  (async () => {
    try {
      if (msg.type === 'set-pac') {
        await chrome.storage.local.set({pacUrl: msg.pacUrl});
        await apply(Boolean(msg.enabled));
      }
      if (msg.type === 'set-enabled') {
        await apply(Boolean(msg.enabled));
      }
      const cfg = await getConfig();
      const current = await chrome.proxy.settings.get({incognito: false});
      sendResponse({ok: true, cfg, current});
    } catch (e) {
      sendResponse({ok: false, error: String(e)});
    }
  })();
  return true;
});
