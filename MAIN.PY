import pandas as pd
import numpy as np
import openpyxl
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from openpyxl.utils.dataframe import dataframe_to_rows
import warnings
import logging
import time
import os
from datetime import datetime, time as dt_time
from tkinter import Tk, filedialog, messagebox
from typing import List, Dict, Optional, Tuple, Union
import tkinter as tk

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('data_processing.log', mode='w', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Подавляем предупреждения от openpyxl
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

# Словарь для перевода дней недели на русский
DAY_OF_WEEK_RU = {
    'Monday': 'Понедельник',
    'Tuesday': 'Вторник',
    'Wednesday': 'Среда',
    'Thursday': 'Четверг',
    'Friday': 'Пятница',
    'Saturday': 'Суббота',
    'Sunday': 'Воскресенье'
}

class ExcelProcessor:
    def __init__(self, file_path):
        self.file_path = file_path
        self.workbook = None
        self.data_sheets = {}
        self.results = {}
        self.family_data = {}
        self.filtered_data = None
        
    def load_data(self):
        try:
            excel_file = pd.ExcelFile(self.file_path)
            for sheet_name in excel_file.sheet_names:
                df = pd.read_excel(self.file_path, sheet_name=sheet_name)
                self.data_sheets[sheet_name] = df
                logger.info(f"Загружен лист: {sheet_name}, строк: {len(df)}")
                print(f"Загружен лист: {sheet_name}, строк: {len(df)}")
                print(f"Столбцы: {list(df.columns)}")
                print(f"Первые 3 строки листа '{sheet_name}':")
                print(df.head(3))
                print("-" * 50)
        except Exception as e:
            logger.error(f"Ошибка загрузки файла: {e}")
            print(f"Ошибка загрузки файла: {e}")
            return False
        return True
    
    def determine_family(self, value):
        if pd.isna(value):
            return 'OTHER'
        value_str = str(value).upper()
        if any(pattern in value_str for pattern in ['DUB', 'ДУБ']):
            return 'DUB'
        elif any(pattern in value_str for pattern in ['ECRU', 'ЭКРУ']):
            return 'ECRU'
        elif any(pattern in value_str for pattern in ['MAAG', 'МААГ']):
            return 'MAAG'
        elif any(pattern in value_str for pattern in ['VILET', 'VIOLET', 'ВИЛЕТ', 'ВИОЛЕТ']):
            return 'VILET'
        else:
            return 'OTHER'
    
    def add_box_column(self, df, group_column='1_Заказ+Семья'):
        df = df.copy()
        logger.info(f"Проверяем столбец для расчета BOX: '{group_column}'")
        print(f"Проверяем столбец для расчета BOX: '{group_column}'")
        if group_column in df.columns:
            box_counts = df[group_column].value_counts()
            df['BOX'] = df[group_column].map(box_counts)
            logger.info(f"Уникальных значений в '{group_column}': {len(box_counts)}")
            print(f"Уникальных значений в '{group_column}': {len(box_counts)}")
            print("Первые 10 значений и их BOX:")
            print(df[[group_column, 'BOX']].drop_duplicates().head(10))
        else:
            logger.warning(f"Столбец '{group_column}' не найден!")
            print(f"Столбец '{group_column}' не найден!")
            potential_columns = [col for col in df.columns if any(keyword in str(col).upper() for keyword in 
                                                                  ['ЗАКАЗ', 'СЕМЬЯ', 'КОНТЕЙНЕР', 'BOX', 'ID', 'КОД', 'НОМЕР', 'NUMBER'])]
            if potential_columns:
                group_column = potential_columns[0]
                box_counts = df[group_column].value_counts()
                df['BOX'] = df[group_column].map(box_counts)
                logger.info(f"Используем альтернативный столбец '{group_column}'")
                print(f"Используем альтернативный столбец '{group_column}'")
                print(f"Уникальных значений в '{group_column}': {len(box_counts)}")
                print("Первые 10 значений и их BOX:")
                print(df[[group_column, 'BOX']].drop_duplicates().head(10))
            else:
                logger.error("Не найден подходящий столбец для расчета BOX. Проверьте структуру данных.")
                raise ValueError("Не найден подходящий столбец для расчета BOX. Проверьте структуру данных.")
        return df
    
    def add_quantity1_column(self, df):
        df = df.copy()
        if 'Целевой контейнер' not in df.columns or 'Семья' not in df.columns:
            logger.warning("Столбцы 'Целевой контейнер' или 'Семья' отсутствуют в данных Unique_S_Data!")
            print("Столбцы 'Целевой контейнер' или 'Семья' отсутствуют в данных Unique_S_Data!")
            return df
        
        if 'Main_Data' not in self.data_sheets:
            logger.warning("Лист 'Main_Data' не найден! Невозможно рассчитать Количество1.")
            print("Лист 'Main_Data' не найден! Невозможно рассчитать Количество1.")
            return df
        
        main_df = self.data_sheets['Main_Data'].copy()
        if 'Целевой контейнер' not in main_df.columns or 'Семья' not in main_df.columns or 'Количество' not in main_df.columns:
            logger.warning("Столбцы 'Целевой контейнер', 'Семья' или 'Количество' отсутствуют в данных Main_Data!")
            print("Столбцы 'Целевой контейнер', 'Семья' или 'Количество' отсутствуют в данных Main_Data!")
            return df
        
        logger.info("Добавляем столбец Количество1 на основе данных из Main_Data...")
        print("Добавляем столбец Количество1 на основе данных из Main_Data...")
        try:
            quantity1 = main_df.groupby(['Целевой контейнер', 'Семья'])['Количество'].sum().to_dict()
            df['Количество1'] = df.apply(
                lambda row: quantity1.get((row['Целевой контейнер'], row['Семья']), 0),
                axis=1
            )
        except Exception as e:
            logger.error(f"Ошибка при расчете Количество1: {e}")
            print(f"Ошибка при расчете Количество1: {e}")
            df['Количество1'] = 0
        
        logger.info(f"Статистика по столбцу Количество1:")
        logger.info(f"Минимальное значение: {df['Количество1'].min()}")
        logger.info(f"Максимальное значение: {df['Количество1'].max()}")
        print(f"Статистика по столбцу Количество1:")
        print(f"Минимальное значение: {df['Количество1'].min()}")
        print(f"Максимальное значение: {df['Количество1'].max()}")
        print("Первые 5 строк с Количество1:")
        print(df[['Целевой контейнер', 'Семья', 'Количество', 'Количество1']].head())
        return df
    
    def determine_shift(self, time_str):
        if pd.isna(time_str):
            return 'Unknown'
        try:
            time_obj = datetime.strptime(str(time_str), '%H:%M:%S').time()
            day_start = dt_time(8, 0)
            night_start = dt_time(20, 0)
            
            if day_start <= time_obj < night_start:
                return 'Day'
            else:
                return 'Night'
        except ValueError:
            return 'Unknown'

    def analyze_daily_stats(self, df):
        logger.info("Анализ статистики по дням с разделением на смены...")
        print("Анализ статистики по дням с разделением на смены...")
        if 'Дата завершения' not in df.columns or 'Время' not in df.columns:
            logger.warning("Столбцы 'Дата завершения' или 'Время' отсутствуют!")
            print("Столбцы 'Дата завершения' или 'Время' отсутствуют!")
            return {}
        
        daily_stats = {}
        df['Дата завершения'] = pd.to_datetime(df['Дата завершения'], format='%d.%m.%Y', errors='coerce')
        df['Shift'] = df['Время'].apply(self.determine_shift)
        dates = df['Дата завершения'].dropna().dt.date.unique()
        
        for date in sorted(dates):
            date_str = date.strftime('%d.%m.%Y')
            daily_stats[date_str] = {'Day': {}, 'Night': {}}
            
            for shift in ['Day', 'Night']:
                shift_df = df[(df['Дата завершения'].dt.date == date) & (df['Shift'] == shift)]
                total_boxes = len(shift_df)
                less_than_4 = len(shift_df[shift_df['Количество1'] < 4])
                
                daily_stats[date_str][shift] = {
                    'Всего коробов': total_boxes,
                    'Менее 4-х': less_than_4
                }
                logger.info(f"Дата {date_str}, Смена {shift}: Всего коробов: {total_boxes}, Менее 4-х: {less_than_4}")
                print(f"Дата {date_str}, Смена {shift}: Всего коробов: {total_boxes}, Менее 4-х: {less_than_4}")
        
        self.create_daily_stats_table(daily_stats)
        return daily_stats
    
    def create_daily_stats_table(self, daily_stats):
        rows_data = []
        families = ['DUB', 'ECRU', 'MAAG', 'VILET']
        
        # Проверяем наличие необходимых данных
        if self.filtered_data is None or 'Дата завершения' not in self.filtered_data.columns or 'Базовая_семья' not in self.filtered_data.columns or 'Время' not in self.filtered_data.columns:
            logger.warning("Отсутствуют данные или необходимые столбцы для создания ежедневной статистики!")
            print("Отсутствуют данные или необходимые столбцы для создания ежедневной статистики!")
            return pd.DataFrame()
        
        logger.info("Создание ежедневной статистики с разбивкой по брендам и сменам...")
        print("Создание ежедневной статистики с разбивкой по брендам и сменам...")
        
        # Группировка данных по дате, смене и бренду
        df = self.filtered_data.copy()
        df['Дата завершения'] = pd.to_datetime(df['Дата завершения'], format='%d.%m.%Y', errors='coerce')
        df['Shift'] = df['Время'].apply(self.determine_shift)
        grouped = df.groupby([df['Дата завершения'].dt.date, 'Shift', 'Базовая_семья'])
        
        # Подготовка данных для таблицы
        for date in sorted(daily_stats.keys()):
            date = datetime.strptime(date, '%d.%m.%Y').date()
            date_str = date.strftime('%d.%m.%Y')
            for shift in ['Day', 'Night']:
                row_data = {'Дата': date_str, 'Смена': shift}
                
                # Общие показатели
                total_boxes = daily_stats[date_str][shift]['Всего коробов']
                less_than_4 = daily_stats[date_str][shift]['Менее 4-х']
                row_data['Всего коробов'] = total_boxes
                row_data['Менее 4-х'] = less_than_4
                row_data['% Менее 4-х'] = f"{(less_than_4 / total_boxes * 100):.1f}%" if total_boxes > 0 else "0.0%"
                
                # Показатели по брендам
                for family in families:
                    family_data = grouped.get_group((date, shift, family)) if (date, shift, family) in grouped.groups else None
                    if family_data is not None:
                        family_total = len(family_data)
                        family_less_than_4 = len(family_data[family_data['Количество1'] < 4])
                        row_data[f'Всего ({family})'] = family_total
                        row_data[f'Менее 4-х ({family})'] = family_less_than_4
                        row_data[f'% Менее 4-х ({family})'] = f"{(family_less_than_4 / family_total * 100):.1f}%" if family_total > 0 else "0.0%"
                    else:
                        row_data[f'Всего ({family})'] = 0
                        row_data[f'Менее 4-х ({family})'] = 0
                        row_data[f'% Менее 4-х ({family})'] = "0.0%"
                
                rows_data.append(row_data)
        
        # Определяем порядок столбцов
        columns = ['Дата', 'Смена', 'Всего коробов', 'Менее 4-х', '% Менее 4-х']
        for family in families:
            columns.extend([f'Всего ({family})', f'Менее 4-х ({family})', f'% Менее 4-х ({family})'])
        
        final_df = pd.DataFrame(rows_data, columns=columns)
        self.results['Ежедневная статистика'] = final_df
        logger.info("\n=== ЕЖЕДНЕВНАЯ СТАТИСТИКА ===")
        print("\n=== ЕЖЕДНЕВНАЯ СТАТИСТИКА ===")
        print(final_df.to_string(index=False))
        return final_df
    
    def analyze_violation_reasons(self, df):
        families = ['DUB', 'ECRU', 'MAAG', 'VILET']
        analysis_data = {}
        logger.info("Начинаем анализ причин нарушений...")
        print("Начинаем анализ причин нарушений...")
        print(f"Общее количество записей: {len(df)}")
        
        required_columns = [
            '1_Заказ+Семья', '2_1+Волна', '3_2+Комбин', '4_3+Дата',
            '5_4+Исполнитель', '6_Заказ+Комби+КОР', 'Семья', 'Количество1'
        ]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            logger.warning(f"Отсутствуют столбцы: {missing_columns}. Анализ причин нарушений невозможен.")
            print(f"Отсутствуют столбцы: {missing_columns}. Анализ причин нарушений невозможен.")
            return {}
        
        if 'BOX' not in df.columns:
            df = self.add_box_column(df)
        
        self.filtered_data = df.copy()
        
        logger.info(f"Количество записей для анализа: {len(self.filtered_data)}")
        print(f"Количество записей для анализа: {len(self.filtered_data)}")
        print(f"Распределение по семьям:")
        if 'Семья' in self.filtered_data.columns:
            print(self.filtered_data['Семья'].value_counts())
        
        for family in families:
            family_df = df[df['Семья'].apply(self.determine_family) == family].copy()
            total_count = len(family_df)
            logger.info(f"\nСемья {family}: {total_count} (Количество строк)")
            print(f"\nСемья {family}: {total_count} (Количество строк)")
            
            if total_count == 0:
                analysis_data[family] = self.get_zero_analysis()
                continue
            
            less_than_4_df = family_df[family_df['Количество1'] < 4].copy()
            less_than_4_count = len(less_than_4_df)
            more_than_or_equal_4_count = total_count - less_than_4_count
            
            logger.info(f"  Менее 4-х: {less_than_4_count} строк")
            logger.info(f"  Более или = 4: {more_than_or_equal_4_count} строк")
            print(f"  Менее 4-х: {less_than_4_count} строк")
            print(f"  Более или = 4: {more_than_or_equal_4_count} строк")
            
            if less_than_4_count == 0:
                analysis_data[family] = {
                    'Всего': total_count,
                    'Менее 4-х': 0,
                    'Более или = 4': more_than_or_equal_4_count,
                    'Заказ из магазина': 0,
                    'Разбивка по этажам': 0,
                    'Разбивка по задачам': 0,
                    'Разные дни сборки': 0,
                    'Разные люди': 0,
                    'Хвосты в задаче': 0
                }
                continue
            
            pivot_columns = [
                ('Заказ из магазина', ['BOX', '1_Заказ+Семья']),
                ('Разбивка по этажам', ['BOX', '2_1+Волна']),
                ('Разбивка по задачам', ['BOX', '3_2+Комбин']),
                ('Разные дни сборки', ['BOX', '4_3+Дата']),
                ('Разные люди', ['BOX', '5_4+Исполнитель']),
                ('Хвосты в задаче', ['BOX', '6_Заказ+Комби+КОР'])
            ]
            
            error_counts = {}
            previous_count = 0
            
            logger.info(f"  Отладка для {family}:")
            print(f"  Отладка для {family}:")
            
            for cause_name, columns in pivot_columns:
                missing_cols = [col for col in columns if col not in family_df.columns]
                if missing_cols:
                    logger.warning(f"    {cause_name}: отсутствуют столбцы {missing_cols}")
                    print(f"    {cause_name}: отсутствуют столбцы {missing_cols}")
                    error_counts[cause_name] = 0
                    continue
                
                pivot_table = family_df.groupby(columns)['Количество1'].sum().reset_index()
                less_than_4_in_pivot = len(pivot_table[pivot_table['Количество1'] < 4])
                
                if cause_name == 'Заказ из магазина':
                    current_count = less_than_4_in_pivot
                else:
                    current_count = max(0, less_than_4_in_pivot - previous_count)
                
                error_counts[cause_name] = current_count
                previous_count = less_than_4_in_pivot
                
                logger.info(f"    {cause_name}:")
                logger.info(f"      Записей в сводной таблице: {len(pivot_table)}")
                logger.info(f"      Записей с суммой < 4: {less_than_4_in_pivot}")
                logger.info(f"      Итоговое значение причины: {current_count}")
                print(f"    {cause_name}:")
                print(f"      Записей в сводной таблице: {len(pivot_table)}")
                print(f"      Записей с суммой < 4: {less_than_4_in_pivot}")
                print(f"      Итоговое значение причины: {current_count}")
                
                if family == 'DUB':
                    pivot_table.to_csv(f'debug_{family.lower()}_{cause_name.replace(" ", "_")}_pivot.csv', index=False)
            
            analysis_data[family] = {
                'Всего': total_count,
                'Менее 4-х': less_than_4_count,
                'Более или = 4': more_than_or_equal_4_count,
                **error_counts
            }
            
            logger.info(f"  Итоговый анализ причин для {family}:")
            print(f"  Итоговый анализ причин для {family}:")
            for key, value in analysis_data[family].items():
                logger.info(f"    {key}: {value}")
                print(f"    {key}: {value}")
        
        self.create_summary_table(analysis_data)
        self.analyze_daily_stats(df)
        return analysis_data
    
    def get_zero_analysis(self):
        return {
            'Всего': 0,
            'Менее 4-х': 0,
            'Более или = 4': 0,
            'Заказ из магазина': 0,
            'Разбивка по этажам': 0,
            'Разбивка по задачам': 0,
            'Разные дни сборки': 0,
            'Разные люди': 0,
            'Хвосты в задаче': 0
        }
    
    def process_main_data(self):
        if not self.data_sheets:
            logger.warning("Нет загруженных данных!")
            print("Нет загруженных данных!")
            return False
        
        main_sheet_name = 'Unique_S_Data'
        if main_sheet_name not in self.data_sheets:
            logger.warning(f"Лист '{main_sheet_name}' не найден! Доступные листы: {list(self.data_sheets.keys())}")
            logger.warning("Лист 'Unique_S_Data' обязателен для анализа!")
            print(f"Лист '{main_sheet_name}' не найден! Доступные листы: {list(self.data_sheets.keys())}")
            print("Лист 'Unique_S_Data' обязателен для анализа!")
            return False
        
        df = self.data_sheets[main_sheet_name].copy()
        logger.info(f"Обрабатываем лист: {main_sheet_name}")
        logger.info(f"Исходных записей: {len(df)}")
        print(f"Обрабатываем лист: {main_sheet_name}")
        print(f"Исходных записей: {len(df)}")
        
        required_columns = ['Семья', 'Целевой контейнер', 'Количество']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            logger.warning(f"Отсутствуют необходимые столбцы: {missing_columns}")
            print(f"Отсутствуют необходимые столбцы: {missing_columns}")
            return False
        
        df = df.rename(columns={
            'Семья': 'Семья',
            'Целевой контейнер': 'Целевой контейнер',
            'Количество': 'Количество'
        })
        
        df['Базовая_семья'] = df['Семья'].apply(self.determine_family)
        logger.info(f"Распределение по базовым семьям:")
        print(f"Распределение по базовым семьям:")
        print(df['Базовая_семья'].value_counts())
        
        df = self.add_box_column(df)
        df = self.add_quantity1_column(df)
        
        logger.info("\n=== ПРОВЕРКА РАСЧЕТА BOX ===")
        print("\n=== ПРОВЕРКА РАСЧЕТА BOX ===")
        if '1_Заказ+Семья' in df.columns and 'BOX' in df.columns and 'Количество' in df.columns:
            logger.info("Первые 10 строк ['1_Заказ+Семья', 'BOX', 'Количество']:")
            print("Первые 10 строк ['1_Заказ+Семья', 'BOX', 'Количество']:")
            print(df[['1_Заказ+Семья', 'BOX', 'Количество']].head(10))
            logger.info("\nСтатистика по столбцу BOX:")
            logger.info(f"Минимальное значение: {df['BOX'].min()}")
            logger.info(f"Максимальное значение: {df['BOX'].max()}")
            logger.info("Распределение значений BOX:")
            logger.info(df['BOX'].value_counts().sort_index())
            print("\nСтатистика по столбцу BOX:")
            print(f"Минимальное значение: {df['BOX'].min()}")
            print(f"Максимальное значение: {df['BOX'].max()}")
            print("Распределение значений BOX:")
            print(df['BOX'].value_counts().sort_index())
        else:
            logger.warning("Столбцы '1_Заказ+Семья', 'BOX' или 'Количество' отсутствуют в данных!")
            print("Столбцы '1_Заказ+Семья', 'BOX' или 'Количество' отсутствуют в данных!")
        
        logger.info(f"\nРаспределение по семьям после обработки:")
        print(f"\nРаспределение по семьям после обработки:")
        print(df['Семья'].value_counts())
        
        target_families = ['DUB', 'ECRU', 'MAAG', 'VILET']
        df_filtered = df[df['Базовая_семья'].isin(target_families)].copy()
        
        if len(df_filtered) == 0:
            logger.warning("Не найдено данных для целевых семей!")
            logger.info("Попробуем анализировать все данные...")
            print("Не найдено данных для целевых семей!")
            print("Попробуем анализировать все данные...")
            df_filtered = df.copy()
        
        logger.info(f"Данных для анализа: {len(df_filtered)}")
        print(f"Данных для анализа: {len(df_filtered)}")
        self.filtered_data = df_filtered
        self.analyze_violation_reasons(df_filtered)
        return True
    
    def create_summary_table(self, analysis_data):
        rows_data = []
        row_names = [
            'Всего',
            'Менее 4-х',
            'Более или = 4',
            'Заказ из магазина',
            'Разбивка по этажам',
            'Разбивка по задачам',
            'Разные дни сборки',
            'Разные люди',
            'Хвосты в задаче'
        ]
        families = ['DUB', 'ECRU', 'MAAG', 'VILET']
        
        for i, row_name in enumerate(row_names):
            row_data = {'№': i + 1, 'Причина': row_name}
            total_count = sum(analysis_data.get(family, {}).get(row_name, 0) for family in families)
            row_data['Кол-во'] = total_count
            total_all = sum(analysis_data.get(family, {}).get('Всего', 0) for family in families)
            row_data['%'] = f"{(total_count / total_all * 100):.1f}%" if total_all > 0 else "0.0%"
            
            for family in families:
                family_count = analysis_data.get(family, {}).get(row_name, 0)
                family_total = analysis_data.get(family, {}).get('Всего', 0)
                row_data[family] = family_count
                row_data[f'% {family}'] = f"{(family_count / family_total * 100):.1f}%" if family_total > 0 else "0.0%"
            rows_data.append(row_data)
        
        final_columns = ['№', 'Причина', 'Кол-во', '%', 'DUB', '% DUB', 'ECRU', '% ECRU', 'MAAG', '% MAAG', 'VILET', '% VILET']
        final_data = []
        for row in rows_data:
            final_row = [
                row['№'],
                row['Причина'],
                row['Кол-во'],
                row['%'],
                row['DUB'],
                row['% DUB'],
                row['ECRU'],
                row['% ECRU'],
                row['MAAG'],
                row['% MAAG'],
                row['VILET'],
                row['% VILET']
            ]
            final_data.append(final_row)
        
        final_df = pd.DataFrame(final_data, columns=final_columns)
        self.results['Итоговая таблица'] = final_df
        logger.info("\n=== ПРЕДВАРИТЕЛЬНЫЙ ПРОСМОТР ТАБЛИЦЫ ===")
        print("\n=== ПРЕДВАРИТЕЛЬНЫЙ ПРОСМОТР ТАБЛИЦЫ ===")
        print(final_df.to_string(index=False))
        return final_df
    
    def save_calculations_sheet(self, ws, df):
        ws.title = "Расчеты"
        columns_to_save = [
            'Целевой контейнер', 'Количество1', 'Количество', 
            '1_Заказ+Семья', 'Семья', 'Базовая_семья', 'BOX', 
            '2_1+Волна', '3_2+Комбин', '4_3+Дата', '5_4+Исполнитель', 
            '6_Заказ+Комби+КОР', 'Shift'
        ]
        df_to_save = df[[col for col in columns_to_save if col in df.columns]].copy()
        
        for r_idx, row in enumerate(dataframe_to_rows(df_to_save, index=False, header=True), 1):
            for c_idx, value in enumerate(row, 1):
                cell = ws.cell(row=r_idx, column=c_idx, value=value)
                if r_idx == 1:
                    cell.font = Font(bold=True, color="FFFFFF")
                    cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                else:
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                thin_border = Border(
                    left=Side(style='thin'),
                    right=Side(style='thin'),
                    top=Side(style='thin'),
                    bottom=Side(style='thin')
                )
                cell.border = thin_border
        
        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 30)
            ws.column_dimensions[column_letter].width = adjusted_width
    
    def save_daily_stats_sheet(self, ws, df):
        ws.title = "Ежедневная статистика"
        for r_idx, row in enumerate(dataframe_to_rows(df, index=False, header=True), 1):
            for c_idx, value in enumerate(row, 1):
                cell = ws.cell(row=r_idx, column=c_idx, value=value)
                if r_idx == 1:
                    cell.font = Font(bold=True, color="FFFFFF")
                    cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                else:
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                thin_border = Border(
                    left=Side(style='thin'),
                    right=Side(style='thin'),
                    top=Side(style='thin'),
                    bottom=Side(style='thin')
                )
                cell.border = thin_border
        
        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 20)
            ws.column_dimensions[column_letter].width = adjusted_width
    
    def save_calculations_only(self, output_file='Причины менее 4-х 25_1503.xlsx'):
        try:
            if os.path.exists(output_file):
                os.remove(output_file)
            wb = Workbook()
            ws_calculations = wb.active
            
            if self.filtered_data is not None:
                self.save_calculations_sheet(ws_calculations, self.filtered_data)
            else:
                logger.warning("Нет данных для сохранения в лист 'Расчеты'!")
                print("Нет данных для сохранения в лист 'Расчеты'!")
                return False
            
            wb.save(output_file)
            logger.info(f"Лист 'Расчеты' сохранен в файл: {output_file}")
            print(f"Лист 'Расчеты' сохранен в файл: {output_file}")
            return True
        except PermissionError:
            logger.error(f"Ошибка: Нет прав доступа для сохранения файла {output_file}. Закройте файл и попробуйте снова.")
            print(f"Ошибка: Нет прав доступа для сохранения файла {output_file}. Закройте файл и попробуйте снова.")
            return False
        except Exception as e:
            logger.error(f"Ошибка сохранения файла: {e}")
            print(f"Ошибка сохранения файла: {e}")
            return False
    
    def save_final_results_with_formatting(self, output_file, df_calculations, df_summary, df_daily_stats):
        try:
            if os.path.exists(output_file):
                os.remove(output_file)
            wb = Workbook()
            
            ws_summary = wb.active
            ws_summary.title = "Анализ причин нарушений"
            
            for r_idx, row in enumerate(dataframe_to_rows(df_summary, index=False, header=True), 1):
                for c_idx, value in enumerate(row, 1):
                    cell = ws_summary.cell(row=r_idx, column=c_idx, value=value)
                    if r_idx == 1:
                        cell.font = Font(bold=True, color="FFFFFF")
                        cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
                        cell.alignment = Alignment(horizontal="center", vertical="center")
                    else:
                        cell.alignment = Alignment(horizontal="center", vertical="center")
                        if r_idx == 2:
                            cell.fill = PatternFill(start_color="E7E6E6", end_color="E7E6E6", fill_type="solid")
                    thin_border = Border(
                        left=Side(style='thin'),
                        right=Side(style='thin'),
                        top=Side(style='thin'),
                        bottom=Side(style='thin')
                    )
                    cell.border = thin_border
            
            for column in ws_summary.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 20)
                ws_summary.column_dimensions[column_letter].width = adjusted_width
            
            ws_calculations = wb.create_sheet(title="Расчеты")
            self.save_calculations_sheet(ws_calculations, df_calculations)
            
            ws_daily_stats = wb.create_sheet(title="Ежедневная статистика")
            self.save_daily_stats_sheet(ws_daily_stats, df_daily_stats)
            
            wb.save(output_file)
            logger.info(f"Финальные результаты сохранены в файл: {output_file}")
            print(f"Финальные результаты сохранены в файл: {output_file}")
            return True
        except PermissionError:
            logger.error(f"Ошибка: Нет прав доступа для сохранения файла {output_file}. Закройте файл и попробуйте снова.")
            print(f"Ошибка: Нет прав доступа для сохранения файла {output_file}. Закройте файл и попробуйте снова.")
            return False
        except Exception as e:
            logger.error(f"Ошибка сохранения финальных результатов: {e}")
            print(f"Ошибка сохранения финальных результатов: {e}")
            return False
    
    def build_final_table_from_calculations(self, input_file='Причины менее 4-х 25_1503.xlsx'):
        try:
            df_calculations = pd.read_excel(input_file, sheet_name='Расчеты')
            logger.info(f"Загружены данные из листа 'Расчеты': {len(df_calculations)} строк")
            print(f"Загружены данные из листа 'Расчеты': {len(df_calculations)} строк")
            
            analysis_data = self.analyze_violation_reasons(df_calculations)
            
            final_df = self.create_summary_table(analysis_data)
            daily_stats_df = self.results.get('Ежедневная статистика', pd.DataFrame())
            
            self.save_final_results_with_formatting(input_file, df_calculations, final_df, daily_stats_df)
            
            return True
        except FileNotFoundError:
            logger.error(f"Файл {input_file} не найден!")
            print(f"Файл {input_file} не найден!")
            return False
        except Exception as e:
            logger.error(f"Ошибка построения финальной таблицы: {e}")
            print(f"Ошибка построения финальной таблицы: {e}")
            return False
    
    def save_results_with_formatting(self, output_file='Причины менее 4-х 25_1503.xlsx'):
        try:
            if os.path.exists(output_file):
                os.remove(output_file)
            wb = Workbook()
            ws_summary = wb.active
            ws_summary.title = "Анализ причин нарушений"
            if 'Итоговая таблица' not in self.results:
                logger.warning("Нет данных для сохранения итоговой таблицы!")
                print("Нет данных для сохранения итоговой таблицы!")
                return False
            df_summary = self.results['Итоговая таблица']
            
            for r_idx, row in enumerate(dataframe_to_rows(df_summary, index=False, header=True), 1):
                for c_idx, value in enumerate(row, 1):
                    cell = ws_summary.cell(row=r_idx, column=c_idx, value=value)
                    if r_idx == 1:
                        cell.font = Font(bold=True, color="FFFFFF")
                        cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
                        cell.alignment = Alignment(horizontal="center", vertical="center")
                    else:
                        cell.alignment = Alignment(horizontal="center", vertical="center")
                        if r_idx == 2:
                            cell.fill = PatternFill(start_color="E7E6E6", end_color="E7E6E6", fill_type="solid")
                    thin_border = Border(
                        left=Side(style='thin'),
                        right=Side(style='thin'),
                        top=Side(style='thin'),
                        bottom=Side(style='thin')
                    )
                    cell.border = thin_border
            
            for column in ws_summary.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 20)
                ws_summary.column_dimensions[column_letter].width = adjusted_width
            
            if self.filtered_data is not None:
                ws_calculations = wb.create_sheet(title="Расчеты")
                self.save_calculations_sheet(ws_calculations, self.filtered_data)
                ws_daily_stats = wb.create_sheet(title="Ежедневная статистика")
                if 'Ежедневная статистика' in self.results:
                    self.save_daily_stats_sheet(ws_daily_stats, self.results['Ежедневная статистика'])
            else:
                logger.warning("Нет данных для сохранения в лист 'Расчеты'!")
                print("Нет данных для сохранения в лист 'Расчеты'!")
                return False
            
            wb.save(output_file)
            logger.info(f"Результаты сохранены в файл: {output_file}")
            print(f"Результаты сохранены в файл: {output_file}")
            return True
        except PermissionError:
            logger.error(f"Ошибка: Нет прав доступа для сохранения файла {output_file}. Закройте файл и попробуйте снова.")
            print(f"Ошибка: Нет прав доступа для сохранения файла {output_file}. Закройте файл и попробуйте снова.")
            return False
        except Exception as e:
            logger.error(f"Ошибка сохранения файла: {e}")
            print(f"Ошибка сохранения файла: {e}")
            return False
    
    def run_full_analysis(self, output_file='Причины менее 4-х 25_1503.xlsx'):
        logger.info("Начинаем полный анализ...")
        print("Начинаем полный анализ...")
        if not self.load_data():
            return False
        if not self.process_main_data():
            return False
        
        self.save_calculations_only(output_file)
        
        self.build_final_table_from_calculations(output_file)
        
        logger.info("Анализ завершен успешно!")
        print("Анализ завершен успешно!")
        return True

class DataProcessor:
    def __init__(self):
        self.root = Tk()
        self.root.withdraw()
        self.required_columns = {
            "Время завершения": "Обязательный для преобразования даты и времени",
            "Волна операции": "Обязательный для фильтрации",
            "Количество": "Обязательный для анализа коробов",
            "Артикул": "Необходим для добавления 'Семьи'",
            "Заказ": "Обязательный для вычисляемых столбцов",
            "Код комбинации": "Обязательный для вычисляемых столбцов",
            "Исполнитель": "Обязательный для вычисляемых столбцов",
            "Целевой контейнер": "Обязательный для определения № короба"
        }
        self.df = None
        self.article_family_file = None
        self.output_file = None
        self.final_output_file = None
        self.input_files = []
        self.input_article_files = []
        self.use_existing_article_file = False
        self.existing_article_file = None
        self.accumulated_files = []  # Для накопленной статистики

    def select_file(self, title: str) -> str:
        file_path = filedialog.askopenfilename(
            title=title,
            filetypes=[("Excel files", "*.xlsx *.xlsm")]
        )
        if not file_path:
            logger.error(f"Файл не выбран для: {title}")
            print(f"Ошибка: Файл не выбран для: {title}")
            raise ValueError(f"Файл не выбран для: {title}")
        logger.info(f"Выбран файл: {file_path}")
        print(f"Выбран файл: {file_path}")
        return file_path

    def select_multiple_files(self, title: str) -> List[str]:
        files = filedialog.askopenfilenames(
            title=title,
            filetypes=[("Excel files", "*.xlsx *.xlsm")]
        )
        if not files:
            logger.error(f"Файлы не выбраны для: {title}")
            print(f"Ошибка: Файлы не выбраны для: {title}")
            raise ValueError(f"Файлы не выбраны для: {title}")
        logger.info(f"Выбрано {len(files)} файлов: {files}")
        print(f"Выбрано {len(files)} файлов: {files}")
        return list(files)

    def select_output_file(self, title: str, default_name: str) -> str:
        file_path = filedialog.asksaveasfilename(
            title=title,
            defaultextension=".xlsx",
            initialfile=default_name,
            filetypes=[("Excel files", "*.xlsx")]
        )
        if not file_path:
            logger.error(f"Файл для сохранения не выбран: {title}")
            print(f"Ошибка: Файл для сохранения не выбран: {title}")
            raise ValueError(f"Файл для сохранения не выбран: {title}")
        logger.info(f"Выбран файл для сохранения: {file_path}")
        print(f"Выбран файл для сохранения: {file_path}")
        return file_path

    def ask_use_existing_article_file(self) -> bool:
        response = messagebox.askyesno(
            title="Выбор файла Артикул-Семья",
            message="Хотите использовать существующий файл Артикул-Семья? Если выберете 'Нет', будет создан новый файл."
        )
        logger.info(f"Пользователь выбрал {'использовать существующий' if response else 'создать новый'} файл Артикул-Семья")
        print(f"Пользователь выбрал {'использовать существующий' if response else 'создать новый'} файл Артикул-Семья")
        return response

    def select_all_files(self):
        print("Выбор всех необходимых файлов и путей сохранения...")
        logger.info("Начало выбора всех файлов и путей сохранения")
        
        # Спрашиваем, хочет ли пользователь использовать существующий файл Артикул-Семья
        self.use_existing_article_file = self.ask_use_existing_article_file()
        
        if self.use_existing_article_file:
            # Выбор существующего файла Артикул-Семья
            self.existing_article_file = self.select_file(
                "Выберите существующий файл Артикул-Семья"
            )
            self.article_family_file = self.existing_article_file
        else:
            # Выбор файлов для создания Артикул-Семья
            self.input_article_files = self.select_multiple_files(
                "Выберите файлы для Артикул-Семья (лист 'Информация о складском запасе с')"
            )
            current_time = datetime.now().strftime("%d_%H%M")
            self.article_family_file = self.select_output_file(
                "Выберите место для сохранения файла Артикул-Семья",
                f"Articul {current_time}.xlsx"
            )
        
        # Выбор файлов для обработки
        self.input_files = self.select_multiple_files(
            "Выберите файлы для обработки"
        )
        
        # Выбор файла для сохранения промежуточного результата
        self.output_file = self.select_output_file(
            "Выберите место для сохранения промежуточного результата",
            "Main_Output.xlsx"
        )
        
        # Выбор файла для сохранения финального результата (Причины менее 4-х)
        self.final_output_file = self.select_output_file(
            "Выберите место для сохранения финального результата (Причины менее 4-х)",
            "Причины менее 4-х.xlsx"
        )
        
        # Выбор файлов для накопленной статистики
        self.accumulated_files = self.select_multiple_files(
            "Выберите файлы с накопленной статистикой по прошлым датам (опционально)"
        )
        
        # Выбор файла для сохранения агрегированных данных (Daily/Weekly)
        self.aggregated_output_file = self.select_output_file(
            "Выберите место для сохранения агрегированных данных (Daily/Weekly)",
            "Aggregated_Stats.xlsx"
        )
        
        # Выбор файла для сохранения объединенной накопленной статистики
        self.combined_accumulated_file = self.select_output_file(
            "Выберите место для сохранения объединенной накопленной статистики",
            "Combined_Accumulated.xlsx"
        )
        
        logger.info("Все файлы и пути выбраны успешно")
        print("Все файлы и пути выбраны успешно")

    def create_article_family_file(self) -> bool:
        if self.use_existing_article_file:
            logger.info(f"Используется существующий файл Артикул-Семья: {self.article_family_file}")
            print(f"Используется существующий файл Артикул-Семья: {self.article_family_file}")
            return True
        
        logger.info(f"Обработка файлов для Артикул-Семья: {self.input_article_files}")
        print("Создание файла Артикул-Семья...")
        
        unique_data = set()
        processed_files = 0
        total_files = len(self.input_article_files)

        for i, file_path in enumerate(self.input_article_files, 1):
            try:
                logger.info(f"Обработка файла {i}/{total_files}: {file_path}")
                print(f"Обработка файла {i} из {total_files} для Артикул-Семья...")
                df = pd.read_excel(file_path, sheet_name="Информация о складском запасе с")
                
                if "Артикул" not in df.columns or "Группа материалов" not in df.columns:
                    logger.warning(f"Пропущен файл {file_path}: отсутствуют столбцы 'Артикул' или 'Группа материалов'")
                    print(f"Пропущен файл {file_path}: отсутствуют столбцы 'Артикул' или 'Группа материалов'")
                    continue
                
                for _, row in df[["Артикул", "Группа материалов"]].iterrows():
                    if pd.isna(row["Артикул"]) or pd.isna(row["Группа материалов"]):
                        continue
                    unique_data.add((str(row["Артикул"]), str(row["Группа материалов"])))
                
                processed_files += 1
                
            except Exception as e:
                logger.error(f"Ошибка при обработке файла {file_path}: {str(e)}")
                print(f"Ошибка при обработке файла {file_path}: {str(e)}")

        if not unique_data:
            logger.error("Не найдено валидных данных для Артикул-Семья.")
            print("Не найдено валидных данных для Артикул-Семья.")
            return False

        result_df = pd.DataFrame(list(unique_data), columns=["Артикул", "Семья"])
        result_df.to_excel(self.article_family_file, index=False)
        
        success_message = (f"Файл Артикул-Семья сохранен в {self.article_family_file}\n"
                          f"Обработано файлов: {processed_files}\n"
                          f"Найдено уникальных комбинаций Артикул-Семья: {len(unique_data)}")
        logger.info(success_message)
        print(success_message)
        
        return True

    def read_excel_files(self, files: List[str]) -> pd.DataFrame:
        if not files:
            raise ValueError("Не выбрано ни одного файла.")
        
        logger.info(f"Чтение файлов: {files}")
        print("Чтение файлов...")
        dfs = []
        total_rows = 0
        
        for i, file in enumerate(files, 1):
            logger.info(f"Чтение файла {i}/{len(files)}: {os.path.basename(file)}")
            print(f"Чтение файла {i} из {len(files)}: {os.path.basename(file)}")
            
            try:
                with pd.ExcelFile(file) as xl:
                    sheet_name = "Набор" if "Набор" in xl.sheet_names else xl.sheet_names[0]
                    logger.info(f"Используется лист '{sheet_name}' в {os.path.basename(file)}")
                    df = pd.read_excel(xl, sheet_name=sheet_name)
                    logger.info(f"Прочитано {len(df)} строк из файла {os.path.basename(file)}")
                    dfs.append(df)
                    total_rows += len(df)
            except Exception as e:
                logger.error(f"Ошибка при чтении файла {file}: {str(e)}")
                print(f"Ошибка при чтении файла {file}: {str(e)}")
                raise
        
        if not dfs:
            raise ValueError("Не удалось прочитать ни один файл.")
        
        result_df = pd.concat(dfs, ignore_index=True)
        logger.info(f"После объединения: {len(result_df)} строк из {len(files)} файлов (исходно {total_rows} строк)")
        print(f"Обработано файлов: {len(files)}\n"
              f"Общее количество строк: {len(result_df)}\n"
              f"Среднее количество строк на файл: {len(result_df) // len(files) if files else 0}")
        
        return result_df

    def validate_required_columns(self, df: pd.DataFrame) -> bool:
        missing_columns = [col for col in self.required_columns if col not in df.columns]
        if missing_columns:
            error_message = "Отсутствуют обязательные столбцы:\n"
            for col in missing_columns:
                error_message += f"- {col}: {self.required_columns[col]}\n"
            logger.error(error_message)
            print(error_message)
            return False
        return True

    def process_datetime_column(self, df: pd.DataFrame) -> pd.DataFrame:
        logger.info("Обработка столбца 'Время завершения'")
        print("Обработка дат и времени...")
        
        if "Время завершения" not in df.columns:
            raise ValueError("Столбец 'Время завершения' не найден.")
        
        original_values = df["Время завершения"].copy()
        
        logger.debug(f"Первые 10 значений в 'Время завершения' (до обработки): {df['Время завершения'].head(10).tolist()}")
        logger.debug(f"Типы данных: {df['Время завершения'].head(10).apply(type).tolist()}")
        
        for fmt in ["%d.%m.%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S"]:
            df["Время завершения"] = pd.to_datetime(
                df["Время завершения"],
                format=fmt,
                errors="coerce"
            )
            if df["Время завершения"].notna().all():
                break
        
        invalid_mask = df["Время завершения"].isna()
        invalid_count = invalid_mask.sum()
        
        if invalid_count > 0:
            invalid_values = original_values[invalid_mask].unique()
            logger.warning(f"Найдено {invalid_count} непреобразуемых значений в 'Время завершения': {invalid_values[:5]}")
            print(f"Предупреждение: Найдено {invalid_count} непреобразуемых значений в столбце 'Время завершения'. "
                  f"Примеры: {', '.join(str(x) for x in invalid_values[:5])}")
        
        df.insert(
            loc=df.columns.get_loc("Время завершения") + 1,
            column="Время",
            value=df["Время завершения"].dt.strftime("%H:%M:%S").where(df["Время завершения"].notna(), np.nan)
        )
        
        df["Время завершения"] = df["Время завершения"].dt.strftime("%d.%m.%Y").where(
            df["Время завершения"].notna(), np.nan
        )
        df = df.rename(columns={"Время завершения": "Дата завершения"})
        
        logger.debug(f"После обработки столбцов даты и времени: {df.head(3).to_dict()}")
        return df

    def filter_by_wave(self, df: pd.DataFrame) -> pd.DataFrame:
        logger.info("Фильтрация по столбцу 'Волна операции'")
        print("Фильтрация по волне операции...")
        
        if "Волна операции" not in df.columns:
            raise ValueError("Столбец 'Волна операции' не найден.")
        
        unique_waves = df["Волна операции"].value_counts()
        wave_message = "Уникальные значения в столбце 'Волна операции':\n" + "\n".join(
            f"{wave} ({count} строк)" for wave, count in unique_waves.items()
        )
        logger.info(wave_message)
        print(wave_message)
        
        exclude_patterns = [
            "(OPT)", "(PROMO)",
            "(POSM штучный отбор из пикинга)",
            "(POSM штучный отбор со стеллажей)",
            "Отгрузка ВОЗВРАТОВ"
        ]
        
        df["Волна операции"] = df["Волна операции"].astype(str).str.strip()
        df_before = df.copy()
        df = df[~df["Волна операции"].str.contains("|".join(exclude_patterns), case=False, na=False)]
        
        rows_removed = len(df_before) - len(df)
        logger.info(f"Удалено {rows_removed} строк после фильтрации по волне операции")
        print(f"Удалено {rows_removed} строк после фильтрации по волне операции")
        
        if len(df) == 0:
            raise ValueError("Все данные были удалены после фильтрации волны операции.")
        
        return df

    def analyze_box_quantity(self, df: pd.DataFrame) -> pd.DataFrame:
        logger.info("Анализ количества коробов")
        print("Анализ количества коробов...")
        
        if "Количество" not in df.columns:
            raise ValueError("Столбец 'Количество' не найден в данных.")
        
        df["Количество"] = pd.to_numeric(df["Количество"], errors="coerce")
        df["менее 4"] = df["Количество"] < 4
        
        less_than_4 = df["менее 4"].sum()
        total_rows = len(df)
        
        logger.info(f"Строк с количеством коробов меньше 4: {less_than_4} из {total_rows}")
        print(f"Строк с количеством коробов меньше 4: {less_than_4} из {total_rows} ({less_than_4/total_rows:.1%})")
        
        return df

    def add_family_column(self, df: pd.DataFrame) -> pd.DataFrame:
        logger.info("Добавление столбца 'Семья'")
        print("Добавление столбца 'Семья'...")
        
        if "Артикул" not in df.columns:
            logger.error(f"Столбец 'Артикул' не найден. Доступные столбцы: {df.columns.tolist()}")
            print(f"Столбец 'Артикул' не найден. Доступные столбцы: {df.columns.tolist()}")
            raise ValueError("Столбец 'Артикул' не найден в данных.")
        
        if not self.article_family_file:
            logger.info("Файл 'Артикул-Семья' не создан. Будет добавлен пустой столбец 'Семья'.")
            print("Файл 'Артикул-Семья' не создан. Добавлен пустой столбец 'Семья'.")
            article_loc = df.columns.get_loc("Артикул")
            df.insert(loc=article_loc + 1, column="Семья", value=np.nan)
            return df
        
        try:
            logger.info(f"Чтение файла 'Артикул-Семья': {os.path.basename(self.article_family_file)}")
            print(f"Чтение файла 'Артикул-Семья': {os.path.basename(self.article_family_file)}")
            df_article = pd.read_excel(self.article_family_file)
            logger.info(f"Столбцы в файле Артикул-Семья: {df_article.columns.tolist()}")
            
            if "Артикул" not in df_article.columns or "Семья" not in df_article.columns:
                if len(df_article.columns) >= 2:
                    df_article.columns = ["Артикул", "Семья"] + df_article.columns[2:].tolist()
                    logger.info("Переименованы столбцы в ['Артикул', 'Семья']")
                    print("Переименованы столбцы в ['Артикул', 'Семья']")
                else:
                    raise ValueError("В файле 'Артикул-Семья' недостаточно столбцов.")
            
            family_dict = {str(row["Артикул"]): str(row["Семья"]) for index, row in df_article.iterrows() if pd.notna(row["Артикул"])}
            logger.info(f"Загружено {len(family_dict)} уникальных артикулов из файла соответствий")
            print(f"Загружено {len(family_dict)} уникальных артикулов из файла соответствий")
            
            df["Семья"] = df["Артикул"].map(lambda x: family_dict.get(str(x), np.nan))
            
            na_count = df["Семья"].isna().sum()
            if na_count > 0:
                logger.warning(f"В столбце 'Семья' найдено {na_count} значений NaN")
                print(f"Предупреждение: В столбце 'Семья' найдено {na_count} значений NaN ({na_count/len(df):.1%}). "
                      "Проверьте соответствие артикулов.")
        except Exception as e:
            logger.error(f"Ошибка при добавлении столбца 'Семья': {str(e)}")
            print(f"Ошибка при обработке файла 'Артикул-Семья': {str(e)}")
            article_loc = df.columns.get_loc("Артикул")
            df.insert(loc=article_loc + 1, column="Семья", value=np.nan)
        
        return df

    def prepare_final_dataframe(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        logger.info("Подготовка итоговых данных")
        print("Подготовка итоговых данных...")
        
        columns_to_drop = ["Партия", "Единица измерения", "Количество коробов"]
        df = df.drop(columns=[col for col in columns_to_drop if col in df.columns])
        
        if "Целевой контейнер" in df.columns:
            df["№ короба"] = df["Целевой контейнер"].astype(str)
        else:
            raise ValueError("Столбец 'Целевой контейнер' не найден.")
        
        required_columns = {
            "Заказ": "a", "Семья": "k", "Волна операции": "b",
            "Код комбинации": "g", "Дата завершения": "e",
            "Исполнитель": "r", "Целевой контейнер": "s"
        }
        
        missing_cols = [col for col in required_columns if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Не найдены необходимые столбцы: {', '.join(missing_cols)}")
        
        try:
            for col in required_columns:
                df[col] = df[col].fillna("").astype(str)
            
            df["1_Заказ+Семья"] = df["Заказ"] + df["Семья"]
            df["2_1+Волна"] = df["1_Заказ+Семья"] + df["Волна операции"]
            df["3_2+Комбин"] = df["2_1+Волна"] + df["Код комбинации"]
            df["4_3+Дата"] = df["3_2+Комбин"] + df["Дата завершения"]
            df["5_4+Исполнитель"] = df["4_3+Дата"] + df["Исполнитель"]
            df["6_Заказ+Комби+КОР"] = df["Заказ"] + df["Код комбинации"] + df["Целевой контейнер"]
        except Exception as e:
            logger.error(f"Ошибка при создании вычисляемых столбцов: {str(e)}")
            print(f"Ошибка при создании вычисляемых столбцов: {str(e)}")
            raise
        
        try:
            unique_s_values = df.drop_duplicates(subset=["Целевой контейнер"])
            
            required_columns_for_unique = {
                "Целевой контейнер": "s", "Заказ": "a", "Семья": "k", "Волна операции": "b",
                "Код комбинации": "g", "Дата завершения": "e", "Исполнитель": "r",
                "менее 4": "m", "Количество": "x", "1_Заказ+Семья": "y",
                "2_1+Волна": "z", "3_2+Комбин": "aa", "4_3+Дата": "ab",
                "5_4+Исполнитель": "ac", "6_Заказ+Комби+КОР": "ad",
                "Время": "time"
            }
            
            missing_cols = [col for col in required_columns_for_unique.keys() if col not in df.columns]
            if missing_cols:
                logger.error(f"В данных отсутствуют столбцы для Unique_S_Data: {', '.join(missing_cols)}")
                print(f"В данных отсутствуют столбцы для Unique_S_Data: {', '.join(missing_cols)}")
                raise ValueError(f"В данных отсутствуют столбцы для Unique_S_Data: {', '.join(missing_cols)}")
            
            unique_df = unique_s_values[list(required_columns_for_unique.keys())]
            logger.info(f"Создана вкладка Unique_S_Data с {len(unique_df)} строками")
            print(f"Создана вкладка Unique_S_Data с {len(unique_df)} строками")
            
            return df, unique_df
        except Exception as e:
            logger.error(f"Ошибка при создании Unique_S_Data: {str(e)}")
            print(f"Ошибка при создании Unique_S_Data: {str(e)}")
            raise

    def save_result(self, main_df: pd.DataFrame, unique_df: pd.DataFrame) -> None:
        logger.info(f"Сохранение результата в {self.output_file}")
        print("Сохранение результата...")
        
        # Проверка входных данных
        if main_df.empty:
            logger.error("main_df пустой, невозможно сохранить данные.")
            print("Ошибка: main_df пустой, невозможно сохранить данные.")
            raise ValueError("main_df пустой, невозможно сохранить данные.")
        if unique_df.empty:
            logger.error("unique_df пустой, невозможно сохранить данные.")
            print("Ошибка: unique_df пустой, невозможно сохранить данные.")
            raise ValueError("unique_df пустой, невозможно сохранить данные.")
        
        logger.info(f"Размер main_df: {len(main_df)} строк, {len(main_df.columns)} столбцов")
        logger.info(f"Размер unique_df: {len(unique_df)} строк, {len(unique_df.columns)} столбцов")
        print(f"Размер main_df: {len(main_df)} строк, {len(main_df.columns)} столбцов")
        print(f"Размер unique_df: {len(unique_df)} строк, {len(unique_df.columns)} столбцов")
        
        try:
            # Удаление файла, если он существует
            if os.path.exists(self.output_file):
                try:
                    os.remove(self.output_file)
                    logger.info(f"Существующий файл {self.output_file} удален.")
                    print(f"Существующий файл {self.output_file} удален.")
                except PermissionError:
                    logger.error(f"Ошибка: Нет прав доступа для удаления файла {self.output_file}. Закройте файл и попробуйте снова.")
                    print(f"Ошибка: Нет прав доступа для удаления файла {self.output_file}. Закройте файл и попробуйте снова.")
                    raise
                except Exception as e:
                    logger.error(f"Ошибка при удалении файла {self.output_file}: {str(e)}")
                    print(f"Ошибка при удалении файла {self.output_file}: {str(e)}")
                    raise
            
            # Сохранение данных в Excel
            with pd.ExcelWriter(self.output_file, engine='openpyxl') as writer:
                # Сохраняем данные на листы
                main_df.to_excel(writer, sheet_name='Main_Data', index=False)
                unique_df.to_excel(writer, sheet_name='Unique_S_Data', index=False)
            
            # Проверяем, что файл создался успешно
            if os.path.exists(self.output_file):
                logger.info(f"Файл {self.output_file} успешно сохранен.")
                print(f"Файл {self.output_file} успешно сохранен.")
            else:
                raise FileNotFoundError(f"Файл {self.output_file} не был создан.")

        except Exception as e:
            logger.error(f"Ошибка при сохранении файла: {str(e)}")
            print(f"Ошибка при сохранении файла: {str(e)}")
            
            # Альтернативный способ сохранения без форматирования
            try:
                logger.info("Попытка сохранения без форматирования...")
                print("Попытка сохранения без форматирования...")
                
                with pd.ExcelWriter(self.output_file, engine='openpyxl') as writer:
                    main_df.to_excel(writer, sheet_name='Main_Data', index=False)
                    unique_df.to_excel(writer, sheet_name='Unique_S_Data', index=False)
                
                logger.info(f"Файл {self.output_file} сохранен без форматирования.")
                print(f"Файл {self.output_file} сохранен без форматирования.")
                
            except Exception as backup_error:
                logger.error(f"Критическая ошибка при сохранении файла: {str(backup_error)}")
                print(f"Критическая ошибка при сохранении файла: {str(backup_error)}")
                raise

    def analyze_data(self):
        logger.info(f"Запуск анализа данных для файла {self.output_file}")
        print("Запуск анализа данных...")
        
        if not self.output_file:
            logger.error("Файл 'Отчет' не создан, анализ невозможен.")
            print("Ошибка: Файл 'Отчет' не создан, анализ невозможен.")
            return False
        
        processor = ExcelProcessor(self.output_file)
        success = processor.run_full_analysis(output_file=self.final_output_file)
        
        if success:
            logger.info("Анализ выполнен успешно.")
            print(f"Анализ выполнен успешно! Проверьте файл '{self.final_output_file}'.")
            self.process_aggregated_stats()  # Автоматически переходим к агрегации
        else:
            logger.error("Ошибка при выполнении анализа.")
            print("Ошибка при выполнении анализа.")
        
        return success

    def process_aggregated_stats(self):
        logger.info(f"Агрегация данных по дням и неделям из {self.final_output_file}")
        print("Агрегация данных по дням и неделям...")

        try:
            # Чтение данных из листа "Ежедневная статистика"
            df = pd.read_excel(self.final_output_file, sheet_name="Ежедневная статистика")
            logger.info(f"Прочитано {len(df)} строк из листа 'Ежедневная статистика'")
            print(f"Прочитано {len(df)} строк из листа 'Ежедневная статистика'")

            if df.empty:
                logger.error("Лист 'Ежедневная статистика' пуст!")
                print("Ошибка: Лист 'Ежедневная статистика' пуст!")
                return

            # Добавляем "День недели" на русском
            df['Дата'] = pd.to_datetime(df['Дата'], format='%d.%m.%Y', errors='coerce')
            df['День недели'] = df['Дата'].dt.strftime('%A').map(DAY_OF_WEEK_RU)

            # Обработка процентных столбцов
            percentage_columns = ['% Менее 4-х', '% Менее 4-х (DUB)', '% Менее 4-х (ECRU)', '% Менее 4-х (MAAG)', '% Менее 4-х (VILET)']
            for col in percentage_columns:
                if col in df.columns:
                    if df[col].dtype == 'object':
                        df[col] = df[col].str.replace(',', '.').str.rstrip('%').astype(float)
                    else:
                        df[col] = df[col].astype(float)

            # Агрегация по дням
            daily_agg = df.groupby(['Дата', 'День недели']).agg({
                'Всего коробов': 'sum',
                'Менее 4-х': 'sum',
                'Всего (DUB)': 'sum',
                'Менее 4-х (DUB)': 'sum',
                'Всего (ECRU)': 'sum',
                'Менее 4-х (ECRU)': 'sum',
                'Всего (MAAG)': 'sum',
                'Менее 4-х (MAAG)': 'sum',
                'Всего (VILET)': 'sum',
                'Менее 4-х (VILET)': 'sum'
            }).reset_index()

            # Расчет процентов для дневной агрегации
            daily_agg['% Менее 4-х'] = (daily_agg['Менее 4-х'] / daily_agg['Всего коробов'] * 100).round(1).fillna(0)
            daily_agg['% Менее 4-х (DUB)'] = (daily_agg['Менее 4-х (DUB)'] / daily_agg['Всего (DUB)'] * 100).round(1).fillna(0)
            daily_agg['% Менее 4-х (ECRU)'] = (daily_agg['Менее 4-х (ECRU)'] / daily_agg['Всего (ECRU)'] * 100).round(1).fillna(0)
            daily_agg['% Менее 4-х (MAAG)'] = (daily_agg['Менее 4-х (MAAG)'] / daily_agg['Всего (MAAG)'] * 100).round(1).fillna(0)
            daily_agg['% Менее 4-х (VILET)'] = (daily_agg['Менее 4-х (VILET)'] / daily_agg['Всего (VILET)'] * 100).round(1).fillna(0)

            # Форматирование процентов с символом "%"
            for col in percentage_columns:
                if col in daily_agg.columns:
                    daily_agg[col] = daily_agg[col].apply(lambda x: f"{x}%")

            # Форматирование даты
            daily_agg['Дата'] = daily_agg['Дата'].dt.strftime('%d.%m.%Y')

            # Порядок столбцов для дневной агрегации
            daily_agg = daily_agg[['Дата', 'День недели', 'Всего коробов', 'Менее 4-х', '% Менее 4-х',
                                   'Всего (DUB)', 'Менее 4-х (DUB)', '% Менее 4-х (DUB)',
                                   'Всего (ECRU)', 'Менее 4-х (ECRU)', '% Менее 4-х (ECRU)',
                                   'Всего (MAAG)', 'Менее 4-х (MAAG)', '% Менее 4-х (MAAG)',
                                   'Всего (VILET)', 'Менее 4-х (VILET)', '% Менее 4-х (VILET)']]

            # Агрегация для новой накопительной недели
            # Определяем номер новой недели (на основе предыдущих данных в aggregated_output_file)
            max_week = 0
            if os.path.exists(self.aggregated_output_file):
                try:
                    existing_weekly = pd.read_excel(self.aggregated_output_file, sheet_name="Weekly")
                    if not existing_weekly.empty:
                        max_week = existing_weekly['Week'].max()
                except:
                    pass
            new_week = max_week + 1

            # Суммируем данные для новой недели (без привязки к календарной неделе)
            weekly_agg = df.agg({
                'Всего коробов': 'sum',
                'Менее 4-х': 'sum',
                'Всего (DUB)': 'sum',
                'Менее 4-х (DUB)': 'sum',
                'Всего (ECRU)': 'sum',
                'Менее 4-х (ECRU)': 'sum',
                'Всего (MAAG)': 'sum',
                'Менее 4-х (MAAG)': 'sum',
                'Всего (VILET)': 'sum',
                'Менее 4-х (VILET)': 'sum'
            }).to_frame().T
            weekly_agg['Week'] = new_week

            # Расчет процентов для недельной агрегации
            weekly_agg['% Менее 4-х'] = (weekly_agg['Менее 4-х'] / weekly_agg['Всего коробов'] * 100).round(1).fillna(0)
            weekly_agg['% Менее 4-х (DUB)'] = (weekly_agg['Менее 4-х (DUB)'] / weekly_agg['Всего (DUB)'] * 100).round(1).fillna(0)
            weekly_agg['% Менее 4-х (ECRU)'] = (weekly_agg['Менее 4-х (ECRU)'] / weekly_agg['Всего (ECRU)'] * 100).round(1).fillna(0)
            weekly_agg['% Менее 4-х (MAAG)'] = (weekly_agg['Менее 4-х (MAAG)'] / weekly_agg['Всего (MAAG)'] * 100).round(1).fillna(0)
            weekly_agg['% Менее 4-х (VILET)'] = (weekly_agg['Менее 4-х (VILET)'] / weekly_agg['Всего (VILET)'] * 100).round(1).fillna(0)

            # Форматирование процентов с символом "%"
            for col in percentage_columns:
                if col in weekly_agg.columns:
                    weekly_agg[col] = weekly_agg[col].apply(lambda x: f"{x}%")

            # Порядок столбцов для недельной агрегации
            weekly_agg = weekly_agg[['Week', 'Всего коробов', 'Менее 4-х', '% Менее 4-х',
                                     'Всего (DUB)', 'Менее 4-х (DUB)', '% Менее 4-х (DUB)',
                                     'Всего (ECRU)', 'Менее 4-х (ECRU)', '% Менее 4-х (ECRU)',
                                     'Всего (MAAG)', 'Менее 4-х (MAAG)', '% Менее 4-х (MAAG)',
                                     'Всего (VILET)', 'Менее 4-х (VILET)', '% Менее 4-х (VILET)']]

            # Сохранение результатов
            if os.path.exists(self.aggregated_output_file):
                os.remove(self.aggregated_output_file)

            wb = Workbook()
            ws_daily = wb.active
            ws_daily.title = "Daily"
            ws_weekly = wb.create_sheet(title="Weekly")

            # Сохранение дневной агрегации
            for r_idx, row in enumerate(dataframe_to_rows(daily_agg, index=False, header=True), 1):
                for c_idx, value in enumerate(row, 1):
                    cell = ws_daily.cell(row=r_idx, column=c_idx, value=value)
                    if r_idx == 1:
                        cell.font = Font(bold=True, color="FFFFFF")
                        cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
                        cell.alignment = Alignment(horizontal="center", vertical="center")
                    else:
                        cell.alignment = Alignment(horizontal="center", vertical="center")
                    thin_border = Border(
                        left=Side(style='thin'),
                        right=Side(style='thin'),
                        top=Side(style='thin'),
                        bottom=Side(style='thin')
                    )
                    cell.border = thin_border

            # Автоматическая настройка ширины столбцов
            for column in ws_daily.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 20)
                ws_daily.column_dimensions[column_letter].width = adjusted_width

            # Сохранение недельной агрегации
            for r_idx, row in enumerate(dataframe_to_rows(weekly_agg, index=False, header=True), 1):
                for c_idx, value in enumerate(row, 1):
                    cell = ws_weekly.cell(row=r_idx, column=c_idx, value=value)
                    if r_idx == 1:
                        cell.font = Font(bold=True, color="FFFFFF")
                        cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
                        cell.alignment = Alignment(horizontal="center", vertical="center")
                    else:
                        cell.alignment = Alignment(horizontal="center", vertical="center")
                    thin_border = Border(
                        left=Side(style='thin'),
                        right=Side(style='thin'),
                        top=Side(style='thin'),
                        bottom=Side(style='thin')
                    )
                    cell.border = thin_border

            # Автоматическая настройка ширины столбцов
            for column in ws_weekly.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 20)
                ws_weekly.column_dimensions[column_letter].width = adjusted_width

            wb.save(self.aggregated_output_file)
            logger.info(f"Агрегированные данные сохранены в {self.aggregated_output_file}")
            print(f"Агрегированные данные сохранены в {self.aggregated_output_file}")

            # Логирование результатов
            logger.info("\n=== Дневная агрегация ===")
            print("\n=== Дневная агрегация ===")
            print(daily_agg.to_string(index=False))
            logger.info("\n=== Недельная агрегация ===")
            print("\n=== Недельная агрегация ===")
            print(weekly_agg.to_string(index=False))

        except FileNotFoundError:
            logger.error(f"Файл {self.final_output_file} не найден!")
            print(f"Ошибка: Файл {self.final_output_file} не найден!")
        except Exception as e:
            logger.error(f"Ошибка при агрегации данных: {str(e)}")
            print(f"Ошибка при агрегации данных: {str(e)}")

    def combine_accumulated_stats(self):
        logger.info(f"Объединение накопленных данных из файлов: {self.accumulated_files}")
        print("Объединение накопленных данных...")
        
        # Добавляем текущий агрегированный файл в список для объединения
        files_to_process = self.accumulated_files.copy()
        if hasattr(self, 'aggregated_output_file') and os.path.exists(self.aggregated_output_file):
            files_to_process.append(self.aggregated_output_file)
            logger.info(f"Добавлен текущий агрегированный файл: {self.aggregated_output_file}")
            print(f"Добавлен текущий агрегированный файл: {self.aggregated_output_file}")
        
        if not files_to_process:
            logger.info("Файлы с накопленной статистикой не выбраны. Пропускаем объединение.")
            print("Файлы с накопленной статистикой не выбраны. Пропускаем объединение.")
            return
        
        daily_dfs = []
        weekly_dfs = []
        
        for file in files_to_process:
            try:
                logger.info(f"Чтение файла накопленной статистики: {file}")
                print(f"Чтение файла: {file}")
                
                xl = pd.ExcelFile(file)
                
                if "Daily" in xl.sheet_names:
                    daily_df = pd.read_excel(file, sheet_name="Daily")
                    daily_dfs.append(daily_df)
                    logger.info(f"Прочитан лист 'Daily' из {file}: {len(daily_df)} строк")
                    print(f"Прочитан лист 'Daily': {len(daily_df)} строк")
                
                if "Weekly" in xl.sheet_names:
                    weekly_df = pd.read_excel(file, sheet_name="Weekly")
                    weekly_dfs.append(weekly_df)
                    logger.info(f"Прочитан лист 'Weekly' из {file}: {len(weekly_df)} строк")
                    print(f"Прочитан лист 'Weekly': {len(weekly_df)} строк")
                
            except Exception as e:
                logger.error(f"Ошибка при чтении файла {file}: {str(e)}")
                print(f"Ошибка при чтении файла {file}: {str(e)}")
                continue
        
        try:
            if daily_dfs:
                combined_daily = pd.concat(daily_dfs, ignore_index=True)
                # Определяем числовые столбцы для суммирования
                numeric_columns = ['Всего коробов', 'Менее 4-х', 
                                  'Всего (DUB)', 'Менее 4-х (DUB)', 
                                  'Всего (ECRU)', 'Менее 4-х (ECRU)', 
                                  'Всего (MAAG)', 'Менее 4-х (MAAG)', 
                                  'Всего (VILET)', 'Менее 4-х (VILET)']
                # Преобразуем процентные столбцы в числа, если они в формате строки
                for col in ['% Менее 4-х', '% Менее 4-х (DUB)', '% Менее 4-х (ECRU)', '% Менее 4-х (MAAG)', '% Менее 4-х (VILET)']:
                    if col in combined_daily.columns and combined_daily[col].dtype == 'object':
                        combined_daily[col] = combined_daily[col].str.replace('%', '').astype(float)
                
                # Суммируем данные по дате и дню недели
                combined_daily = combined_daily.groupby(['Дата', 'День недели']).agg({
                    col: 'sum' for col in numeric_columns
                }).reset_index()
                
                # Пересчитываем проценты
                combined_daily['% Менее 4-х'] = (combined_daily['Менее 4-х'] / combined_daily['Всего коробов'] * 100).round(1).fillna(0)
                combined_daily['% Менее 4-х (DUB)'] = (combined_daily['Менее 4-х (DUB)'] / combined_daily['Всего (DUB)'] * 100).round(1).fillna(0)
                combined_daily['% Менее 4-х (ECRU)'] = (combined_daily['Менее 4-х (ECRU)'] / combined_daily['Всего (ECRU)'] * 100).round(1).fillna(0)
                combined_daily['% Менее 4-х (MAAG)'] = (combined_daily['Менее 4-х (MAAG)'] / combined_daily['Всего (MAAG)'] * 100).round(1).fillna(0)
                combined_daily['% Менее 4-х (VILET)'] = (combined_daily['Менее 4-х (VILET)'] / combined_daily['Всего (VILET)'] * 100).round(1).fillna(0)
                
                # Форматируем процентные столбцы
                for col in ['% Менее 4-х', '% Менее 4-х (DUB)', '% Менее 4-х (ECRU)', '% Менее 4-х (MAAG)', '% Менее 4-х (VILET)']:
                    combined_daily[col] = combined_daily[col].apply(lambda x: f"{x}%")
                
                # Устанавливаем порядок столбцов
                combined_daily = combined_daily[['Дата', 'День недели', 'Всего коробов', 'Менее 4-х', '% Менее 4-х',
                                                'Всего (DUB)', 'Менее 4-х (DUB)', '% Менее 4-х (DUB)',
                                                'Всего (ECRU)', 'Менее 4-х (ECRU)', '% Менее 4-х (ECRU)',
                                                'Всего (MAAG)', 'Менее 4-х (MAAG)', '% Менее 4-х (MAAG)',
                                                'Всего (VILET)', 'Менее 4-х (VILET)', '% Менее 4-х (VILET)']]
                
                logger.info(f"Объединено {len(daily_dfs)} дневных таблиц: {len(combined_daily)} строк после агрегации")
                print(f"Объединено {len(daily_dfs)} дневных таблиц: {len(combined_daily)} строк после агрегации")
                
                combined_daily['Дата'] = pd.to_datetime(combined_daily['Дата'], format='%d.%m.%Y', errors='coerce')
                combined_daily = combined_daily.sort_values('Дата').reset_index(drop=True)
                combined_daily['Дата'] = combined_daily['Дата'].dt.strftime('%d.%m.%Y')
            else:
                combined_daily = pd.DataFrame()
                logger.warning("Нет данных для объединения дневной статистики")
                print("Нет данных для объединения дневной статистики")
            
            if weekly_dfs:
                # Определяем максимальный номер недели из всех файлов
                max_week = 0
                for file in files_to_process:
                    try:
                        xl = pd.ExcelFile(file)
                        if "Weekly" in xl.sheet_names:
                            weekly_df = pd.read_excel(file, sheet_name="Weekly")
                            if not weekly_df.empty and 'Week' in weekly_df.columns:
                                current_max = weekly_df['Week'].max()
                                if pd.notna(current_max) and current_max > max_week:
                                    max_week = current_max
                    except:
                        continue
                
                combined_weekly = pd.concat(weekly_dfs, ignore_index=True)
                # Определяем числовые столбцы
                numeric_columns = ['Всего коробов', 'Менее 4-х', 
                                  'Всего (DUB)', 'Менее 4-х (DUB)', 
                                  'Всего (ECRU)', 'Менее 4-х (ECRU)', 
                                  'Всего (MAAG)', 'Менее 4-х (MAAG)', 
                                  'Всего (VILET)', 'Менее 4-х (VILET)']
                # Преобразуем процентные столбцы в числа, если они в формате строки
                for col in ['% Менее 4-х', '% Менее 4-х (DUB)', '% Менее 4-х (ECRU)', '% Менее 4-х (MAAG)', '% Менее 4-х (VILET)']:
                    if col in combined_weekly.columns and combined_weekly[col].dtype == 'object':
                        combined_weekly[col] = combined_weekly[col].str.replace('%', '').astype(float)
                
                # Присваиваем новый номер недели для последней записи (из aggregated_output_file)
                if (hasattr(self, 'aggregated_output_file') and 
                    self.aggregated_output_file in files_to_process and 
                    not combined_weekly.empty):
                    last_file_index = files_to_process.index(self.aggregated_output_file)
                    last_weekly_df_rows = len(weekly_dfs[last_file_index])
                    combined_weekly.iloc[-last_weekly_df_rows:, combined_weekly.columns.get_loc('Week')] = max_week + 1
                
                # Устанавливаем порядок столбцов
                combined_weekly = combined_weekly[['Week', 'Всего коробов', 'Менее 4-х', '% Менее 4-х',
                                                  'Всего (DUB)', 'Менее 4-х (DUB)', '% Менее 4-х (DUB)',
                                                  'Всего (ECRU)', 'Менее 4-х (ECRU)', '% Менее 4-х (ECRU)',
                                                  'Всего (MAAG)', 'Менее 4-х (MAAG)', '% Менее 4-х (MAAG)',
                                                  'Всего (VILET)', 'Менее 4-х (VILET)', '% Менее 4-х (VILET)']]
                
                logger.info(f"Объединено {len(weekly_dfs)} недельных таблиц: {len(combined_weekly)} строк")
                print(f"Объединено {len(weekly_dfs)} недельных таблиц: {len(combined_weekly)} строк")
            else:
                combined_weekly = pd.DataFrame()
                logger.warning("Нет данных для объединения недельной статистики")
                print("Нет данных для объединения недельной статистики")
            
            if os.path.exists(self.combined_accumulated_file):
                os.remove(self.combined_accumulated_file)
            
            with pd.ExcelWriter(self.combined_accumulated_file, engine='openpyxl') as writer:
                if not combined_daily.empty:
                    combined_daily.to_excel(writer, sheet_name='Daily', index=False)
                if not combined_weekly.empty:
                    combined_weekly.to_excel(writer, sheet_name='Weekly', index=False)
            
            logger.info(f"Объединенные накопленные данные сохранены в {self.combined_accumulated_file}")
            print(f"Объединенные накопленные данные сохранены в {self.combined_accumulated_file}")
            
        except Exception as e:
            logger.error(f"Ошибка при объединении накопленных данных: {str(e)}")
            print(f"Ошибка при объединении накопленных данных: {str(e)}")

    def process_data(self):
        logger.info("Начало обработки данных")
        print("Начало обработки данных...")
        
        try:
            start_time = time.time()
            
            # Выбор файлов
            self.select_all_files()
            
            # Создание/использование файла Артикул-Семья
            if not self.create_article_family_file():
                logger.error("Не удалось создать файл Артикул-Семья. Завершение программы.")
                print("Не удалось создать файл Артикул-Семья. Завершение программы.")
                return False
            
            # Чтение и объединение файлов
            self.df = self.read_excel_files(self.input_files)
            
            # Проверка обязательных столбцов
            if not self.validate_required_columns(self.df):
                logger.error("Обработка прервана из-за отсутствия обязательных столбцов")
                print("Обработка прервана из-за отсутствия обязательных столбцов")
                return False
            
            # Обработка столбцов
            self.df = self.process_datetime_column(self.df)
            self.df = self.filter_by_wave(self.df)
            self.df = self.analyze_box_quantity(self.df)
            self.df = self.add_family_column(self.df)
            main_df, unique_df = self.prepare_final_dataframe(self.df)
            
            # Сохранение результатов
            self.save_result(main_df, unique_df)
            
            # Анализ данных
            success = self.analyze_data()
            
            # Объединение накопленных данных
            self.combine_accumulated_stats()
            
            end_time = time.time()
            execution_time = end_time - start_time
            logger.info(f"Обработка завершена за {execution_time:.2f} секунд")
            print(f"Обработка завершена за {execution_time:.2f} секунд")
            
            return success
            
        except Exception as e:
            logger.error(f"Критическая ошибка при обработке данных: {str(e)}")
            print(f"Критическая ошибка при обработке данных: {str(e)}")
            return False

def main():
    processor = DataProcessor()
    try:
        success = processor.process_data()
        if success:
            messagebox.showinfo("Успех", "Обработка данных успешно завершена!")
        else:
            messagebox.showerror("Ошибка", "Произошла ошибка при обработке данных. Проверьте лог-файл.")
    except Exception as e:
        logger.error(f"Ошибка в main: {str(e)}")
        print(f"Ошибка: {str(e)}")
        messagebox.showerror("Ошибка", f"Произошла критическая ошибка: {str(e)}")

if __name__ == "__main__":
    main()