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

// 動態從伺服器取得方案中文名稱
(async function() {
  try {
    var res = await fetch(API_BASE + '/api/plans');
    var d = await res.json();
    if (d.ok && Array.isArray(d.plans)) {
      var found = d.plans.find(function(p) { return p.id === plan; });
      if (found) {
        document.getElementById('sum-plan').textContent = found.name;
      }
    }
  } catch (e) {}
})();

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

// --- 優惠碼 / 推薦碼即時驗證折抵 ---
var refInput = document.getElementById('f-ref');
var discountNote = document.getElementById('discount-note');
var applyPromoBtn = document.getElementById('apply-promo-btn');
var appliedPromoCode = '';
var promoDebounceTimer = null;

// 清理與正規化優惠碼（全形轉半形、移除空白、轉大寫）
function cleanPromoCode(str) {
  if (!str) return '';
  return str
    .replace(/[\uff01-\uff5e]/g, function(ch) {
      return String.fromCharCode(ch.charCodeAt(0) - 0xfee0);
    })
    .replace(/\u3000/g, ' ')
    .trim()
    .toUpperCase();
}

async function verifyPromo() {
  if (!refInput) return;
  var code = cleanPromoCode(refInput.value);
  refInput.value = code; // 自動把欄位正規化為大寫半形

  if (!code) {
    appliedPromoCode = '';
    finalAmount = baseAmount;
    document.getElementById('sum-amount').textContent = finalAmount + 'U';
    if (discountNote) discountNote.textContent = '';
    return;
  }
  if (discountNote) {
    discountNote.style.color = '#70f3ff';
    discountNote.textContent = '驗證優惠碼中...';
  }
  try {
    var res = await fetch(API_BASE + '/api/promo/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: code, amount: baseAmount, plan: plan, quantity: quantity })
    });
    var d = await res.json();
    if (d.ok && d.valid) {
      appliedPromoCode = d.code;
      finalAmount = d.final_amount;
      document.getElementById('sum-amount').innerHTML = finalAmount + 'U <small style="color:#8affb4;">(已折抵 ' + d.discount + 'U)</small>';
      if (discountNote) {
        discountNote.style.color = '#8affb4';
        discountNote.textContent = '✅ ' + d.message;
      }
    } else {
      appliedPromoCode = '';
      finalAmount = baseAmount;
      document.getElementById('sum-amount').textContent = finalAmount + 'U';
      if (discountNote) {
        discountNote.style.color = '#ffb86c';
        discountNote.textContent = '❌ ' + (d.message || '無效或已停用的優惠碼');
      }
    }
  } catch(err) {
    if (discountNote) {
      discountNote.style.color = '#ffb86c';
      discountNote.textContent = '驗證失敗，無法連線至伺服器';
    }
  }
}

if (applyPromoBtn) {
  applyPromoBtn.addEventListener('click', verifyPromo);
}
if (refInput) {
  // 輸入時停止 600ms 自動觸發驗證，使用者不需要手動點套用
  refInput.addEventListener('input', function() {
    clearTimeout(promoDebounceTimer);
    var code = cleanPromoCode(refInput.value);
    if (!code) {
      appliedPromoCode = '';
      finalAmount = baseAmount;
      document.getElementById('sum-amount').textContent = finalAmount + 'U';
      if (discountNote) discountNote.textContent = '';
      return;
    }
    promoDebounceTimer = setTimeout(verifyPromo, 600);
  });

  // 離開輸入框時自動驗證
  refInput.addEventListener('blur', verifyPromo);

  refInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      clearTimeout(promoDebounceTimer);
      verifyPromo();
    }
  });
}

// --- 截圖上傳預覽與 Base64 轉換 ---
var screenshotInput = document.getElementById('screenshot-input');
var uploadLabel     = document.getElementById('upload-label');
var uploadHint      = document.getElementById('upload-hint');
var screenshotBase64 = '';

screenshotInput.addEventListener('change', function() {
  if (this.files && this.files[0]) {
    var file = this.files[0];
    uploadHint.textContent = '已選擇：' + file.name;
    uploadLabel.classList.add('has-file');

    // 壓縮並轉為 Base64
    var reader = new FileReader();
    reader.onload = function(e) {
      var img = new Image();
      img.onload = function() {
        var canvas = document.createElement('canvas');
        var maxW = 1200;
        var maxH = 1200;
        var w = img.width;
        var h = img.height;
        if (w > maxW || h > maxH) {
          if (w > h) {
            h = Math.round((h * maxW) / w);
            w = maxW;
          } else {
            w = Math.round((w * maxH) / h);
            h = maxH;
          }
        }
        canvas.width = w;
        canvas.height = h;
        var ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, w, h);
        screenshotBase64 = canvas.toDataURL('image/jpeg', 0.8);
      };
      img.src = e.target.result;
    };
    reader.readAsDataURL(file);
  }
});

// --- 表單提交 ---
var payForm    = document.getElementById('pay-form');
var payMessage = document.getElementById('pay-message');
var paySubmit  = document.getElementById('pay-submit');
var successBox = document.getElementById('success-box');

payForm.addEventListener('submit', async function(e) {
  e.preventDefault();
  var name   = document.getElementById('f-name').value.trim();
  var dcName = document.getElementById('f-dc').value.trim();
  var refCode = refInput ? cleanPromoCode(refInput.value) : '';

  // 若使用者填了優惠碼但尚未點套用，送出前自動為其驗證
  if (refCode && !appliedPromoCode) {
    await verifyPromo();
  }

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
  if (!screenshotBase64) {
    payMessage.style.color = '#ffcf89';
    payMessage.textContent = '請上傳交易紀錄截圖。';
    return;
  }

  paySubmit.disabled = true;
  payMessage.style.color = '#8affb4';
  payMessage.textContent = '送出中，請稍候...';

  try {
    var resp = await fetch(API_BASE + '/api/orders', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: name,
        contact: dcName,
        plan: plan,
        quantity: quantity,
        network: selectedChain,
        group: 'https://discord.gg/JvFTfFY5KZ',
        referral: appliedPromoCode || refCode || null,
        screenshot: screenshotBase64
      })
    });
    var d = await resp.json();
    if (!resp.ok || !d.ok) {
      payMessage.style.color = '#ffcf89';
      payMessage.textContent = d.message || '送出失敗，請稍後再試。';
      paySubmit.disabled = false;
      return;
    }

    payMessage.textContent = '';
    payForm.style.display = 'none';
    document.getElementById('suc-order-id').textContent = '訂單編號：' + d.order_id;
    successBox.classList.add('show');
  } catch(err) {
    payMessage.style.color = '#ffcf89';
    payMessage.textContent = '無法連線到伺服器，請確認伺服器已啟動。';
    paySubmit.disabled = false;
  }
});
