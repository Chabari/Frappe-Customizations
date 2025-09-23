app_name = "customizations"
app_title = "Customizations"
app_publisher = "Geetab Technologies"
app_description = "Custom Updates"
app_email = "geetabtechnologies@gmail.com"
app_license = "mit"

jinja = {
	"methods": [
		"customizations.api.get_customer_balance",
	],
}

doc_events = {
    "Sales Order": {
        "before_submit": "customizations.api.before_order_submit",
    },
    "Item Price": {
		"on_update": "customizations.api.update_price_list_rate",
	},
    "Purchase Receipt": {
        "before_submit": "customizations.api.before_receipt_submit",
    },
    "Sales Invoice": {
        "before_print": "customizations.api.prevent_reprint"
    },
}

fixtures = [
   
    {
        "doctype": "Custom Field",
        "filters": [
            [
                "name",
                "in",
                (
                    "Sales Invoice-custom_first_printed"                    
                ),
            ]
        ],
    },
    
]
