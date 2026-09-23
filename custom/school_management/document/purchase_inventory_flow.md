# Native Purchase and Inventory Flow

This guide documents Odoo 19's native procurement workflow for university operations:

```text
RFQ -> Purchase Order -> Receipt -> Vendor Bill -> Payment
```

Use this flow for school supplies, laboratory equipment, library materials, furniture, and other goods purchased from vendors. It is separate from student enrollment and the addon’s lightweight student fee workflow.

## Required native apps

Install and configure these standard Odoo apps in the database:

| App | Purpose |
|---|---|
| Purchase | Vendors, requests for quotation, purchase orders, and purchase order lines |
| Inventory | Warehouses, incoming operations, receipts, stock moves, and on-hand quantities |
| Accounting | Vendor bills, payable entries, payments, and reconciliation |

The `school_management` manifest does not depend on these apps. Installing them is an administrator decision for the database, and does not require adding duplicate models to this addon.

## Initial configuration

Before creating an RFQ, an administrator should verify:

1. The company has a warehouse and an incoming receipt operation type.
2. The vendor exists as a contact with vendor information and payment terms.
3. Each item exists as a product with the correct product type, unit of measure, purchase taxes, vendor, and cost.
4. Products that must update stock are configured as storable goods according to the installed Odoo 19 Inventory configuration.
5. Inventory valuation, stock accounts, taxes, fiscal positions, and the chart of accounts are configured for the company.
6. Purchase users, inventory users, and accounting users have the required access rights.

For a laboratory purchase, for example, create the vendor, create products such as microscopes or reagents, and set the appropriate warehouse, taxes, expense or stock accounts, and units of measure before requesting prices.

## Step 1: Create and send an RFQ

Open **Purchase -> Orders -> Requests for Quotation** and create a new request:

1. Select the vendor.
2. Set the order deadline and expected delivery date when applicable.
3. Add product lines with quantities, units of measure, and agreed or requested prices.
4. Review taxes, currency, payment terms, and delivery address.
5. Save the RFQ and use **Send by Email** when the vendor should receive the request.

The RFQ is represented by `purchase.order` in the draft or sent state. Its lines are `purchase.order.line`. At this stage no purchase commitment has been confirmed and no receipt should be validated.

## Step 2: Confirm the purchase order

After the vendor accepts the quotation, open the RFQ and select **Confirm Order**. Odoo changes the document into a purchase order and generates the related incoming logistics operation when the order lines require receipt.

The purchase order remains the commercial source document. Its purchase lines carry the product, ordered quantity, price, taxes, and received or billed quantities used by later steps.

Use the purchase order’s **Receipt** smart button or the related delivery operation to open the incoming transfer.

## Step 3: Receive and validate the goods

Open **Inventory -> Operations -> Receipts** or the receipt linked from the purchase order:

1. Confirm the source document, vendor, warehouse, and destination location.
2. Enter the actual quantities received. Record partial quantities when the vendor delivers in stages.
3. Record lots or serial numbers when product tracking requires them.
4. Record damaged, missing, or backordered quantities using the appropriate operation or backorder flow.
5. Select **Validate** after the physical receipt has been checked.

The receipt is represented by `stock.picking`; its detailed operations and movements use `stock.move` and the related stock move line records. Validation completes the stock movement and updates on-hand inventory according to the configured routes and valuation settings.

Do not validate a receipt merely because the purchase order is confirmed. The receipt represents physical goods received by the university.

## Step 4: Create and post the vendor bill

Return to the confirmed purchase order and select **Create Bill** after the vendor invoice is available. Odoo creates a draft vendor bill in Accounting:

1. Review the vendor, invoice date, accounting date, currency, taxes, payment terms, and invoice lines.
2. Check that billed quantities agree with the company’s purchase and invoicing policy.
3. Add the vendor invoice reference and attach the source document when required.
4. Select **Confirm** or **Post** only after the accounting review is complete.

The vendor bill is an `account.move` with vendor-bill type and `account.move.line` lines. Posting creates the payable accounting entry. A posted bill is paid through the normal Accounting payment flow and reconciled with the payable entry.

The receipt and the vendor bill are separate controls:

- Inventory confirms what physically arrived.
- Accounting confirms what the vendor invoiced.
- The purchase order connects the commercial agreement to both records.

Depending on product and company configuration, invoicing may be based on ordered quantities or received quantities. Review the purchase and product invoicing policy before posting a bill for a partial delivery.

## Native model relationship

```text
res.partner (vendor)
        |
        v
purchase.order (RFQ / purchase order)
        |
        +--> purchase.order.line
        |
        +--> stock.picking (incoming receipt)
        |       |
        |       +--> stock.move / stock.move.line
        |
        +--> account.move (vendor bill)
                |
                +--> account.move.line
```

The normal lifecycle is:

| Business stage | Native record | Expected outcome |
|---|---|---|
| Request prices | `purchase.order` | RFQ is draft or sent |
| Commit purchase | `purchase.order` | RFQ is confirmed as a purchase order |
| Receive goods | `stock.picking` | Receipt is validated and stock moves are done |
| Record supplier invoice | `account.move` | Vendor bill is posted after review |
| Settle payable | Accounting payment | Payment is posted and reconciled |

### Technical states

The common native values behind the workflow are:

| Model | Relevant values | Meaning in this flow |
|---|---|---|
| `purchase.order.state` | `draft`, `sent`, `to approve`, `purchase`, `cancel` | RFQ, sent RFQ, approval step when enabled, confirmed purchase order, or cancelled |
| `stock.picking.state` | `draft`, `waiting`, `confirmed`, `assigned`, `done`, `cancel` | Receipt is being prepared, waiting on upstream moves, confirmed, ready, validated, or cancelled |
| `account.move.move_type` / `state` | `in_invoice` / `draft`, `posted`, `cancel` | Vendor bill before review, posted payable entry, or cancelled bill |

The visible labels can vary with translation and configuration, so use the technical values when troubleshooting logs, domains, or integrations.

## Relationship to this project

The native procurement flow is organizational purchasing. It does not create or confirm an academic enrollment.

| University process | Current project records |
|---|---|
| Academic registration | `university.enrollment` and enrollment wizards |
| Student charges | `university.fee` and `university.fee.line` |
| Student payments | `university.payment` |
| Vendor procurement | Native `purchase.order`, `stock.picking`, and `account.move` |

For example, purchasing laboratory equipment should use the native Purchase and Inventory apps. It should not create a `university.enrollment`, student fee, or student payment unless a separate business requirement is designed and approved.

## Roles and hand-off

- **Purchase user:** prepares RFQs, compares vendor offers, and confirms approved purchase orders.
- **Inventory user:** receives physical goods, records quantities and tracking details, and validates receipts.
- **Accounting user:** checks taxes and accounts, creates or reviews vendor bills, posts bills, and reconciles payments.
- **Manager or approver:** approves the commercial commitment according to the company’s purchase approval policy.

Keep the commercial, physical, and accounting checks separate when possible. A single user may perform more than one role in a small local database, but the documents should still be reviewed in that order.

## Troubleshooting

### No receipt is generated

Check that the product is configured for stock receipt, the purchase order has a warehouse and incoming operation type, and the order line is not a service or configuration that does not require inventory movement.

### The receipt quantity cannot be validated

Check the received quantity, units of measure, lot or serial tracking, destination location, and backorder or split-operation details.

### The bill has the wrong quantity

Review the product’s purchase and invoicing policy, the quantities received on the receipt, and any existing vendor bills for the purchase order.

### Taxes or accounts are missing

Configure the product category, product, vendor fiscal position, taxes, accounts, and company chart of accounts. Accounting users should correct the draft bill before posting it.

### The project finance menus do not show native purchasing

Confirm that the Purchase, Inventory, and Accounting apps are installed in the database and that the user has the corresponding Odoo access groups. The `school_management` addon’s own Finance menu remains the student fee and payment workflow.

## Verification checklist

Use a test vendor and a low-value test product to verify the complete path:

- RFQ is created and sent.
- RFQ is confirmed into a purchase order.
- Incoming receipt is generated.
- Partial or full receipt is recorded and validated.
- On-hand quantity changes as expected.
- Vendor bill is created from the purchase order.
- Bill is reviewed and posted.
- Payment is posted and reconciled.
- The student enrollment and student fee records remain unchanged.
