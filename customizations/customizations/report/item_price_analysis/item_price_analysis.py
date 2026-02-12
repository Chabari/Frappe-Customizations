# Copyright (c) 2026, Geetab Technologies and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe import _
from frappe.utils import flt


def execute(filters: dict | None = None):
	"""Return columns and data for the report.

	This is the main entry point for the report. It accepts the filters as a
	dictionary and should return columns and data. It is called by the framework
	every time the report is refreshed or a filter is updated.
	"""
	# discover selling price lists (Price List.doctype has `selling` flag)
	# allow override from filters.price_list (compare only one selling price list)
	if filters and filters.get("price_list"):
		selling_names = [filters.get("price_list")]
	else:
		selling_pls = frappe.get_all("Price List", filters={"selling": 1}, fields=["name"], order_by="name")
		selling_names = [p.name for p in selling_pls]

	columns = get_columns(selling_names)
	data = get_data(selling_names, filters)

	return columns, data


def get_columns(selling_price_lists: list[str]) -> list[dict]:
	"""Return columns for the report.

	One field definition per column, just like a DocType field definition.
	"""
	cols = [
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item",},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data",},
		{"label": _("Standard Buying"), "fieldname": "standard_buying", "fieldtype": "Float",},
	]

	# Add a column per selling price list (e.g. Standard Selling, Wholesale)
	for pl in selling_price_lists:
		# fieldname safe key
		fieldname = f"pl_{frappe.scrub(pl)}"
		cols.append({
			"label": _(pl),
			"fieldname": fieldname,
			"fieldtype": "Float",
		})

	return cols


def get_data(selling_price_lists: list[str], filters: dict | None = None) -> list[dict]:
	"""Return rows where any selling price is <= Standard Buying.

	Rows are dicts keyed by column fieldnames produced in `get_columns`.
	"""
	rows: list[dict] = []

	# fetch items that have a Standard Buying price
	sql = """
		SELECT ip.item_code, ip.price_list_rate AS standard_buying, i.item_name
		FROM `tabItem Price` ip
		JOIN `tabItem` i ON i.name = ip.item_code
		WHERE ip.price_list = %s
	"""
	params: list = ["Standard Buying"]

	# filter by Item Group if provided
	if filters and filters.get("item_group"):
		sql += " AND i.item_group = %s"
		params.append(filters.get("item_group"))

	std_buying = frappe.db.sql(sql, tuple(params), as_dict=1)

	if not std_buying:
		return rows

	# prepare selling price lists placeholder
	selling_names = selling_price_lists or []

	for rec in std_buying:
		item_code = rec.item_code
		try:
			standard_buying = flt(rec.standard_buying)
		except Exception:
			standard_buying = flt(0)

		# skip if no selling price lists defined
		if not selling_names:
			continue

		# fetch minimum selling rate per price list for this item (some price lists may have multiple rows)
		if not selling_names:
			selling_rates = []
		else:
			in_clause = ",".join(["%s"] * len(selling_names))
			query = f"SELECT price_list, MIN(price_list_rate) AS rate FROM `tabItem Price` WHERE item_code=%s AND price_list IN ({in_clause}) GROUP BY price_list"
			params = [item_code] + selling_names
			selling_rates = frappe.db.sql(query, tuple(params), as_dict=1)

		# map price_list -> rate
		rate_map = {r.price_list: flt(r.rate) for r in selling_rates}

		# determine if any selling rate is <= standard_buying
		below_or_equal = False
		for pl in selling_names:
			rate = rate_map.get(pl)
			if rate is not None and rate <= standard_buying:
				below_or_equal = True
				break

		if not below_or_equal:
			continue

		# compose row
		row = {
			"item_code": item_code,
			"item_name": rec.item_name,
			"standard_buying": standard_buying,
		}

		for pl in selling_names:
			fieldname = f"pl_{frappe.scrub(pl)}"
			row[fieldname] = rate_map.get(pl) if rate_map.get(pl) is not None else None

		rows.append(row)

	return rows
