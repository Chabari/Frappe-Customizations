import frappe
from frappe.utils import flt
from frappe import _
from frappe.model.mapper import map_doc, map_child_doc
import math

def get_customer_balance(customer):
    try:
        customer_doc = frappe.get_doc("Customer", customer)
        customer_name = customer_doc.customer_name

        # Fetch outstanding balance from GL Entries
        balance = frappe.db.sql("""
            SELECT SUM(debit - credit) AS balance
            FROM `tabGL Entry`
            WHERE party_type = 'Customer' AND party = %s AND docstatus = 1
        """, (customer,), as_dict=True)

        return {
            "balance": flt(balance[0].get("balance", 0)) if balance else 0,
            "customer_name": customer_name
        }
    except Exception as e:
        frappe.log_error(f"Error fetching customer balance: {e}")
        return {"balance": 0, "customer_name": None}
    
def before_order_submit(doc, method):
    if doc.get("reserve_stock"):
        from erpnext.stock.doctype.stock_reservation_entry.stock_reservation_entry import (
            get_available_qty_to_reserve, get_sre_reserved_qty_details_for_voucher
        )
        from erpnext.selling.doctype.sales_order.sales_order import get_unreserved_qty
        reserved_qty_details = get_sre_reserved_qty_details_for_voucher("Sales Order", doc.name)
        for item in doc.get("items"):
            unreserved_qty = get_unreserved_qty(item, reserved_qty_details)
            available_qty_to_reserve = get_available_qty_to_reserve(item.item_code, item.warehouse)

            # No stock available to reserve, notify the user and skip the item.
            if available_qty_to_reserve <= 0:
                frappe.throw(_("Row #{0}: Stock not available to reserve for the Item {1} in Warehouse {2}. Available {3}").format(
                        item.idx, frappe.bold(item.item_code), frappe.bold(item.warehouse), frappe.bold(str(available_qty_to_reserve))
                    ))
            
            if available_qty_to_reserve < item.get('qty'):
                frappe.throw(_("Row #{0}: Stock not enough to reserve for the Item {1} in Warehouse {2}. Available {3}").format(
                        item.idx, frappe.bold(item.item_code), frappe.bold(item.warehouse), frappe.bold(str(available_qty_to_reserve))
                    ))
                
def update_price_list_rate(doc, method):
    price_list = doc.price_list
    if(price_list == "Standard Buying"):
        new_price = doc.price_list_rate
        item_code = doc.item_code
        update_tables(new_price, item_code)
        

def update_tables(new_price, item_code):
    return
    price_lists = frappe.get_all(
        "Price List", 
        fields=['custom_percentage_markup', 'name'],
        filters={"selling": 1}
    )
    for pr in price_lists:
        if pr.custom_percentage_markup:
            new_price_rate = ((pr.custom_percentage_markup / 100) * float(new_price)) + float(new_price)
            new_price_rate = 10 * int(math.ceil( new_price_rate / 10.0))
            query = f"""UPDATE `tabItem Price` SET price_list_rate='{new_price_rate}' WHERE item_code='{item_code}' AND price_list='{pr.name}' """
            frappe.db.sql(query)
            
def before_receipt_submit(doc, method):
    for itm in doc.items:
        new_price = itm.rate
        item_code = itm.item_code
        x_price = frappe.db.get_value('Item Price', {'item_code': item_code, 'price_list': 'Standard Buying'}, ['price_list_rate'], as_dict=1)
        if x_price and float(x_price.price_list_rate) != float(new_price):
            update_tables(new_price, item_code)
            
def prevent_reprint(doc, method=None, meth = None):
    user = frappe.session.user
    if "Reprint Invoice" in frappe.get_roles(user):
        return
    if doc.get("custom_first_printed"):
        return
        # frappe.throw("This Invoice has already been printed. Only System Manager can reprint.")
    # doc.db_set("custom_first_printed", 1)
    # frappe.db.commit()
    query = f"""UPDATE `tabSales Invoice` SET custom_first_printed=1 WHERE name='{doc.name}' """
    frappe.db.sql(query)


def create_sales_invoice_from_pos(doc, method):
    """Create a Sales Invoice automatically when a POS Invoice is submitted."""

    # Skip return invoices — handle them separately if needed
    if doc.get("is_return"):
        return

    try:
        si = frappe.new_doc("Sales Invoice")

        # Map header fields from POS Invoice → Sales Invoice
        map_doc(doc, si, table_map={"doctype": si.doctype})

        # Override key flags
        si.is_pos = doc.is_pos
        si.is_consolidated = 0
        si.set_posting_time = 1
        si.posting_date = doc.posting_date
        si.posting_time = doc.posting_time
        si.due_date = doc.due_date
        si.pos_profile = doc.pos_profile
        si.payments = doc.payments
        si.update_stock = doc.update_stock

        # Link back to the originating POS Invoice
        # si.pos_invoice = doc.name

        # ── Items ──
        si_items = []
        for item in doc.get("items", []):
            si_item = map_child_doc(item, si, {"doctype": "Sales Invoice Item"})
            si_item.pos_invoice = doc.name
            si_item.pos_invoice_item = item.name
            si_items.append(si_item)
        si.set("items", si_items)

        # ── Taxes ──
        si_taxes = []
        for tax in doc.get("taxes", []):
            si_tax = map_child_doc(tax, si, {"doctype": "Sales Taxes and Charges"})
            si_taxes.append(si_tax)
        si.set("taxes", si_taxes)

        # ── Sales Team ──
        si_team = []
        for member in doc.get("sales_team", []):
            si_member = map_child_doc(member, si, {"doctype": "Sales Team"})
            si_team.append(si_member)
        si.set("sales_team", si_team)

        si.flags.ignore_permissions = True
        frappe.flags.ignore_account_permission = True
        si.posa_is_printed = 1
        si.save()
        si.submit()

        frappe.msgprint(
            _("Sales Invoice {0} created from POS Invoice {1}").format(
                frappe.bold(si.name), frappe.bold(doc.name)
            ),
            alert=True,
        )

    except Exception:
        frappe.log_error(
            title=_("Auto Sales Invoice Creation Failed"),
            message=frappe.get_traceback(),
        )
        frappe.msgprint(
            _("Failed to create Sales Invoice from POS Invoice {0}. Check Error Log.").format(doc.name),
            alert=True,
            indicator="red",
        )