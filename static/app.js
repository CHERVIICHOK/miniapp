/* Prices are integers in kopecks. The API is authoritative for checkout. */
const $ = (selector) => document.querySelector(selector);
const money = (value) => new Intl.NumberFormat('ru-RU', {style:'currency',currency:'RUB',maximumFractionDigits:0}).format(value / 100);
const escapeHtml = (value) => String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const tg = window.Telegram?.WebApp;
const state = {products:[],cart:{},category:'Все',mode:'local',busy:false};
try { const saved = JSON.parse(localStorage.getItem('tz-cart') || '{}'); if (saved && typeof saved === 'object' && !Array.isArray(saved)) state.cart = Object.fromEntries(Object.entries(saved).filter(([id,q]) => /^\d+$/.test(id) && Number.isInteger(q) && q > 0 && q <= 99)); } catch {}
let toastTimer;

async function api(path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 12000);
  try {
    const response = await fetch('/api' + path, {...options, signal:controller.signal, headers:{'Content-Type':'application/json','X-Telegram-Init-Data':tg?.initData || '',...options.headers}});
    const result = await response.json();
    if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Не удалось выполнить запрос.');
    return result;
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('Сервер долго не отвечает. Попробуйте ещё раз.');
    if (error instanceof TypeError) throw new Error('Нет связи с сервером. Проверьте подключение и повторите.');
    throw error;
  } finally { clearTimeout(timer); }
}

function toast(text) { clearTimeout(toastTimer); $('#toast').textContent=text; $('#toast').hidden=false; toastTimer=setTimeout(()=>$('#toast').hidden=true,2400); }
function cartProducts() { return state.products.filter(p => state.cart[p.id]).map(p => ({...p,quantity:state.cart[p.id]})); }
function saveCart() { try { localStorage.setItem('tz-cart', JSON.stringify(state.cart)); } catch {} $('#cart-count').textContent=Object.values(state.cart).reduce((a,b)=>a+b,0); renderCart(); }
function setQuantity(id, change) {
  if (state.busy || !state.products.some(p=>p.id===id)) return;
  const quantity=(state.cart[id] || 0)+change;
  if (quantity>99) { toast('Не более 99 единиц одного товара'); return; }
  if (quantity<=0) delete state.cart[id]; else state.cart[id]=quantity;
  saveCart();
}

function renderCategories() {
  const categories=['Все',...new Set(state.products.map(p=>p.category))];
  $('#categories').innerHTML=categories.map(c=>`<button class="category-tab ${c===state.category?'active':''}" aria-pressed="${c===state.category}" data-category="${escapeHtml(c)}">${escapeHtml(c)} <span>${c==='Все'?state.products.length:state.products.filter(p=>p.category===c).length}</span></button>`).join('');
}
function renderProducts() {
  $('#products').innerHTML=state.products.filter(p=>state.category==='Все'||p.category===state.category).map(p=>`<article class="product-card"><div class="product-image"><img src="${escapeHtml(p.image)}" alt="${escapeHtml(p.name)}" loading="lazy"><span class="product-category">${escapeHtml(p.category)}</span></div><h3>${escapeHtml(p.name)}</h3><p class="product-variant">${escapeHtml(p.variant)}</p><p class="product-description">${escapeHtml(p.description)}</p><div class="product-bottom"><strong class="price">${money(p.price)}</strong><button class="add-button" data-add="${p.id}" aria-label="Добавить ${escapeHtml(p.name)} в корзину">В корзину <span aria-hidden="true">+</span></button></div></article>`).join('');
}
function renderCart() {
  const items=cartProducts();
  $('#cart-bottom').hidden=!items.length;
  $('#cart-items').innerHTML=items.length?items.map(p=>`<div class="cart-row"><img src="${escapeHtml(p.image)}" alt=""><div class="cart-row-body"><h3>${escapeHtml(p.name)}</h3><p>${escapeHtml(p.variant)}</p><strong>${money(p.price*p.quantity)}</strong></div><div class="quantity-control"><button type="button" data-change="${p.id}" data-delta="-1" aria-label="Убрать одну единицу ${escapeHtml(p.name)}" ${state.busy?'disabled':''}>−</button><span>${p.quantity}</span><button type="button" data-change="${p.id}" data-delta="1" aria-label="Добавить одну единицу ${escapeHtml(p.name)}" ${state.busy?'disabled':''}>+</button></div></div>`).join(''):'<div class="empty-state">Здесь пока тихо.<br>Добавьте что-нибудь для тёплого дня из каталога.</div>';
  $('#cart-total').textContent=money(items.reduce((sum,p)=>sum+p.price*p.quantity,0));
}
async function loadProducts() {
  const message=$('#catalog-message'); message.hidden=false; message.className='message'; message.textContent='Загружаем вашу коллекцию…';
  try {
    state.products=await api('/products');
    const valid=new Set(state.products.map(p=>String(p.id)));
    state.cart=Object.fromEntries(Object.entries(state.cart).filter(([id])=>valid.has(id)));
    renderCategories(); renderProducts(); saveCart();
    message.hidden=state.products.length>0; message.textContent='В каталоге пока нет товаров.';
  } catch(error) { message.className='message error'; message.textContent=error.message; const retry=document.createElement('button'); retry.className='text-button retry-button'; retry.textContent='Повторить загрузку ↻'; retry.addEventListener('click',loadProducts); message.append(document.createElement('br'),retry); }
}
async function loadOrders() {
  const message=$('#orders-message'); message.hidden=false; message.className='message'; message.textContent='Загружаем заказы…'; $('#orders-list').replaceChildren();
  $('#refresh-orders').disabled=true;
  try {
    const orders=await api('/orders');
    message.hidden=orders.length>0; message.textContent='Пока нет заказов. Начните с любимого вкуса в магазине.';
    $('#orders-list').innerHTML=orders.map(order=>`<article class="order-card"><div class="order-card-header"><h3>Заказ №${order.id}</h3><span class="order-status">Принят · Самовывоз</span></div><p class="order-date">${new Date(order.created_at).toLocaleString('ru-RU',{dateStyle:'long',timeStyle:'short'})}</p>${order.items.map(item=>`<div class="order-item"><span>${escapeHtml(item.name)}<small>${escapeHtml(item.variant)} · ${item.quantity} шт.</small></span><span>${money(item.unit_price*item.quantity)}</span></div>`).join('')}<p class="order-total"><span>Итого</span><strong>${money(order.total)}</strong></p><p class="order-contact">${escapeHtml(order.name)} · ${escapeHtml(order.phone)}</p></article>`).join('');
  } catch(error) { message.className='message error'; message.textContent=error.message; }
  finally { $('#refresh-orders').disabled=false; }
}
function showView(view) {
  $('#catalog-view').hidden=view!=='catalog'; $('#orders-view').hidden=view!=='orders';
  document.querySelectorAll('[data-view]').forEach(button=>{const active=button.dataset.view===view;button.classList.toggle('active',active);if(active)button.setAttribute('aria-current','page');else button.removeAttribute('aria-current');});
  if(view==='orders') loadOrders(); window.scrollTo({top:0,behavior:'smooth'});
}

document.addEventListener('click',event=>{
  const target=event.target.closest('button,a'); if(!target) return;
  if(target.dataset.add) {setQuantity(Number(target.dataset.add),1);toast('Добавлено в корзину');tg?.HapticFeedback?.impactOccurred('light');}
  if(target.dataset.category){state.category=target.dataset.category;renderCategories();renderProducts();}
  if(target.dataset.change) setQuantity(Number(target.dataset.change),Number(target.dataset.delta));
  if(target.dataset.view) showView(target.dataset.view);
  if(target.dataset.closeDialog && !state.busy) document.getElementById(target.dataset.closeDialog).close();
  if(target.classList.contains('brand')) showView('catalog');
});
$('#cart-button').addEventListener('click',()=>{renderCart();$('#checkout-error').textContent='';$('#cart-dialog').showModal();});
$('#refresh-orders').addEventListener('click',loadOrders);
$('#show-orders').addEventListener('click',()=>{$('#success-dialog').close();showView('orders');});
$('#cart-dialog').addEventListener('cancel',event=>{if(state.busy) event.preventDefault();});
$('#checkout-form').addEventListener('submit',async event=>{
  event.preventDefault(); if(state.busy) return;
  const items=cartProducts().map(p=>({product_id:p.id,quantity:p.quantity})); if(!items.length) return;
  const form=event.currentTarget; const payload={name:form.elements.name.value.trim(),phone:form.elements.phone.value.trim(),items};
  state.busy=true; $('#submit-order').disabled=true; $('#submit-order').textContent='Сохраняем заказ…'; $('#checkout-error').textContent=''; renderCart();
  try {
    const order=await api('/orders',{method:'POST',body:JSON.stringify(payload)});
    state.cart={};saveCart();$('#cart-dialog').close();form.reset();
    $('#success-title').textContent=`Заказ №${order.id} принят`;
    $('#success-description').textContent=`${order.name}, ваш выбор на ${money(order.total)} сохранён. Найти его можно в разделе «Мои заказы».`;
    $('#success-dialog').showModal();tg?.HapticFeedback?.notificationOccurred('success');
  } catch(error) {$('#checkout-error').textContent=error.message;}
  finally {state.busy=false;$('#submit-order').disabled=false;$('#submit-order').innerHTML='Оформить самовывоз <span aria-hidden="true">→</span>';renderCart();}
});

async function start() {
  tg?.ready();tg?.expand();
  try {const config=await api('/config');state.mode=config.mode;$('#mode-label').textContent=config.mode==='local'?'· Локальный демо-режим':'· Telegram MiniApp';} catch {}
  if(tg?.initDataUnsafe?.user?.first_name) $('#checkout-form').elements.name.value=tg.initDataUnsafe.user.first_name;
  saveCart();await loadProducts();
}
start();
