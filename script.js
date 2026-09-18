const API_BASE = window.location.protocol === 'file:' ? 'http://127.0.0.1:8001' : '';

const checkoutForm = document.getElementById('checkout-form');
const planSelect = document.getElementById('plan');
const quantitySelect = document.getElementById('quantity');
const priceNotice = document.getElementById('price-notice');

// 初始預設方案 (若離線或 API 尚未回應時作為優雅備案)
let availablePlans = [
  {
    id: '1M',
    name: '月費方案',
    price: 99,
    period: 'U / 月',
    tag: 'Standard',
    badge: '',
    features: [
      '全天候 AI 數據與策略分析提醒',
      '技術面與籌碼面指標推播',
      'Discord 會員群組加入權限'
    ],
    highlight: false
  },
  {
    id: '1Y',
    name: '年費方案',
    price: 1188,
    period: 'U / 年',
    tag: 'Pro Value',
    badge: '推薦 · 買 1 年送 1 個月',
    features: [
      '包含月費方案所有功能與權限',
      '享有 13 個月完整使用時間 (免費贈送 1 個月)',
      '專屬優先客服與一對一諮詢服務'
    ],
    highlight: true
  }
];

function escapeHtml(s) {
  if (!s) return '';
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function getPlanObj(planId) {
  return availablePlans.find(p => p.id === planId) || availablePlans[0];
}

function planPrice(planId) {
  const p = getPlanObj(planId);
  return p ? Number(p.price || 0) : 99;
}

function updateAmount() {
  if (!planSelect) return;
  const planId = planSelect.value;
  const quantity = Math.max(1, Number(quantitySelect ? quantitySelect.value : 1) || 1);
  const price = planPrice(planId);
  const amount = Math.round(price * quantity * 100) / 100;
  if (priceNotice) priceNotice.textContent = `${amount}U`;
}

// 點擊方案卡片按鈕直接選中對應方案並滾動至結帳區
window.selectPlan = function(planId) {
  if (planSelect) {
    planSelect.value = planId;
    updateAmount();
  }
};

function renderPricingCards() {
  const grid = document.querySelector('.pricing-grid');
  if (!grid || availablePlans.length === 0) return;

  grid.innerHTML = availablePlans.map(p => {
    const badgeHtml = p.badge ? `<span class="plan-badge">${escapeHtml(p.badge)}</span>` : '';
    const tagHtml = p.tag ? `<span class="plan-tag" ${p.highlight ? 'style="background:rgba(56,189,248,0.15);color:var(--accent);"' : ''}>${escapeHtml(p.tag)}</span>` : '';
    const featuresHtml = (p.features || []).map(f => `<li>${escapeHtml(f)}</li>`).join('');
    const btnClass = p.highlight ? 'plan-button primary-plan-button' : 'plan-button';
    const cardClass = p.highlight ? 'pricing-card highlighted' : 'pricing-card';

    return `
      <article class="${cardClass}">
        ${badgeHtml}
        <div class="plan-head">
          <span class="plan-name">${escapeHtml(p.name)}</span>
          ${tagHtml}
        </div>
        <div class="plan-price">
          <span class="plan-amount">${p.price}</span>
          <span class="plan-period">${escapeHtml(p.period || 'U / 月')}</span>
        </div>
        <ul class="plan-features">
          ${featuresHtml}
        </ul>
        <a class="${btnClass}" href="#checkout" onclick="selectPlan('${p.id}')">選擇${escapeHtml(p.name)}</a>
      </article>
    `;
  }).join('');
}

function updatePlanDropdown() {
  if (!planSelect) return;
  const currentVal = planSelect.value;
  planSelect.innerHTML = availablePlans.map(p => {
    const label = `${p.name} (${p.price}${p.period || 'U'})`;
    return `<option value="${p.id}">${escapeHtml(label)}</option>`;
  }).join('');

  if (availablePlans.some(p => p.id === currentVal)) {
    planSelect.value = currentVal;
  } else if (availablePlans.length > 0) {
    planSelect.value = availablePlans[0].id;
  }
}

async function fetchDynamicPlans() {
  try {
    const res = await fetch(API_BASE + '/api/plans');
    const d = await res.json();
    if (d.ok && Array.isArray(d.plans) && d.plans.length > 0) {
      availablePlans = d.plans;
      renderPricingCards();
      updatePlanDropdown();
      updateAmount();
    }
  } catch (e) {
    // 保持使用預設方案
    console.log('[Info] Using default pricing fallback.');
  }
}

if (planSelect) planSelect.addEventListener('change', updateAmount);
if (quantitySelect) quantitySelect.addEventListener('change', updateAmount);

if (checkoutForm) {
  checkoutForm.addEventListener('submit', function (event) {
    event.preventDefault();
    const plan = planSelect ? planSelect.value : '1M';
    const quantity = Math.max(1, Number(quantitySelect ? quantitySelect.value : 1) || 1);
    const amount = planPrice(plan) * quantity;
    const params = new URLSearchParams({ plan, quantity, amount });
    window.location.href = `payment.html?${params.toString()}`;
  });
}

// 頁面載入時請求最新方案
fetchDynamicPlans();
updateAmount();
