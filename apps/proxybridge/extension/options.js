const api=(type,enabled)=>new Promise(r=>chrome.runtime.sendMessage({
  type,enabled,pacUrl:document.querySelector('#pac').value
},r));
(async()=>{
  const r=await api('status',true);
  if(r.ok) document.querySelector('#pac').value=r.cfg.pacUrl;
})();
document.querySelector('#save').onclick=async()=>{
  const r=await api('set-pac',true);
  document.querySelector('#msg').textContent=r.ok?'ذخیره شد':'خطا: '+r.error;
};
