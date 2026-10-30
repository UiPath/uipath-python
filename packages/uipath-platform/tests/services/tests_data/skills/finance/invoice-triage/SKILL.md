---
name: invoice-triage
description: Classify an incoming invoice, match it to a purchase order and route exceptions. Use when the task mentions invoices, purchase orders or vendor bills.
---

# Invoice triage

Follow these steps in order. Stop and escalate at the first unrecoverable mismatch.

1. **Identify the vendor.** If the vendor is not already confirmed, load and follow the `vendor-lookup` skill first.
2. **Find the purchase order.** Call the agent's purchase-order tool with the PO number from the invoice. If the invoice has no PO number, search by vendor and amount within ±2 %.
3. **Match line items.** Compare quantity and unit price per line. Tolerances: quantity exact, price ±1 %.
4. **Classify.**
   - All lines match → `approved`
   - One line outside tolerance → `exception:price` or `exception:quantity`
   - No PO found → `exception:no-po`
5. **Route.** Approved invoices go to the payment queue. Exceptions go to the escalation tool with the classification, the invoice id and the specific line.
6. **Report.** Return the classification, the PO number (or `none`) and a one-line reason.

Never approve an invoice above 10,000 without a matching PO, even if the vendor is trusted.

See `reference/vendors.md` for the vendor normalization table.
