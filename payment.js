const API_BASE = window.location.protocol === 'file:' ? 'http://127.0.0.1:8001' : '';
const PAYMENT_ADDRESSES = {
  BEP20: '0x3C602BA23061F760F3a86f25698a6696804c2254',
  TRC20: 'TVDXooB8mC6AD1W68yNLuauQ39cQSJKkQ3'
};

const urlParams = new URLSearchParams(window.location.search);
const plan     = urlParams.get('plan')     || '1M';
const quantity = Number(urlParams.get('quantity') || 1);
let   baseAmount = Number(urlParams.get('amount') || 99);
let   finalAmount = baseAmount;

const planLabels = { '1M': '1 個月 (月費)', '1Y': '買 1 年送 1 個月 (年費)' };
document.getElementById('sum-plan').textContent   = planLabels[plan] || plan;
document.getElementById('sum-qty').textContent    = quantity;
document.getElementById('sum-amount').textContent = finalAmount + 'U';

// --- 選鏈 ---
let selectedChain = 'BEP20';
function setChain(chain) {
  selectedChain = chain;
  document.querySelectorAll('.chain-btn').forEach(function(btn) {
    if (btn.getAttribute('data-chain') === chain) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });
  document.getElementById('pay-address').textContent = PAYMENT_ADDRESSES[chain];
}
document.querySelectorAll('.chain-btn').forEach(function(btn) {
  btn.addEventListener('click', function() {
    setChain(btn.getAttribute('data-chain'));
  });
});

// --- 複製地址 (含 fallback) ---
document.getElementById('copy-addr-btn').addEventListener('click', function() {
  var addr = document.getElementById('pay-address').textContent.trim();
  var btn = document.getElementById('copy-addr-btn');
  function onSuccess() {
    btn.textContent = '已複製!';
    setTimeout(function() { btn.textContent = '複製'; }, 2000);
  }
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(addr).then(onSuccess).catch(function() {
      fallbackCopy(addr, onSuccess);
    });
  } else {
    fallbackCopy(addr, onSuccess);
  }
});
function fallbackCopy(text, cb) {
  var ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed';
  ta.style.opacity = '0';
  document.body.appendChild(ta);
  ta.focus();
  ta.select();
  try { document.execCommand('copy'); cb(); } catch(e) {}
  document.body.removeChild(ta);
}

// --- 推薦碼折扣 (預留，管理後台設定後套用) ---
var refInput = document.getElementById('f-ref');
var discountNote = document.getElementById('discount-note');
if (refInput && discountNote) {
  refInput.addEventListener('input', function() {
    var code = refInput.value.trim();
    if (code) {
      discountNote.textContent = '推薦碼已記錄，折扣將由管理員審核後套用。';
      discountNote.style.color = '#8affb4';
    } else {
      discountNote.textContent = '';
    }
  });
}

// --- 截圖上傳預覽 ---
var screenshotInput = document.getElementById('screenshot-input');
var uploadLabel     = document.getElementById('upload-label');
var uploadHint      = document.getElementById('upload-hint');
var screenshotFile  = null;
screenshotInput.addEventListener('change', function() {
  if (this.files && this.files[0]) {
    screenshotFile = this.files[0];
    uploadHint.textContent = '已選擇：' + screenshotFile.name;
    uploadLabel.classList.add('has-file');
  }
});

// --- 表單提交 ---
var payForm    = document.getElementById('pay-form');
var payMessage = document.getElementById('pay-message');
var paySubmit  = document.getElementById('pay-submit');
var successBox = document.getElementById('success-box');

payForm.addEventListener('submit', function(e) {
  e.preventDefault();
  var name    = document.getElementById('f-name').value.trim();
  var dcName  = document.getElementById('f-dc').value.trim();
  var refCode = document.getElementById('f-ref').value.trim();

  if (!name) {
    payMessage.style.color = '#ffcf89';
    payMessage.textContent = '請填寫付款人名稱。';
    return;
  }
  if (!dcName) {
    payMessage.style.color = '#ffcf89';
    payMessage.textContent = '請填寫 DC 名稱。';
    return;
  }
  if (!screenshotFile) {
    payMessage.style.color = '#ffcf89';
    payMessage.textContent = '請上傳交易紀錄截圖。';
    return;
  }

  paySubmit.disabled = true;
  payMessage.style.color = '#8affb4';
  payMessage.textContent = '送出中，請稍候...';

  fetch(API_BASE + '/api/orders', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: name,
      contact: dcName,
      plan: plan,
      quantity: quantity,
      network: selectedChain,
      group: 'https://discord.gg/JvFTfFY5KZ',
      referral: refCode || null
    })
  })
  .then(function(resp) { return resp.json().then(function(d) { return { ok: resp.ok, data: d }; }); })
  .then(function(res) {
    if (!res.ok || !res.data.ok) {
      payMessage.style.color = '#ffcf89';
      payMessage.textContent = res.data.message || '送出失敗，請稍後再試。';
      paySubmit.disabled = false;
      return;
    }
    payMessage.textContent = '';
    payForm.style.display = 'none';
    document.getElementById('suc-order-id').textContent = '訂單編號：' + res.data.order_id;
    successBox.classList.add('show');
  })
  .catch(function() {
    payMessage.style.color = '#ffcf89';
    payMessage.textContent = '無法連線到伺服器，請確認本地伺服器已啟動。';
    paySubmit.disabled = false;
  });
});
