"""Módulo para la exportación de datos de facturación a formato Excel (.xlsx).

Este módulo utiliza la librería openpyxl para generar archivos de Excel siguiendo
un formato estándar corporativo (Quipux SAS). Incluye configuraciones de estilos,
encabezados combinados, bordes y formatos de fuente específicos.
"""

import os
import yaml
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, Fill, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

class ExcelExporter:
    """Clase encargada de la generación de archivos Excel para reportes de control.
    
    Carga la configuración de columnas y estilos desde un archivo de metadatos
    y aplica el formato requerido a las hojas de cálculo.
    """

    def __init__(self):
        """Inicializa el exportador cargando la configuración desde excel_config.yml."""
        config_path = os.path.join("metadata", "excel_config.yml")
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)
        
        self.styles = self.config["styles"]
        self.columns = self.config["columns"]

    def generate_excel(
        self,
        data: list[dict],
        month_name: str,
        year: str | int,
    ) -> Workbook:
        """Genera un objeto Workbook con los datos y formatos especificados.

        Args:
            data: Lista de diccionarios con los registros de la base de datos.
            month_name: Nombre del mes o rango de fechas para el encabezado.
            year: Año del reporte para el encabezado.

        Returns:
            Workbook listo para ser guardado o transmitido.

        """
        wb = Workbook()
        ws = wb.active
        ws.title = self.config.get("sheet_name", "Facturas")

        # Styles
        header_fill = PatternFill(start_color=self.styles["header_bg_color"], 
                                  end_color=self.styles["header_bg_color"], 
                                  fill_type="solid")
        header_font = Font(name=self.styles["font_name"], 
                           size=self.styles["font_size"], 
                           bold=True, 
                           color=self.styles["header_font_color"])
        thin_border = Border(left=Side(style='thin'), 
                             right=Side(style='thin'), 
                             top=Side(style='thin'), 
                             bottom=Side(style='thin'))

        # 1. Quipux SAS Header
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(self.columns))
        cell_1 = ws.cell(row=1, column=1, value=self.config["company_name"])
        cell_1.font = Font(name=self.styles["font_name"], size=12, bold=True)
        cell_1.alignment = Alignment(horizontal="center")
        cell_1.border = thin_border
        # Aplicar borde a las celdas combinadas de la fila 1
        for i in range(1, len(self.columns) + 1):
            ws.cell(row=1, column=i).border = thin_border

        # 2. Title Header
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(self.columns))
        title = self.config["report_title"].format(MONTH=month_name.upper(), YEAR=year)
        cell_2 = ws.cell(row=2, column=1, value=title)
        cell_2.font = Font(name=self.styles["font_name"], size=11, bold=True)
        cell_2.alignment = Alignment(horizontal="center")
        cell_2.border = thin_border
        # Aplicar borde a las celdas combinadas de la fila 2
        for i in range(1, len(self.columns) + 1):
            ws.cell(row=2, column=i).border = thin_border

        # 3. Table Headers
        header_fill = PatternFill(start_color=self.styles["header_bg_color"], 
                                  end_color=self.styles["header_bg_color"], 
                                  fill_type="solid")
        header_font = Font(name=self.styles["font_name"], 
                           size=self.styles["font_size"], 
                           bold=True, 
                           color=self.styles["header_font_color"])
        thin_border = Border(left=Side(style='thin'), 
                             right=Side(style='thin'), 
                             top=Side(style='thin'), 
                             bottom=Side(style='thin'))

        for i, col in enumerate(self.columns, 1):
            cell = ws.cell(row=3, column=i, value=col["label"])
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = thin_border

        # 4. Data Rows
        for r_idx, row_data in enumerate(data, 4):
            for c_idx, col in enumerate(self.columns, 1):
                value = row_data.get(col["db_field"])
                # Format dates if necessary
                if isinstance(value, datetime):
                    value = value.strftime("%Y-%m-%d %H:%M:%S")
                elif value is None:
                    value = ""
                
                cell = ws.cell(row=r_idx, column=c_idx, value=value)
                cell.font = Font(name=self.styles["font_name"], size=self.styles["font_size"])
                cell.border = thin_border
                cell.alignment = Alignment(vertical="center")

        return wb
