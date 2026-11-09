from __future__ import annotations

from datetime import date, datetime
import unicodedata

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
WEEKDAYS = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")


def money(value: float) -> str:
    return f"Q {value:,.2f}"


def month_label(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y-%m").strftime("%B %Y").capitalize()
    except ValueError:
        return value


def transaction_day(value: str) -> str:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
        return WEEKDAYS[parsed.weekday()]
    except ValueError:
        return ""


def normalize_search_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    without_accents = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(without_accents.lower().split())


def card(content: ft.Control, width: int | None = None) -> ft.Container:
    return ft.Container(content=content, bgcolor=CARD, border_radius=18, padding=20, width=width, shadow=ft.BoxShadow(blur_radius=18, color="#16000000", offset=ft.Offset(0, 4)))


def main(page: ft.Page):
    store = DataStore()
    current_month = date.today().strftime("%Y-%m")
    selected_section = {"value": "dashboard"}
    transaction_filters = {"account_id": "", "category_id": "", "subcategory_id": ""}
    dashboard_selection = {"category_id": "", "subcategory_id": ""}
    content = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=20)
    month_picker = ft.Dropdown(width=160, label="Periodo", value=current_month, options=[], color=INK, text_style=ft.TextStyle(color=INK), label_style=ft.TextStyle(color=MUTED), hint_style=ft.TextStyle(color=MUTED))
    file_picker = ft.FilePicker()

    page.title = "Pulso financiero"
    page.bgcolor = BG
    page.padding = 0
    page.theme = ft.Theme(color_scheme_seed=PRIMARY, font_family="Inter")

    def toast(message: str, color: str = INK):
        page.show_dialog(ft.SnackBar(ft.Text(message), bgcolor=color, duration=3000))

    def dialog_text_field(**kwargs):
        return ft.TextField(color=INK, text_style=ft.TextStyle(color=INK), label_style=ft.TextStyle(color=MUTED), hint_style=ft.TextStyle(color=MUTED), border_color="#98A2B3", focused_border_color=PRIMARY, **kwargs)

    def dialog_dropdown(**kwargs):
        return ft.Dropdown(color=INK, text_style=ft.TextStyle(color=INK), label_style=ft.TextStyle(color=MUTED), border_color="#98A2B3", focused_border_color=PRIMARY, **kwargs)

    def light_dialog(title: str, content: ft.Control, actions: list[ft.Control]):
        return ft.AlertDialog(modal=True, bgcolor=CARD, barrier_color="#66000000", title=ft.Text(title, color=INK, weight=ft.FontWeight.BOLD), content=content, actions=actions, title_text_style=ft.TextStyle(color=INK, weight=ft.FontWeight.BOLD), content_text_style=ft.TextStyle(color=INK))

    def cancel_button(on_click):
        return ft.TextButton("Cancelar", style=ft.ButtonStyle(color=INK), on_click=on_click)

    def sync_status(noun: str):
        if not store.remote.enabled:
            return f"{noun} guardada localmente. Supabase no está configurado."
        if store.last_sync_error:
            return f"{noun} guardada localmente, pero no se pudo subir a Supabase: {store.last_sync_error}"
        return f"{noun} guardada y sincronizada con Supabase."

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

    def select_dashboard_category(category_id: str):
        dashboard_selection["category_id"] = category_id
        dashboard_selection["subcategory_id"] = ""
        render()

    def select_dashboard_subcategory(subcategory_id: str):
        dashboard_selection["subcategory_id"] = subcategory_id
        render()

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
            category_rows.append(ft.Container(ft.Column([ft.Row([ft.Text(category["name"], size=13, color=INK, expand=True), ft.Text(f"{money(spent)} / {money(category['monthly_budget'])}", size=12, color=MUTED)]), ft.ProgressBar(value=progress, color=category["color"], bgcolor="#ECEEF3", bar_height=8, border_radius=8)], spacing=5), padding=8, border_radius=8, bgcolor="#EEEDFF" if dashboard_selection["category_id"] == category["id"] else None, on_click=lambda _, category_id=category["id"]: select_dashboard_category(category_id)))

        selected_category = next((category for category in categories if category["id"] == dashboard_selection["category_id"]), None)
        selected_subcategories = store.subcategories(selected_category["id"]) if selected_category else []
        selected_subcategory = next((item for item in selected_subcategories if item["id"] == dashboard_selection["subcategory_id"]), None)
        if dashboard_selection["subcategory_id"] and not selected_subcategory:
            dashboard_selection["subcategory_id"] = ""
        month_rows = store.transactions(month)
        subcategory_rows = []
        detail_title = "Subcategorías"
        detail_subtitle = "Selecciona una categoría para ver cómo se distribuyen sus gastos."
        movement_rows = []
        if selected_category:
            detail_title = selected_category["name"]
            category_transactions = [row for row in month_rows if row.get("category_id") == selected_category["id"]]
            category_spent = sum(row["amount"] for row in category_transactions if row["amount"] > 0 and row["transaction_type"] == "expense")
            detail_subtitle = f"Gasto del periodo: {money(category_spent)}"
            for subcategory in selected_subcategories:
                subcategory_transactions = [row for row in category_transactions if row.get("subcategory_id") == subcategory["id"]]
                subcategory_spent = sum(row["amount"] for row in subcategory_transactions if row["amount"] > 0 and row["transaction_type"] == "expense")
                subcategory_rows.append(ft.Container(ft.Row([ft.Text(subcategory["name"], color=INK, expand=True), ft.Text(money(subcategory_spent), color=INK, weight=ft.FontWeight.BOLD), ft.Text(f"{len(subcategory_transactions)} mov.", color=MUTED, size=11)], spacing=10), padding=ft.Padding.symmetric(vertical=8, horizontal=6), border_radius=8, bgcolor="#EEEDFF" if selected_subcategory and selected_subcategory["id"] == subcategory["id"] else None, on_click=lambda _, subcategory_id=subcategory["id"]: select_dashboard_subcategory(subcategory_id)))
            if not subcategory_rows:
                subcategory_rows = [ft.Text("Esta categoría todavía no tiene subcategorías.", color=MUTED)]
            if selected_subcategory:
                subcategory_transactions = [row for row in category_transactions if row.get("subcategory_id") == selected_subcategory["id"]]
                subcategory_spent = sum(row["amount"] for row in subcategory_transactions if row["amount"] > 0 and row["transaction_type"] == "expense")
                movement_rows = [transaction_row(row, compact=True) for row in subcategory_transactions] or [ft.Text("No hay movimientos asociados en este periodo.", color=MUTED)]

        panel_width = max(320, min(510, int(((page.width or 1200) - 100) / (3 if selected_subcategory else 2))))
        subcategory_card = card(ft.Column([ft.Row([ft.Column([ft.Text(detail_title, size=18, weight=ft.FontWeight.BOLD, color=INK), ft.Text(detail_subtitle, color=MUTED, size=12)], spacing=2, expand=True), ft.TextButton("Ver movimientos", on_click=lambda _: navigate("transactions"))], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), ft.Divider(height=8, color="#EEF0F4"), *subcategory_rows], spacing=10), width=panel_width)
        dashboard_cards = [card(ft.Column([ft.Text("Presupuesto por categoría", size=18, weight=ft.FontWeight.BOLD, color=INK), ft.Text("Haz clic en una categoría para ver sus subcategorías", color=MUTED, size=12), ft.Divider(height=8, color="#EEF0F4"), *category_rows], spacing=15), width=panel_width), subcategory_card]
        if selected_subcategory:
            movement_card = card(ft.Column([ft.Text(f"Movimientos de {selected_subcategory['name']}", size=18, weight=ft.FontWeight.BOLD, color=INK), ft.Text(f"Gasto del periodo: {money(subcategory_spent)}", color=MUTED, size=12), ft.Divider(height=8, color="#EEF0F4"), *movement_rows], spacing=10), width=panel_width)
            dashboard_cards.append(movement_card)
        return [header("Resumen financiero", "Tu control presupuestario, actualizado con cada movimiento."), ft.Row([stat("Gastos del mes", money(summary["expenses"]), f"{summary['count']} movimientos", RED), stat("Ingresos", money(summary["income"]), "Entradas registradas", GREEN), stat("Disponible", money(summary["balance"]), "Ingresos menos gastos", PRIMARY), stat("Presupuesto usado", f"{budget_used:.0%}", f"de {money(budget_total)}", PRIMARY)], wrap=True, spacing=14), ft.Row(dashboard_cards, wrap=True, spacing=14)]

    def transaction_row(row: dict, compact: bool = False):
        type_labels = {"expense": ("Gasto", "#FEF3F2", RED), "income": ("Ingreso", "#ECFDF3", GREEN), "transfer": ("Transferencia", "#EEEDFF", PRIMARY)}
        type_label, type_bg, type_color = type_labels.get(row["transaction_type"], (row["transaction_type"], "#F1F3F6", MUTED))
        type_badge = ft.Container(ft.Text(type_label, color=type_color, size=11, weight=ft.FontWeight.BOLD), bgcolor=type_bg, border_radius=12, padding=ft.Padding.symmetric(horizontal=10, vertical=6), alignment=ft.Alignment(0, 0), width=115)
        if row["transaction_type"] == "transfer":
            route = f"{row['account_name']} → {row.get('destination_account_name') or 'Destino'}"
            detail = row.get("notes") or row["description"]
            if compact:
                return ft.Container(ft.Row([ft.Icon(ft.Icons.SWAP_HORIZ, color=PRIMARY), ft.Column([ft.Text(row["description"][:45], color=INK, weight=ft.FontWeight.W_500), ft.Text(f"{row['transaction_date']} · {route} · {detail}", size=11, color=MUTED)], expand=True), ft.Text(money(abs(row["amount"])), color=PRIMARY, weight=ft.FontWeight.BOLD)], spacing=10), padding=ft.Padding.symmetric(vertical=8))
            amount_cell = ft.Container(ft.Text(money(abs(row["amount"])), color=PRIMARY, weight=ft.FontWeight.BOLD), width=125, alignment=ft.Alignment(1, 0))
            return ft.DataRow(cells=[ft.DataCell(ft.Text(row["transaction_date"], color=INK)), ft.DataCell(ft.Column([ft.Text(row["description"], color=INK), ft.Text(route, color=MUTED, size=11)], spacing=2)), ft.DataCell(type_badge), ft.DataCell(ft.Text("Sin categoría", color=MUTED)), ft.DataCell(ft.Text(detail, color=MUTED, size=11)), ft.DataCell(amount_cell), ft.DataCell(ft.IconButton(icon=ft.Icons.EDIT_OUTLINED, tooltip="Editar movimiento", on_click=lambda _: open_transaction_dialog(row)))])
        amount_color = RED if row["amount"] > 0 else GREEN
        sign = "-" if row["amount"] > 0 else "+"
        category_name = row.get("category_name") or "Sin clasificar"
        subcategory_name = row.get("subcategory_name")
        classification = f"{category_name} · {subcategory_name}" if subcategory_name else category_name
        suggestion = store.suggest_classification(row["description"]) if not row.get("category_id") else None
        if compact:
            return ft.Container(ft.Row([ft.Container(width=10, height=10, bgcolor=row.get("category_color") or MUTED, border_radius=10), ft.Column([ft.Text(row["description"][:45], color=INK, weight=ft.FontWeight.W_500), ft.Text(f"{row['transaction_date']} · {row['account_name']} · {classification}", size=11, color=MUTED)], expand=True), ft.Text(f"{sign}{money(abs(row['amount']))}", color=amount_color, weight=ft.FontWeight.BOLD)], spacing=10), padding=ft.Padding.symmetric(vertical=8))
        options = [ft.DropdownOption(key="", text="Sin clasificar")] + [ft.DropdownOption(key=c["id"], text=c["name"]) for c in store.categories()]
        category_dropdown = ft.Dropdown(value=row["category_id"] or "", options=options, width=155, dense=True, color=INK, text_style=ft.TextStyle(color=INK), label_style=ft.TextStyle(color=MUTED))
        subcategory_options = [ft.DropdownOption(key="", text="Sin subcategoría")] + [ft.DropdownOption(key=s["id"], text=s["name"]) for s in store.subcategories(row["category_id"])] if row.get("category_id") else [ft.DropdownOption(key="", text="Selecciona categoría")]
        subcategory_dropdown = ft.Dropdown(value=row.get("subcategory_id") or "", options=subcategory_options, width=165, dense=True, color=INK, text_style=ft.TextStyle(color=INK), label_style=ft.TextStyle(color=MUTED), filled=not row.get("subcategory_id"), fill_color="#26F59E0B" if not row.get("subcategory_id") else None, disabled=not row.get("category_id"))

        def change_category(e):
            category_id = e.control.value or None
            store.update_transaction_classification(row["id"], category_id, None)
            render()

        def change_subcategory(e):
            store.update_transaction_classification(row["id"], row.get("category_id"), e.control.value or None)
            render()

        category_dropdown.on_select = change_category
        subcategory_dropdown.on_select = change_subcategory
        date_cell = ft.Container(ft.Column([ft.Text(row["transaction_date"], size=14, color=INK, weight=ft.FontWeight.BOLD), ft.Text(transaction_day(row["transaction_date"]), size=11, color=MUTED)], spacing=1), width=125)
        description_lines = [ft.Text(row["description"][:70], color=INK), ft.Text(row["account_name"], color=MUTED, size=11)]
        if suggestion:
            suggestion_category = next((category["name"] for category in store.categories() if category["id"] == suggestion["category_id"]), "")
            suggestion_subcategory = next((item["name"] for item in store.subcategories(suggestion["category_id"]) if item["id"] == suggestion["subcategory_id"]), "") if suggestion.get("subcategory_id") else ""
            suggestion_text = f"Sugerencia: {suggestion_category}{' · ' + suggestion_subcategory if suggestion_subcategory else ''}"
            description_lines.append(ft.Text(suggestion_text, color=PRIMARY, size=10, italic=True))
        description_cell = ft.Container(ft.Column(description_lines, spacing=2), width=max(310, int((page.width or 1200) * 0.27)))
        amount_cell = ft.Container(ft.Text(f"{sign}{money(abs(row['amount']))}", color=amount_color, weight=ft.FontWeight.BOLD), width=125, alignment=ft.Alignment(1, 0))
        return ft.DataRow(cells=[ft.DataCell(date_cell), ft.DataCell(description_cell), ft.DataCell(type_badge), ft.DataCell(category_dropdown), ft.DataCell(subcategory_dropdown), ft.DataCell(amount_cell), ft.DataCell(ft.IconButton(icon=ft.Icons.EDIT_OUTLINED, tooltip="Editar movimiento", on_click=lambda _: open_transaction_dialog(row)))])

    def transactions_page():
        month = month_picker.value or current_month
        rows = store.transactions(month)
        search = ft.TextField(label="Buscar movimiento", prefix_icon=ft.Icons.SEARCH, expand=True, color=INK, text_style=ft.TextStyle(color=INK), label_style=ft.TextStyle(color=MUTED), hint_style=ft.TextStyle(color=MUTED))
        account_filter = ft.Dropdown(label="Cuenta o tarjeta", value=transaction_filters["account_id"], width=190, options=[ft.DropdownOption(key="", text="Todas las cuentas")] + [ft.DropdownOption(key=account["id"], text=account["name"]) for account in store.accounts()], color=INK, text_style=ft.TextStyle(color=INK), label_style=ft.TextStyle(color=MUTED), border_color="#98A2B3", focused_border_color=PRIMARY, dense=True)
        category_filter = ft.Dropdown(label="Categoría", value=transaction_filters["category_id"], width=175, options=[ft.DropdownOption(key="", text="Todas las categorías")] + [ft.DropdownOption(key=category["id"], text=category["name"]) for category in store.categories()], color=INK, text_style=ft.TextStyle(color=INK), label_style=ft.TextStyle(color=MUTED), border_color="#98A2B3", focused_border_color=PRIMARY, dense=True)
        selected_category = transaction_filters["category_id"]
        subcategory_options = [ft.DropdownOption(key="", text="Todas las subcategorías")]
        available_subcategories = store.subcategories(selected_category) if selected_category else store.subcategories()
        subcategory_options += [ft.DropdownOption(key=subcategory["id"], text=subcategory["name"] if selected_category else f"{subcategory['category_name']} · {subcategory['name']}") for subcategory in available_subcategories]
        if transaction_filters["subcategory_id"] and not any(option.key == transaction_filters["subcategory_id"] for option in subcategory_options):
            transaction_filters["subcategory_id"] = ""
        subcategory_filter = ft.Dropdown(label="Subcategoría", value=transaction_filters["subcategory_id"], width=185, options=subcategory_options, color=INK, text_style=ft.TextStyle(color=INK), label_style=ft.TextStyle(color=MUTED), border_color="#98A2B3", focused_border_color=PRIMARY, dense=True)
        description_width = max(310, int((page.width or 1200) * 0.27))
        table = ft.DataTable(columns=[ft.DataColumn(ft.Container(ft.Text("Fecha", color=INK, weight=ft.FontWeight.BOLD), width=125)), ft.DataColumn(ft.Container(ft.Text("Descripción", color=INK, weight=ft.FontWeight.BOLD), width=description_width)), ft.DataColumn(ft.Text("Tipo", color=INK, weight=ft.FontWeight.BOLD)), ft.DataColumn(ft.Text("Categoría", color=INK, weight=ft.FontWeight.BOLD)), ft.DataColumn(ft.Text("Subcategoría", color=INK, weight=ft.FontWeight.BOLD)), ft.DataColumn(ft.Container(ft.Text("Monto", color=INK, weight=ft.FontWeight.BOLD), width=125)), ft.DataColumn(ft.Text("Acciones", color=INK, weight=ft.FontWeight.BOLD))], rows=[], heading_row_color="#F5F6FA", data_text_style=ft.TextStyle(color=INK), heading_text_style=ft.TextStyle(color=INK, weight=ft.FontWeight.BOLD), column_spacing=32, horizontal_margin=18, expand=True)
        count_text = ft.Text(color=INK, weight=ft.FontWeight.BOLD)
        def filtered_rows():
            terms = normalize_search_text(search.value or "").split()
            account_id = account_filter.value or ""
            category_id = category_filter.value or ""
            subcategory_id = subcategory_filter.value or ""
            return [
                row for row in rows
                if (not terms or all(word in normalize_search_text(" ".join(str(row.get(field) or "") for field in ("description", "notes", "account_name", "destination_account_name", "category_name", "subcategory_name", "transaction_type", "transaction_date"))) for word in terms))
                and (not account_id or row["account_id"] == account_id or row.get("destination_account_id") == account_id)
                and (not category_id or row.get("category_id") == category_id)
                and (not subcategory_id or row.get("subcategory_id") == subcategory_id)
            ]

        def filter_rows(_, update=True):
            transaction_filters["account_id"] = account_filter.value or ""
            transaction_filters["category_id"] = category_filter.value or ""
            transaction_filters["subcategory_id"] = subcategory_filter.value or ""
            matching_rows = filtered_rows()
            table.rows = [transaction_row(row) for row in matching_rows]
            count_text.value = f"{len(matching_rows)} de {len(rows)} movimientos en {month_label(month)}" if len(matching_rows) != len(rows) else f"{len(rows)} movimientos en {month_label(month)}"
            if update:
                # Actualiza el árbol de la página, no la tabla directamente.
                # La vista puede haber sido reemplazada al navegar a otra sección.
                page.update()

        def category_filter_changed(_):
            selected_category = category_filter.value or ""
            transaction_filters["category_id"] = selected_category
            options = [ft.DropdownOption(key="", text="Todas las subcategorías")]
            if selected_category:
                options += [ft.DropdownOption(key=subcategory["id"], text=subcategory["name"]) for subcategory in store.subcategories(selected_category)]
            else:
                options += [ft.DropdownOption(key=subcategory["id"], text=f"{subcategory['category_name']} · {subcategory['name']}") for subcategory in store.subcategories()]
            current_subcategory = transaction_filters["subcategory_id"]
            if current_subcategory and not any(option.key == current_subcategory for option in options):
                current_subcategory = ""
            subcategory_filter.options = options
            subcategory_filter.value = current_subcategory
            transaction_filters["subcategory_id"] = current_subcategory
            subcategory_filter.update()
            filter_rows(None)

        def clear_filters(_):
            search.value = ""
            account_filter.value = ""
            category_filter.value = ""
            subcategory_filter.value = ""
            transaction_filters.update(account_id="", category_id="", subcategory_id="")
            subcategory_filter.options = [ft.DropdownOption(key="", text="Todas las subcategorías")] + [ft.DropdownOption(key=subcategory["id"], text=f"{subcategory['category_name']} · {subcategory['name']}") for subcategory in store.subcategories()]
            filter_rows(None)

        # La búsqueda se ejecuta únicamente al enviar el campo con Enter.
        search.on_submit = filter_rows
        account_filter.on_select = filter_rows
        category_filter.on_select = category_filter_changed
        subcategory_filter.on_select = filter_rows
        filter_rows(None, update=False)
        return [header("Movimientos", "Clasifica, revisa e importa los consumos de tus cuentas y tarjetas."), ft.Row([search, ft.FilledButton("Importar archivo", icon=ft.Icons.UPLOAD_FILE, on_click=lambda _: open_import_dialog()), ft.FilledButton("Nuevo movimiento", icon=ft.Icons.ADD, on_click=lambda _: open_transaction_dialog())], spacing=10), ft.Row([account_filter, category_filter, subcategory_filter, ft.OutlinedButton("Limpiar filtros", icon=ft.Icons.CLEAR, on_click=clear_filters, style=ft.ButtonStyle(color=INK))], wrap=True, spacing=10), card(ft.Column([ft.Row([count_text, ft.Text("Los cambios se guardan automáticamente", color=MUTED, size=12)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), ft.Container(content=ft.Row([table], expand=True, scroll=ft.ScrollMode.AUTO), expand=True)], spacing=15))]

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

    def open_category_dialog(category_id: str | None = None):
        current = next((category for category in store.categories() if category["id"] == category_id), None)
        name = dialog_text_field(label="Nombre de la categoría", value=current["name"] if current else "", autofocus=True)

        def close_dialog():
            dialog.open = False
            page.update()

        def save(_):
            try:
                if category_id:
                    store.rename_category(category_id, name.value)
                else:
                    store.add_category(name.value)
                close_dialog()
                toast(sync_status("Categoría"), RED if store.last_sync_error else GREEN)
                render()
            except ValueError as error:
                name.error_text = str(error)
                name.update()

        dialog = light_dialog("Editar categoría" if category_id else "Nueva categoría", ft.Column([name], tight=True), [cancel_button(lambda _: close_dialog()), ft.FilledButton("Guardar", color="white", bgcolor=PRIMARY, on_click=save)])
        page.show_dialog(dialog)

    def open_subcategory_dialog(category_id: str, subcategory_id: str | None = None):
        current = next((subcategory for subcategory in store.subcategories(category_id) if subcategory["id"] == subcategory_id), None)
        name = dialog_text_field(label="Nombre de la subcategoría", value=current["name"] if current else "", hint_text="Ej. Supermercado", autofocus=True)

        def close_dialog():
            dialog.open = False
            page.update()

        def save(_):
            try:
                if subcategory_id:
                    store.rename_subcategory(subcategory_id, name.value)
                else:
                    store.add_subcategory(category_id, name.value)
                close_dialog()
                toast(sync_status("Subcategoría"), RED if store.last_sync_error else GREEN)
                render()
            except ValueError as error:
                name.error_text = str(error)
                name.update()

        dialog = light_dialog("Editar subcategoría" if subcategory_id else "Nueva subcategoría", ft.Column([name], tight=True), [cancel_button(lambda _: close_dialog()), ft.FilledButton("Guardar", color="white", bgcolor=PRIMARY, on_click=save)])
        page.show_dialog(dialog)

    def confirm_delete_subcategory(subcategory: dict):
        def close_dialog():
            dialog.open = False
            page.update()

        def delete(_):
            store.delete_subcategory(subcategory["id"])
            close_dialog()
            render()

        dialog = light_dialog("Eliminar subcategoría", ft.Text(f"¿Eliminar «{subcategory['name']}»? Los movimientos conservarán su categoría, pero quedarán sin subcategoría.", color=INK), [cancel_button(lambda _: close_dialog()), ft.FilledButton("Eliminar", bgcolor=RED, color="white", on_click=delete)])
        page.show_dialog(dialog)

    def categories_page():
        def sync_categories(_):
            if not store.remote.enabled:
                toast("Supabase no está configurado; los datos permanecen en SQLite local.", MUTED)
                return
            store.sync_from_supabase()
            if store.last_sync_error:
                toast(f"No se pudieron sincronizar las categorías: {store.last_sync_error}", RED)
            else:
                toast("Categorías y subcategorías sincronizadas con Supabase.", GREEN)
            render()

        category_cards = []
        for category in store.categories():
            subcategories = store.subcategories(category["id"])
            subcategory_rows = []
            for subcategory in subcategories:
                subcategory_rows.append(ft.Container(ft.Row([ft.Icon(ft.Icons.SUBDIRECTORY_ARROW_RIGHT, size=17, color=category["color"]), ft.Text(subcategory["name"], color=INK, expand=True), ft.IconButton(icon=ft.Icons.EDIT_OUTLINED, icon_color=MUTED, tooltip="Editar", on_click=lambda _, item=subcategory, parent=category: open_subcategory_dialog(parent["id"], item["id"])), ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_color=RED, tooltip="Eliminar", on_click=lambda _, item=subcategory: confirm_delete_subcategory(item))], spacing=5), padding=ft.Padding.only(left=8, top=5, bottom=5)))
            if not subcategory_rows:
                subcategory_rows = [ft.Container(ft.Row([ft.Icon(ft.Icons.WARNING_AMBER_OUTLINED, size=17, color="#9A6700"), ft.Text("Sin subcategorías todavía.", size=12, color="#7A5200", weight=ft.FontWeight.W_500)], spacing=7), bgcolor="#26F59E0B", border_radius=8, padding=ft.Padding.symmetric(horizontal=10, vertical=8))]
            category_cards.append(card(ft.Column([
                ft.Row([ft.Container(width=12, height=12, bgcolor=category["color"], border_radius=12), ft.Text(category["name"], size=18, weight=ft.FontWeight.BOLD, color=INK, expand=True), ft.IconButton(icon=ft.Icons.EDIT_OUTLINED, icon_color=MUTED, tooltip="Renombrar categoría", on_click=lambda _, item=category: open_category_dialog(item["id"]))]),
                ft.Text(f"Presupuesto mensual: {money(category['monthly_budget'])}", size=12, color=MUTED),
                ft.Divider(height=8, color="#EEF0F4"),
                *subcategory_rows,
                ft.TextButton("Agregar subcategoría", icon=ft.Icons.ADD, on_click=lambda _, item=category: open_subcategory_dialog(item["id"]))
            ], spacing=5), width=480))
        return [header("Categorías", "Organiza tus gastos con subcategorías personalizadas."), ft.Row([ft.FilledButton("Nueva categoría", icon=ft.Icons.ADD, on_click=lambda _: open_category_dialog()), ft.OutlinedButton("Sincronizar", icon=ft.Icons.SYNC, on_click=sync_categories), ft.Text("Cada categoría puede tener todas las subcategorías que necesites.", color=MUTED, size=12)], spacing=15), ft.Row(category_cards, wrap=True, spacing=14) if category_cards else ft.Text("Crea tu primera categoría para comenzar.", color=MUTED)]

    def accounts_page():
        account_cards = []
        for account in store.accounts():
            label = "Deuda" if account["account_type"] == "tarjeta" else "Saldo"
            account_cards.append(card(ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.CREDIT_CARD if account["account_type"] == "tarjeta" else ft.Icons.ACCOUNT_BALANCE, color=PRIMARY),
                    ft.Text(account["name"], size=17, weight=ft.FontWeight.BOLD, color=INK, expand=True),
                    ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_color=RED, tooltip="Eliminar cuenta", on_click=lambda _, item=account: confirm_delete_account(item)),
                ]),
                ft.Text(account["institution"] or "Institución no definida", color=MUTED),
                ft.Text(money(account["balance"]), size=24, weight=ft.FontWeight.BOLD, color=INK),
                ft.Text(f"{label} · {account['account_type'].capitalize()} · {account['currency']}", color=MUTED, size=12),
            ], spacing=9), width=300))
        status_color = GREEN if store.remote.enabled else MUTED
        return [header("Cuentas y tarjetas", "Agrega todas tus cuentas y tarjetas con el nombre que quieras."), ft.Row([ft.Row([ft.FilledButton("Nueva cuenta", icon=ft.Icons.ACCOUNT_BALANCE_OUTLINED, on_click=lambda _: open_account_dialog("cuenta")), ft.FilledButton("Nueva tarjeta", icon=ft.Icons.CREDIT_CARD, on_click=lambda _: open_account_dialog("tarjeta"))], spacing=10), ft.Container(expand=True), ft.Container(content=ft.Row([ft.Icon(ft.Icons.CLOUD_DONE, color=status_color), ft.Text(store.backend_label, color=MUTED, size=12)]), padding=10, bgcolor="#ECFDF5" if store.remote.enabled else "#F1F3F6", border_radius=10)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), ft.Row(account_cards, wrap=True, spacing=14) if account_cards else ft.Text("Agrega tu primera cuenta o tarjeta para comenzar.", color=MUTED)]

    def confirm_delete_account(account: dict):
        movement_count = store.account_transaction_count(account["id"])
        movement_label = "movimiento" if movement_count == 1 else "movimientos"

        def close_dialog():
            dialog.open = False
            page.update()

        def delete(_):
            try:
                deleted_count = store.delete_account(account["id"])
            except (RuntimeError, ValueError) as error:
                toast(str(error), RED)
                return
            close_dialog()
            toast(f"Se eliminó «{account['name']}» y {deleted_count} {movement_label}.", GREEN)
            render()

        dialog = light_dialog(
            "Eliminar cuenta o tarjeta",
            ft.Text(
                f"¿Eliminar «{account['name']}»? Se borrará la cuenta y sus {movement_count} {movement_label}. "
                "Esta acción es permanente y no se puede deshacer.",
                color=INK,
            ),
            [cancel_button(lambda _: close_dialog()), ft.FilledButton("Eliminar", bgcolor=RED, color="white", on_click=delete)],
        )
        page.show_dialog(dialog)

    def open_account_dialog(default_type: str = "cuenta"):
        is_card = default_type == "tarjeta"
        name = dialog_text_field(label="Nombre visible", hint_text="Tarjeta BAC Platinum" if is_card else "Cuenta BAC principal")
        institution = dialog_text_field(label="Banco o institución", hint_text="BAC, G&T...")
        kind = dialog_dropdown(label="Tipo", value=default_type, options=[ft.DropdownOption(key="cuenta", text="Cuenta bancaria"), ft.DropdownOption(key="tarjeta", text="Tarjeta de crédito")])

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

        dialog = light_dialog("Agregar cuenta o tarjeta", ft.Column([name, institution, kind], tight=True, spacing=12), [cancel_button(lambda _: close_dialog()), ft.FilledButton("Guardar", color="white", bgcolor=PRIMARY, on_click=save)])
        page.show_dialog(dialog)

    def open_transaction_dialog(transaction: dict | None = None):
        editing = transaction is not None
        description = dialog_text_field(label="Descripción", value=(transaction or {}).get("description", ""), autofocus=True)
        notes = dialog_text_field(label="Notas o detalle", value=(transaction or {}).get("notes", ""), hint_text="Pago de tarjeta Visa, fondo de ahorro...", visible=False)
        amount = dialog_text_field(label="Monto", prefix="Q ", value=str(abs((transaction or {}).get("amount", ""))) if editing else "", keyboard_type=ft.KeyboardType.NUMBER)
        transaction_date = dialog_text_field(label="Fecha", value=(transaction or {}).get("transaction_date", date.today().isoformat()))
        accounts = store.accounts()
        account = dialog_dropdown(label="Cuenta o tarjeta", value=(transaction or {}).get("account_id", ""), options=[ft.DropdownOption(key=a["id"], text=a["name"]) for a in accounts])
        destination = dialog_dropdown(label="Cuenta destino", value=(transaction or {}).get("destination_account_id", ""), options=[ft.DropdownOption(key=a["id"], text=a["name"]) for a in accounts], visible=False)
        category = dialog_dropdown(label="Categoría", value=(transaction or {}).get("category_id", "") or "", options=[ft.DropdownOption(key="", text="Sin clasificar")] + [ft.DropdownOption(key=c["id"], text=c["name"]) for c in store.categories()])
        initial_subcategories = store.subcategories(category.value) if category.value else []
        subcategory = dialog_dropdown(label="Subcategoría", value=(transaction or {}).get("subcategory_id", "") or "", options=[ft.DropdownOption(key="", text="Sin subcategoría")] + [ft.DropdownOption(key=s["id"], text=s["name"]) for s in initial_subcategories], disabled=not bool(category.value))
        kind = dialog_dropdown(label="Tipo", value=(transaction or {}).get("transaction_type", "expense"), options=[ft.DropdownOption(key="expense", text="Gasto"), ft.DropdownOption(key="income", text="Ingreso"), ft.DropdownOption(key="transfer", text="Transferencia")])
        initial_transfer = kind.value == "transfer"
        destination.visible = initial_transfer
        category.visible = not initial_transfer
        subcategory.visible = not initial_transfer
        notes.visible = initial_transfer

        def kind_changed(_):
            is_transfer = kind.value == "transfer"
            destination.visible = is_transfer
            category.visible = not is_transfer
            subcategory.visible = not is_transfer
            notes.visible = is_transfer
            if is_transfer:
                category.value = ""
                subcategory.value = ""
            destination.update()
            category.update()
            subcategory.update()
            notes.update()

        kind.on_select = kind_changed

        def category_changed(_):
            selected_category = category.value or ""
            subcategory.options = [ft.DropdownOption(key="", text="Sin subcategoría")] + [ft.DropdownOption(key=item["id"], text=item["name"]) for item in store.subcategories(selected_category)] if selected_category else [ft.DropdownOption(key="", text="Selecciona una categoría")]
            subcategory.value = ""
            subcategory.disabled = not bool(selected_category)
            subcategory.update()

        category.on_select = category_changed

        def close_dialog():
            dialog.open = False
            page.update()

        def save(e):
            try:
                value = float((amount.value or "0").replace(",", ""))
                datetime.strptime(transaction_date.value or "", "%Y-%m-%d")
                if kind.value == "transfer":
                    if not account.value or not destination.value:
                        raise ValueError("Selecciona origen y destino")
                    if account.value == destination.value:
                        raise ValueError("El origen y destino deben ser diferentes")
                    transfer_data = {"account_id": account.value, "destination_account_id": destination.value, "transaction_date": transaction_date.value, "description": description.value or notes.value or "Transferencia", "amount": value, "transaction_type": "transfer", "notes": notes.value or ""}
                    if editing:
                        store.update_transaction(transaction["id"], transfer_data)
                    else:
                        store.add_transfer(account.value, destination.value, value, transaction_date.value, description.value or notes.value or "Transferencia", notes.value or "")
                else:
                    if kind.value == "income":
                        value = -abs(value)
                    if not description.value or not account.value:
                        raise ValueError
                    movement_data = {"account_id": account.value, "category_id": category.value or None, "subcategory_id": subcategory.value or None, "transaction_date": transaction_date.value, "description": description.value, "amount": value, "transaction_type": kind.value, "notes": notes.value or ""}
                    if editing:
                        store.update_transaction(transaction["id"], movement_data)
                    else:
                        store.add_transaction(movement_data)
                close_dialog()
                toast(sync_status("Movimiento"), RED if store.last_sync_error else GREEN)
                render()
            except ValueError as error:
                toast(str(error) or "Completa descripción, cuenta y monto válido", RED)

        dialog = light_dialog("Editar movimiento" if editing else "Nuevo movimiento", ft.Column([description, notes, amount, transaction_date, account, destination, category, subcategory, kind], tight=True, spacing=12), [cancel_button(lambda _: close_dialog()), ft.FilledButton("Guardar cambios" if editing else "Guardar", color="white", bgcolor=PRIMARY, on_click=save)])
        page.show_dialog(dialog)

    def open_import_dialog():
        account = dialog_dropdown(label="Importar a", options=[ft.DropdownOption(key=a["id"], text=a["name"]) for a in store.accounts()])
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

        dialog = light_dialog("Importar movimientos", ft.Column([account, help_text], tight=True, spacing=12), [cancel_button(lambda _: close_dialog()), ft.FilledButton("Seleccionar archivo", color="white", bgcolor=PRIMARY, on_click=choose)])
        page.show_dialog(dialog)

    def file_result(e: ft.FilePickerResultEvent):
        if not e.files:
            return
        imported, skipped = import_file(e.files[0].path, file_picker.data, store)
        toast(f"Importados {imported} movimientos; omitidos {skipped} duplicados o sin monto.", GREEN)
        render()

    file_picker.on_result = file_result
    month_picker.on_select = lambda _: render()

    sidebar = ft.Container(width=220, bgcolor=CARD, padding=ft.Padding.only(left=18, right=18, top=28, bottom=24))

    def refresh_sidebar():
        sidebar.content = ft.Column([
            ft.Container(ft.Row([ft.Container(width=38, height=38, bgcolor=PRIMARY, border_radius=12, content=ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET, color="white")), ft.Column([ft.Text("Pulso", size=19, weight=ft.FontWeight.BOLD, color=INK), ft.Text("financiero", size=11, color=MUTED)], spacing=0)]), padding=ft.Padding.only(left=6, bottom=32)),
            nav_item(ft.Icons.DASHBOARD_OUTLINED, "Resumen", "dashboard"),
            nav_item(ft.Icons.SWAP_VERT, "Movimientos", "transactions"),
            nav_item(ft.Icons.PIE_CHART_OUTLINE, "Presupuestos", "budgets"),
            nav_item(ft.Icons.CATEGORY_OUTLINED, "Categorías", "categories"),
            nav_item(ft.Icons.ACCOUNT_BALANCE_OUTLINED, "Cuentas", "accounts"),
            ft.Container(expand=True),
            ft.Container(ft.Column([ft.Text("Persistencia activa", size=12, weight=ft.FontWeight.BOLD, color=INK), ft.Text(store.backend_label, size=11, color=MUTED)], spacing=3), bgcolor="#F0F1F6", border_radius=12, padding=14),
        ], expand=True, spacing=6)

    def render():
        refresh_sidebar()
        refresh_month_options()
        if selected_section["value"] == "dashboard":
            controls = dashboard()
        elif selected_section["value"] == "transactions":
            controls = transactions_page()
        elif selected_section["value"] == "budgets":
            controls = budgets_page()
        elif selected_section["value"] == "categories":
            controls = categories_page()
        else:
            controls = accounts_page()
        content.controls = controls
        page.update()

    page.add(ft.Row([sidebar, ft.Container(content=content, expand=True, padding=ft.Padding.only(left=34, right=34, top=30, bottom=30))], expand=True, spacing=0))
    render()


if __name__ == "__main__":
    ft.run(main)
