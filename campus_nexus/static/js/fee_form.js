(function () {
  const SUB_FIELDS = [
    "duration_months",
    "grace_days",
    // "reminder_days_before_due",
    "max_missed_cycles",
    "allow_installments",
  ];

  function findFieldContainer(fieldName) {
    const input = document.getElementById("id_" + fieldName);

    // Jazzmin/Django usually renders a wrapper with class: field-<field_name>
    // This is the best reliable container to hide.
    const byClass = document.querySelector(".field-" + fieldName);
    if (byClass) return byClass;

    // Fallbacks
    if (!input) return null;
    return (
      input.closest(".form-group") ||
      input.closest(".row") ||
      input.closest("div") ||
      input.parentElement
    );
  }

  function setVisible(fieldName, visible) {
    const container = findFieldContainer(fieldName);
    if (!container) return;

    container.style.display = visible ? "" : "none";

    // Disable input when hidden to avoid confusion / accidental submit values
    const input = document.getElementById("id_" + fieldName);
    if (input) input.disabled = !visible;
  }

  function setSubFieldsVisible(visible) {
    SUB_FIELDS.forEach((f) => setVisible(f, visible));
  }

  function ensureHint() {
    const feeTypeContainer =
      document.querySelector(".field-fee_type") ||
      (document.getElementById("id_fee_type") || {}).closest?.(".form-group");

    if (!feeTypeContainer) return;

    if (!document.getElementById("fee_type_hint")) {
      const hint = document.createElement("div");
      hint.id = "fee_type_hint";
      hint.style.marginTop = "6px";
      hint.style.opacity = "0.85";
      hint.style.fontSize = "0.9rem";
      hint.style.lineHeight = "1.25rem";
      feeTypeContainer.appendChild(hint);
    }
  }

  function apply() {
    const feeType = document.getElementById("id_fee_type");
    if (!feeType) return;

    const isSubscription = feeType.value === "subscription";
    setSubFieldsVisible(isSubscription);

    const hint = document.getElementById("fee_type_hint");
    if (hint) {
      hint.innerText = isSubscription
        ? "Subscription selected: configure cycle, grace period, reminders and enforcement below."
        : "Membership selected: subscription policy fields are hidden (not required).";
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    ensureHint();
    apply();

    const feeType = document.getElementById("id_fee_type");
    if (feeType) feeType.addEventListener("change", apply);
  });
})();
