// Copyright (c) 2026, Geetab Technologies and contributors
// For license information, please see license.txt

frappe.query_reports["Item Price Analysis"] = {
	filters: [
		{
			"fieldname": "item_group",
			"label": __("Item Group"),
			"fieldtype": "Link",
			"options": "Item Group",
		},
		{
			"fieldname": "price_list",
			"label": __("Price List"),
			"fieldtype": "Link",
			"options": "Price List",
			"description": __("If set, compare only this selling Price List against Standard Buying."),
		},
	],
};
