from collections import defaultdict
import pandas as pd
import click
import csv

from regex import P

XERO_BILL_IMPORT_FIELDS = [
    "*ContactName",
    "EmailAddress",
    "POAddressLine1",
    "POAddressLine2",
    "POAddressLine3",
    "POAddressLine4",
    "POCity",
    "PORegion",
    "POPostalCode",
    "POCountry",
    "*InvoiceNumber",
    "*InvoiceDate",
    "*DueDate",
    "Total",
    "InventoryItemCode",
    "Description",
    "*Quantity",
    "*UnitAmount",
    "*AccountCode",
    "*TaxType",
    "TaxAmount",
    "TrackingName1",
    "TrackingOption1",
    "TrackingName2",
    "TrackingOption2",
    "Currency",
]


def get_account_code(dept):
    return {
        "EMF SHOP": "314",
        "volunteer kitchen": "383",
        "Youth": "379",
        "Team Design": "389",
    }.get(dept, "325")


@click.command()
@click.option("--invoice", help="Output for specific invoice ID only")
@click.argument("shipments_file", type=click.File("r"))
@click.argument("output_file", type=click.File("w"))
def amazon_to_xero(shipments_file, output_file, invoice):
    """SHIPMENTS_FILE is the shipments report exported from Amazon Business, with cancelled items hidden."""
    data = pd.read_csv(shipments_file, parse_dates=["Order Date"], dayfirst=True)
    data = data[data["Delivery status"] == "Delivered"]

    if invoice:
        order_ids = [invoice]
    else:
        order_ids = data["Order ID"].unique()

    total = total_vat = 0
    output_rows = []

    totals = defaultdict(float)
    dates = {}

    for order_id in order_ids:
        lines = data[data["Order ID"] == order_id]
        for _, line in lines.iterrows():
            if line["Item subtotal sum"] < 0:
                click.secho(f"Negative item balance: {line}")
                return
            line_data = {
                "*ContactName": "Amazon",
                "*InvoiceNumber": line["Order ID"],
                "*InvoiceDate": line["Order Date"].strftime("%d/%m/%Y"),
                "*DueDate": line["Order Date"].strftime("%d/%m/%Y"),
                "*Quantity": 1,
                "*UnitAmount": round(line["Item subtotal sum"], 2),
                "*AccountCode": get_account_code(line["Customised Field"]),
                "Description": line["Title"],
                "TaxAmount": round(line["Item VAT"], 2),
            }

            total += line["Item subtotal sum"]
            total_vat += line["Item VAT"]

            totals[line["Order ID"]] += line["Item subtotal sum"] + line["Item VAT"]
            dates[line["Order ID"]] = line["Order Date"]

            if line["Item VAT"] > 0:
                line_data["*TaxType"] = "20% (VAT on Expenses)"
            else:
                line_data["*TaxType"] = "Zero Rated Expenses"

            output_rows.append(line_data)

    for invoice_id, total in totals.items():
        output_rows.append(
            {
                "*ContactName": "Amazon",
                "*InvoiceNumber": invoice_id,
                "*InvoiceDate": dates[invoice_id].strftime("%d/%m/%Y"),
                "*DueDate": dates[invoice_id].strftime("%d/%m/%Y"),
                "*Quantity": 1,
                "*UnitAmount": round(-total, 2),
                "*AccountCode": "812",
                "Description": f"Amazon Order {invoice_id}",
                "*TaxType": "No VAT",
            }
        )

    output_rows = sorted(
        output_rows,
        key=lambda row: (row["*InvoiceDate"], row["*InvoiceNumber"]),
        reverse=True,
    )
    writer = csv.DictWriter(output_file, fieldnames=XERO_BILL_IMPORT_FIELDS)
    writer.writeheader()
    writer.writerows(output_rows)

    click.secho(
        f"Total £{round(total, 2)} + £{round(total_vat, 2)} VAT = £{round(total + total_vat, 2)}",
        fg="green",
    )
    click.secho(
        "You should check the above numbers match your outstanding account balance.",
        fg="yellow",
    )


if __name__ == "__main__":
    amazon_to_xero()
