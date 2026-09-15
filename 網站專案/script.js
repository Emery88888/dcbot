const checkoutForm = document.getElementById('checkout-form');
const planSelect = document.getElementById('plan');
const quantitySelect = document.getElementById('quantity');
const priceNotice = document.getElementById('price-notice');

function planPrice(plan) {
  if (plan === '1Y') return 1188;
  return 99;
}

function maxQuantityForPlan(plan) {
  return plan === '1Y' ? 2 : 20;
}

function updateAmount() {
  const plan = planSelect.value;
  const maxQuantity = maxQuantityForPlan(plan);
  const requestedQuantity = Number(quantitySelect.value || 1);
  const quantity = Math.max(1, Math.min(maxQuantity, requestedQuantity));
  const amount = planPrice(plan) * quantity;
  quantitySelect.value = quantity;
  if (priceNotice) priceNotice.textContent = `${amount}U`;
}

if (planSelect) planSelect.addEventListener('change', updateAmount);
if (quantitySelect) quantitySelect.addEventListener('change', updateAmount);
updateAmount();

if (checkoutForm) {
  checkoutForm.addEventListener('submit', function (event) {
    event.preventDefault();
    const plan = planSelect.value;
    const maxQuantity = maxQuantityForPlan(plan);
    const quantity = Math.max(1, Math.min(maxQuantity, Number(quantitySelect.value || 1)));
    const amount = planPrice(plan) * quantity;
    const params = new URLSearchParams({ plan, quantity, amount });
    window.location.href = `payment.html?${params.toString()}`;
  });
}
