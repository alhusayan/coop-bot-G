/* Home positioning changes presentation, never validates or blocks an image. */
(()=>{
 'use strict';
 function mount(){
  const root=document.querySelector('.fz-home');
  const project=document.documentElement.dataset.hubProject;
  if(!root||!['shop','one','space'].includes(project))return;
  const copy=key=>window.FindziaHomeCopy?.get(root.dataset.lang||document.documentElement.lang,key)||'';
  function text(node,value){if(node&&node.textContent!==value)node.textContent=value;}
  // Space owns per-element actions; never inject a second generic service button.
  if(project==='space')return;
  const home=root.querySelector('[data-dark-home]'),main=home?.querySelector('.fz-dark-main');if(!main)return;
  root.dataset.homeFocus='true';
  let title=main.querySelector('.fz-dark-title'),description=main.querySelector('.fz-dark-description');
  if(!description){description=document.createElement('p');description.className='fz-dark-description';title?.after(description);}
  for(const element of [title,description]){element?.removeAttribute('data-dark-copy');element?.setAttribute('data-no-i18n','');}
  const hint=document.createElement('p');hint.className='home-search-hint';hint.setAttribute('data-no-i18n','');description.after(hint);
  const examples=document.createElement('div');examples.className='home-product-examples';examples.setAttribute('data-no-i18n','');hint.after(examples);
  const terms={ar:['إضاءة','أثاث','أدوات صحية'],en:['Lighting','Furniture','Bathroom fixtures'],fr:['Éclairage','Meubles','Sanitaires'],de:['Beleuchtung','Möbel','Sanitär'],es:['Iluminación','Muebles','Sanitarios'],it:['Illuminazione','Mobili','Sanitari'],pt:['Iluminação','Móveis','Louças sanitárias'],ru:['Освещение','Мебель','Сантехника'],zh:['灯具','家具','卫浴'],ja:['照明','家具','水回り'],ko:['조명','가구','욕실 설비'],hi:['रोशनी','फ़र्नीचर','बाथरूम फ़िटिंग'],ur:['روشنیاں','فرنیچر','باتھ روم کا سامان'],id:['Lampu','Furnitur','Perlengkapan kamar mandi'],ms:['Lampu','Perabot','Kelengkapan bilik mandi'],nl:['Verlichting','Meubels','Sanitair'],tr:['Aydınlatma','Mobilya','Banyo ürünleri']};
  function render(){
   text(title,copy(project==='one'?'one':'shop'));text(description,copy(project==='one'?'oneDetail':'shopDetail'));text(hint,copy('instruction'));
   examples.replaceChildren();for(const label of terms[root.dataset.lang]||terms.en){const button=document.createElement('button');button.type='button';button.textContent=label;button.onclick=()=>{window.FindziaHubBridge?.action('query',{query:label});try{parent.document.querySelector('#header-query')?.focus();}catch{}};examples.append(button);}
  }
  new MutationObserver(render).observe(root,{attributes:true,attributeFilter:['data-lang']});render();
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount,{once:true});else mount();
})();
