/* FINDZIA_BILLING_RELEASE=156.7.39 */
/* Findzia 156.7.20 — resumable checkout, safe plan changes and persistent payment UI. */
(() => {
  'use strict';
  const searches = new Set(['/api/search','/api/search/stream','/api/search/image','/api/search/image/stream',
    '/api/search/more','/api/search/more/stream','/api/search/markets/stream','/api/refine/search/stream']);
  const uid = () => crypto.randomUUID().replace(/-/g,'');
  function abortable(work, signal) {
    if (!signal) return Promise.resolve(work);
    return new Promise((resolve,reject)=>{
      const abort=()=>reject(new DOMException('Aborted','AbortError'));
      if(signal.aborted){Promise.resolve(work).catch(()=>{});abort();return;}
      signal.addEventListener('abort',abort,{once:true});
      Promise.resolve(work).then(resolve,reject).finally(()=>signal.removeEventListener('abort',abort));
    });
  }
  const el = (tag, cls, text) => {const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};
  async function waitFor(root) {
    for(let i=0;i<80;i++){if(root.fzBilling)return root.fzBilling;await new Promise(r=>setTimeout(r,50));}
    throw Error('credits_unavailable');
  }
  window.FindziaBillingFetch = async (root, url, options) => (await abortable(waitFor(root),options?.signal)).fetch(url,options);
  window.FindziaBeforeSearch = async (root, payload) => {
    const ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),20000);
    try{return await abortable((async()=>(await waitFor(root)).beforeSearch(payload))(),ctl.signal);}
    catch(_){root.fzRefineBridge?.accountNotice(root.dataset.lang==='ar'?'تعذّر التحقق من الرصيد. حاول مجددًا.':'Could not check your credits. Please try again.');return false;}
    finally{clearTimeout(timer);}
  };
  function pendingStore(action, value) {
    return new Promise((resolve,reject)=>{
      const req=indexedDB.open('findzia-pending-search',1);
      req.onupgradeneeded=()=>req.result.createObjectStore('pending');
      req.onerror=()=>reject(req.error);
      req.onsuccess=()=>{const db=req.result,tx=db.transaction('pending','readwrite'),store=tx.objectStore('pending');
        const op=action==='set'?store.put(value,'search'):action==='get'?store.get('search'):store.delete('search');
        let result;op.onsuccess=()=>result=op.result;tx.oncomplete=()=>{db.close();resolve(result);};tx.onerror=()=>{db.close();reject(tx.error);};};
    });
  }
  function mount(root) {
    if(root.fzBilling||!root.fzAccount||!root.fzRefineBridge)return;
    const account=root.fzAccount, bridge=root.fzRefineBridge, api=bridge.api.replace(/\/$/,''), ar=()=>root.dataset.lang==='ar';
    const tr=(en,arabic)=>window.FindziaI18n?.t(en,arabic,root)||(ar()?arabic:en);
    const tf=(en,values,arabic)=>window.FindziaI18n?.format(en,values,root,arabic)||(ar()&&arabic?arabic:en).replace(/\{(\w+)\}/g,(all,key)=>String(values[key]??all));
    const rtl=()=>['ar','ur'].includes(root.dataset.lang);
    let status=null, config=null, error='', flight=null, stamp=0, active=0, revision=0, guestFlight=null, linkTimer=null;
    let noticeCode='', noticeKey='', allowedView=null, blockedSearch=null;
    let paddleConfig=null, paymentBusy=false, paymentMessage='', paymentTxn='', paymentRevision=0, walletDialog=null;
    let checkoutView=null, standardPreferred=false, mfConfig=null;
    let mfView=null, mfScriptPromise=null, paymentFlow=0;
    let startingPayment=false, queuedPlan='', recoveryTimer=null, recoveryDeadline=0, pendingCheckoutIntent='';
    const mfReturnKey="findzia-mf-return-v1";
    const retiredCheckouts=new Set();
    const guestKey='findzia-guest-v1:'+new URL(api).origin, planKey='findzia-plan-intent-v1';
    let guestToken='';try{guestToken=localStorage.getItem(guestKey)||'';}catch(_){}
    const credential=()=>account.session()?.access_token||guestToken;
    function selectedPlan(){try{const v=JSON.parse(sessionStorage.getItem(planKey))||memoryPlan;return v&&Date.now()-v.at<1800000?v.plan:'';}catch(_){return memoryPlan&&Date.now()-memoryPlan.at<1800000?memoryPlan.plan:'';}}
    const operations=new Map();
    let device;
    try{device=localStorage.getItem('findzia-device-v1');if(!/^[a-zA-Z0-9_-]{20,100}$/.test(device||'')){device=uid();localStorage.setItem('findzia-device-v1',device);}}
    catch(_){device=uid();}
    const notice=code=>{noticeCode=code;paint();
      if(code==='credits_exhausted')requestAnimationFrame(()=>{
        if(hint.hidden||!hint.isConnected)return;
        const header=root.dataset.homeState==='empty'?null:root.querySelector('[data-fixed-header]');
        const inset=header?Math.max(0,header.getBoundingClientRect().bottom):0;
        hint.style.scrollMarginTop=(inset+12)+'px';
        const rect=hint.getBoundingClientRect();
        if(rect.top<inset||rect.bottom>(window.visualViewport?.height||window.innerHeight||800))hint.scrollIntoView?.({block:'start',behavior:'auto'});
      });
    };
    function blockSearch(code){
      root.querySelectorAll('dialog[data-refine-dialog][open],dialog.fz-guide[open]').forEach(dialog=>dialog.close());
      notice(code);return false;
    }
    function button(text, fn, cls='fza-primary'){const b=el('button',cls,text);b.type='button';b.addEventListener('click',fn);return b;}
    function message(code){return ({
      credits_exhausted:tr('Your searches are used. Choose a plan to keep discovering.','استهلكت رصيدك. اختر باقة لتكمل البحث.'),
      trial_budget_reached:tr('New free trials are paused for now. Please try later.','التجارب المجانية الجديدة متوقفة مؤقتًا. حاول لاحقًا.'),
      trial_daily_limit:tr('Free searches have reached today’s limit. Please try tomorrow.','وصلت التجارب المجانية لحد اليوم. جرّب باچر.'),
      retry_limit:tr('Several searches could not finish today. Please try again tomorrow. Your refunded credits are safe.','تعذّر إكمال عدة بحوث اليوم. حاول باچر؛ رصيدك المسترجع محفوظ.'),
      search_in_progress:tr('A search is already running. Wait for it to finish.','في بحث شغال. انتظر لين يخلص.'),
      search_already_processed:tr('This search was already processed. You were not charged again.','سبق معالجة هذا البحث، ما خصمنا منك مرة ثانية.'),
      helper_limit:tr('You’ve reached the assistance limit for this search. Your search credits are unchanged.','وصلت لحد المساعدة لهذا البحث. ما خصمنا رصيد بحث.'),
      sign_in_required:tr('Could not start your free trial. Please try again.','تعذّر بدء تجربتك المجانية. حاول مجددًا.'),
      trial_transfer_pending:tr('Your previous search is finishing. Please try again shortly.','بحثك السابق قاعد يخلص. جرّب بعد شوي.'),
      guest_session_expired:tr('Could not restore this browser’s trial. Please try again.','تعذّر استعادة تجربة هذا المتصفح. حاول مجددًا.'),
      session_expired:tr('Please sign in again. Your credits are saved.','سجّل الدخول مجددًا؛ رصيدك محفوظ.'),
      payments_not_connected:tr('Purchases are not available yet. No payment was taken.','الشراء مو متاح حاليًا، وما تم خصم أي مبلغ.')
    })[code]||tr('Could not check your credits. Please try again.','تعذّر التحقق من الرصيد. حاول مجددًا.');}
    async function json(path, body, authenticated=true, timeout=8000){
      const headers={'Accept':'application/json','Content-Type':'application/json'};
      if(authenticated&&credential())headers.Authorization='Bearer '+credential();
      const ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),timeout);
      try{const response=await fetch(api+'/api/billing'+path,{method:body===undefined?'GET':'POST',headers,body:body===undefined?undefined:JSON.stringify(body),signal:ctl.signal,credentials:'omit'});
        const data=await response.json();if(!response.ok||!data.ok)throw Object.assign(Error(data.error||data.detail||'credits_unavailable'),{code:response.status});return data;
      }finally{clearTimeout(timer);}
    }
    // A limit card sits above the home composer or above the result tools in normal flow.
    // Existing results stay in place; only a confirmed zero balance shows the purchase card.
    const hint=el('div','fzb-search-notice');hint.id=root.id+'-credit-notice';hint.hidden=true;
    hint.dataset.billingNotice='';hint.setAttribute('role','status');hint.setAttribute('aria-live','polite');hint.setAttribute('aria-atomic','true');
    const inputs=[root.querySelector('[id^="fz-query-"]'),root.querySelector('[data-dark-input]')].filter(Boolean);
    function paintNotice(){
      const busy=active>0||bridge.context().busy||status?.reserved>0;
      const code=noticeCode||(!busy&&status?.remaining===0?'credits_exhausted':'');
      const home=root.dataset.homeState==='empty',limited=code==='credits_exhausted';
      const anchor=home?root.querySelector('[data-dark-form]'):limited?root.querySelector('.fz-results-tools'):root.querySelector('[data-search-card]');
      const before=home||limited;
      if(anchor&&(before?anchor.previousElementSibling:anchor.nextElementSibling)!==hint){if(before)anchor.before(hint);else anchor.after(hint);}
      const key=[code,root.dataset.lang].join('|');hint.dir=rtl()?'rtl':'ltr';
      hint.className='fzb-search-notice'+(limited?' fzb-credit-card':'');
      hint.hidden=!code;
      if(key!==noticeKey){noticeKey=key;hint.replaceChildren();
        if(code==='credits_exhausted'){
          const title=el('h2','fzb-credit-title',tr('You’re out of search credits','انتهى رصيد البحث'));
          title.id=hint.id+'-title';
          hint.append(title,el('p','fzb-credit-copy',tr('Add credits to keep searching.','أضف رصيدًا لمتابعة البحث.')),
            button(tr('Add credits','إضافة رصيد'),()=>account.open('plans'),'fzb-credit-action'));
        }else if(code){hint.append(document.createTextNode(message(code)));}
      }
      for(const input of inputs){const ids=new Set((input.getAttribute('aria-describedby')||'').split(/\s+/).filter(Boolean));
        ids.delete(hint.id);if(code)ids.add(hint.id);if(ids.size)input.setAttribute('aria-describedby',[...ids].join(' '));else input.removeAttribute('aria-describedby');}
    }
    function paint(){
      paintNotice();
      account.render();
    }
    const limitCodes=new Set(['credits_exhausted','trial_budget_reached','trial_daily_limit','retry_limit','search_in_progress','search_already_processed','sign_in_required','trial_transfer_pending','guest_session_expired','session_expired','credits_unavailable']);
    function errorCode(value){let code=value?.message||value?.error||String(value||'');try{const data=JSON.parse(code);code=data.error||data.detail||code;}catch(_){}return typeof code==='string'?code:'';}
    function handleSearchError(value){
      const code=errorCode(value);if(!limitCodes.has(code))return false;
      // A cross-tab debit can reach the API after the preflight succeeded.
      // Restore the previous cards once; callers skip generic errors and retries.
      if(blockedSearch?.generation===bridge.context().generation){
        const previous=blockedSearch.previous;blockedSearch=null;
        if(previous?.snapshot.view?.items?.length)bridge.restore(previous.snapshot);
        else if(previous?.homeState==='empty')root.dataset.homeState='empty';
      }
      notice(code);return true;
    }
    async function ensureGuest(){
      if(guestToken)return;
      if(guestFlight)return guestFlight;
      guestFlight=(async()=>{const data=await json('/guest',{device_id:device},false);
        guestToken=data.guest_token;try{localStorage.setItem(guestKey,guestToken);}catch(_){}
        if(!account.member()){status=data;stamp=Date.now();error='';}
      })();try{await guestFlight;}finally{guestFlight=null;}
    }
    async function refresh(force=false,activate=false){
      await account.ready;
      if(flight){await flight;if(!force)return status;}
      // Merely opening Findzia does not allocate a trial or run a paid provider.
      if(!account.session()?.access_token&&!guestToken&&!activate){paint();return null;}
      if(!force&&status&&Date.now()-stamp<4000)return status;
      let generation=revision;
      flight=(async()=>{try{
        let data;
        if(!account.session()?.access_token){
          await ensureGuest();
          try{data=await json('/status',{});}catch(e){
            if(e.code!==401)throw e;
            guestToken='';try{localStorage.removeItem(guestKey);}catch(_){}
            await ensureGuest();data=await json('/status',{});
          }
        }else{
          try{data=await json('/status',{device_id:device,guest_token:guestToken||undefined});}
          catch(e){
            if(e.message==='guest_session_expired'&&guestToken){guestToken='';try{localStorage.removeItem(guestKey);}catch(_){}
              data=await json('/status',{device_id:device});
            }else if(e.code===401){account.expire();revision++;generation=revision;await ensureGuest();data=await json('/status',{});}
            else throw e;
          }
        }
        if(generation===revision){status=data;stamp=Date.now();error='';if(noticeCode==='credits_exhausted'&&data.remaining>0)noticeCode='';}
        clearTimeout(linkTimer);if(data.trial_link_pending)linkTimer=setTimeout(()=>refresh(true),3000);
        return data;
      }catch(e){if(generation===revision)error=e.message;return null;}
      finally{flight=null;paint();}})();return flight;
    }
    async function beforeSearch(){
      // The search endpoint atomically checks/reserves credit. A failed
      // informational status call must not block a valid authenticated search.
      // No client-side balance is invented, and 401/402 responses still block.
      const data=await refresh(false,true);
      if(!data){
        const transient=!['session_expired','guest_session_expired','sign_in_required','trial_transfer_pending',
          'credits_exhausted','trial_daily_limit','trial_budget_reached','retry_limit'].includes(error);
        if(!transient||!credential())return blockSearch(error||'credits_unavailable');
      }
      if(data?.trial_link_pending)return blockSearch('trial_transfer_pending');
      if(data&&data.remaining<=0)return blockSearch('credits_exhausted');
      noticeCode='';blockedSearch=null;paintNotice();
      allowedView={snapshot:bridge.snapshot(),homeState:root.dataset.homeState};
      return true;
    }
    async function beforeSignIn(){
      // Restore already-received cards after OAuth without rerunning/charging search.
      try{const saved=bridge.snapshot();await pendingStore('set',{at:Date.now(),api,view:saved.view,recommendation:saved.recommendation,country:bridge.context().country});}catch(_){}
    }
    let memoryPlan=null;
    function storePlan(value){memoryPlan=value;try{if(value)sessionStorage.setItem(planKey,JSON.stringify(value));else sessionStorage.removeItem(planKey);}catch(_){}}
    function resumePlan(){try{return JSON.parse(sessionStorage.getItem(planKey)||'null')?.resume===true;}catch(_){return memoryPlan?.resume===true;}}
    function choosePlan(id){
      if(mfView||checkoutView||(paymentBusy&&!startingPayment))return;
      if(!(config?.plans||status?.plans||[]).some(p=>p.id===id))return;
      clearTimeout(recoveryTimer);recoveryTimer=null;recoveryDeadline=0;
      pendingCheckoutIntent='';
      storePlan({plan:id,at:Date.now(),resume:!account.member()});paymentMessage='';
      // Let the customer change their selection during loading. Finish the
      // outstanding request first; the server safely retires its unpaid order.
      if(startingPayment){queuedPlan=id;account.render();return;}
      if(!account.member()){account.open('signin');return;}
      startPayment();
    }
    function resumePendingPayment(data,flow,id){
      if(data.checkout_intent)pendingCheckoutIntent=data.checkout_intent;
      if(data.transaction_id){paymentTxn=data.transaction_id;paymentRevision=revision;}
      paymentMessage=tr('Checking your payment… This updates automatically.','نتحقق من حالة الدفع… تتحدث تلقائيًا.');
      if(Date.now()>=recoveryDeadline){
        paymentMessage=tr('Payment status is taking longer to confirm. You can keep browsing and check your payment here.','تأكيد حالة الدفع تأخر. تقدر تكمل التصفح وتتحقق من دفعتك هنا.');
        return;
      }
      recoveryTimer=setTimeout(()=>{
        recoveryTimer=null;
        if(flow===paymentFlow&&id===selectedPlan()&&account.member())startPayment(true);
      },Math.max(2,Math.min(8,Number(data.retry_after)||3))*1000);
    }
    async function startPayment(automatic=false){
      if(paymentBusy||mfView||checkoutView||!selectedPlan())return;
      if(!account.member()){account.open('signin');return;}
      clearTimeout(recoveryTimer);recoveryTimer=null;
      if(automatic!==true)recoveryDeadline=Date.now()+150000;
      const rev=revision,flow=++paymentFlow,id=selectedPlan();paymentBusy=true;startingPayment=true;paymentMessage='';
      storePlan({plan:id,at:Date.now(),resume:false});account.render();
      try{
        await paymentConfig(); // Domain registration may finish after page load.
        if(flow!==paymentFlow||rev!==revision||!account.member()||id!==selectedPlan())return;
        const useMF=id==='pack'&&mfConfig?.enabled;
        if(useMF){
          if(!mfConfig.checkout_available)throw Error('live_checkout_not_available');
          if(!mfConfig.embedded_available)throw Error('embedded_not_available');
          await openMF();return;
        }
        if(!paddleConfig?.checkout_available)throw Error('live_checkout_not_available');
        const paddle=await loadPaddle();if(flow!==paymentFlow||rev!==revision||id!==selectedPlan())return;
        const data=await json('/paddle/checkout',{plan_id:id,...(pendingCheckoutIntent?{resume_intent:pendingCheckoutIntent}:{})},true,45000);if(flow!==paymentFlow||rev!==revision||id!==selectedPlan())return;
        if(data.confirmed){
          await refresh(true);if(flow!==paymentFlow||rev!==revision)return;
          storePlan(null);paymentTxn='';pendingCheckoutIntent='';
          paymentMessage=tr('Payment confirmed. Your search credits are ready.','تأكد الدفع. رصيد البحث جاهز.');account.open('checkout');return;
        }
        if(data.payment_pending){resumePendingPayment(data,flow,id);return;}
        pendingCheckoutIntent='';paymentTxn=data.transaction_id;paymentRevision=revision;
        // Keep the account surface until the next surface exists. Closing it
        // first canceled our own flow and swallowed immediate provider errors.
        if(standardPreferred)openStandard(paddle,paymentTxn);else openWallet(paddle,paymentTxn);
        if(checkoutView)account.close();
      }catch(e){if(flow===paymentFlow&&rev===revision&&id===selectedPlan()){
        if(errorCode(e)==='checkout_pending')resumePendingPayment({},flow,id);
        else paymentMessage=paymentError(e);
        account.render();
      }}
      finally{if(rev===revision&&flow===paymentFlow){
        paymentBusy=false;startingPayment=false;account.render();
        const next=queuedPlan;queuedPlan='';
        if(next&&next===selectedPlan()&&flow===paymentFlow&&!checkoutView&&!mfView)startPayment();
      }}
    }
    function plan(){return (config?.plans||status?.plans||[]).find(p=>p.id===selectedPlan());}
    function planSummary(body){
      const p=plan();if(!p)return;
      const summary=el('div','fzb-selected-plan');summary.dataset.selectedPlan=p.id;
      const amount=el('span','',`$${(p.amount_cents/100).toFixed(2)} USD`+(p.interval==='month'?tr(' / month',' / شهر'):tr(' once',' دفعة واحدة')));amount.dir='ltr';amount.style.display='inline-block';
      summary.append(el('strong','',p.name),amount,el('p','',tf('Searches: {count}',{count:p.credits},'عمليات البحث: {count}')+(p.interval==='month'?tr(' / month',' / شهر'):'')));body.append(summary);
    }
    async function paymentConfig(){
      const rev=revision;
      const results=await Promise.allSettled([
        json('/myfatoorah/config',account.member()?{}:undefined,!!account.member()),
        account.member()?json('/paddle/config',{}):Promise.resolve(null)
      ]);
      if(rev!==revision)return;
      mfConfig=results[0].status==='fulfilled'?results[0].value:null;
      paddleConfig=results[1].status==='fulfilled'?results[1].value:null;
    }
    async function confirmMyFatoorah(){
      // A stored return from the former provider must not interrupt Paddle.
      if(!mfConfig?.enabled)return false;
      let record;try{record=JSON.parse(sessionStorage.getItem(mfReturnKey));}catch(_){}
      if(!record||Date.now()-record.at>86400000)return false;
      if(!account.member()){account.open('signin');return true;}
      if(record.owner&&account.member()?.id&&record.owner!==account.member().id)return false;
      const rev=revision;paymentBusy=true;
      paymentMessage=tr('Confirming your payment…','نتحقق من دفعتك…');account.open('checkout');
      try{
        const hasPayment=typeof record.payment==='string'&&/^[A-Za-z0-9_-]{1,100}$/.test(record.payment);
        const data=hasPayment
          ?await json('/myfatoorah/confirm',{intent:record.intent,payment_id:record.payment})
          :await json('/myfatoorah/resume',{intent:record.intent});
        if(rev!==revision)return true;
        if(data.confirmed){
          sessionStorage.removeItem(mfReturnKey);sessionStorage.removeItem(planKey);memoryPlan=null;
          await refresh(true);if(rev!==revision)return true;
          paymentMessage=tr('Payment confirmed. Your 20 searches have been added.','تم تأكيد الدفع وإضافة 20 بحثًا لرصيدك.');
        }else paymentMessage=tr('Payment is not confirmed yet. You can check again shortly.','لم يتأكد الدفع بعد. تقدر تتحقق مرة ثانية بعد شوي.');
      }catch(e){if(rev===revision)paymentMessage=tr('We could not confirm this payment yet. Your receipt will be checked securely; please try again.','ما قدرنا نؤكد الدفعة حاليًا. جرّب التحقق مرة ثانية.');}
      finally{if(rev===revision){paymentBusy=false;account.render();}}
      return true;
    }
    function captureMyFatoorahReturn(){
      const u=new URL(location.href),intent=u.searchParams.get('fz_mf_intent'),payment=u.searchParams.get('paymentId');
      if(!intent)return;
      if(/^[A-Za-z0-9_-]{1,100}$/.test(intent)){
        const validPayment=typeof payment==='string'&&/^[A-Za-z0-9_-]{1,100}$/.test(payment);
        try{sessionStorage.setItem(mfReturnKey,JSON.stringify({intent,payment:validPayment?payment:null,at:Date.now()}));}catch(_){}
      }
      u.searchParams.delete('fz_mf_intent');u.searchParams.delete('paymentId');
      history.replaceState(history.state,'',u.pathname+u.search+u.hash);
    }
    function mfNavigate(url){
      const u=new URL(url),hosts=mfConfig?.environment==='sandbox'?['demo.myfatoorah.com']:['portal.myfatoorah.com','pay.myfatoorah.com','www.myfatoorah.com','myfatoorah.com'];
      if(u.protocol!=='https:'||!hosts.includes(u.hostname)||u.username||u.password||u.port)throw Error('invalid_checkout_url');
      location.assign(u.href);
    }
    function closeMF(){
      const view=mfView;mfView=null;
      if(view){clearTimeout(view.timer);clearTimeout(view.checkTimer);if(view.onMessage)window.removeEventListener('message',view.onMessage);window.FindziaModalScroll?.unlock(view.dialog);view.dialog.close();view.dialog.remove();}
    }
    function mfInlineApplePay(){
      // The API subdomain and legacy boolean are not proof for this page.
      // Let the provider render its native wallet button in this same form.
      const config=mfConfig?.apple_pay_inline;
      if(config?.available!==true||!Array.isArray(config.origins))return false;
      try{
        const page=new URL(location.href);
        return ['https://findzia.com','https://www.findzia.com'].includes(page.origin)
          &&config.origins.includes(page.origin);
      }catch(_){return false;}
    }
    function loadMF(){
      if(mfScriptPromise)return mfScriptPromise;
      mfScriptPromise=new Promise((resolve,reject)=>{
        const script=document.createElement('script');
        script.src=(mfConfig?.environment==='sandbox'?'https://demo.myfatoorah.com':'https://portal.myfatoorah.com')+'/sessions/v1/session.js';
        let settled=false;
        const finish=ok=>{if(settled)return;settled=true;clearTimeout(timer);script.onload=null;script.onerror=null;
          if(ok&&window.myfatoorah?.init)resolve(window.myfatoorah);
          else{script.remove();reject(Error('embedded_unavailable'));}};
        const timer=setTimeout(()=>finish(false),12000);
        script.onload=()=>finish(true);script.onerror=()=>finish(false);document.head.append(script);
      }).catch(e=>{mfScriptPromise=null;throw e;});
      return mfScriptPromise;
    }
    async function openMF(restart={}){
      closeMF();const rev=revision;
      const dialog=el('dialog','fzb-wallet-dialog fzb-mf-dialog');
      dialog.dir=rtl()?'rtl':'ltr';dialog.dataset.theme=root.dataset.theme;
      const view={dialog,rev,submitted:false,leaving:false,checking:false,polls:0};mfView=view;
      const current=()=>mfView===view&&rev===revision&&!!account.member();
      const title=el('h2','',tr('Payment','الدفع'));title.id='fz-mf-title';dialog.setAttribute('aria-labelledby',title.id);
      const header=el('div','fzb-wallet-header');
      const leave=()=>{closeMF();paymentMessage='';account.open('plans');};
      const close=button('×',leave,'fzb-wallet-close');close.setAttribute('aria-label',tr('Close','إغلاق'));
      header.append(title,close);
      const summary=el('p','fzb-wallet-status',tf('{count} searches · {price}',{count:20,price:'$4.99 USD'},'{count} عملية بحث · {price}'));
      const message=el('p','fzb-wallet-status',tr('Loading secure payment…','جارٍ تحميل الدفع الآمن…'));message.setAttribute('role','status');
      const surface=el('div','fzb-mf-surface');surface.id='fz-mf-'+uid();
      // The hosted iframe owns its document background. Give it an intentional
      // light card in either theme rather than unreadable dark text overrides.
      // Freeze this payment view's appearance; never re-init an active wallet
      // when the site's automatic day/night theme changes.
      surface.setAttribute('data-no-i18n','');
      const retry=button(tr('Try again','إعادة المحاولة'),()=>{if(current()&&!view.submitted&&!view.paying)openMF(restart);},'fza-text');retry.hidden=true;
      const check=button(tr('Check payment','تحقق من الدفع'),()=>checkPayment(),'fza-text');check.hidden=true;
      const separate=button(tr('Start a new purchase','ابدأ شراءً جديدًا'),()=>{
        if(!current()||view.checking||!view.canStartNew||!view.intent)return;
        view.reviewing=true;clearTimeout(view.checkTimer);surface.hidden=true;
        separate.hidden=true;check.hidden=true;approve.hidden=false;back.hidden=false;
        message.textContent=tr('The earlier payment is unconfirmed. A separate purchase could result in two charges if both payments succeed.','الدفعة السابقة غير مؤكدة. بدء شراء منفصل قد يؤدي إلى خصم المبلغ مرتين إذا نجحت الدفعتان.');
        back.focus();
      },'fza-text');separate.hidden=true;
      const approve=button(tr('Continue with a new purchase','متابعة شراء جديد'),()=>{
        if(!current()||!view.reviewing||!view.intent||view.restarting)return;
        view.restarting=true;approve.disabled=true;back.disabled=true;
        openMF({previous_intent:view.intent,acknowledge_unconfirmed:true});
      });approve.hidden=true;
      const back=button(tr('Back','رجوع'),()=>{
        if(!current()||view.restarting)return;
        view.reviewing=false;approve.hidden=true;back.hidden=true;
        pending({intent:view.intent,payment_id:view.payment,can_start_new_purchase:view.canStartNew,
          authentication_url:view.authenticationUrl});
      },'fza-text');back.hidden=true;
      const actions=el('div','fzb-mf-actions');actions.append(retry,check,separate,approve,back);
      async function success(){
        if(!current())return;
        try{sessionStorage.removeItem(mfReturnKey);sessionStorage.removeItem(planKey);memoryPlan=null;}catch(_){}
        await refresh(true);if(!current())return;
        closeMF();paymentMessage=tr('Payment confirmed. Your 20 searches have been added.','تم تأكيد الدفع وإضافة 20 بحثًا لرصيدك.');account.open('checkout');
      }
      async function checkPayment(){
        if(!current()||view.checking||view.reviewing)return;
        view.checking=true;check.disabled=true;separate.disabled=true;
        try{
          const result=await json('/myfatoorah/resume',{intent:view.intent||undefined},true,35000);
          if(!current())return;
          if(result.confirmed){await success();return;}
          if(result.ready_for_payment){
            await openMF();return;
          }
          pending(result);
        }catch(_){if(current())message.textContent=tr('The earlier payment could not be verified yet.','لم نتمكن من تأكيد الدفعة السابقة بعد.');}
        finally{view.checking=false;if(current()){check.disabled=false;separate.disabled=false;}}
      }
      function scheduleCheck(){
        clearTimeout(view.checkTimer);
        if(!current()||view.reviewing)return;
        if(view.polls>=12){
          if(!view.authenticationUrl)message.textContent=tr('Your previous payment is still unconfirmed.','الدفعة السابقة ما زالت غير مؤكدة.');
          return;
        }
        view.checkTimer=setTimeout(async()=>{if(!current())return;view.polls++;await checkPayment();if(current())scheduleCheck();},5000);
      }
      function pending(data){
        if(!current())return;
        clearTimeout(view.timer);view.submitted=true;retry.hidden=true;check.hidden=false;
        view.canStartNew=data.can_start_new_purchase===true;separate.hidden=!view.canStartNew;
        rememberPayment(data.intent||view.intent,data.payment_id||view.payment);
        if(data.authentication_url){
          if(view.authenticationUrl!==data.authentication_url)authentication(data.authentication_url);
          else{surface.hidden=false;message.textContent=tr('Complete your bank’s verification below.','أكمل تحقق البنك بالأسفل.');}
        }
        else if(!view.authenticationUrl){surface.hidden=true;message.textContent=tr('Your previous payment is still unconfirmed.','الدفعة السابقة ما زالت غير مؤكدة.');}
        scheduleCheck();
      }
      function rememberPayment(intent,payment){
        view.intent=intent;view.payment=payment;
        if(payment)try{sessionStorage.setItem(mfReturnKey,JSON.stringify({intent,payment,at:Date.now()}));}catch(_){}
      }
      function authentication(url){
        if(!current())return;
        const u=new URL(url),hosts=mfConfig?.environment==='sandbox'?['demo.myfatoorah.com']:['portal.myfatoorah.com','pay.myfatoorah.com','www.myfatoorah.com','myfatoorah.com'];
        if(u.protocol!=='https:'||!hosts.includes(u.hostname)||u.username||u.password||u.port)throw Error('invalid_checkout_url');
        view.submitted=true;view.authenticationUrl=u.href;clearTimeout(view.timer);surface.replaceChildren();surface.hidden=false;retry.hidden=true;check.hidden=false;
        if(view.onMessage)window.removeEventListener('message',view.onMessage);
        message.textContent=tr('Complete your bank’s verification below.','أكمل تحقق البنك بالأسفل.');
        const frame=el('iframe','fzb-mf-auth');frame.title=tr('Secure bank verification','التحقق الآمن من البنك');
        frame.setAttribute('sandbox','allow-forms allow-scripts allow-same-origin');
        frame.style.cssText='display:block;width:100%;height:min(58dvh,560px);min-height:280px;border:0;background:#fff;border-radius:16px';
        // Only the provider's authenticated URL is framed. Never navigate using a posted URL.
        view.onMessage=event=>{
          if(!current()||event.source!==frame.contentWindow||event.origin!==u.origin)return;
          try{
            const data=typeof event.data==='string'?JSON.parse(event.data):event.data;
            if(data?.sender!=='MF-3DSecure')return;
            checkPayment();
          }catch(_){}
        };
        window.addEventListener('message',view.onMessage);frame.src=u.href;surface.append(frame);
        // A bank may not post a message. Verify the SAME payment, never submit it again.
        scheduleCheck();
      }
      const failed=(error)=>{
        if(!current()||view.submitted||view.paying)return;
        view.unavailable=true;clearTimeout(view.timer);surface.hidden=true;
        message.textContent=['payment_creation_pending','payment_verification_unavailable'].includes(errorCode(error))?paymentError(error):tr('Payment could not load. Try again here.','تعذّر تحميل الدفع. جرّب مرة ثانية هنا.');
        retry.hidden=false;
      };
      dialog.append(header,summary,message,surface,actions);document.body.append(dialog);account.close();dialog.showModal();window.FindziaModalScroll?.lock(dialog);dialog.addEventListener('close',()=>window.FindziaModalScroll?.unlock(dialog),{once:true});close.focus();
      dialog.addEventListener('cancel',e=>{e.preventDefault();leave();});
      view.timer=setTimeout(()=>failed(Error('embedded_unavailable')),45000);
      try{
        const data=await json('/myfatoorah/session',{plan_id:'pack',...restart},true,35000);if(!current()||view.unavailable)return;
        if(data.confirmed){await success();return;}
        if(data.payment_pending||data.pending_checkout||data.url){pending(data);return;}
        if(data.authentication_url&&data.intent&&data.payment_id){rememberPayment(data.intent,data.payment_id);authentication(data.authentication_url);return;}
        if(!data.session_id||!data.intent)throw Error('embedded_unavailable');
        rememberPayment(data.intent,null);
        const sdk=await loadMF();if(!current()||view.unavailable)return;
        // Only a server-owned intent is sent back. Card details stay with MyFatoorah.
        sdk.init({sessionId:data.session_id,containerId:surface.id,shouldHandlePaymentUrl:false,
          subscribedEvents:['VIEW_READY','PAYMENT_STARTED','SESSION_STARTED','SESSION_CANCELED'],
          eventListener:event=>{
            if(!current()||view.submitted||view.unavailable)return;
            if(event?.name==='VIEW_READY'){clearTimeout(view.timer);message.textContent='';retry.hidden=true;}
            if(event?.name==='PAYMENT_STARTED'||event?.name==='SESSION_STARTED'){clearTimeout(view.timer);view.paying=true;retry.hidden=true;}
            if(event?.name==='SESSION_CANCELED'){view.paying=false;message.textContent=tr('Choose a payment method to continue.','اختر طريقة دفع للمتابعة.');}
          },
          settings:{applePay:{isEnabled:mfInlineApplePay(),language:ar()?'ar':'en',
            style:{frameWidth:'100%',frameHeight:'48px',button:{height:'48px',type:'pay',borderRadius:'10px'}}},
            googlePay:{isEnabled:true,language:ar()?'ar':'en',
              style:{frameWidth:'100%',frameHeight:'48px',button:{height:'48px',type:'pay',borderRadius:'10px',color:'black'}}},
            card:{isEnabled:true,language:ar()?'ar':'en',
            style:{input:{fontSize:'16px',fontFamily:'Arial, sans-serif',color:'#24332d',backgroundColor:'#ffffff',
                borderColor:'#ccd3cd',borderWidth:'1px',outerRadius:'10px',placeHolder:{color:'#606d64'}},
              button:{textContent:tr('Pay $4.99','ادفع 4.99 دولار'),fontFamily:'Arial, sans-serif',fontSize:'16px',
                backgroundColor:'#394e40',color:'#ffffff',borderRadius:'10px',height:'48px',width:'100%'},
              separator:{textContent:tr('Or pay by card','أو ادفع بالبطاقة'),fontFamily:'Arial, sans-serif',
                fontSize:'14px',color:'#606d64',lineStyle:'solid',lineColor:'#dfe4df',lineThickness:'1px'}}}},
          callback:async response=>{
            if(!current()||view.submitted||view.unavailable)return;
            if(response?.isSuccess!==true){view.paying=false;message.textContent=tr('Payment was not completed. Please try again.','لم تكتمل العملية. حاول مرة ثانية.');return;}
            view.submitted=true;clearTimeout(view.timer);retry.hidden=true;surface.hidden=true;
            message.textContent=tr('Confirming your payment…','نتحقق من دفعتك…');
            try{
              const result=await json('/myfatoorah/session/complete',{intent:data.intent},true,35000);
              if(!current())return;
              rememberPayment(result.intent||data.intent,result.payment_id);
              if(result.confirmed){await success();}
              else if(result.payment_pending){pending(result);}
              else if(result.url){authentication(result.url);}
              else{pending(result);}
            }catch(e){if(current()){check.hidden=false;message.textContent=tr('Checking your payment. This window will update automatically.','نتحقق من دفعتك. تتحدث النافذة تلقائيًا.');scheduleCheck();}}
          }});
      }catch(e){failed(e);}
    }
    async function loadPaddle(){
      const environment=paddleConfig?.paddle_environment;
      const token=paddleConfig?.paddle_client_token;
      if(!['sandbox','live'].includes(environment)||typeof token!=='string'||!token.startsWith(environment==='live'?'live_':'test_'))throw Error('paddle_configuration_invalid');
      const identity=environment+':'+token;
      if(window.FindziaPaddleInitialized&&window.FindziaPaddleIdentity!==identity)throw Error('paddle_reload_required');
      if(!window.FindziaPaddleLoading){
        window.FindziaPaddleLoading=new Promise((resolve,reject)=>{
          if(window.Paddle?.Checkout?.open){resolve(window.Paddle);return;}
          const script=document.createElement('script');script.src='https://cdn.paddle.com/paddle/v2/paddle.js';
          let settled=false;
          const finish=ok=>{if(settled)return;settled=true;clearTimeout(timer);script.onload=null;script.onerror=null;
            if(ok&&window.Paddle?.Checkout?.open)resolve(window.Paddle);
            else{script.remove();reject(Error('paddle_load_failed'));}};
          const timer=setTimeout(()=>finish(false),12000);
          script.onload=()=>finish(true);script.onerror=()=>finish(false);document.head.append(script);
        });
      }
      const pending=window.FindziaPaddleLoading;
      let paddle;
      try{paddle=await pending;}catch(e){if(window.FindziaPaddleLoading===pending)window.FindziaPaddleLoading=null;throw e;}
      if(!window.FindziaPaddleInitialized){
        paddle.Environment.set(environment==='live'?'production':'sandbox');
        paddle.Initialize({token,pwCustomer:account.member()?.email?{email:account.member().email}:{},eventCallback:event=>{
          document.dispatchEvent(new CustomEvent('findzia:paddle',{detail:event}));
        }});window.FindziaPaddleInitialized=true;window.FindziaPaddleIdentity=identity;
      }
      return paddle;
    }
    function closeWallet(closeProvider=true){
      const dialog=walletDialog,view=checkoutView;walletDialog=null;checkoutView=null;
      if(view){clearTimeout(view.timer);if(view.id){retiredCheckouts.add(view.id);if(retiredCheckouts.size>40)retiredCheckouts.delete(retiredCheckouts.values().next().value);}}
      // Clear our state first: Paddle may emit checkout.closed synchronously.
      if(closeProvider&&(view||dialog))try{window.Paddle?.Checkout?.close();}catch(_){}
      if(dialog){window.FindziaModalScroll?.unlock(dialog);if(dialog.open)dialog.close();dialog.remove();}
    }
    function checkoutOptions(transactionId){
      // The selected search market is not the buyer's billing country.
      const email=account.member()?.email;
      return {transactionId,...(email?{customer:{email}}:{})};
    }
    function openStandard(paddle,transactionId){
      if(paymentRevision!==revision||paymentTxn!==transactionId||!account.member()||checkoutView?.paying)return;
      // Reopen the exact transaction. Do not create another order or debit credits.
      closeWallet();standardPreferred=true;
      checkoutView={mode:'overlay',id:'',paying:false,loaded:false};
      try{paddle.Checkout.open({...checkoutOptions(transactionId),settings:{displayMode:'overlay',variant:'one-page',
        allowedPaymentMethods:['apple_pay','google_pay','card'],theme:'light'}});}
      catch(e){closeWallet();paymentMessage=paymentError(e);account.open('checkout');}
    }
    function checkoutHelp(text){
      const view=checkoutView;
      if(!view||view.mode!=='inline'||view.paying)return;
      clearTimeout(view.timer);view.status.hidden=false;view.status.textContent=text;
      view.status.after(view.fallback);
      view.dialog.dataset.checkoutState='delayed';
    }
    function updateWalletTotals(data){
      const view=checkoutView;if(!view?.totals)return;
      const currency=data.currency_code,totals=data.totals;
      if(!/^[A-Z]{3}$/.test(currency||'')||!totals||!['subtotal','tax','total'].every(k=>typeof totals[k]==='number'&&Number.isFinite(totals[k])&&totals[k]>=0))return;
      // Paddle.js event amounts are major units, unlike the REST API's minor units.
      const money=n=>new Intl.NumberFormat(ar()?'ar-KW':'en-US',{style:'currency',currency}).format(n);
      view.totals.replaceChildren();
      for(const [label,value] of [[tr('Subtotal','المجموع الفرعي'),totals.subtotal],[tr('Tax','الضريبة'),totals.tax],[tr('Total','الإجمالي'),totals.total]]){
        const row=el('div','fzb-checkout-total');row.append(el('span','',label),el('bdi','',money(value)));view.totals.append(row);
      }
      const recurring=data.recurring_totals?.total;
      if(plan()?.interval==='month'&&typeof recurring==='number'&&Number.isFinite(recurring))view.totals.append(el('p','fzb-wallet-note',tr('Renews monthly at '+money(recurring),'يتجدد شهريًا بقيمة '+money(recurring))));
      view.totals.hidden=false;
    }
    function openWallet(paddle,transactionId){
      closeWallet();
      const walletFrame='fzb-wallet-frame-'+uid();
      const dialog=el('dialog','fzb-wallet-dialog');walletDialog=dialog;
      dialog.dir=rtl()?'rtl':'ltr';dialog.dataset.theme=root.dataset.theme;dialog.dataset.checkoutState='loading';
      const header=el('div','fzb-wallet-header'),title=el('h2','',tr('Complete your purchase','أكمل عملية الشراء'));
      title.id=walletFrame+'-title';title.tabIndex=-1;dialog.setAttribute('aria-labelledby',title.id);
      const close=button('×',()=>{closeWallet();account.open('plans');},'fzb-wallet-close');
      close.setAttribute('aria-label',tr('Close checkout','إغلاق الدفع'));
      header.append(title,close);
      const frame=el('div',walletFrame);frame.classList.add('fzb-wallet-frame');
      const summary=el('div','fzb-wallet-summary'),p=plan();
      if(p){summary.append(el('strong','',p.name),el('span','',tf('Searches: {count}',{count:p.credits},'عمليات البحث: {count}')+' · '+(p.interval==='month'?tr('Monthly subscription','اشتراك شهري'):tr('One-time purchase','شراء لمرة واحدة'))));}
      const totals=el('div','fzb-checkout-totals');totals.hidden=true;
      const status=el('p','fzb-wallet-status',tr('Loading secure checkout…','جاري تحميل الدفع الآمن…'));
      status.setAttribute('role','status');status.setAttribute('aria-live','polite');
      const fallback=button(tr('Use standard checkout','فتح الدفع المعتاد'),()=>openStandard(paddle,transactionId),'fzb-wallet-alternative');
      dialog.append(header,summary,totals,status,frame,fallback);document.body.append(dialog);
      const view={mode:'inline',id:'',dialog,status,totals,fallback,loaded:false,paying:false,timer:null};checkoutView=view;
      view.timer=setTimeout(()=>{if(checkoutView===view&&!view.loaded&&!view.paying)checkoutHelp(tr('Checkout is taking longer than expected. You can try the standard checkout.','الدفع تأخر في التحميل. تقدر تجرّب الدفع المعتاد.'));},12000);
      dialog.addEventListener('cancel',e=>{e.preventDefault();closeWallet();account.open('plans');});
      dialog.showModal();window.FindziaModalScroll?.lock(dialog);dialog.addEventListener('close',()=>window.FindziaModalScroll?.unlock(dialog),{once:true});title.focus({preventScroll:true});
      // Express inherits enabled methods from Paddle. allowedPaymentMethods is
      // incompatible with variant: 'express'; keep that option in openStandard only.
      try{paddle.Checkout.open({...checkoutOptions(transactionId),
        settings:{displayMode:'inline',variant:'express',frameTarget:walletFrame,
          frameInitialHeight:450,frameStyle:'width:100%;min-width:312px;background-color:transparent;border:none;',
          showNonExpressPaymentMethods:true,theme:'light'}
      });}catch(e){closeWallet();throw e;}
    }
    function paymentError(e){
      const code=errorCode(e);
      return ({
        payment_verification_unavailable:tr('Could not verify the previous payment. Please try again.','تعذّر التحقق من الدفعة السابقة. جرّب مرة ثانية.'),
        embedded_not_available:tr('In-site payment is not available yet. Please contact support.','الدفع داخل الموقع غير متاح حاليًا. تواصل مع الدعم.'),
        paddle_load_failed:tr('The payment service could not load. Please try again in a regular Safari or Chrome tab.','تعذّر تحميل خدمة الدفع. جرّب مرة ثانية بتبويب عادي في Safari أو Chrome.'),
        paddle_configuration_invalid:tr('Payment configuration is not ready yet.','إعدادات الدفع غير مكتملة حاليًا.'),
        paddle_reload_required:tr('Please refresh the page to use the updated payment settings.','حدّث الصفحة لاستخدام إعدادات الدفع الجديدة.'),
        live_checkout_not_available:tr('Purchases are not available for this account yet.','الشراء غير متاح لهذا الحساب حاليًا.'),
        sandbox_test_account_required:tr('Test checkout is available only to approved test accounts.','الدفع التجريبي متاح لحسابات الاختبار فقط.'),
        subscription_exists:tr('You already have a monthly plan. Manage it from Subscription.','عندك باقة شهرية. تقدر تديرها من الاشتراك.'),
        payment_creation_pending:tr('A payment is being checked. Please do not pay again. Check Restore purchases before retrying.','في عملية دفع قيد التحقق. لا تدفع مرة ثانية؛ تحقق من استعادة المشتريات أولًا.'),
        paddle_authentication_failed:tr('Payments are temporarily unavailable. Please contact support. (P01)','الدفع غير متاح مؤقتًا. تواصل مع الدعم. (P01)'),
        paddle_access_denied:tr('Payments are temporarily unavailable. Please contact support. (P02)','الدفع غير متاح مؤقتًا. تواصل مع الدعم. (P02)'),
        paddle_checkout_rejected:tr('Checkout could not be started. Please contact support. (P03)','تعذّر بدء الدفع. تواصل مع الدعم. (P03)'),
        paddle_recovery_unavailable:tr('We could not verify the previous checkout. Please contact support before paying again. (P04)','تعذّر التحقق من محاولة الدفع السابقة. تواصل مع الدعم قبل الدفع مجددًا. (P04)'),
        checkout_pending:tr('Checking your payment… This updates automatically.','نتحقق من حالة الدفع… تتحدث تلقائيًا.'),
        checkout_limit:tr('Please wait before starting another checkout.','انتظر شوي قبل بدء عملية دفع ثانية.')
      })[code]||tr('Could not complete this step. Check your purchases before retrying.','تعذّر إكمال الخطوة. تحقق من مشترياتك قبل المحاولة مجددًا.');
    }
    async function confirmPayment(){
      if(paymentBusy||!paymentTxn||!account.member()||paymentRevision!==revision)return;
      clearTimeout(recoveryTimer);recoveryTimer=null;
      paymentBusy=true;const rev=revision,tid=paymentTxn;
      paymentMessage=tr('Confirming payment…','نتحقق من الدفع…');account.open('checkout');
      try{
        let confirmed=false;
        for(let i=0;i<8;i++){
          if(rev!==revision)return;
          const data=await json('/paddle/confirm',{transaction_id:tid});
          if(data.confirmed){confirmed=true;break;}
          await new Promise(resolve=>setTimeout(resolve,2000));
        }
        if(rev!==revision)return;
        await refresh(true);
        if(confirmed){
          paymentMessage=tr('Payment confirmed. Your search credits are ready.','تأكد الدفع. رصيد البحث جاهز.');
          try{sessionStorage.removeItem(planKey);memoryPlan=null;}catch(_){}
          paymentTxn='';
        }else paymentMessage=tr('Payment is still being checked. Your credits will update after confirmation.','التحقق من الدفع مستمر. الرصيد يتحدث بعد التأكيد.');
      }catch(e){if(rev===revision)paymentMessage=paymentError(e);}
      finally{if(rev===revision){paymentBusy=false;account.render();}}
    }
    document.addEventListener('findzia:paddle',event=>{
      const e=event.detail;if(!paymentTxn||paymentRevision!==revision)return;
      if(e?.name==='checkout.completed'&&e.data?.transaction_id===paymentTxn){closeWallet();confirmPayment();return;}
      const view=checkoutView;if(!view||!e)return;
      if(retiredCheckouts.has(e.data?.id)||(e.data?.transaction_id&&e.data.transaction_id!==paymentTxn))return;
      if(view.id&&e.data?.id&&view.id!==e.data.id)return;
      if(e.name==='checkout.error'){
        if(view.mode==='inline')checkoutHelp(tr('Express checkout could not load. Try the standard checkout.','تعذّر تحميل الدفع السريع. جرّب الدفع المعتاد.'));
        else if(!view.paying){closeWallet();paymentMessage=tr('Checkout could not load. Try again in a regular Safari or Chrome tab.','تعذّر تحميل الدفع. جرّب مرة ثانية بتبويب عادي في Safari أو Chrome.');account.open('checkout');}
        return;
      }
      if(e.data?.transaction_id!==paymentTxn||retiredCheckouts.has(e.data?.id))return;
      const mode=e.data?.settings?.display_mode;
      if(mode&&(mode==='inline')!==(view.mode==='inline'))return;
      if(view.id&&e.data?.id&&view.id!==e.data.id)return;
      if(e.name==='checkout.loaded'){
        view.id=e.data.id||'';view.loaded=true;clearTimeout(view.timer);
        if(view.status){view.status.hidden=true;view.dialog.dataset.checkoutState='ready';view.dialog.append(view.fallback);}
        updateWalletTotals(e.data);
      }
      if(e.name==='checkout.updated')updateWalletTotals(e.data);
      if(e.name==='checkout.payment.initiated'){
        view.paying=true;clearTimeout(view.timer);if(view.fallback)view.fallback.disabled=true;
        if(view.status)view.status.hidden=true;
      }
      if(e.name==='checkout.payment.failed'||e.name==='checkout.payment.error'){
        view.paying=false;if(view.fallback)view.fallback.disabled=false;
        checkoutHelp(tr('Payment was not completed. Try another card or use standard checkout.','ما اكتمل الدفع. جرّب بطاقة ثانية أو افتح الدفع المعتاد.'));
      }
      // Programmatic closes are cleared/retired before reaching this handler.
      if(e.name==='checkout.closed'&&view.id&&e.data.id===view.id){closeWallet(false);account.open('plans');}
    });
    function manageSubscription(){
      const manager=window.FindziaSubscriptionManager?.mount(root,{
        rpc:json,paddle:async()=>{await paymentConfig();return loadPaddle();},
        refresh:()=>refresh(true),balance:()=>status
      });
      if(manager)return manager.open();
      paymentMessage=tr('Please refresh the page to load subscription management.','حدّث الصفحة لتحميل إدارة الاشتراك.');account.open('checkout');
    }
    async function restorePurchases(){
      if(!account.member()){account.open('signin');return;}
      if(paymentBusy)return;
      const rev=revision;paymentBusy=true;paymentMessage=tr('Checking your purchases…','نتحقق من مشترياتك…');account.open('checkout');
      try{
        await paymentConfig();if(rev!==revision)return;
        const paths=[];
        if(mfConfig?.enabled&&mfConfig?.checkout_available)paths.push('/myfatoorah/restore');
        if(paddleConfig?.restore_available)paths.push('/paddle/restore');
        if(!paths.length)throw Error('credits_unavailable');
        const results=await Promise.allSettled(paths.map(path=>json(path,{})));
        if(rev!==revision)return;
        const failures=results.filter(result=>result.status==='rejected');
        const current=await refresh(true);if(rev!==revision)return;
        if(!current)throw Error('credits_unavailable');
        if(failures.length===results.length)throw failures[0].reason;
        paymentMessage=failures.length
          ?tr('Some purchases were checked. One payment provider is unavailable; please retry to check the rest.','تحققنا من بعض المشتريات. إحدى بوابات الدفع غير متاحة؛ أعد المحاولة للتحقق من الباقي.')
          :tr('Your purchase records and search balance are up to date.','تم تحديث سجل مشترياتك ورصيد البحث.');
      }
      catch(e){if(rev===revision)paymentMessage=paymentError(e);}
      finally{if(rev===revision){paymentBusy=false;account.render();}}
    }
    function renderCheckout(body){
      const msg=el('p','fza-payment-message',paymentMessage||tr('Payment','الدفع'));msg.setAttribute('role','status');body.append(msg);
      if(selectedPlan()&&!paymentBusy){const retry=button(tr('Try again','حاول مجددًا'),startPayment);retry.dataset.checkout='';body.append(retry);}
      appendPaymentCheck(body);
      body.append(button(tr('Your search credits','رصيد البحث'),()=>account.open('usage'),'fza-text'),button(tr('Back to search','العودة للبحث'),()=>account.close(),'fza-text'));
    }
    function appendPaymentCheck(body){
      let check=null;
      if(paymentTxn)check=confirmPayment;
      else try{if(mfConfig?.enabled&&sessionStorage.getItem(mfReturnKey))check=confirmMyFatoorah;}catch(_){}
      if(check){const b=button(tr('Check payment','تحقق من الدفع'),check,'fza-text');b.disabled=paymentBusy;body.append(b);}
    }
    async function paidFetch(url,options={}){
      const target=new URL(url,location.href), allowed=new URL(api);
      if(target.origin!==allowed.origin||!target.pathname.startsWith('/api/'))throw Error('invalid_api_target');
      await abortable(account.ready,options.signal);
      if(options.signal?.aborted)throw new DOMException('Aborted','AbortError');
      const headers=new Headers(options.headers||{}), charge=searches.has(target.pathname),generation=bridge.context().generation,previous=allowedView;
      if(!credential())await abortable(ensureGuest(),options.signal);
      if(options.signal?.aborted)throw new DOMException('Aborted','AbortError');
      headers.set('Authorization','Bearer '+credential());
      if(charge){
        // A stream-to-JSON fallback or reconnect belongs to the same search.
        // A deliberate new search changes the renderer's generation.
        const input=target.pathname.replace(/\/stream$/,'')+'|'+bridge.context().generation+'|'+(options.body||'');
        const bytes=new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(input)));
        const key=Array.from(bytes,x=>x.toString(16).padStart(2,'0')).join('');
        if(!operations.has(key))operations.set(key,uid());
        if(operations.size>60)operations.delete(operations.keys().next().value);
        headers.set('X-Findzia-Request-Id',operations.get(key));active++;
      }
      try{
        const response=await fetch(url,{...options,headers,credentials:'omit'});
        if(!response.ok){let data;try{data=await response.clone().json();}catch(_){}const code=data?.error||data?.detail;
          if(response.status===401){if(account.member())account.expire();await refresh(true,true);}
          if(charge)active=Math.max(0,active-1);
          if(response.status===402)await refresh(true);
          if(charge&&limitCodes.has(code)&&generation===bridge.context().generation){blockedSearch={generation,previous};notice(code);}
          return response;
        }
        if(!charge||!response.body)return response;
        // One reader; pass through chunks immediately. No tee buffering or second search.
        const reader=response.body.getReader();let finished=false;
        const finish=()=>{if(finished)return;finished=true;active=Math.max(0,active-1);setTimeout(()=>refresh(true),100);};
        const stream=new ReadableStream({async pull(controller){try{const chunk=await reader.read();if(chunk.done){controller.close();finish();}else controller.enqueue(chunk.value);}catch(e){controller.error(e);finish();}},async cancel(reason){try{await reader.cancel(reason);}finally{finish();}}});
        return new Response(stream,{status:response.status,statusText:response.statusText,headers:response.headers});
      }catch(e){if(charge){active=Math.max(0,active-1);setTimeout(()=>refresh(true),300);}throw e;}
      finally{if(charge)setTimeout(()=>refresh(true),300);}
    }
    function renderUsage(body){
      
      if(!status&&!account.member()&&!error){body.append(el('p','fza-caption',tr('Your first 10 searches are ready. Search with text or a photo.','أول 10 بحوث جاهزة لك. ابحث بالنص أو الصورة.')),button(tr('Start searching','ابدأ البحث'),()=>account.close()));return;}
      if(!status){body.append(el('p','fza-caption',error?message(error):tr('Loading…','جاري التحميل…')),button(tr('Try again','حاول مجددًا'),()=>refresh(true)));return;}
      const summary=el('div','fza-usage-summary');summary.append(el('span','',tr('Searches remaining','البحوث المتبقية')),el('strong','',String(status.remaining)));body.append(summary);
      const group=el('div','fza-group');for(const [key,en,arabic] of [['subscription','Monthly plan','الباقة الشهرية'],['trial','Free trial','التجربة المجانية'],['pack','Top-up credits','رصيد الشحن']]){if(!Number(status.balances?.[key]))continue;const row=el('div','fza-metric');row.append(el('span','',tr(en,arabic)),el('strong','',String(status.balances[key])));group.append(row);}body.append(group);
      if(status.reserved)body.append(el('p','fza-caption',tf('Reserved for an active search: {count}',{count:status.reserved},'رصيد محجوز لبحث جارٍ: {count}')));
      if(status.subscription){const sub=status.subscription,date=new Intl.DateTimeFormat(root.dataset.lang||'en',{dateStyle:'medium'}).format(new Date(sub.period_end*1000));body.append(el('p','fza-caption',tf('Plan: Findzia {plan} · Current period ends {date}.',{plan:sub.plan,date},'الباقة: Findzia {plan} · تنتهي الفترة الحالية في {date}.')));}
      if(account.member()&&(paddleConfig?.management_available||paddleConfig?.checkout_available))body.append(button(tr('Manage subscription','إدارة الاشتراك'),manageSubscription));
      const details=el('details','fza-faq');details.append(el('summary','',tr('How credits work','كيف يُستخدم الرصيد')),
        el('p','',tr('Text or photo: 1 credit per new search. Technical failures and searches with no results are refunded. Up to 5 refunded attempts a day.','النص أو الصورة: رصيد واحد لكل بحث جديد. نرجع الرصيد للفشل التقني أو عدم وجود نتائج، بحد 5 محاولات مسترجعة باليوم.')));
      if(status.subscription)details.append(el('p','',tr('Your monthly allowance is used first and does not roll over. Pack credits do not expire.','نستخدم رصيد الاشتراك أولًا، ولا يترحّل للشهر التالي. رصيد الشحن بدون انتهاء.')));
      body.append(details,button(tr('Buy credits','شراء رصيد'),()=>account.open('plans')));
    }
    function renderPlans(body){
      const plans=config?.plans||status?.plans||[];
      if(!plans.length){body.append(el('p','fza-caption',error?message(error):tr('Loading…','جاري التحميل…')));if(error)body.append(button(tr('Try again','حاول مجددًا'),()=>refresh(true)));return;}
      if(paymentMessage){const msg=el('p','fza-payment-message',paymentMessage);msg.setAttribute('role','status');body.append(msg);appendPaymentCheck(body);}
      const list=el('div','fzb-plans');
      for(const plan of plans.filter(p=>!mfConfig?.enabled||p.id==='pack')){
        const card=el('article','fzb-plan');card.dataset.plan=plan.id;
        card.append(el('h3','',tf('{count} searches',{count:plan.credits},'{count} عملية بحث')));
        const price=el('p','fzb-price');price.dir='ltr';price.append(el('strong','',new Intl.NumberFormat(root.dataset.lang||'en',{style:'currency',currency:'USD'}).format(plan.amount_cents/100)),el('span','',plan.interval==='once'?'USD':tr('/ month','/ شهر')));card.append(price);
        card.append(el('p','fza-caption',plan.interval==='once'?tr('One payment. Credits do not expire.','دفعة واحدة. الرصيد لا ينتهي.'):tr('Renews monthly. Unused searches do not roll over.','تتجدد شهريًا. البحوث غير المستخدمة لا تترحّل.')));
        const loading=startingPayment&&selectedPlan()===plan.id;
        const buy=button(loading?tr('Preparing payment…','نجهّز الدفع…'):tr('Continue to payment','المتابعة للدفع'),()=>choosePlan(plan.id));
        buy.dataset.planBuy=plan.id;buy.disabled=(paymentBusy&&!startingPayment)||loading||!!mfView||!!checkoutView;
        buy.setAttribute('aria-busy',String(loading));card.append(buy);list.append(card);
      }
      body.append(list);
      if(mfConfig?.environment==='sandbox'||paddleConfig?.paddle_environment==='sandbox')body.append(el('p','fza-footnote',tr('Test mode. No real payment is collected.','وضع التجربة، بدون تحصيل مبلغ حقيقي.')));
    }
    root.fzBilling={manageSubscription,restorePurchases,fetch:paidFetch,beforeSearch,refresh,renderUsage,renderPlans,renderCheckout,planSummary,selectedPlan,beforeSignIn,handleSearchError,notice,status:()=>status,label:()=>status?tf('Searches remaining: {count}',{count:status.remaining},'عمليات البحث المتبقية: {count}'):tr('10 free searches','10 بحوث مجانية')};
    root.addEventListener('fz:account-session',()=>{clearTimeout(recoveryTimer);recoveryTimer=null;queuedPlan='';pendingCheckoutIntent='';startingPayment=false;closeMF();closeWallet();revision++;status=null;stamp=0;error='';noticeCode='';paddleConfig=null;mfConfig=null;paymentBusy=false;paymentMessage='';paymentTxn='';standardPreferred=false;memoryPlan=null;paymentConfig().then(async()=>{account.render();if(await confirmMyFatoorah())return;if(account.member()&&selectedPlan()&&resumePlan())startPayment();});refresh(true);});
    root.addEventListener('fz:account-closed',()=>{if(!mfView&&!checkoutView){
      clearTimeout(recoveryTimer);recoveryTimer=null;queuedPlan='';paymentFlow++;
      if(startingPayment){startingPayment=false;paymentBusy=false;}
    }});
    const obs=new MutationObserver(paint);obs.observe(root,{attributes:true,attributeFilter:['data-lang','data-theme','data-home-state']});
    root.addEventListener('fz:search-state',paintNotice);
    window.addEventListener('focus',()=>refresh(true));
    window.addEventListener('storage',ev=>{if(ev.key===guestKey){guestToken=ev.newValue||'';revision++;stamp=0;refresh(true);}});
    json('/config',undefined,false).then(c=>{config=c;paint();}).catch(()=>{error='credits_unavailable';paint();});
    captureMyFatoorahReturn();
    (async()=>{await account.ready;await paymentConfig();await refresh(true);paint();
      try{const saved=await pendingStore('get');await pendingStore('delete');if(saved?.view?.items?.length&&saved.api===api&&saved.country===bridge.context().country&&Date.now()-saved.at<600000){root.dataset.homeState='results';bridge.restore(saved);}}catch(_){}
      if(await confirmMyFatoorah())return;
      if(account.member()&&selectedPlan()&&resumePlan())await startPayment();
    })();
  }
  const style=el('style');style.textContent=`
    .fzb-mf-dialog .fzb-mf-surface{min-height:80px;width:100%}.fzb-mf-dialog iframe{max-width:100%}.fzb-mf-dialog .fzb-wallet-header h2{font-size:22px;margin:0}.fzb-mf-dialog .fza-text{padding:12px;cursor:pointer}.fzb-mf-dialog .fzb-wallet-status:empty{display:none}
    .fzb-mf-actions{display:flex;align-items:center;justify-content:flex-end;gap:8px;flex-wrap:wrap}.fzb-mf-actions .fza-primary{appearance:none;flex:1;min-width:180px;min-height:46px;padding:12px 16px;border:0;border-radius:14px;background:#394e40;color:#fff;font:600 13px/1.5 system-ui,sans-serif;cursor:pointer}.fzb-mf-actions button:disabled{opacity:.55;cursor:wait}.fzb-mf-actions .fza-text{font-size:13px}.fzb-wallet-dialog.fzb-mf-dialog{width:min(560px,calc(100vw - 24px));padding:20px}.fzb-mf-dialog .fzb-wallet-header{padding:0 0 12px}
    .fzb-wallet-dialog{box-sizing:border-box;width:min(560px,calc(100vw - 24px));max-width:none;max-height:90vh;max-height:90dvh;margin:auto;padding:16px;border:1px solid #e1e3dc;border-radius:22px;background:#fff;color:#28352e;overflow:auto;overscroll-behavior:contain;font-family:system-ui,sans-serif}
    .fzb-wallet-dialog::backdrop{background:rgba(25,34,28,.42);backdrop-filter:blur(5px)}
    .fzb-wallet-header{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:0 4px 14px}
    .fzb-wallet-header h2{font:600 18px/1.4 system-ui,sans-serif;margin:0}.fzb-wallet-header h2:focus{outline:none}
    .fzb-wallet-close{display:grid;place-items:center;flex:none;width:44px;height:44px;padding:0;border:1px solid #e1e3dc;border-radius:50%;background:#fff;color:#28352e;font:28px/1 system-ui;cursor:pointer}
    .fzb-wallet-close:focus-visible{outline:2px solid #3a5143;outline-offset:2px}
    .fzb-wallet-frame{min-width:312px}.fzb-wallet-frame iframe{display:block;max-width:100%}
    .fzb-wallet-summary{display:grid;gap:4px;margin:0 4px 14px}.fzb-wallet-summary strong{font-size:15px;font-weight:600}.fzb-wallet-summary span,.fzb-wallet-note{font-size:12px;line-height:1.6;color:#68736c}
    .fzb-wallet-status{margin:8px 4px 12px;font-size:13px;line-height:1.6;color:#68736c}.fzb-wallet-dialog [hidden]{display:none!important}
    .fzb-wallet-alternative{display:block;appearance:none;margin:10px auto 0;min-height:44px;padding:8px 12px;border:0;border-radius:8px;background:none;color:#3a5143;font:500 13px/1.5 system-ui,sans-serif;text-decoration:underline;text-underline-offset:3px;cursor:pointer}
    .fzb-wallet-alternative:focus-visible{outline:2px solid #3a5143;outline-offset:2px}.fzb-wallet-alternative:disabled{opacity:.45;cursor:default}
    .fzb-wallet-dialog[data-checkout-state="delayed"] .fzb-wallet-alternative{margin:0 4px 12px;background:#edf0e9;text-decoration:none;padding-inline:18px}
    .fzb-checkout-totals{display:grid;gap:5px;margin:0 4px 14px;padding-bottom:12px;border-bottom:1px solid #e1e3dc}.fzb-checkout-total{display:flex;justify-content:space-between;gap:12px;font-size:12px;line-height:1.5}.fzb-checkout-total:last-of-type{font-weight:600;font-size:14px}.fzb-wallet-note{margin:5px 0 0}
    @media(max-width:400px){.fzb-wallet-dialog{width:100vw;padding:4px;border:0;border-radius:16px}.fzb-wallet-header{padding:8px 10px 14px}}

    .fzb-selected-plan{padding:18px;margin:0 0 20px;border:1px solid var(--a-line);border-radius:18px;background:var(--a-surface)}.fzb-selected-plan strong{display:block;margin-bottom:6px}.fzb-selected-plan p{font-size:13px;color:var(--a-muted);margin:8px 0 0}
    .fz-home .fzb-search-notice{box-sizing:border-box;display:block;margin:9px 8px 2px;padding:0;border:0;background:none;color:var(--fz-muted,#737a73);font:inherit;font-size:12px;line-height:1.8;letter-spacing:normal;text-align:start;overflow-wrap:break-word}
    .fz-home .fzb-search-notice[hidden]{display:none!important}
    .fz-home .fz-dark-bottom>.fzb-search-notice{margin:0 8px 12px}
    .fz-home .fzb-search-notice.fzb-credit-card{width:100%;max-width:640px;margin:12px auto 18px;padding:20px;border:1px solid var(--fz-line,#e1e5df);border-radius:22px;background:var(--fz-surface,#fff);color:var(--fz-ink,#29372f);box-shadow:0 6px 24px #1c302108;text-align:start;line-height:1.5}
    .fz-home .fzb-credit-title{margin:0 0 6px;padding:0;color:inherit;font:inherit;font-size:17px;line-height:1.45;font-weight:650;letter-spacing:normal}
    .fz-home .fzb-credit-copy{margin:0;padding:0;color:var(--fz-muted,#68736c);font:inherit;font-size:14px;line-height:1.6;letter-spacing:normal}
    .fz-home .fzb-credit-action{box-sizing:border-box;appearance:none;display:block;width:100%;min-height:46px;margin:18px 0 0;padding:11px 18px;border:1px solid transparent;border-radius:999px;background:#edf3ed;color:#365542;font:inherit;font-size:15px;line-height:1.5;font-weight:650;letter-spacing:normal;cursor:pointer;text-align:center}
    .fz-home .fzb-credit-action:hover{background:#e3ede3}.fz-home .fzb-credit-action:focus-visible{outline:2px solid currentColor;outline-offset:3px}
    .fz-home[data-theme=dark] .fzb-credit-card{box-shadow:0 6px 24px #0002}
    .fz-home[data-theme=dark] .fzb-credit-copy{color:#bac6bd}
    .fz-home[data-theme=dark] .fzb-credit-action{background:#2e4337;color:#e2f0e6}
    .fz-home[data-theme=dark] .fzb-credit-action:hover{background:#3b5143}
    .fzb-plans{display:grid;gap:13px}.fzb-plans:has(>.fzb-plan:only-child){grid-template-columns:1fr;max-width:440px;margin-inline:auto}.fzb-plan{border:1px solid var(--a-line);border-radius:20px;background:var(--a-surface);padding:20px}
    .fzb-plan h3{font-size:16px;margin:0 0 12px;font-weight:600}.fzb-price{display:flex;align-items:baseline;gap:7px;margin:0 0 14px;justify-content:flex-start}
    .fzb-price strong{font-size:35px;letter-spacing:-1px;font-weight:550}.fzb-price span{font-size:12px;color:var(--a-muted)}
    .fzb-allowance{font-size:18px;font-weight:550;margin:0 0 7px}.fzb-plan .fza-caption{font-size:12px;line-height:1.7;margin:5px 0}
    .fzb-plan .fza-primary{width:100%;margin-top:14px;min-height:44px}
    @media(min-width:1000px){.fz-account:has(.fzb-plans){width:850px}.fzb-plans{grid-template-columns:repeat(3,minmax(0,1fr))}.fzb-plan{display:flex;flex-direction:column;padding:18px}.fzb-plan .fza-primary{margin-top:auto}.fzb-plan .fza-caption:last-of-type{margin-bottom:20px}}
  
.fzb-plan{padding:22px!important;border-radius:14px!important;margin:0!important;background:var(--a-surface)!important}.fzb-plan h3{font-size:19px!important;margin:0 0 14px!important}.fzb-price{margin:0 0 18px!important;gap:8px!important}.fzb-price strong{font-size:38px!important;line-height:1.15!important;letter-spacing:-1px!important}.fzb-plan .fza-primary{margin-top:12px!important;width:100%}.fzb-plan .fza-caption{margin:0!important;font-size:13px!important}.fza-payment-message{font-size:16px;line-height:1.7;margin:0 0 20px}.fza-payment-message~.fza-text{display:block}.fzb-wallet-header h2{font-size:19px!important}.fzb-wallet-dialog{border-radius:16px}.fzb-wallet-dialog[data-theme=dark]{background:#202622;color:#f5f6f0}

.fzb-plans{grid-template-columns:repeat(auto-fit,minmax(min(240px,100%),1fr))!important}.fz-account:has(.fzb-plans){width:min(620px,calc(100vw - 40px))}@media(max-width:600px){.fz-account:has(.fzb-plans){width:100%}}

/* 156.7.2: readable night shell and a deliberate secure hosted-fields card. */
.fzb-wallet-dialog.fzb-mf-dialog{--pay-bg:#fff;--pay-ink:#24332d;--pay-muted:#606d64;--pay-line:#dfe4df;--pay-close:#f2f4f0;
 background:var(--pay-bg);color:var(--pay-ink);border:1px solid var(--pay-line);padding:20px;border-radius:18px;
 width:min(480px,calc(100vw - 24px));max-width:calc(100vw - 24px);min-width:0;text-align:start;}
.fzb-wallet-dialog.fzb-mf-dialog[data-theme=dark]{--pay-bg:#202923;--pay-ink:#f3f5ef;--pay-muted:#c1cbbf;--pay-line:#455249;--pay-close:#2c3830;color-scheme:dark}
.fzb-mf-dialog .fzb-wallet-header{padding:0 0 12px;gap:16px}
.fzb-mf-dialog .fzb-wallet-header h2{color:var(--pay-ink);font-size:20px!important;line-height:1.4}
.fzb-mf-dialog .fzb-wallet-close{background:var(--pay-close);border-color:var(--pay-line);color:var(--pay-ink);width:40px;height:40px;font-size:28px}
.fzb-mf-dialog .fzb-wallet-close:focus-visible{outline-color:var(--pay-ink)}
.fzb-mf-dialog .fzb-wallet-status{margin:0 0 16px;color:var(--pay-muted);font-size:14px;line-height:1.6;overflow-wrap:anywhere}
.fzb-mf-dialog .fzb-mf-surface{box-sizing:border-box;background:#fff;color:#24332d;color-scheme:light;
 padding:16px;border:1px solid #dfe4df;border-radius:14px;width:100%;min-width:0;overflow:hidden}
.fzb-mf-dialog .fzb-mf-surface iframe{display:block;width:100%;max-width:100%;border:0;color-scheme:light}
.fzb-mf-dialog .fzb-mf-actions .fza-text{color:var(--pay-ink)}
@media(max-width:380px){.fzb-wallet-dialog.fzb-mf-dialog{padding:16px}.fzb-mf-dialog .fzb-mf-surface{padding:12px}}
`;document.head.append(style);
  const scan=()=>document.querySelectorAll('.fz-home').forEach(mount);scan();
  const timer=setInterval(scan,100);setTimeout(()=>clearInterval(timer),15000);
  document.addEventListener('shopify:section:load',scan);
})();
