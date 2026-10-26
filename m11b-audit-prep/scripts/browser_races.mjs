// Pass an actual candidate route matcher; no proposed /jobs schema is assumed.
// before: the server has NOT seen the request. after: it may already have acted.
export async function holdOnce(page, matcher, phase='before', timeoutMs=15000) {
  if (!['before','after'].includes(phase)) throw Error('unknown gate phase');
  let release, entered;
  const ready=new Promise(resolve => {entered=resolve});
  const latch=new Promise(resolve => {release=resolve});
  let used=false;
  const handler=async route => {
    if (used) return route.continue();
    used=true;
    const response=phase==='after' ? await route.fetch() : null;
    entered({method:route.request().method(), body:route.request().postData(), phase});
    let timer;
    try {
      await Promise.race([latch,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('audit barrier timeout')),timeoutMs)})]);
      if(response) await route.fulfill({response}); else await route.continue();
    } catch (error) { await route.abort(); throw error; } finally {clearTimeout(timer)}
  };
  await page.route(matcher,handler);
  return {ready, release, dispose:async()=>{release();await page.unroute(matcher,handler)}};
}
