import frappe
from frappe.utils import flt
from frappe import _

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