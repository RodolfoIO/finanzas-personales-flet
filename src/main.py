from __future__ import annotations

from datetime import date, datetime

import flet as ft

from importers import import_file
from store import DataStore

BG = "#F7F8FC"
INK = "#172033"
MUTED = "#475467"
PRIMARY = "#5B55D9"
GREEN = "#18A66B"
RED = "#E45757"
CARD = "#FFFFFF"


def money(value: float) -> str:
    return f"Q {value:,.2f}"


def month_label(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y-%m").strftime("%B %Y").capitalize()
    except ValueError:
        return value


def card(content: ft.Control, width: int | None = None) -> ft.Container:
    return ft.Container(content=content, bgcolor=CARD, border_radius=18, padding=20, width=width, shadow=ft.BoxShadow(blur_radius=18, color="#16000000", offset=ft.Offset(0, 4)))


def main(page: ft.Page):
    store = DataStore()
    current_month = date.today().strftime("%Y-%m")
    selected_section = {"value": "dashboard"}
    content = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=20)
    month_picker = ft.Dropdown(width=160, label="Periodo", value=current_month, options=[], color=INK, text_style=ft.TextStyle(color=INK), label_style=ft.TextStyle(color=MUTED), hint_style=ft.TextStyle(color=MUTED))
    file_picker = ft.FilePicker()

    page.title = "Pulso financiero"
    page.bgcolor = BG
    page.padding = 0
    page.theme = ft.Theme(color_scheme_seed=PRIMARY, font_family="Inter")

    def toast(message: str, color: str = INK):
        page.show_dialog(ft.SnackBar(ft.Text(message), bgcolor=color, duration=3000))

    def navigate(section: str):
        selected_section["value"] = section
        render()

    def nav_item(icon: str, label: str, section: str):
        active = selected_section["value"] == section
        return ft.Container(content=ft.Row([ft.Icon(icon, color=PRIMARY if active else MUTED), ft.Text(label, color=PRIMARY if active else INK, weight=ft.FontWeight.W_600 if active else ft.FontWeight.NORMAL)], spacing=14), padding=ft.Padding.symmetric(horizontal=16, vertical=12), border_radius=12, bgcolor="#EEEDFF" if active else None, on_click=lambda _: navigate(section))

    def header(title: str, subtitle: str):
        selector = month_picker if selected_section["value"] in ("dashboard", "transactions", "budgets") else ft.Container()
        return ft.Row([ft.Column([ft.Text(title, size=28, weight=ft.FontWeight.BOLD, color=INK), ft.Text(subtitle, color=MUTED)], spacing=3, expand=True), selector], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    def refresh_month_options():
        months = {current_month}
        for row in store.transactions():
            months.add(row["transaction_date"][:7])
        month_picker.options = [ft.DropdownOption(key=month, text=month_label(month)) for month in sorted(months, reverse=True)]
        if not month_picker.value:
            month_picker.value = current_month

    def stat(title: str, value: str, detail: str, color: str):
        return card(ft.Column([ft.Row([ft.Text(title, color=MUTED, size=13), ft.Icon(ft.Icons.TRENDING_UP, color=color, size=18)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), ft.Text(value, size=25, weight=ft.FontWeight.BOLD, color=INK), ft.Text(detail, color=color, size=12)], spacing=8), width=230)

    def dashboard():
        month = month_picker.value or current_month
        summary = store.summary(month)
        categories = store.categories()
        budget_total = sum(row["monthly_budget"] for row in categories)
        budget_used = summary["expenses"] / budget_total if budget_total else 0
        category_rows = []
        for category in categories:
            spent = summary["by_category"].get(category["name"], 0)
            progress = min(spent / category["monthly_budget"], 1) if category["monthly_budget"] else 0
            category_rows.append(ft.Column([ft.Row([ft.Text(category["name"], size=13, color=INK, expand=True), ft.Text(f"{money(spent)} / {money(category['monthly_budget'])}", size=12, color=MUTED)]), ft.ProgressBar(value=progress, color=category["color"], bgcolor="#ECEEF3", bar_height=8, border_radius=8)], spacing=5))
        recent = store.transactions(month, limit=6)
        recent_rows = [transaction_row(row, compact=True) for row in recent] or [ft.Text("Todavía no hay movimientos en este periodo.", color=MUTED)]
        return [header("Resumen financiero", "Tu control presupuestario, actualizado con cada movimiento."), ft.Row([stat("Gastos del mes", money(summary["expenses"]), f"{summary['count']} movimientos", RED), stat("Ingresos", money(summary["income"]), "Entradas registradas", GREEN), stat("Disponible", money(summary["balance"]), "Ingresos menos gastos", PRIMARY), stat("Presupuesto usado", f"{budget_used:.0%}", f"de {money(budget_total)}", PRIMARY)], wrap=True, spacing=14), ft.Row([card(ft.Column([ft.Text("Presupuesto por categoría", size=18, weight=ft.FontWeight.BOLD, color=INK), ft.Divider(height=8, color="#EEF0F4"), *category_rows], spacing=15), width=510), card(ft.Column([ft.Row([ft.Text("Últimos movimientos", size=18, weight=ft.FontWeight.BOLD, color=INK), ft.TextButton("Ver todos", on_click=lambda _: navigate("transactions"))], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), *recent_rows], spacing=10), width=510)], wrap=True, spacing=14)]

    def transaction_row(row: dict, compact: bool = False):
        amount_color = RED if row["amount"] > 0 else GREEN
        sign = "-" if row["amount"] > 0 else "+"
        category_name = row.get("category_name") or "Sin clasificar"
        subcategory_name = row.get("subcategory_name")
        classification = f"{category_name} · {subcategory_name}" if subcategory_name else category_name
        if compact:
            return ft.Container(ft.Row([ft.Container(width=10, height=10, bgcolor=row.get("category_color") or MUTED, border_radius=10), ft.Column([ft.Text(row["description"][:45], color=INK, weight=ft.FontWeight.W_500), ft.Text(f"{row['transaction_date']} · {row['account_name']} · {classification}", size=11, color=MUTED)], expand=True), ft.Text(f"{sign}{money(abs(row['amount']))}", color=amount_color, weight=ft.FontWeight.BOLD)], spacing=10), padding=ft.Padding.symmetric(vertical=8))
        options = [ft.DropdownOption(key="", text="Sin clasificar")] + [ft.DropdownOption(key=c["id"], text=c["name"]) for c in store.categories()]
        category_dropdown = ft.Dropdown(value=row["category_id"] or "", options=options, width=155, dense=True, color=INK, text_style=ft.TextStyle(color=INK), label_style=ft.TextStyle(color=MUTED))
        subcategory_options = [ft.DropdownOption(key="", text="Sin subcategoría")] + [ft.DropdownOption(key=s["id"], text=s["name"]) for s in store.subcategories(row["category_id"])] if row.get("category_id") else [ft.DropdownOption(key="", text="Selecciona categoría")]
        subcategory_dropdown = ft.Dropdown(value=row.get("subcategory_id") or "", options=subcategory_options, width=165, dense=True, color=INK, text_style=ft.TextStyle(color=INK), label_style=ft.TextStyle(color=MUTED), disabled=not row.get("category_id"))

        def change_category(e):
            category_id = e.control.value or None
            store.update_transaction_classification(row["id"], category_id, None)
            render()

        def change_subcategory(e):
            store.update_transaction_classification(row["id"], row.get("category_id"), e.control.value or None)
            render()

        category_dropdown.on_select = change_category
        subcategory_dropdown.on_select = change_subcategory
        return ft.DataRow(cells=[ft.DataCell(ft.Text(row["transaction_date"], size=12, color=MUTED)), ft.DataCell(ft.Column([ft.Text(row["description"][:48], color=INK), ft.Text(row["account_name"], color=MUTED, size=11)])), ft.DataCell(category_dropdown), ft.DataCell(subcategory_dropdown), ft.DataCell(ft.Text(f"{sign}{money(abs(row['amount']))}", color=amount_color, weight=ft.FontWeight.BOLD))])

    def transactions_page():
        month = month_picker.value or current_month
        rows = store.transactions(month)
        search = ft.TextField(label="Buscar movimiento", prefix_icon=ft.Icons.SEARCH, expand=True, color=INK, text_style=ft.TextStyle(color=INK), label_style=ft.TextStyle(color=MUTED), hint_style=ft.TextStyle(color=MUTED))
        table = ft.DataTable(columns=[ft.DataColumn(ft.Text("Fecha", color=INK, weight=ft.FontWeight.BOLD)), ft.DataColumn(ft.Text("Descripción", color=INK, weight=ft.FontWeight.BOLD)), ft.DataColumn(ft.Text("Categoría", color=INK, weight=ft.FontWeight.BOLD)), ft.DataColumn(ft.Text("Subcategoría", color=INK, weight=ft.FontWeight.BOLD)), ft.DataColumn(ft.Text("Monto", color=INK, weight=ft.FontWeight.BOLD))], rows=[], heading_row_color="#F5F6FA", data_text_style=ft.TextStyle(color=INK), heading_text_style=ft.TextStyle(color=INK, weight=ft.FontWeight.BOLD))

        def filter_rows(_, update=True):
            term = (search.value or "").lower()
            table.rows = [transaction_row(row) for row in rows if term in row["description"].lower() or term in (row.get("category_name") or "").lower() or term in (row.get("subcategory_name") or "").lower()]
            if update:
                # Actualiza el árbol de la página, no la tabla directamente.
                # La vista puede haber sido reemplazada al navegar a otra sección.
                page.update()

        search.on_change = filter_rows
        filter_rows(None, update=False)
        return [header("Movimientos", "Clasifica, revisa e importa los consumos de tus cuentas y tarjetas."), ft.Row([search, ft.FilledButton("Importar archivo", icon=ft.Icons.UPLOAD_FILE, on_click=lambda _: open_import_dialog()), ft.FilledButton("Nuevo movimiento", icon=ft.Icons.ADD, on_click=lambda _: open_transaction_dialog())], spacing=10), card(ft.Column([ft.Row([ft.Text(f"{len(rows)} movimientos en {month_label(month)}", weight=ft.FontWeight.BOLD, color=INK), ft.Text("Los cambios se guardan automáticamente", color=MUTED, size=12)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), ft.Row([table], scroll=ft.ScrollMode.AUTO)], spacing=15))]

    def budgets_page():
        month = month_picker.value or current_month
        summary = store.summary(month)
        controls = []
        for category in store.categories():
            budget = ft.TextField(value=str(category["monthly_budget"]), prefix="Q ", width=140, keyboard_type=ft.KeyboardType.NUMBER)
            spent = summary["by_category"].get(category["name"], 0)

            def save(e, category_id=category["id"], field=budget):
                try:
                    store.save_budget(category_id, float((field.value or "0").replace(",", "")))
                    toast("Presupuesto actualizado", GREEN)
                    render()
                except ValueError:
                    toast("Ingresa un monto válido", RED)

            controls.append(ft.Row([ft.Container(width=12, height=12, bgcolor=category["color"], border_radius=12), ft.Text(category["name"], expand=True, color=INK), ft.Text(f"Gastado: {money(spent)}", color=MUTED, size=12), budget, ft.IconButton(icon=ft.Icons.SAVE_OUTLINED, tooltip="Guardar", on_click=save)], spacing=12))
        return [header("Presupuestos", "Define límites mensuales y observa el avance por categoría."), card(ft.Column([ft.Text(f"Presupuesto de {month_label(month)}", size=18, weight=ft.FontWeight.BOLD, color=INK), ft.Divider(height=8, color="#EEF0F4"), *controls], spacing=14))]

    def accounts_page():
        account_cards = []
        all_transactions = store.transactions()
        for account in store.accounts():
            total = sum(row["amount"] for row in all_transactions if row["account_id"] == account["id"])
            account_cards.append(card(ft.Column([ft.Row([ft.Icon(ft.Icons.CREDIT_CARD if account["account_type"] == "tarjeta" else ft.Icons.ACCOUNT_BALANCE, color=PRIMARY), ft.Text(account["name"], size=17, weight=ft.FontWeight.BOLD, color=INK, expand=True)]), ft.Text(account["institution"] or "Institución no definida", color=MUTED), ft.Text(money(total), size=24, weight=ft.FontWeight.BOLD, color=INK), ft.Text(f"{account['account_type'].capitalize()} · {account['currency']}", color=MUTED, size=12)], spacing=9), width=300))
        status_color = GREEN if store.remote.enabled else MUTED
        return [header("Cuentas y tarjetas", "Agrega todas tus cuentas y tarjetas con el nombre que quieras."), ft.Row([ft.Row([ft.FilledButton("Nueva cuenta", icon=ft.Icons.ACCOUNT_BALANCE_OUTLINED, on_click=lambda _: open_account_dialog("cuenta")), ft.FilledButton("Nueva tarjeta", icon=ft.Icons.CREDIT_CARD, on_click=lambda _: open_account_dialog("tarjeta"))], spacing=10), ft.Container(expand=True), ft.Container(content=ft.Row([ft.Icon(ft.Icons.CLOUD_DONE, color=status_color), ft.Text(store.backend_label, color=MUTED, size=12)]), padding=10, bgcolor="#ECFDF5" if store.remote.enabled else "#F1F3F6", border_radius=10)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), ft.Row(account_cards, wrap=True, spacing=14) if account_cards else ft.Text("Agrega tu primera cuenta o tarjeta para comenzar.", color=MUTED)]

    def open_account_dialog(default_type: str = "cuenta"):
        is_card = default_type == "tarjeta"
        name = ft.TextField(label="Nombre visible", hint_text="Tarjeta BAC Platinum" if is_card else "Cuenta BAC principal")
        institution = ft.TextField(label="Banco o institución", hint_text="BAC, G&T...")
        kind = ft.Dropdown(label="Tipo", value=default_type, options=[ft.DropdownOption(key="cuenta", text="Cuenta bancaria"), ft.DropdownOption(key="tarjeta", text="Tarjeta de crédito")])

        def close_dialog():
            dialog.open = False
            page.update()

        def save(e):
            if not name.value:
                name.error_text = "Requerido"
                name.update()
                return
            try:
                store.add_account(name.value, institution.value or "", kind.value or "cuenta")
            except ValueError as error:
                name.error_text = str(error)
                name.update()
                return
            close_dialog()
            render()

        dialog = ft.AlertDialog(modal=True, title=ft.Text("Agregar cuenta o tarjeta"), content=ft.Column([name, institution, kind], tight=True, spacing=12), actions=[ft.TextButton("Cancelar", on_click=lambda _: close_dialog()), ft.FilledButton("Guardar", on_click=save)])
        page.show_dialog(dialog)

    def open_transaction_dialog():
        description = ft.TextField(label="Descripción", autofocus=True)
        amount = ft.TextField(label="Monto", prefix="Q ", keyboard_type=ft.KeyboardType.NUMBER)
        account = ft.Dropdown(label="Cuenta o tarjeta", options=[ft.DropdownOption(key=a["id"], text=a["name"]) for a in store.accounts()])
        kind = ft.Dropdown(label="Tipo", value="expense", options=[ft.DropdownOption(key="expense", text="Gasto"), ft.DropdownOption(key="income", text="Ingreso")])

        def close_dialog():
            dialog.open = False
            page.update()

        def save(e):
            try:
                value = float((amount.value or "0").replace(",", ""))
                if kind.value == "income":
                    value = -abs(value)
                if not description.value or not account.value:
                    raise ValueError
                store.add_transaction({"account_id": account.value, "transaction_date": date.today().isoformat(), "description": description.value, "amount": value, "transaction_type": kind.value})
                close_dialog()
                render()
            except ValueError:
                toast("Completa descripción, cuenta y monto válido", RED)

        dialog = ft.AlertDialog(modal=True, title=ft.Text("Nuevo movimiento"), content=ft.Column([description, amount, account, kind], tight=True, spacing=12), actions=[ft.TextButton("Cancelar", on_click=lambda _: close_dialog()), ft.FilledButton("Guardar", on_click=save)])
        page.show_dialog(dialog)

    def open_import_dialog():
        account = ft.Dropdown(label="Importar a", options=[ft.DropdownOption(key=a["id"], text=a["name"]) for a in store.accounts()])
        help_text = ft.Text("Formatos: CSV de BAC (cuenta o tarjeta) y TXT tabulado de G&T.", size=12, color=MUTED)

        def close_dialog():
            dialog.open = False
            page.update()

        def choose(e):
            if not account.value:
                toast("Selecciona una cuenta destino", RED)
                return
            file_picker.data = account.value
            file_picker.pick_files(allow_multiple=False, allowed_extensions=["csv", "txt"])
            close_dialog()

        dialog = ft.AlertDialog(modal=True, title=ft.Text("Importar movimientos"), content=ft.Column([account, help_text], tight=True, spacing=12), actions=[ft.TextButton("Cancelar", on_click=lambda _: close_dialog()), ft.FilledButton("Seleccionar archivo", on_click=choose)])
        page.show_dialog(dialog)

    def file_result(e: ft.FilePickerResultEvent):
        if not e.files:
            return
        imported, skipped = import_file(e.files[0].path, file_picker.data, store)
        toast(f"Importados {imported} movimientos; omitidos {skipped} duplicados o sin monto.", GREEN)
        render()

    file_picker.on_result = file_result
    month_picker.on_select = lambda _: render()

    def render():
        refresh_month_options()
        if selected_section["value"] == "dashboard":
            controls = dashboard()
        elif selected_section["value"] == "transactions":
            controls = transactions_page()
        elif selected_section["value"] == "budgets":
            controls = budgets_page()
        else:
            controls = accounts_page()
        content.controls = controls
        page.update()

    sidebar = ft.Container(ft.Column([ft.Container(ft.Row([ft.Container(width=38, height=38, bgcolor=PRIMARY, border_radius=12, content=ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET, color="white")), ft.Column([ft.Text("Pulso", size=19, weight=ft.FontWeight.BOLD, color=INK), ft.Text("financiero", size=11, color=MUTED)], spacing=0)]), padding=ft.Padding.only(left=6, bottom=32)), nav_item(ft.Icons.DASHBOARD_OUTLINED, "Resumen", "dashboard"), nav_item(ft.Icons.SWAP_VERT, "Movimientos", "transactions"), nav_item(ft.Icons.PIE_CHART_OUTLINE, "Presupuestos", "budgets"), nav_item(ft.Icons.ACCOUNT_BALANCE_OUTLINED, "Cuentas", "accounts"), ft.Container(expand=True), ft.Container(ft.Column([ft.Text("Persistencia activa", size=12, weight=ft.FontWeight.BOLD, color=INK), ft.Text(store.backend_label, size=11, color=MUTED)], spacing=3), bgcolor="#F0F1F6", border_radius=12, padding=14)], expand=True, spacing=6), width=220, bgcolor=CARD, padding=ft.Padding.only(left=18, right=18, top=28, bottom=24))
    page.add(ft.Row([sidebar, ft.Container(content=content, expand=True, padding=ft.Padding.only(left=34, right=34, top=30, bottom=30))], expand=True, spacing=0))
    render()


if __name__ == "__main__":
    ft.run(main)
