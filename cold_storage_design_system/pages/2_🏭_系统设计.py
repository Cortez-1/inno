import base64
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import json
from pathlib import Path
from io import BytesIO
import sys
import os
from scipy.optimize import minimize


# 添加路径以便导入自定义模块
current_file = os.path.abspath(__file__)
PROJECT_ROOT = os.path.dirname(os.path.dirname(current_file))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

try:
    from compressor_database_enhanced import BitzerCompressorCalculator, CDS3001BCalculator
    from heat_load_calculator import HeatLoadCalculator
    from data_sharing import DataSharing
except ImportError as e:
    st.error(f"❌ 模块导入错误: {e}")
    st.info("请确保所有依赖文件都在同一目录下")
    st.stop()

def load_design_data():
    """智能加载设计数据"""
    # 尝试从data_sharing加载
    try:
        from data_sharing import DataSharing
        data_sharing = DataSharing()

        # 检查session_state
        if 'design_data' in st.session_state and st.session_state.design_data:
            return st.session_state.design_data

        # 检查查询参数
        query_params = st.query_params.to_dict()
        if 'project' in query_params:
            project_name = query_params['project']
            design_data = data_sharing.load_design_data(project_name)
            if design_data:
                st.session_state.design_data = design_data
                return design_data

        # 加载最新项目
        design_data = data_sharing.load_design_data()
        if design_data:
            st.session_state.design_data = design_data
            return design_data

    except Exception as e:
        st.warning(f"数据加载警告: {e}")

    return None

class IntelligentColdFanSelector:
    """智能冷风机选型器"""

    def __init__(self, json_file_path="冷风机选型表.json"):
        """初始化冷风机数据库"""
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)

            self.parse_cold_fan_data()
            print(f"✅ 冷风机数据库加载完成，共 {len(self.cold_fans)} 个型号")

        except Exception as e:
            st.error(f"冷风机数据库加载失败: {e}")
            self.cold_fans = []

    def parse_cold_fan_data(self):
        """解析冷风机数据"""
        self.cold_fans = []

        if "选型数据" in self.data and len(self.data["选型数据"]) > 0:
            # 直接从"选型数据"数组获取数据
            self.cold_fans = self.data["选型数据"]
            print(f"✅ 成功解析 {len(self.cold_fans)} 个冷风机型号")

            for fan in self.cold_fans:
                # 确保有统一的字段名称
                if "制冷量_R744(kW)" in fan:
                    fan["单台制冷量（kw）"] = fan["制冷量_R744(kW)"]
                if "风机功率(kW)" in fan:
                    fan["风机功率（kw）"] = fan["风机功率(kW)"]
                if "化霜功率(kW)" in fan:
                    fan["化霜功率（kw）"] = fan["化霜功率(kW)"]
                # 添加制冷剂类型
                fan["制冷剂"] = "R744"

        elif "工作表" in self.data and len(self.data["工作表"]) > 0:
            sheet_data = self.data["工作表"][0]

            # 获取参数行
            param_rows = sheet_data.get("数据类别", [])

            # 找到型号列
            model_data = None
            other_params = []

            for row in param_rows:
                param_name = row.get("参数名称", "")
                if param_name == "型号":
                    model_data = row
                else:
                    other_params.append(row)

            if model_data:
                models = model_data.get("参数值", [])

                # 为每个型号创建记录
                for i, model in enumerate(models):
                    fan_info = {"型号": model}

                    # 添加其他参数
                    for param in other_params:
                        param_name = param.get("参数名称", "")
                        param_values = param.get("参数值", [])

                        if i < len(param_values):
                            fan_info[param_name] = param_values[i]

                    self.cold_fans.append(fan_info)

    def map_defrost_method(self, input_defrost_method):
        """映射输入的除霜方式到数据库中的系列名称"""
        defrost_mapping = {
            "电热除霜": "电热除霜系列",
            "热气除霜": "电热除霜系列",  # 数据库中没有热气除霜系列，暂时映射到电热
            "水除霜": "水除霜系列",
            "自然除霜": "自然除霜系列"
        }

        # 返回映射后的系列名称，如果没有匹配则使用输入值
        return defrost_mapping.get(input_defrost_method, input_defrost_method)

    def get_condition_by_room_temp(self, room_temp):
        """
        根据库温确定冷风机工况
        规则（根据冷风机选型表）：
        - R工况：蒸发温度0℃，环境温度10℃ → 适用于5°C以上的穿堂和高温操作间
        - S工况：蒸发温度-7℃，环境温度0℃ → 适用于-5°C~+5°C的保鲜库
        - T工况：蒸发温度-25℃，环境温度-18℃ → 适用于-20°C~-5°C的冷藏库
        - U工况：蒸发温度-32℃，环境温度-25℃ → 适用于-30°C~-20°C的低温冷藏库
        - V工况：蒸发温度-41℃，环境温度-34℃ → 适用于-30°C以下的速冻库
        """
        if room_temp >= 5:
            return "R工况"  # 5°C以上，穿堂、高温操作间
        elif room_temp >= -5:
            return "S工况"  # -5°C~5°C范围，保鲜库
        elif room_temp >= -20:
            return "T工况"  # -20°C~-5°C范围，冷藏库
        elif room_temp >= -30:
            return "U工况"  # -30°C~-20°C范围，低温冷藏库
        else:
            return "V工况"  # -30°C以下，速冻库

    def select_cold_fan_by_conditions(self, required_capacity_kw, room_temp, defrost_method):
        """
        根据库温和除霜方式选择冷风机

        选型逻辑：
        1. 根据库温确定冷风机工况
        2. 根据除霜方式确定系列
        3. 从符合条件的冷风机中选择制冷量匹配的型号
        4. 基于中等功率设备 和 应用N+1冗余理念
        5. 确保余量在合理≥10%
        6. 选取制冷剂为R744的型号

        Args:
            required_capacity_kw: 所需制冷量(kW)
            room_temp: 库温(°C)
            defrost_method: 除霜方式
        """

        # 1. 确定系列和工况
        series = self.map_defrost_method(defrost_method)
        condition = self.get_condition_by_room_temp(room_temp)

        # 2. 筛选符合条件的冷风机
        suitable_fans = []
        for fan in self.cold_fans:
            # 检查除霜方式和工况
            fan_series = fan.get("系列", "")
            if fan_series != series:
                continue

            fan_condition_desc = fan.get("工况说明", "")
            if condition not in fan_condition_desc:
                continue

            # 检查制冷量
            capacity = fan.get("制冷量_R744(kW)", 0)
            if isinstance(capacity, str):
                try:
                    capacity = float(capacity)
                except:
                    continue

            if capacity <= 0:
                continue

            # 获取功率数据
            suitable_fans.append({
                'fan_data': fan,
                'model': fan.get("型号", ""),
                'capacity': capacity,
                'fan_power': float(fan.get("风机功率(kW)", 0)),
                'defrost_power': float(fan.get("化霜功率(kW)", 0))
            })

        if not suitable_fans:
            return {
                    "selected": False,
                    "message": f"未找到适合{series}、{condition}的冷风机型号"
            }

        # 3. 按容量从小到大排序
        suitable_fans.sort(key=lambda x: x['capacity'])

        # 4. 找出单台刚好满足需求的型号（容量≥需求的最小型号）
        valid_configs = []

        if required_capacity_kw < 20:
            # 优先寻找单台满足需求的型号
            for fan_info in suitable_fans:
                single_capacity = fan_info['capacity']
                if single_capacity >= required_capacity_kw * 1.1:  # 单台余量≥10%
                    excess_percent = (single_capacity - required_capacity_kw) / required_capacity_kw * 100
                    if excess_percent <= 30:  # 余量不超过30%
                        # 记录为候选配置（评分时会考虑）
                        pass

        for fan_info in suitable_fans:
            single_capacity = fan_info['capacity']

            # 计算最小需求台数N
            min_units_required = int(np.ceil(required_capacity_kw / single_capacity))


            # 台数范围控制
            # 小负荷特殊处理：至少2台（避免单点故障）
            min_units = max(2, min_units_required) if required_capacity_kw < 20 else min_units_required

            # 限制最大台数
            max_allowed_units = min(6, max(2, int(required_capacity_kw / 15) + 1))

            # 尝试不同台数配置
            for units in range(min_units, max_allowed_units + 1):
                total_capacity = single_capacity * units
                excess_kw = total_capacity - required_capacity_kw
                excess_percent = (excess_kw / required_capacity_kw) * 100

                # 余量检查：必须在10%-30%范围内
                if excess_percent < 10:
                    continue  # 余量不足，跳过
                elif excess_percent > 30:
                    break  # 余量过大，此型号不适合（因为已按容量排序）

                # 计算总功率
                total_fan_power = fan_info['fan_power'] * units
                total_defrost_power = fan_info['defrost_power'] * units
                total_power = total_fan_power + total_defrost_power

                # 计算配置评分（分数越低越好）
                # 评分项1：余量偏离12%的程度（理想余量）
                margin_score = abs(excess_percent - 12) * 0.8

                # 评分项2：台数经济性
                unit_score = units * 2.0

                # 评分项3：单台容量匹配度
                ideal_single_capacity = required_capacity_kw / units
                capacity_match_score = abs(single_capacity - ideal_single_capacity) / ideal_single_capacity * 1.0

                # 评分项4：功率效率
                power_score = total_power / required_capacity_kw * 0.5
                total_score = margin_score + unit_score + capacity_match_score + power_score

                config = {
                    'fan_info': fan_info,
                    'units': units,
                    'total_capacity': total_capacity,
                    'excess_kw': excess_kw,
                    'excess_percent': excess_percent,
                    'total_power': total_power,
                    'total_fan_power': total_fan_power,
                    'total_defrost_power': total_defrost_power,
                    'selection_score': total_score,
                    'min_units_required': min_units_required,
                    'redundancy_units': 0,
                    'selection_logic': f"余量控制:10%-30%，最佳12%"
                }

                valid_configs.append(config)

        # 5. 选择最优配置
        if valid_configs:
            # 按综合评分排序（分数越低越好）
            valid_configs.sort(key=lambda x: x['selection_score'])
            best_config = valid_configs[0]

            # 如果多个配置分数相近(<0.5分差)，选择台数少的
            if len(valid_configs) > 1:
                top_scores = [c['selection_score'] for c in valid_configs[:3]]
                if max(top_scores) - min(top_scores) < 0.5:
                    # 分数相近，按台数排序
                    valid_configs.sort(key=lambda x: (x['units'], x['selection_score']))
                    best_config = valid_configs[0]

            return self._format_selection_result(best_config, series, condition,
                                                 defrost_method, required_capacity_kw, room_temp)

        else:
            # 如果没有满足10%-30%余量的配置，选择后备方案
            return self._select_fallback_config(suitable_fans, required_capacity_kw,
                                                series, condition, defrost_method, room_temp)

    def _select_fallback_config(self, suitable_fans, required_capacity_kw,
                                series, condition, defrost_method, room_temp):
        """后备方案：选择最接近10%余量的配置"""

        fallback_config = None
        best_margin_diff = float('inf')  # 余量与10%的差值

        for fan_info in suitable_fans:
            single_capacity = fan_info['capacity']

            # 计算最小需求台数
            min_units = int(np.ceil(required_capacity_kw / single_capacity))

            # 尝试不同台数（从小开始）
            for units in range(min_units, min_units + 3):  # 最多尝试+2台
                if units > 6:  # 台数上限
                    break

                total_capacity = single_capacity * units
                excess_kw = total_capacity - required_capacity_kw

                if excess_kw < 0:
                    continue  # 不满足需求

                excess_percent = (excess_kw / required_capacity_kw) * 100

                # 计算余量与10%的差值
                margin_diff = abs(excess_percent - 10)

                if margin_diff < best_margin_diff:
                    best_margin_diff = margin_diff

                    total_fan_power = fan_info['fan_power'] * units
                    total_defrost_power = fan_info['defrost_power'] * units
                    total_power = total_fan_power + total_defrost_power

                    fallback_config = {
                        'fan_info': fan_info,
                        'units': units,
                        'total_capacity': total_capacity,
                        'excess_kw': excess_kw,
                        'excess_percent': excess_percent,
                        'total_power': total_power,
                        'total_fan_power': total_fan_power,
                        'total_defrost_power': total_defrost_power,
                        'selection_score': 999,  # 后备方案低优先级
                        'min_units_required': min_units,
                        'redundancy_units': 0,
                        'warning': f"⚠️ 余量{excess_percent:.1f}%，不在推荐范围(10%-30%)"
                    }

        if fallback_config:
            return self._format_selection_result(fallback_config, series, condition,
                                                 defrost_method, required_capacity_kw, room_temp)
        else:
            return {"selected": False, "message": "未找到满足要求的冷风机配置"}

    def _format_selection_result(self, config, series, condition, defrost_method,
                                 required_capacity_kw, room_temp):
        """格式化选型结果"""
        fan_info = config['fan_info']

        return {
            "selected": True,
            "series": series,
            "condition": condition,
            "model": fan_info['model'],
            "defrost_method": defrost_method,
            "required_capacity_kw": required_capacity_kw,
            "single_capacity_kw": round(fan_info['capacity'], 2),
            "units": config['units'],
            "redundancy": "无冗余",
            "total_capacity_kw": round(config['total_capacity'], 2),
            "excess_kw": round(config['excess_kw'], 2),
            "excess_percent": round(config['excess_percent'], 1),
            "fan_power_kw": round(fan_info['fan_power'], 2),
            "defrost_power_kw": round(fan_info['defrost_power'], 2),
            "total_fan_power_kw": round(config['total_fan_power'], 2),
            "total_defrost_power_kw": round(config['total_defrost_power'], 2),
            "total_power_kw": round(config['total_power'], 2),
            "room_temp": room_temp,
            "selection_logic": f"工况: {condition} (库温{room_temp}°C), 系列: {series}",
            "condition_description": fan_info['fan_data'].get("工况说明", ""),
            "fan_data": fan_info['fan_data'],
            "warning": config.get('warning', ''),
            "selection_score": round(config['selection_score'], 2),
            "min_units_required": config['min_units_required'],
            "selection_strategy": "余量优先(10%-30%)"
        }



class DynamicLoadCorrector:
    """动态负荷校正器"""

    def __init__(self, heat_load_calculator):
        self.calculator = heat_load_calculator

    def correct_heat_load(self, rooms_data, cold_fan_selections, project_info):
        """
        根据选定的冷风机功率重新校正热负荷

        选型逻辑第2点：将已确定好的风机功率、数量、化霜功率
        返回heat_load_calculator重新校正电机热和化霜热
        从而校正设备负荷和机械负荷
        """

        # 冷风机选择结果包含：
        # result['fan_power_kw']: 风机功率 (kW)
        # result['defrost_power_kw']: 化霜功率 (kW)
        # result['units']: 数量

        # 应该用这些实际选型结果更新房间数据
        for selection in cold_fan_selections:
            room_name = selection['room_name']
            result = selection['selection_result']

            if result['selected']:
                # 找到对应的房间数据
                for room in rooms_data:
                    if room['room_name'] == room_name:
                        room['fan_power_kw'] = result['fan_power_kw']  # kW
                        room['defrost_power_kw'] = result['defrost_power_kw']  # kW
                        room['fan_count'] = result['units']  # 数量
                        break

        corrected_rooms = []

        for room in rooms_data:
            # 复制房间数据
            corrected_room = room.copy()

            # 如果有冷风机信息，计算额外的热负荷
            if 'fan_power_kw' in room and 'defrost_power_kw' in room and 'fan_count' in room:

                # 计算新的电机热和化霜热
                # 电机热 = 风机功率 × 数量
                units = result.get('units', 1)
                fan_motor_heat = result['fan_power_kw'] * units

                # 化霜热 = 化霜功率 × 化霜时间系数
                defrost_heat = result['defrost_power_kw'] * 1 / 24

                # 创建修正后的房间数据
                corrected_room['additional_motor_heat'] = fan_motor_heat
                corrected_room['additional_defrost_heat'] = defrost_heat

                corrected_rooms.append(corrected_room)
            else:
                corrected_rooms.append(room)

        # 使用修正后的数据重新计算热负荷
        corrected_result = self.calculator.calculate_multiple_rooms(
            rooms_data=corrected_rooms,
            project_info=project_info
        )

        return corrected_result


class PlateHeatExchangerSelector:
    """板式换热器选型器"""

    def __init__(self, json_file_path="板换选型表.json"):
        """初始化板换选型数据库"""
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)

            # 直接解析为模型列表
            self.models = self._parse_models()

            if self.models:
                print(f"✅ 板换选型数据加载成功，共 {len(self.models)} 个型号")
            else:
                print("⚠️  板换选型数据加载成功但未找到有效型号")

        except Exception as e:
            st.error(f"板换选型表加载失败: {e}")
            self.models = []
            print("⚠️  使用空模型列表继续运行")

    def _parse_models(self):
        """解析JSON数据为模型列表"""
        models = []

        try:
            # 新的JSON结构：直接包含数据行
            if "工作表" in self.data and len(self.data["工作表"]) > 0:
                sheet_data = self.data["工作表"][0]

                if "数据类别" in sheet_data and len(sheet_data["数据类别"]) > 0:
                    data_category = sheet_data["数据类别"][0]

                    if "数据行" in data_category:
                        data_rows = data_category["数据行"]

                        # 查找型号行
                        model_row = None
                        for row in data_rows:
                            if row.get("参数名称") == "型号":
                                model_row = row
                                break

                        if model_row and "参数值" in model_row:
                            models_list = model_row["参数值"]

                            # 为每个型号创建记录
                            for i, model_name in enumerate(models_list):
                                model_info = {"型号": model_name}

                                # 为每个型号添加其他参数
                                for row in data_rows:
                                    param_name = row.get("参数名称", "")
                                    param_values = row.get("参数值", [])

                                    if param_name != "型号" and i < len(param_values):
                                        model_info[param_name] = param_values[i]

                                models.append(model_info)

            return models

        except Exception as e:
            print(f"解析板换数据失败: {e}")
            return []

    def select_plate_exchanger(self, required_capacity_kw):
        """根据需求制冷量选择板式换热器"""
        selected_model = None
        min_diff = float('inf')

        for model in self.models:
            if "换热量（KW）" in model:
                capacity = model["换热量（KW）"]
                diff = abs(capacity - required_capacity_kw)

                if diff < min_diff:
                    min_diff = diff
                    selected_model = model

        if selected_model:
            plate_count = selected_model.get("板式换热器数量", 1)
            pump_count = selected_model.get("制冷泵数量", 2)
            pump_power = selected_model.get("制冷泵功率（KW）", 3)

            # 价格计算（假设规则）
            plate_price_per_kw = 80
            pump_price_per_kw = 500

            total_plate_price = required_capacity_kw * plate_price_per_kw
            total_pump_price = pump_power * pump_price_per_kw * pump_count
            total_price = total_plate_price + total_pump_price

            return {
                "selected": True,
                "model": selected_model["型号"],
                "heat_exchange_capacity_kw": selected_model.get("换热量（KW）", 0),
                "required_capacity_kw": required_capacity_kw,
                "plate_count": plate_count,
                "pump_power_kw": pump_power,
                "pump_count": pump_count,
                "total_price_yuan": round(total_price),
                "details": selected_model
            }

        return {"selected": False, "message": "未找到合适的板换型号"}


class EvaporativeCondenserSelector:
    """蒸发式冷凝器选型器"""

    def __init__(self, json_file_path="蒸发冷价格.json"):
        """初始化蒸发冷价格数据库"""
        with open(json_file_path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)

        self.condensers = self.data.get("items", [])

    def select_condenser(self, required_heat_rejection_kw):
        """根据需求排热量选择蒸发式冷凝器"""
        selected_condenser = None
        min_diff = float('inf')

        for condenser in self.condensers:
            capacity = condenser.get("名义工况排热量KW", 0)
            if capacity > 0:
                diff = abs(capacity - required_heat_rejection_kw)

                if diff < min_diff:
                    min_diff = diff
                    selected_condenser = condenser

        if selected_condenser:
            capacity = selected_condenser.get("名义工况排热量KW", 0)
            required_count = max(1, int(np.ceil(required_heat_rejection_kw / capacity)))
            unit_price = selected_condenser.get("单价(元)", 0)
            total_price = unit_price * required_count

            return {
                "selected": True,
                "model": selected_condenser.get("型号", ""),
                "heat_rejection_capacity_kw": capacity,
                "required_heat_rejection_kw": required_heat_rejection_kw,
                "unit_price_yuan": unit_price,
                "required_count": required_count,
                "total_price_yuan": total_price,
                "details": selected_condenser
            }

        return {"selected": False, "message": "未找到合适的冷凝器型号"}


class IntelligentCompressorSelector:
    """智能压缩机选型器 - 严格按复叠系统逻辑"""

    def __init__(self, total_high_temp_load_kw=0):
        try:
            # 加载完整的压缩机数据库（包含比泽尔和都凌）
            with open("压缩机数据库.json", 'r', encoding='utf-8') as f:
                compressor_db = json.load(f)

            # 分离两种类型的压缩机数据
            self.bitzer_data = compressor_db.get("比泽尔压缩机数据库", [])
            self.duling_data = compressor_db.get("都压缩机数据库", [])

            # 确保价格字段是数值类型
            for comp in self.bitzer_data:
                if "价格" in comp:
                    try:
                        comp["价格"] = float(comp["价格"])
                    except (ValueError, TypeError):
                        comp["价格"] = 0

            for comp in self.duling_data:
                if "价格" in comp:
                    try:
                        comp["价格"] = float(comp["价格"])
                    except (ValueError, TypeError):
                        comp["价格"] = 0

            # 高温级需要承担的额外制冷负荷（来自中温/高温库）
            self.high_temp_load_kw = total_high_temp_load_kw

            # 初始化计算器
            self.bitzer_calc = BitzerCompressorCalculator(self.bitzer_data)
            co2_compressor_data = self.duling_data[0]  # 获取第一个都凌压缩机数据
            self.co2_calc = CDS3001BCalculator(co2_compressor_data)
            self.duling_cds3001b_price = co2_compressor_data.get("价格", 19000)

            print(f"✅ 智能压缩机选型器初始化完成")
            print(f"   - 加载{len(self.bitzer_data)}个比泽尔型号")
            print(f"   - 加载{len(self.duling_data)}个都凌型号")

        except Exception as e:
            st.error(f"压缩机选型器初始化失败: {e}")

    def _calculate_evap_temp_from_room_temp(self, room_temp):
        """根据冷间温度计算蒸发温度"""
        # 规范：蒸发温度比冷间温度低5-10°C
        return room_temp - 8

    def _calculate_cond_temp_from_ambient(self, ambient_temp):
        """根据环境温度计算冷凝温度"""
        # 规范：冷凝温度比环境温度高8-12°C
        return ambient_temp + 10

    def _check_co2_constraints(self, evap_temp, cond_temp):
        """检查CO2压缩机温度约束条件"""
        # 调用CO2计算器的约束检查
        constraints_valid, _ = self.co2_calc._check_temperature_constraints(evap_temp, cond_temp)
        return constraints_valid

    def select_optimal_compressors(self, low_temp_load_kw, room_temp, ambient_temp):
        """严格按复叠系统逻辑选择压缩机 - 完全修正"""

        print(f"\n🔧 开始复叠系统选型:")
        print(f"   低温负荷: {low_temp_load_kw} kW")
        print(f"   库温: {room_temp}°C")
        print(f"   环境温度: {ambient_temp}°C")

        # ================ 第一步：确定温度范围 ================

        # 1. 低温级蒸发温度（由库温决定）
        # 蒸发温度比冷间温度低5-15°C
        evap_deltas = [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
        evap_temp_options = [room_temp - delta for delta in evap_deltas]
        print(f"   低温级蒸发温度选项: {evap_temp_options}")

        # 2. 高温级冷凝温度（由环境温度决定）
        # 冷凝温度比环境温度高8-15°C
        cond_deltas = [8, 9, 10, 11, 12, 13, 14, 15]
        cond_temp_options = [ambient_temp + delta for delta in cond_deltas]
        # 限制在合理范围：20-45°C
        cond_temp_options = [t for t in cond_temp_options if 20 <= t <= 45]
        print(f"   高温级冷凝温度选项: {cond_temp_options}")

        if not cond_temp_options:
            print(f"❌ 没有合理的高温级冷凝温度选项，环境温度{ambient_temp}°C可能不适合")
            return {
                'selection_valid': False,
                'error_message': f'环境温度{ambient_temp}°C不适合复叠系统运行'
            }

        # 3. 中间温度范围（连接低温级和高温级）
        # 合理的中间温度范围：-15°C 到 0°C
        cascade_temp_options = np.linspace(-15, 0, 16)  # -15, -14, ..., 0

        # ================ 第二步：优化中间温度 ================

        print(f"\n🔍 开始优化中间温度:")
        print(f"   中间温度候选: {cascade_temp_options}")

        best_config = None
        best_cop = 0

        # 遍历所有可能的温度组合
        for evap_temp in evap_temp_options:
            for cond_temp in cond_temp_options:
                for cascade_temp in cascade_temp_options:

                    # 1. 检查温度组合是否合理
                    # 中间温度必须在蒸发温度和冷凝温度之间，且有合理温差
                    if not (evap_temp + 10 <= cascade_temp <= cond_temp - 15):
                        continue

                    # 2. 检查低温级约束（CO₂：蒸发温度 → 中间温度）
                    if not self._check_co2_constraints_for_cascade(evap_temp, cascade_temp):
                        continue

                    # 3. 检查高温级约束（比泽尔：中间温度 → 冷凝温度）
                    if not self._check_bitzer_constraints(cascade_temp, cond_temp):
                        continue

                    # 4. 计算系统COP
                    system_cop = self._calculate_cascade_system_cop(
                        evap_temp, cascade_temp, cond_temp, low_temp_load_kw
                    )

                    if system_cop > best_cop:
                        best_cop = system_cop
                        best_config = {
                            'evap_temp': evap_temp,
                            'cascade_temp': cascade_temp,
                            'cond_temp': cond_temp,
                            'cop': system_cop
                        }

        if not best_config:
            print("❌ 未找到可行的温度配置")
            return {
                'selection_valid': False,
                'error_message': '未找到满足所有约束的温度配置'
            }

        print(f"✅ 找到最优温度配置:")
        print(f"   低温级: 蒸发温度{best_config['evap_temp']}°C → 中间温度{best_config['cascade_temp']}°C")
        print(f"   高温级: 蒸发温度{best_config['cascade_temp']}°C → 冷凝温度{best_config['cond_temp']}°C")
        print(f"   系统COP: {best_config['cop']:.3f}")

        # ================ 第三步：选型压缩机 ================

        # 3.1 选择低温级压缩机（CO₂）
        print(f"\n🔧 选择低温级压缩机...")
        low_stage_selection = self._select_low_stage_compressor_for_cascade(
            best_config['evap_temp'], best_config['cascade_temp'], low_temp_load_kw
        )

        if not low_stage_selection['selected']:
            return {
                'selection_valid': False,
                'error_message': low_stage_selection['error']
            }

        # 3.2 计算高温级负荷
        # 高温级需要承担：低温级的排热量 + 高温级的直接制冷量
        low_stage_capacity = low_stage_selection['total_capacity_kw']
        low_stage_power = low_stage_selection['total_power_kw']
        low_stage_heat_rejection = low_stage_capacity + low_stage_power

        high_stage_load = low_stage_heat_rejection + self.high_temp_load_kw

        print(f"   低温级排热量: {low_stage_heat_rejection:.1f} kW")
        print(f"   高温级直接制冷: {self.high_temp_load_kw:.1f} kW")
        print(f"   高温级总负荷: {high_stage_load:.1f} kW")

        # 3.3 选择高温级压缩机（比泽尔）
        print(f"\n🔧 选择高温级压缩机...")
        high_stage_selection = self._select_high_stage_compressor_for_cascade(
            best_config['cascade_temp'], best_config['cond_temp'], high_stage_load
        )

        if not high_stage_selection['selected']:
            return {
                'selection_valid': False,
                'error_message': high_stage_selection['error']
            }

        # ================ 第四步：计算系统性能 ================

        system_performance = self._calculate_system_performance(
            low_stage_selection, high_stage_selection
        )

        print(f"\n✅ 复叠系统选型完成!")
        print(f"   系统总COP: {system_performance['system_cop']:.3f}")
        print(f"   总投资: ¥{system_performance['total_compressor_cost']:,}")

        return {
            'selection_valid': True,
            'operating_conditions': {
                'room_temp': room_temp,
                'ambient_temp': ambient_temp,
                'low_evap_temp': best_config['evap_temp'],
                'cascade_temp': best_config['cascade_temp'],
                'high_cond_temp': best_config['cond_temp']
            },
            'temperature_explanation': {
                'evap_delta': room_temp - best_config['evap_temp'],
                'cond_delta': best_config['cond_temp'] - ambient_temp,
                'cascade_position': f"中间温度位于{best_config['cascade_temp']}°C"
            },
            'low_stage': low_stage_selection,
            'high_stage': high_stage_selection,
            'system_performance': system_performance,
            'load_calculation': {
                'low_stage_required_kw': low_temp_load_kw,
                'low_stage_actual_kw': low_stage_capacity,
                'high_stage_required_kw': high_stage_load,
                'high_stage_actual_kw': high_stage_selection['total_capacity_kw'],
                'energy_flow': f"低温级排热量({low_stage_heat_rejection:.1f}kW) + 高温级直接制冷({self.high_temp_load_kw:.1f}kW)"
            }
        }

    def _check_co2_constraints_for_cascade(self, evap_temp, cascade_temp):
        """检查CO2压缩机在复叠系统中的约束"""

        # CO2压缩机在复叠系统中：
        # 蒸发温度: 由库温决定（低温级）
        # 冷凝温度: 中间温度（不是最终冷凝温度！）

        # 蒸发温度范围：-40°C 到 -10°C
        if evap_temp < -40 or evap_temp > -10:
            return False

        # 冷凝温度（中间温度）范围：-15°C 到 5°C
        if cascade_temp < -15 or cascade_temp > 5:
            return False

        # 压差范围：15°C 到 50°C
        temp_diff = cascade_temp - evap_temp
        if temp_diff < 15 or temp_diff > 50:
            return False

        return True

    def _check_bitzer_constraints(self, evap_temp, cond_temp):
        """检查比泽尔压缩机在复叠系统中的约束"""

        # 比泽尔压缩机在复叠系统中：
        # 蒸发温度: 中间温度
        # 冷凝温度: 由环境温度决定

        # 蒸发温度范围：-20°C 到 10°C
        if evap_temp < -20 or evap_temp > 10:
            return False

        # 冷凝温度范围：20°C 到 50°C
        if cond_temp < 20 or cond_temp > 50:
            return False

        # 压差范围：15°C 到 60°C
        temp_diff = cond_temp - evap_temp
        if temp_diff < 15 or temp_diff > 60:
            return False

        return True

    def _calculate_cascade_system_cop(self, evap_temp, cascade_temp, cond_temp, load_kw):
        """计算复叠系统COP"""

        try:
            # 1. 计算低温级（CO₂）性能
            low_perf = self.co2_calc.calculate_performance(
                evap_temp=evap_temp,
                cond_temp=cascade_temp  # 注意：这是中间温度！
            )

            if not low_perf.get('calculation_valid', False):
                return 0

            low_capacity = low_perf['cooling_capacity_kw']
            low_power = low_perf['power_consumption_kw']

            if low_capacity <= 0:
                return 0

            # 2. 计算低温级配置（N+1冗余）
            min_units = max(1, int(np.ceil(load_kw / low_capacity)))
            selected_units = min_units + 1

            total_low_capacity = low_capacity * selected_units
            total_low_power = low_power * selected_units

            # 3. 计算高温级负荷
            low_stage_heat_rejection = total_low_capacity + total_low_power
            high_stage_load = low_stage_heat_rejection + self.high_temp_load_kw

            # 4. 找到最小功率的高温级配置
            best_high_power = float('inf')

            for comp_data in self.bitzer_data:
                model = comp_data.get("型号", "")
                if not model:
                    continue

                high_perf = self.bitzer_calc.calculate_performance(
                    model=model,
                    evap_temp=cascade_temp,  # 高温级蒸发温度 = 中间温度
                    cond_temp=cond_temp  # 高温级冷凝温度 = 最终冷凝温度
                )

                if not high_perf.get('calculation_valid', False):
                    continue

                high_capacity = high_perf['cooling_capacity_kw']
                if high_capacity <= 0:
                    continue

                # 计算所需台数
                high_units = max(1, int(np.ceil(high_stage_load / high_capacity)))

                if high_capacity * high_units >= high_stage_load:
                    total_high_power = high_perf['power_consumption_kw'] * high_units
                    if total_high_power < best_high_power:
                        best_high_power = total_high_power

            if best_high_power == float('inf'):
                return 0

            # 5. 计算系统总COP
            total_cooling = total_low_capacity
            total_power = total_low_power + best_high_power

            return total_cooling / total_power if total_power > 0 else 0

        except Exception as e:
            print(f"计算COP时出错: {e}")
            return 0

    def _select_low_stage_compressor_for_cascade(self, evap_temp, cascade_temp, required_load_kw):
        """为复叠系统选择低温级压缩机"""

        print(f"   🔧 低温级选型: 蒸发{evap_temp}°C → 中间{cascade_temp}°C")

        # 检查约束
        if not self._check_co2_constraints_for_cascade(evap_temp, cascade_temp):
            error_msg = f"低温级温度约束不满足: 蒸发{evap_temp}°C → 中间{cascade_temp}°C"
            print(f"   ❌ {error_msg}")
            return {'selected': False, 'error': error_msg}

        # 计算CO2压缩机性能
        performance_result = self.co2_calc.calculate_performance(
            evap_temp=evap_temp,
            cond_temp=cascade_temp  # CO2的冷凝温度是中间温度
        )

        if not performance_result['calculation_valid']:
            error_msg = f"CO2压缩机性能计算失败: {performance_result['error_message']}"
            print(f"   ❌ {error_msg}")
            return {'selected': False, 'error': error_msg}

        capacity_kw = performance_result['cooling_capacity_kw']
        power_kw = performance_result['power_consumption_kw']

        # 计算配置
        min_units = max(1, int(np.ceil(required_load_kw / capacity_kw)))
        selected_units = min_units + 1  # N+1冗余

        total_capacity = capacity_kw * selected_units
        total_power = power_kw * selected_units
        margin_percent = ((total_capacity - required_load_kw) / required_load_kw) * 100

        print(f"   ✅ 低温级选型成功:")
        print(f"      型号: CDS3001B × {selected_units}台")
        print(f"      总能力: {total_capacity:.1f} kW")
        print(f"      总功率: {total_power:.1f} kW")
        print(f"      余量: {margin_percent:.1f}%")

        return {
            'selected': True,
            'brand': '都凌',
            'model': 'CDS3001B',
            'refrigerant': 'R744_CO2',
            'evap_temp': evap_temp,
            'cond_temp': cascade_temp,  # 注意：这是中间温度！
            'single_capacity_kw': round(capacity_kw, 2),
            'single_power_kw': round(power_kw, 2),
            'single_cop': round(performance_result['cop'], 2),
            'required_units': min_units,
            'selected_units': selected_units,
            'redundancy': 'N+1',
            'total_capacity_kw': round(total_capacity, 2),
            'total_power_kw': round(total_power, 2),
            'capacity_margin_percent': round(margin_percent, 1),
            'heat_rejection_kw': round(total_capacity + total_power, 2),
            'price': self.duling_cds3001b_price,
            'total_price': self.duling_cds3001b_price * selected_units
        }

    def _select_high_stage_compressor_for_cascade(self, cascade_temp, cond_temp, high_stage_load_kw):
        """为复叠系统选择高温级压缩机"""

        print(f"   🔧 高温级选型: 蒸发{cascade_temp}°C → 冷凝{cond_temp}°C")

        # 检查约束
        if not self._check_bitzer_constraints(cascade_temp, cond_temp):
            error_msg = f"高温级温度约束不满足: 蒸发{cascade_temp}°C → 冷凝{cond_temp}°C"
            print(f"   ❌ {error_msg}")
            return {'selected': False, 'error': error_msg}

        best_selection = None
        best_margin = float('inf')

        for comp_data in self.bitzer_data:
            model = comp_data.get("型号", "")

            # 计算性能
            high_perf = self.bitzer_calc.calculate_performance(
                model=model,
                evap_temp=cascade_temp,  # 高温级蒸发温度 = 中间温度
                cond_temp=cond_temp  # 高温级冷凝温度
            )

            if not high_perf.get('calculation_valid', False):
                continue

            capacity_kw = high_perf['cooling_capacity_kw']
            power_kw = high_perf['power_consumption_kw']

            # 计算所需台数
            min_units = max(1, int(np.ceil(high_stage_load_kw / capacity_kw)))
            selected_units = min_units

            total_capacity = capacity_kw * selected_units
            margin = total_capacity - high_stage_load_kw

            if margin < 0:  # 不满足需求
                continue

            margin_percent = (margin / high_stage_load_kw) * 100

            # 选择最接近需求的配置
            if margin < best_margin:
                best_margin = margin
                best_selection = {
                    'selected': True,
                    'brand': '比泽尔',
                    'model': model,
                    'refrigerant': comp_data.get("制冷剂", "R507A"),
                    'evap_temp': cascade_temp,
                    'cond_temp': cond_temp,
                    'single_capacity_kw': round(capacity_kw, 2),
                    'single_power_kw': round(power_kw, 2),
                    'single_cop': round(high_perf['cop'], 2),
                    'selected_units': selected_units,
                    'total_capacity_kw': round(total_capacity, 2),
                    'total_power_kw': round(power_kw * selected_units, 2),
                    'capacity_margin_percent': round(margin_percent, 1),
                    'price': comp_data.get("价格", 0),
                    'total_price': comp_data.get("价格", 0) * selected_units
                }

        if best_selection:
            print(f"   ✅ 高温级选型成功:")
            print(f"      型号: {best_selection['model']} × {best_selection['selected_units']}台")
            print(f"      总能力: {best_selection['total_capacity_kw']:.1f} kW")
            print(f"      总功率: {best_selection['total_power_kw']:.1f} kW")
            print(f"      余量: {best_selection['capacity_margin_percent']:.1f}%")
            return best_selection
        else:
            error_msg = f"未找到满足需求的高温级压缩机"
            print(f"   ❌ {error_msg}")
            return {'selected': False, 'error': error_msg}

    def _calculate_system_performance(self, low_stage, high_stage, total_heat_rejection_kw=None):
        """计算复叠系统总性能"""

        # 确保价格是数值类型
        low_price = float(low_stage.get('total_price', 0))
        high_price = float(high_stage.get('total_price', 0))

        # 系统总制冷量 = 低温级制冷量
        total_cooling_capacity = low_stage['total_capacity_kw']

        # 系统总功率 = 低温级功率 + 高温级功率
        total_power = low_stage['total_power_kw'] + high_stage['total_power_kw']

        # 系统COP = 总制冷量 / 总功率
        system_cop = total_cooling_capacity / total_power if total_power > 0 else 0

        # 计算排热量（如果没有传入，使用能量守恒公式计算）
        if total_heat_rejection_kw is None:
            total_heat_rejection_kw = low_stage['total_capacity_kw'] + low_stage['total_power_kw']

        # 年能耗
        annual_hours = 12 * 360  # 12小时/天 × 360天
        annual_energy_kwh = total_power * annual_hours

        # 总压缩机成本
        total_compressor_cost = low_stage['total_price'] + high_stage['total_price']

        # 初始化板换和蒸发冷选择器
        plate_selector = PlateHeatExchangerSelector()
        condenser_selector = EvaporativeCondenserSelector()

        # 1. 板换选型
        # 板换需要承担高温级的排热量
        plate_heat_load = high_stage['total_capacity_kw'] + high_stage['total_power_kw']
        plate_selection = plate_selector.select_plate_exchanger(plate_heat_load)

        # 2. 蒸发冷选型
        # 蒸发冷需要承担高温级的排热量
        condenser_heat_load = high_stage['total_capacity_kw'] + high_stage['total_power_kw']
        condenser_selection = condenser_selector.select_condenser(condenser_heat_load)

        return {
            'total_cooling_capacity_kw': round(total_cooling_capacity, 2),
            'total_power_consumption_kw': round(total_power, 2),
            'system_cop': round(system_cop, 3),
            'annual_energy_consumption_kwh': round(annual_energy_kwh),
            'annual_electricity_cost': round(annual_energy_kwh * 0.8),
            'energy_flow_efficiency': round(total_cooling_capacity / (total_power + 0.001), 3),
            'total_compressor_cost': total_compressor_cost,
            'compressor_cost_breakdown': {
                'low_stage': low_stage['total_price'],
                'high_stage': high_stage['total_price'],
                'total': total_compressor_cost
            },
            'plate_heat_exchanger': plate_selection,
            'evaporative_condenser': condenser_selection,
            'heat_rejection_analysis': {
                'low_stage_heat_rejection': low_stage['heat_rejection_kw'],
                'high_stage_heat_rejection': high_stage.get('heat_rejection_kw',
                                                            high_stage['total_capacity_kw'] + high_stage[
                                                                'total_power_kw']),
                'total_heat_rejection': total_heat_rejection_kw
            }
        }

class BusinessIntelligenceSelector:
    """商务智能选型引擎 - 生成三种方案（优化版）"""

    def __init__(self):
        self.compressor_selector = IntelligentCompressorSelector()
        self.plate_exchanger_selector = PlateHeatExchangerSelector()
        self.condenser_selector = EvaporativeCondenserSelector()

    def generate_proposals(self, low_temp_load_kw, room_temp, ambient_temp):
        """生成三种专业提案（优化版逻辑）"""

        # 首先获取所有可行的配置
        all_configs = self._get_all_feasible_configs(
            low_temp_load_kw, room_temp, ambient_temp
        )

        if not all_configs:
            return []

        proposals = []

        # 方案1：能效优先方案（COP最高，成本次优）
        proposal1 = self._generate_efficiency_priority_proposal(all_configs)
        if proposal1:
            proposals.append(proposal1)

        # 方案2：经济优先方案（成本最低，COP次优）
        proposal2 = self._generate_economic_priority_proposal(all_configs)
        if proposal2:
            proposals.append(proposal2)

        # 方案3：均衡推荐方案（介于前两者之间）
        balanced_proposals = self._generate_balanced_proposal(all_configs, proposals)
        if balanced_proposals:
            # 直接将均衡方案列表添加到总方案列表中
            proposals.extend(balanced_proposals)

        return proposals

    def _get_all_feasible_configs(self, low_temp_load_kw, room_temp, ambient_temp):
        """获取所有可行的配置组合"""
        all_configs = []

        # 温度组合遍历
        evap_deltas = [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
        cond_deltas = [8, 9, 10, 11, 12, 13, 14, 15]
        cascade_temps = np.linspace(-15, 0, 16)

        # 遍历所有可能的温度组合
        for evap_temp in [room_temp - delta for delta in evap_deltas]:
            for cond_temp in [ambient_temp + delta for delta in cond_deltas]:
                if cond_temp < 20 or cond_temp > 45:
                    continue

                for cascade_temp in cascade_temps:
                    # 检查温度组合是否合理
                    if not (evap_temp + 10 <= cascade_temp <= cond_temp - 15):
                        continue

                    # 检查低温级约束
                    if not self.compressor_selector._check_co2_constraints_for_cascade(evap_temp, cascade_temp):
                        continue

                    # 检查高温级约束
                    if not self.compressor_selector._check_bitzer_constraints(cascade_temp, cond_temp):
                        continue

                    # 计算配置
                    config = self._evaluate_config(
                        evap_temp, cascade_temp, cond_temp, low_temp_load_kw
                    )

                    if config:
                        all_configs.append(config)

        # 计算每个配置的综合评分
        for config in all_configs:
            config['comprehensive_score'] = self._calculate_comprehensive_score(config, all_configs)

        all_configs.sort(key=lambda x: self._calculate_comprehensive_score(x, all_configs))

        return all_configs

    def _evaluate_config(self, evap_temp, cascade_temp, cond_temp, load_kw):
        """评估单个配置的性能和成本"""
        try:
            # 1. 选择低温级压缩机
            low_stage = self.compressor_selector._select_low_stage_compressor_for_cascade(
                evap_temp, cascade_temp, load_kw
            )

            if not low_stage['selected']:
                return None

            # 2. 计算高温级负荷
            low_capacity = low_stage['total_capacity_kw']
            low_power = low_stage['total_power_kw']
            low_heat_rejection = low_capacity + low_power
            high_load = low_heat_rejection + self.compressor_selector.high_temp_load_kw

            # 3. 选择高温级压缩机
            high_stage = self.compressor_selector._select_high_stage_compressor_for_cascade(
                cascade_temp, cond_temp, high_load
            )

            if not high_stage['selected']:
                return None

            # 4. 计算系统性能
            system_perf = self.compressor_selector._calculate_system_performance(low_stage, high_stage)

            # 5. 计算总成本
            total_cost = low_stage['total_price'] + high_stage['total_price']

            # 添加辅助设备成本
            if system_perf.get('plate_heat_exchanger', {}).get('selected', False):
                total_cost += system_perf['plate_heat_exchanger']['total_price_yuan']

            if system_perf.get('evaporative_condenser', {}).get('selected', False):
                total_cost += system_perf['evaporative_condenser']['total_price_yuan']

            return {
                'evap_temp': evap_temp,
                'cascade_temp': cascade_temp,
                'cond_temp': cond_temp,
                'low_stage': low_stage,
                'high_stage': high_stage,
                'system_performance': system_perf,
                'system_cop': system_perf['system_cop'],
                'total_cost': total_cost,
                'config_id': f"{evap_temp:.0f}_{cascade_temp:.0f}_{cond_temp:.0f}",
                'comprehensive_score': self._calculate_comprehensive_score_temp(evap_temp, cascade_temp,
                                                                                             cond_temp, load_kw)
            }

        except Exception as e:
            print(f"配置评估失败: {e}")
            return None

    def _calculate_comprehensive_score(self, config, all_configs):
        """计算配置的综合评分（分数越低越好）"""
        # 权重分配
        cost_weight = 0.4
        cop_weight = 0.3
        temp_weight = 0.2
        margin_weight = 0.1

        if not all_configs:
            return 0

        # 获取基准值（用于归一化）
        max_cost = max(c['total_cost'] for c in all_configs)
        min_cost = min(c['total_cost'] for c in all_configs)
        max_cop = max(c['system_cop'] for c in all_configs)
        min_cop = min(c['system_cop'] for c in all_configs)

        # 归一化处理
        norm_cost = (config['total_cost'] - min_cost) / (max_cost - min_cost) if max_cost > min_cost else 0
        norm_cop = 1 - (config['system_cop'] - min_cop) / (max_cop - min_cop) if max_cop > min_cop else 0

        # 中间温度评分（越接近-5°C越好）
        temp_score = abs(config['cascade_temp'] + 5) / 15

        # 余量评分（越接近15%越好）
        low_margin = config['low_stage']['capacity_margin_percent']
        high_margin = config['high_stage']['capacity_margin_percent']
        margin_score = (abs(low_margin - 15) + abs(high_margin - 15)) / 30

        return (norm_cost * cost_weight +
                norm_cop * cop_weight +
                temp_score * temp_weight +
                margin_score * margin_weight)

    def _calculate_comprehensive_score_temp(self, evap_temp, cascade_temp, cond_temp, load_kw):
        """基于温度参数计算综合评分"""
        # 中间温度评分：越接近-5°C越好
        temp_score = abs(cascade_temp + 5) / 15

        # 温差评分：合理的温差范围
        low_diff = cascade_temp - evap_temp  # 低温级温差
        high_diff = cond_temp - cascade_temp  # 高温级温差

        # 理想的温差：低温级25°C，高温级30°C
        low_diff_score = abs(low_diff - 25) / 25
        high_diff_score = abs(high_diff - 30) / 30
        diff_score = (low_diff_score + high_diff_score) / 2

        return temp_score * 0.6 + diff_score * 0.4

    def _generate_efficiency_priority_proposal(self, all_configs):
        """能效优先方案：COP最高，成本次优"""
        if not all_configs:
            return None

        # 按COP降序排序
        configs_by_cop = sorted(all_configs, key=lambda x: x['system_cop'], reverse=True)

        # 找出COP最高的配置组（COP差异在5%以内视为相近）
        best_cop = configs_by_cop[0]['system_cop']
        similar_cop_configs = [
            config for config in configs_by_cop
            if config['system_cop'] >= best_cop * 0.95
        ]

        # 如果有多组COP相近的配置，选择成本最低的
        if len(similar_cop_configs) > 1:
            similar_cop_configs.sort(key=lambda x: x['total_cost'])

        best_config = similar_cop_configs[0]

        return self._format_proposal(
            best_config,
            '能效优先方案',
            '系统COP最大化，适合对运行效率要求高的项目',
            f'系统COP: {best_config["system_cop"]:.2f}（同性能中成本最低）'
        )

    def _generate_economic_priority_proposal(self, all_configs):
        """经济优先方案：成本最低，COP次优"""
        if not all_configs:
            return None

        # 按成本升序排序
        configs_by_cost = sorted(all_configs, key=lambda x: x['total_cost'])

        # 找出成本最低的配置组（成本差异在5%以内视为相近）
        best_cost = configs_by_cost[0]['total_cost']
        similar_cost_configs = [
            config for config in configs_by_cost
            if config['total_cost'] <= best_cost * 1.05
        ]

        # 如果有多组成本相近的配置，选择COP最高的
        if len(similar_cost_configs) > 1:
            similar_cost_configs.sort(key=lambda x: x['system_cop'], reverse=True)

        best_config = similar_cost_configs[0]

        return self._format_proposal(
            best_config,
            '经济优选方案',
            '设备成本最小化，适合预算有限的项目',
            f'总投资: ¥{best_config["total_cost"]:,}（同成本中COP最高）'
        )

    def _generate_balanced_proposal(self, all_configs, existing_proposals):
        """均衡推荐方案：介于能效和经济方案之间"""
        if not all_configs or len(existing_proposals) < 2:
            return []  # 返回空列表而不是单个元素

        balanced_proposals = []
        excluded_config_ids = []

        # 排除已经选为能效方案和经济方案的配置
        for proposal in existing_proposals:
            if 'config_id' in proposal:
                excluded_config_ids.append(proposal['config_id'])

        # 获取能效方案和经济方案的COP和成本
        if existing_proposals and 'system_performance' in existing_proposals[0]:
            eff_cop = existing_proposals[0]['system_performance']['system_cop']
            eff_cost = self._get_total_cost(existing_proposals[0])
        else:
            eff_cop = 0
            eff_cost = 0

        if len(existing_proposals) > 1 and 'system_performance' in existing_proposals[1]:
            eco_cop = existing_proposals[1]['system_performance']['system_cop']
            eco_cost = self._get_total_cost(existing_proposals[1])
        else:
            eco_cop = 0
            eco_cost = 0

        # 计算中间值
        if eff_cop > 0 and eco_cop > 0:
            target_cop_range = (eco_cop * 0.95, eff_cop * 1.05)
            target_cost_range = (eco_cost * 0.95, eff_cost * 1.05)
        else:
            target_cop_range = (0, float('inf'))
            target_cost_range = (0, float('inf'))

        # 找出最接近中间值的配置（综合评分）
        balanced_candidates = []
        for config in all_configs:
            if config.get('config_id') in excluded_config_ids:
                continue

            config_cop = config.get('system_cop', 0)
            config_cost = config.get('total_cost', 0)

            if (target_cop_range[0] <= config_cop <= target_cop_range[1] and
                    target_cost_range[0] <= config_cost <= target_cost_range[1]):
                balanced_candidates.append(config)

        # 如果没有中间范围的配置，选择综合评分最好的几个
        if not balanced_candidates:
            # 按综合评分排序
            all_configs_sorted = sorted(all_configs, key=lambda x: x.get('comprehensive_score', 0))

            # 跳过已选方案，选择接下来的几个
            count = 0
            for config in all_configs_sorted:
                if config.get('config_id') in excluded_config_ids:
                    continue

                if count >= 4:
                    break

                balanced_proposal = self._format_proposal(
                    config,
                    f'均衡备选方案 {count + 1}',
                    f'中间温度: {config["cascade_temp"]}°C，综合性能良好',
                    f'COP: {config["system_cop"]:.2f}，投资: ¥{config["total_cost"]:,}'
                )
                balanced_proposals.append(balanced_proposal)
                count += 1
        else:
            # 按综合评分排序
            balanced_candidates.sort(key=lambda x: x.get('comprehensive_score', 0))

            # 选择最多4个配置
            for i, config in enumerate(balanced_candidates[:4]):
                balanced_proposal = self._format_proposal(
                    config,
                    f'均衡备选方案 {i + 1}',
                    f'中间温度: {config["cascade_temp"]}°C，性能与成本的平衡选择',
                    f'COP: {config["system_cop"]:.2f}，投资: ¥{config["total_cost"]:,}'
                )
                balanced_proposals.append(balanced_proposal)

        return balanced_proposals  # 返回列表

    def _get_total_cost(self, proposal):
        """计算提案总成本"""
        total_cost = 0

        # 压缩机成本
        if 'low_stage' in proposal:
            total_cost += proposal['low_stage'].get('total_price', 0)
        if 'high_stage' in proposal:
            total_cost += proposal['high_stage'].get('total_price', 0)

        # 辅助设备成本
        if 'system_performance' in proposal:
            sp = proposal['system_performance']
            if 'plate_heat_exchanger' in sp and sp['plate_heat_exchanger']['selected']:
                total_cost += sp['plate_heat_exchanger']['total_price_yuan']
            if 'evaporative_condenser' in sp and sp['evaporative_condenser']['selected']:
                total_cost += sp['evaporative_condenser']['total_price_yuan']

        return total_cost

    def _format_proposal(self, config, name, description, key_feature):

        """格式化提案"""
        proposal = {
            'proposal_name': name,
            'description': description,
            'key_feature': key_feature,
            'operating_temp': config['cascade_temp'],
            'low_stage': config['low_stage'],
            'high_stage': config['high_stage'],
            'system_performance': config['system_performance'],
            'selection_criteria': name.split()[0],
            'total_cost': config['total_cost'],
            'config_id': config['config_id']
        }

        # 添加更多技术细节
        proposal['technical_details'] = {
            'evap_temp': config['evap_temp'],
            'cascade_temp': config['cascade_temp'],
            'cond_temp': config['cond_temp'],
            'low_stage_config': f"{config['low_stage']['model']} × {config['low_stage']['selected_units']}",
            'high_stage_config': f"{config['high_stage']['model']} × {config['high_stage']['selected_units']}",
            'low_stage_cop': config['low_stage']['single_cop'],
            'high_stage_cop': config['high_stage']['single_cop'],
            'comprehensive_score': config.get('comprehensive_score', 0)
        }

        return proposal

    def generate_comparison_data(self, proposals):
        """生成方案比较数据，用于图表展示"""
        if not proposals:
            return None

        comparison_data = []

        for proposal in proposals:
            comparison_data.append({
                '方案名称': proposal['proposal_name'],
                '系统COP': proposal['system_performance']['system_cop'],
                '总投资(万元)': proposal['total_cost'] / 10000,
                '年能耗(万度)': proposal['system_performance']['annual_energy_consumption_kwh'] / 10000,
                '低温级压缩机': f"{proposal['low_stage']['brand']} {proposal['low_stage']['model']} × {proposal['low_stage']['selected_units']}",
                '高温级压缩机': f"{proposal['high_stage']['brand']} {proposal['high_stage']['model']} × {proposal['high_stage']['selected_units']}",
                '中间温度(°C)': proposal['operating_temp']
            })

        return pd.DataFrame(comparison_data)

def create_header_with_icon(title, icon_path="icons/logo.png", icon_size=100,
                            top_offset=0):
    """创建带自定义图标的标题"""
    with open(icon_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode()
    icon_html = f'<img src="data:image/png;base64,{encoded_string}" width="{icon_size}" height="{icon_size}" style="position: relative; top: {top_offset}px; margin-right: 12px; border-radius: 5px;">'

    return f'<h1 class="main-header">{icon_html}{title}</h1>'

def generate_detailed_proposal_report(proposal, project_info, low_temp_rooms):
    """生成详细提案报告"""

    report = f"""
复叠制冷系统设计方案报告
============================

生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

一、项目信息
-----------
项目名称: {project_info['project_name']}
客户名称: {project_info['customer_name']}
项目地区: {project_info['project_location']}
夏季环境温度: {project_info['summer_temp']}°C
冬季环境温度: {project_info['winter_temp']}°C

二、低温冷间概况
---------------
低温冷间数量: {len(low_temp_rooms)} 个
低温系统总负荷: {sum(r.get('equipment_load_kw', 0) for r in low_temp_rooms):.1f} kW

低温冷间详情:
"""

    for room in low_temp_rooms:
        report += f"- {room['room_name']}: {room['temperature']}°C, 负荷: {room['equipment_load_kw']:.1f} kW\n"

    report += f"""
三、选型方案详情
---------------
方案名称: {proposal['proposal_name']}
方案描述: {proposal['description']}
选型标准: {proposal['selection_criteria']}
推荐中间温度: {proposal['operating_temp']}°C

四、低温级系统配置 (CO2系统)
-------------------------
压缩机型号: {proposal['low_stage']['brand']} {proposal['low_stage']['model']}
制冷剂类型: {proposal['low_stage']['refrigerant']}
运行工况: {proposal['low_stage']['evap_temp']}°C → {proposal['low_stage']['cond_temp']}°C

单台性能:
- 制冷量: {proposal['low_stage']['single_capacity_kw']} kW
- 功率: {proposal['low_stage']['single_power_kw']} kW
- COP: {proposal['low_stage']['single_cop']}

配置方案:
- 需求台数: {proposal['low_stage']['required_units']} 台
- 实际配置: {proposal['low_stage']['selected_units']} 台 (N+1冗余)
- 总制冷量: {proposal['low_stage']['total_capacity_kw']} kW
- 总功率: {proposal['low_stage']['total_power_kw']} kW
- 余量百分比: {proposal['low_stage']['capacity_margin_percent']}%
- 排热量: {proposal['low_stage']['heat_rejection_kw']} kW

五、高温级系统配置 (比泽尔系统)
---------------------------
压缩机型号: {proposal['high_stage']['brand']} {proposal['high_stage']['model']}
制冷剂类型: {proposal['high_stage']['refrigerant']}
运行工况: {proposal['high_stage']['evap_temp']}°C → {proposal['high_stage']['cond_temp']}°C

单台性能:
- 制冷量: {proposal['high_stage']['single_capacity_kw']} kW
- 功率: {proposal['high_stage']['single_power_kw']} kW
- COP: {proposal['high_stage']['single_cop']}

配置方案:
- 配置数量: {proposal['high_stage']['selected_units']} 台
- 总制冷量: {proposal['high_stage']['total_capacity_kw']} kW
- 总功率: {proposal['high_stage']['total_power_kw']} kW
- 余量百分比: {proposal['high_stage']['capacity_margin_percent']}%

六、复叠系统整体性能
-------------------
总制冷量: {proposal['system_performance']['total_cooling_capacity_kw']} kW
系统总功率: {proposal['system_performance']['total_power_consumption_kw']} kW
系统COP: {proposal['system_performance']['system_cop']}
能量流效率: {proposal['system_performance']['energy_flow_efficiency']}

能耗估算:
- 年运行时间: 12小时/天 × 360天 = 4320小时
- 年耗电量: {proposal['system_performance']['annual_energy_consumption_kwh']:,} 度
- 年电费成本: ¥{proposal['system_performance']['annual_electricity_cost']:,} (按0.8元/度)

七、投资成本分析
---------------
低温级压缩机投资: ¥{proposal['low_stage']['total_price']:,}
高温级压缩机投资: ¥{proposal['high_stage']['total_price']:,}
压缩机总投资: ¥{proposal['system_performance']['total_compressor_cost']:,}

八、设计说明
-----------
1. 本方案采用CO2/R507A复叠制冷系统设计
2. 低温级使用CO2制冷剂，高温级使用R507A制冷剂
3. 系统通过优化中间温度实现两级系统的最佳匹配
4. 低温级采用N+1冗余配置确保系统可靠性
5. 所有选型基于精确的热负荷计算和规范的工程实践

============================
报告生成完成
"""

    return report

def main():
    st.set_page_config(
        page_title="英诺绿能制冷系统智能化设计",
        page_icon="icons/logo.png",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # 初始化session_state中的选择状态
    if 'selected_proposal_idx' not in st.session_state:
        st.session_state.selected_proposal_idx = -1  # -1表示未选择
    if 'selected_proposal' not in st.session_state:
        st.session_state.selected_proposal = None

    # 自定义CSS样式
    st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .section-header {
        font-size: 1.5rem;
        color: #2e86ab;
        border-bottom: 2px solid #2e86ab;
        padding-bottom: 0.5rem;
        margin-top: 2rem;
    }
    .proposal-card {
        background-color: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        border: 2px solid #dee2e6;
        margin-bottom: 1rem;
        transition: all 0.3s;
    }
    .proposal-card:hover {
        border-color: #2e86ab;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    .proposal-card.selected {
        border-color: #28a745;
        background-color: #e8f5e8;
    }
    .performance-badge {
        background-color: #17a2b8;
        color: white;
        padding: 0.25rem 0.75rem;
        border-radius: 12px;
        font-size: 0.875rem;
    }
    .cost-badge {
        background-color: #ffc107;
        color: #212529;
        padding: 0.25rem 0.75rem;
        border-radius: 12px;
        font-size: 0.875rem;
    }
    .balanced-badge {
        background-color: #28a745;
        color: white;
        padding: 0.25rem 0.75rem;
        border-radius: 12px;
        font-size: 0.875rem;
    }
    .equipment-card {
        background-color: #f0f8ff;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #2e86ab;
        margin-bottom: 0.5rem;
    }
    .cascade-system {
        background-color: #e8f5e8;
        padding: 1.5rem;
        border-radius: 10px;
        border: 2px solid #4caf50;
        margin-bottom: 1rem;
    }
    </style>
    """, unsafe_allow_html=True)

    # 页面标题
    st.markdown(
        create_header_with_icon("英诺绿能制冷系统智能化设计", "icons/logo.png",
                                top_offset=-8),
        unsafe_allow_html=True
    )

    # 加载设计数据
    design_data = load_design_data()

    if design_data is None:
        st.error("❌ 没有找到可用的设计数据")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🏠 返回主页面配置", use_container_width=True):
                st.switch_page("cold_storage_input_interface.py")
        with col2:
            if st.button("🔄 重新加载数据", use_container_width=True):
                st.rerun()
        return

    project_info = design_data['project_info']
    rooms_data = design_data['rooms_data']

    st.success(f"✅ 成功加载项目: **{project_info['project_name']}**")

    # 显示项目概览
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("冷间数量", len(rooms_data))
    with col2:
        total_volume = sum(room['length'] * room['width'] * room['height'] for room in rooms_data)
        st.metric("总体积", f"{total_volume:.0f} m³")
    with col3:
        st.metric("设计优先级", project_info['design_priority'])
    with col4:
        st.metric("夏季环境温度", f"{project_info['summer_temp']}°C")

    # 步骤1：计算热负荷
    st.markdown('<h2 class="section-header">📊 热负荷计算</h2>', unsafe_allow_html=True)

    with st.spinner("正在计算热负荷..."):
        try:
            # 初始化热负荷计算器
            heat_load_calculator = HeatLoadCalculator()

            # 批量计算所有冷间的热负荷
            summary_result = heat_load_calculator.calculate_multiple_rooms(
                rooms_data=rooms_data,
                project_info=project_info
            )

            # 提取结果
            room_results = summary_result.get('room_results', {})
            total_equipment_load_kw = summary_result.get('total_equipment_load_kw', 0)
            total_mechanical_load_kw = summary_result.get('total_mechanical_load_kw', 0)

            # 显示热负荷结果
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("总设备负荷", f"{total_equipment_load_kw:.1f} kW")
            with col2:
                st.metric("总机械负荷", f"{total_mechanical_load_kw:.1f} kW")
            with col3:
                st.metric("冷间数量", len(room_results))

            # 保存热负荷结果
            st.session_state.heat_load_results = {
                'room_results': room_results,
                'total_equipment_load_kw': total_equipment_load_kw,
                'total_mechanical_load_kw': total_mechanical_load_kw
            }

        except Exception as e:
            st.error(f"热负荷计算失败: {e}")
            return

    # 步骤2：冷风机选型
    st.markdown('<h2 class="section-header">🌬️ 冷风机智能选型</h2>', unsafe_allow_html=True)

    with st.spinner("正在进行冷风机选型..."):
        try:
            # 初始化冷风机选择器
            cold_fan_selector = IntelligentColdFanSelector()
            dynamic_corrector = DynamicLoadCorrector(heat_load_calculator)

            # 为每个冷间选择冷风机
            cold_fan_selections = []

            # 创建一个容器来显示所有冷间的详细信息
            st.markdown("### 📋 各冷间热负荷及冷风机选型结果")

            for idx, (room_name, room_result) in enumerate(room_results.items()):
                equipment_load_kw = room_result['equipment_load_kw']
                mechanical_load_kw = room_result.get('mechanical_load_kw', 0)

                # 找到对应的房间温度
                room_data = None
                for room in rooms_data:
                    if room['room_name'] == room_name:
                        room_data = room
                        break

                if room_data is not None:
                    # 从房间数据中获取除霜方式
                    defrost_method = room_data.get('defrost_method', '电热除霜')  # 默认值

                    selection_result = cold_fan_selector.select_cold_fan_by_conditions(
                        required_capacity_kw=equipment_load_kw,
                        room_temp=room_data['temperature'],
                        defrost_method=defrost_method  # 传递除霜方式
                    )

                    if selection_result['selected']:
                        cold_fan_selections.append({
                            'room_name': room_name,
                            'room_temp': room_data['temperature'],
                            'equipment_load_kw': equipment_load_kw,
                            'defrost_method': defrost_method,  # 保存除霜方式
                            'selection_result': selection_result
                        })

            # 动态校正热负荷
            corrected_results = dynamic_corrector.correct_heat_load(
                rooms_data, cold_fan_selections, project_info
            )

            # 更新热负荷结果
            st.session_state.corrected_heat_load_results = corrected_results
            st.session_state.cold_fan_selections = cold_fan_selections

            # 从校正结果中获取最终的房间结果
            corrected_room_results = corrected_results.get('room_results', {})
            final_total_equipment_load = corrected_results.get('total_equipment_load_kw', 0)
            final_total_mechanical_load = corrected_results.get('total_mechanical_load_kw', 0)

            # 显示最终的负荷汇总
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("最终设备负荷", f"{final_total_equipment_load:.1f} kW")
            with col2:
                st.metric("最终机械负荷", f"{final_total_mechanical_load:.1f} kW")
            with col3:
                st.metric("冷间数量", len(corrected_room_results))

        except Exception as e:
            st.error(f"冷风机选型失败: {e}")
            import traceback
            st.error(f"详细错误: {traceback.format_exc()}")
            return

    st.markdown('<h2 class="section-header">📊 冷间热负荷与冷风机选型汇总</h2>', unsafe_allow_html=True)

    # 创建汇总数据表格
    summary_data = []

    # 获取所有房间的数据
    for idx, room in enumerate(rooms_data):
        room_name = room['room_name']
        room_type = room.get('room_type', '冷冻冷藏间')

        # 获取热负荷数据
        if room_name in room_results:
            equipment_load = room_results[room_name]['equipment_load_kw']
            mechanical_load = room_results[room_name].get('mechanical_load_kw', 0)
        else:
            equipment_load = 0
            mechanical_load = 0

        # 获取冷风机选型结果
        fan_selection = None
        for selection in cold_fan_selections:
            if selection['room_name'] == room_name:
                fan_selection = selection['selection_result']
                break

        # 获取校正后的热负荷
        corrected_result = None
        if 'corrected_heat_load_results' in st.session_state:
            corrected_results = st.session_state.corrected_heat_load_results
            corrected_room_results = corrected_results.get('room_results', {})
            if room_name in corrected_room_results:
                corrected_result = corrected_room_results[room_name]

        # 构建汇总数据
        row_data = {
            '序号': idx + 1,
            '冷间名称': room_name,
            '冷间类型': room_type,
            '温度(°C)': room['temperature'],
            '尺寸(m)': f"{room['length']}×{room['width']}×{room['height']}",
            '体积(m³)': round(room['length'] * room['width'] * room['height'], 1),
            '除霜方式': room.get('defrost_method', '电热除霜'),
            '原始设备负荷(kW)': round(equipment_load, 1),
            '原始机械负荷(kW)': round(mechanical_load, 1),
        }

        # 添加校正后的负荷
        if corrected_result:
            row_data['校正设备负荷(kW)'] = round(corrected_result.get('equipment_load_kw', 0), 1)
            row_data['校正机械负荷(kW)'] = round(corrected_result.get('mechanical_load_kw', 0), 1)

        # 添加冷风机选型信息
        if fan_selection and fan_selection['selected']:
            row_data.update({
                '冷风机型号': fan_selection['model'],
                '冷风机系列': fan_selection['series'],
                '冷风机工况': fan_selection['condition'],
                '冷风机数量': f"{fan_selection['units']}台",
                '单台制冷量(kW)': round(fan_selection['single_capacity_kw'], 1),
                '总制冷量(kW)': round(fan_selection['total_capacity_kw'], 1),
                '余量(%)': round(fan_selection['excess_percent'], 1),
                '总风机功率(kW)': round(fan_selection['total_fan_power_kw'], 1),
                '总化霜功率(kW)': round(fan_selection['total_defrost_power_kw'], 1),
                '总功率(kW)': round(fan_selection['total_power_kw'], 1),
                '选型状态': '✅ 已选型'
            })
        else:
            row_data.update({
                '冷风机型号': '待选型',
                '冷风机数量': '-',
                '单台制冷量(kW)': '-',
                '总制冷量(kW)': '-',
                '余量(%)': '-',
                '总风机功率(kW)': '-',
                '总化霜功率(kW)': '-',
                '总功率(kW)': '-',
                '选型状态': '❌ 未选型'
            })

        summary_data.append(row_data)

    # 创建DataFrame
    summary_df = pd.DataFrame(summary_data)

    # 重新排序列顺序
    column_order = [
        '序号', '冷间名称', '冷间类型', '温度(°C)', '尺寸(m)', '体积(m³)',
        '除霜方式', '原始设备负荷(kW)', '原始机械负荷(kW)',
        '校正设备负荷(kW)', '校正机械负荷(kW)',
        '冷风机型号', '冷风机系列', '冷风机工况', '冷风机数量',
        '单台制冷量(kW)', '总制冷量(kW)', '余量(%)',
        '总风机功率(kW)', '总化霜功率(kW)', '总功率(kW)', '选型状态'
    ]

    # 只保留实际存在的列
    existing_columns = [col for col in column_order if col in summary_df.columns]
    summary_df = summary_df[existing_columns]

    # 显示汇总表格
    st.markdown("### 📋 热负荷与冷风机选型汇总表")

    # 使用st.dataframe显示，配置列格式
    st.dataframe(
        summary_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "序号": st.column_config.NumberColumn("序号", format="%d"),
            "冷间名称": st.column_config.TextColumn("冷间名称", width="medium"),
            "冷间类型": st.column_config.TextColumn("冷间类型", width="small"),
            "温度(°C)": st.column_config.NumberColumn("温度(°C)", format="%.1f"),
            "尺寸(m)": st.column_config.TextColumn("尺寸(m)", width="medium"),
            "体积(m³)": st.column_config.NumberColumn("体积(m³)", format="%.1f"),
            "除霜方式": st.column_config.TextColumn("除霜方式", width="small"),
            "原始设备负荷(kW)": st.column_config.NumberColumn("原始设备负荷(kW)", format="%.1f"),
            "原始机械负荷(kW)": st.column_config.NumberColumn("原始机械负荷(kW)", format="%.1f"),
            "校正设备负荷(kW)": st.column_config.NumberColumn("校正设备负荷(kW)", format="%.1f"),
            "校正机械负荷(kW)": st.column_config.NumberColumn("校正机械负荷(kW)", format="%.1f"),
            "冷风机型号": st.column_config.TextColumn("冷风机型号", width="medium"),
            "冷风机系列": st.column_config.TextColumn("冷风机系列", width="small"),
            "冷风机工况": st.column_config.TextColumn("冷风机工况", width="small"),
            "冷风机数量": st.column_config.TextColumn("冷风机数量", width="small"),
            "单台制冷量(kW)": st.column_config.NumberColumn("单台制冷量(kW)", format="%.1f"),
            "总制冷量(kW)": st.column_config.NumberColumn("总制冷量(kW)", format="%.1f"),
            "余量(%)": st.column_config.NumberColumn("余量(%)", format="%.1f"),
            "总风机功率(kW)": st.column_config.NumberColumn("总风机功率(kW)", format="%.1f"),
            "总化霜功率(kW)": st.column_config.NumberColumn("总化霜功率(kW)", format="%.1f"),
            "总功率(kW)": st.column_config.NumberColumn("总功率(kW)", format="%.1f"),
            "选型状态": st.column_config.TextColumn("选型状态", width="small")
        }
    )

    # 添加统计信息
    st.markdown("### 📊 总体统计")

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        total_rooms = len(summary_df)
        selected_fans = len(summary_df[summary_df['选型状态'] == '✅ 已选型'])
        st.metric("总冷间数", total_rooms)
        st.metric("已选型冷间", selected_fans)

    with col2:
        total_original_load = summary_df['原始设备负荷(kW)'].replace('-', 0).astype(float).sum()
        total_corrected_load = summary_df['校正设备负荷(kW)'].replace('-', 0).astype(
            float).sum() if '校正设备负荷(kW)' in summary_df.columns else 0
        st.metric("原始设备负荷", f"{total_original_load:.1f} kW")
        if total_corrected_load > 0:
            st.metric("校正设备负荷", f"{total_corrected_load:.1f} kW")

    with col3:
        total_original_mech_load = summary_df['原始机械负荷(kW)'].replace('-', 0).astype(float).sum()
        total_corrected_mech_load = summary_df['校正机械负荷(kW)'].replace('-', 0).astype(
            float).sum()if '校正机械负荷(kW)' in summary_df.columns else 0
        st.metric("原始机械负荷", f"{total_original_mech_load:.1f} kW")
        if total_corrected_mech_load > 0:
            st.metric("校正机械负荷",f"{total_corrected_mech_load:.1f} kW")

    with col4:
        total_fan_power = summary_df['总风机功率(kW)'].replace('-', 0).astype(float).sum()
        total_defrost_power = summary_df['总化霜功率(kW)'].replace('-', 0).astype(float).sum()
        st.metric("总风机功率", f"{total_fan_power:.1f} kW")
        st.metric("总化霜功率", f"{total_defrost_power:.1f} kW")

    with col5:
        total_capacity = summary_df['总制冷量(kW)'].replace('-', 0).astype(float).sum()
        if total_capacity > 0 and total_original_load > 0:
            overall_margin = ((total_capacity - total_original_load) / total_original_load) * 100
            st.metric("总制冷量", f"{total_capacity:.1f} kW")
            st.metric("综合余量", f"{overall_margin:.1f}%")

    # 添加按类型分组的统计
    st.markdown("### 📈 按冷间类型统计")

    if '冷间类型' in summary_df.columns:
        type_stats = summary_df.groupby('冷间类型').agg({
            '序号': 'count',
            '温度(°C)': 'mean',
            '原始设备负荷(kW)': 'sum',
            '校正设备负荷(kW)': 'sum' if '校正设备负荷(kW)' in summary_df.columns else None,
            '原始机械负荷(kW)': 'sum',
            '校正机械负荷(kW)': 'sum' if '校正机械负荷(kW)' in summary_df.columns else None
        }).reset_index()

        type_stats = type_stats.rename(columns={
            '序号': '冷间数量',
            '温度(°C)': '平均温度(°C)',
            '原始设备负荷(kW)': '原始设备负荷(kW)',
            '校正设备负荷(kW)': '校正设备负荷(kW)',
            '原始机械负荷(kW)': '原始机械负荷(kW)',
            '校正机械负荷(kW)': '校正机械负荷(kW)'
        })

        st.dataframe(
            type_stats,
            use_container_width=True,
            hide_index=True
        )

    # 添加下载功能
    st.markdown("### 💾 导出汇总数据")

    # 创建下载按钮
    csv = summary_df.to_csv(index=False, encoding='utf-8-sig')
    st.download_button(
        label="📥 下载CSV格式汇总表",
        data=csv,
        file_name=f"冷间热负荷与冷风机选型汇总_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )

    # 步骤4：复叠系统选型
    st.markdown('<h2 class="section-header">🔄 复叠系统智能选型</h2>', unsafe_allow_html=True)

    low_temp_rooms = []
    low_temp_load_kw = 0

    if 'heat_load_results' in st.session_state:
        room_results = st.session_state.corrected_heat_load_results.get('room_results', {})

        # 匹配房间数据
        for room_name, room_result in room_results.items():
            # 在原始rooms_data中找到对应的房间
            room_data = None
            for room in rooms_data:
                if room['room_name'] == room_name:
                    room_data = room
                    break

            if room_data and room_data['temperature'] <= -18:
                # 检查是否为冷冻冷藏间
                if room_data.get('room_type', '冷冻冷藏间') == '冷冻冷藏间':
                    equipment_load = room_result['equipment_load_kw']
                    mechanical_load = room_result['mechanical_load_kw']
                    low_temp_rooms.append({
                        'room_name': room_name,
                        'temperature': room_data['temperature'],
                        'equipment_load_kw': equipment_load,
                        'mechanical_load_kw': mechanical_load,
                        'room_data': room_data
                    })
                    low_temp_load_kw += mechanical_load

    # 显示识别结果
    if len(low_temp_rooms) > 0:
        total_equipment_load = sum(r['equipment_load_kw'] for r in low_temp_rooms)
        total_mechanical_load = sum(r.get('mechanical_load_kw', 0) for r in low_temp_rooms)
        st.info(f"识别到 {len(low_temp_rooms)} 个低温冷间（≤-18°C），总设备负荷: {total_equipment_load:.1f} kW ，总机械负荷: {total_mechanical_load:.1f} kW")

        # 创建表格展示低温冷间
        low_temp_data = []
        for room in low_temp_rooms:
            low_temp_data.append({
                '冷间名称': room['room_name'],
                '温度(°C)': room['temperature'],
                '负荷(kW)': round(room['equipment_load_kw'], 1),
                '冷间类型': room['room_data'].get('room_type', '冷冻冷藏间'),
                '尺寸(m)': f"{room['room_data']['length']}×{room['room_data']['width']}×{room['room_data']['height']}"
            })

        low_temp_df = pd.DataFrame(low_temp_data)
        st.dataframe(
            low_temp_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "冷间名称": st.column_config.TextColumn("冷间名称", width="medium"),
                "温度(°C)": st.column_config.NumberColumn("温度(°C)", format="%.1f"),
                "负荷(kW)": st.column_config.NumberColumn("负荷(kW)", format="%.1f"),
                "冷间类型": st.column_config.TextColumn("冷间类型", width="small"),
                "尺寸(m)": st.column_config.TextColumn("尺寸(m)", width="medium")
            }
        )
    else:
        st.warning("没有识别到需要复叠系统的低温冷间")

        st.info("""
        **提示：**
        - 复叠系统适用于温度≤-18°C的冷冻冷藏间
        - 请检查冷间温度设定或返回修改参数
        """)
        if st.button("返回修改参数"):
            st.switch_page("cold_storage_input_interface.py")
        return

    # 保存低温冷间数据到session_state
    st.session_state.low_temp_rooms = low_temp_rooms
    st.session_state.low_temp_load_kw = low_temp_load_kw

    with st.spinner("正在生成三种专业提案..."):
        try:
            # 初始化商务智能选型引擎
            bi_selector = BusinessIntelligenceSelector()

            # 生成三种提案
            proposals = bi_selector.generate_proposals(
                low_temp_load_kw=low_temp_load_kw,
                room_temp=min([r['temperature'] for r in low_temp_rooms]),
                ambient_temp=project_info['summer_temp']
            )

            # 保存提案
            st.session_state.proposals = proposals

            # 显示提案选择界面
            st.markdown("### 🎯 请选择推荐方案")

            # 初始化session_state中的选择状态
            if 'selected_proposal' not in st.session_state:
                st.session_state.selected_proposal = proposals[0] if proposals and proposals[0] else None

            # 找到当前选中的提案索引
            if 'selected_proposal_idx' not in st.session_state:
                st.session_state.selected_proposal_idx = 0 if proposals else -1

            # 根据提案数量动态创建列
            num_proposals = len(proposals)

            if num_proposals == 0:
                st.warning("没有生成任何提案")
                return
            elif num_proposals == 1:
                cols = st.columns(1)
            elif num_proposals == 2:
                cols = st.columns(2)
            else:
                cols = st.columns(3)  # 最多3列

            # 确保有足够的列
            for idx, proposal in enumerate(proposals):
                if idx >= len(cols):
                    st.warning(f"⚠️ 提案数量({num_proposals})超过显示列数({len(cols)})")
                    break

                if proposal:
                    with cols[idx]:
                        # 添加提案显示逻辑（保持不变）
                        badge_class = ""
                        badge_text = ""

                        if idx == 0:
                            badge_class = "performance-badge"
                            badge_text = "性能优先"
                        elif idx == 1:
                            badge_class = "cost-badge"
                            badge_text = "经济优选"
                        else:
                            badge_class = "balanced-badge"
                            badge_text = f"备选方案{idx - 1}"

                        is_selected = (idx == st.session_state.selected_proposal_idx)

                        # 创建提案卡片
                        card_html = f"""
                        <div class="proposal-card {'selected' if idx == st.session_state.selected_proposal_idx else ''}">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                                <h4 style="margin: 0;">{proposal['proposal_name']}</h4>
                                <span class="{badge_class}">{badge_text}</span>
                            </div>
                            <p style="color: #666; margin-bottom: 1rem;">{proposal['description']}</p>
                            <div style="background-color: #e9ecef; padding: 0.75rem; border-radius: 6px; margin-bottom: 1rem;">
                                <strong>关键指标:</strong> {proposal['key_feature']}
                            </div>
                            <div style="display: flex; justify-content: space-between;">
                                <div>
                                    <div style="font-size: 0.875rem; color: #6c757d;">系统COP</div>
                                    <div style="font-size: 1.25rem; font-weight: bold; color: #2e86ab;">
                                        {proposal['system_performance']['system_cop']:.2f}
                                    </div>
                                </div>
                                <div>
                                    <div style="font-size: 0.875rem; color: #6c757d;">总投资</div>
                                    <div style="font-size: 1.25rem; font-weight: bold; color: #28a745;">
                                        ¥{proposal['system_performance']['total_compressor_cost']:,}
                                    </div>
                                </div>
                            </div>
                        </div>
                        """

                        if st.button(f"{'✅ 已选择' if is_selected else '选择此方案'}",
                                     key=f"select_proposal_{idx}",
                                     use_container_width=True,
                                     type="primary" if is_selected else "secondary"):
                            # 更新session_state中的选择状态
                            st.session_state.selected_proposal_idx = idx
                            st.session_state.selected_proposal = proposal
                            st.rerun()

                        st.markdown(card_html, unsafe_allow_html=True)

            # 显示选中的提案详情
            if 'selected_proposal' in st.session_state and st.session_state.selected_proposal:
                proposal = st.session_state.selected_proposal

                # 添加方案比较图表
                st.markdown("### 📈 方案对比分析")

                if 'proposals' in st.session_state:
                    # 生成比较数据
                    comparison_df = pd.DataFrame([{
                        '方案': p['proposal_name'],
                        '系统COP': p['system_performance']['system_cop'],
                        '总投资(万元)': p['total_cost'] / 10000,
                        '年能耗(万度)': p['system_performance']['annual_energy_consumption_kwh'] / 10000,
                        '综合评价': p.get('selection_criteria', '')
                    } for p in st.session_state.proposals if p])

                    if not comparison_df.empty:
                        # 显示比较表格
                        st.dataframe(comparison_df, use_container_width=True, hide_index=True)

                        # 创建雷达图对比
                        fig = go.Figure()

                        # 标准化数据（0-1范围）
                        normalized_data = []
                        for idx, proposal in enumerate(st.session_state.proposals):
                            if proposal:
                                norm_cop = proposal['system_performance']['system_cop'] / comparison_df['系统COP'].max()
                                norm_cost = 1 - (proposal['total_cost'] / comparison_df['总投资(万元)'].max() * 10000) / \
                                            comparison_df['总投资(万元)'].max()
                                norm_energy = 1 - (proposal['system_performance']['annual_energy_consumption_kwh'] /
                                                   comparison_df['年能耗(万度)'].max() * 10000) / comparison_df[
                                                  '年能耗(万度)'].max()

                                fig.add_trace(go.Scatterpolar(
                                    r=[norm_cop, norm_cost, norm_energy],
                                    theta=['COP', '成本效益', '能耗效益'],
                                    name=proposal['proposal_name'],
                                    fill='toself'
                                ))

                        fig.update_layout(
                            polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
                            title="方案综合对比雷达图",
                            showlegend=True
                        )

                        st.plotly_chart(fig, use_container_width=True)

                # 显示系统配置
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.markdown('<div class="cascade-system">', unsafe_allow_html=True)
                    st.subheader("❄️ 低温级系统 (CO2)")
                    low_stage = proposal['low_stage']

                    st.write(f"**压缩机:** {low_stage['brand']} {low_stage['model']}")
                    st.write(f"**制冷剂:** {low_stage['refrigerant']}")
                    st.write(f"**运行工况:** {low_stage['evap_temp']}°C → {low_stage['cond_temp']}°C")
                    st.write(f"**单台能力:** {low_stage['single_capacity_kw']} kW")
                    st.write(f"**单台功率:** {low_stage['single_power_kw']} kW")
                    st.write(f"**单台COP:** {low_stage['single_cop']}")
                    st.write(f"**配置数量:** {low_stage['selected_units']} 台 (N+1冗余)")
                    st.write(f"**总能力:** {low_stage['total_capacity_kw']} kW")
                    st.write(f"**余量:** {low_stage['capacity_margin_percent']}%")
                    st.write(f"**排热量:** {low_stage['heat_rejection_kw']} kW")
                    st.write(f"**低温级总价:** ¥{low_stage['total_price']:,}")
                    st.markdown('</div>', unsafe_allow_html=True)

                with col2:
                    st.markdown('<div class="cascade-system">', unsafe_allow_html=True)
                    st.subheader("🔥 高温级系统 (比泽尔)")
                    high_stage = proposal['high_stage']

                    st.write(f"**压缩机:** {high_stage['brand']} {high_stage['model']}")
                    st.write(f"**制冷剂:** {high_stage['refrigerant']}")
                    st.write(f"**运行工况:** {high_stage['evap_temp']}°C → {high_stage['cond_temp']}°C")
                    st.write(f"**单台能力:** {high_stage['single_capacity_kw']} kW")
                    st.write(f"**单台功率:** {high_stage['single_power_kw']} kW")
                    st.write(f"**单台COP:** {high_stage['single_cop']}")
                    st.write(f"**配置数量:** {high_stage['selected_units']} 台")
                    st.write(f"**总能力:** {high_stage['total_capacity_kw']} kW")
                    st.write(f"**余量:** {high_stage['capacity_margin_percent']}%")
                    st.write(f"**高温级总价:** ¥{high_stage['total_price']:,}")
                    st.markdown('</div>', unsafe_allow_html=True)

                with col3:
                    st.markdown('<div class="cascade-system">', unsafe_allow_html=True)
                    st.subheader("⚙️ 辅助设备选型")
                    system_perf = proposal['system_performance']

                    # 显示板换选型结果
                    if 'plate_heat_exchanger' in system_perf and system_perf['plate_heat_exchanger']['selected']:
                        plate = system_perf['plate_heat_exchanger']
                        st.markdown("**板式换热器:**")
                        st.write(f"型号: {plate['model']}")
                        st.write(f"换热量: {plate['heat_exchange_capacity_kw']} kW")
                        st.write(f"板换数量: {plate['plate_count']}")
                        st.write(f"制冷泵: {plate['pump_count']} × {plate['pump_power_kw']}kW")
                        st.write(f"价格: ¥{plate['total_price_yuan']:,}")
                        st.markdown("---")
                    else:
                        st.write("⚠️ 板换未选型")
                        st.markdown("---")

                    # 显示蒸发冷选型结果
                    if 'evaporative_condenser' in system_perf and system_perf['evaporative_condenser']['selected']:
                        condenser = system_perf['evaporative_condenser']
                        st.markdown("**蒸发式冷凝器:**")
                        st.write(f"型号: {condenser['model']}")
                        st.write(f"排热量: {condenser['heat_rejection_capacity_kw']} kW")
                        st.write(f"数量: {condenser['required_count']}")
                        st.write(f"单价: ¥{condenser['unit_price_yuan']:,}")
                        st.write(f"总价: ¥{condenser['total_price_yuan']:,}")
                        st.markdown("---")
                    else:
                        st.write("⚠️ 蒸发冷未选型")
                        st.markdown("---")

                    # 排热量分析
                    if 'heat_rejection_analysis' in system_perf:
                        heat = system_perf['heat_rejection_analysis']
                        st.markdown("**排热量分析:**")
                        st.write(f"低温级: {heat['low_stage_heat_rejection']} kW")
                        st.write(f"高温级: {heat['high_stage_heat_rejection']} kW")
                        st.write(f"总计: {heat['total_heat_rejection']} kW")

                    st.markdown('</div>', unsafe_allow_html=True)

                # 系统性能汇总
                st.markdown("### 📊 系统性能汇总")

                perf = proposal['system_performance']
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    st.metric("总制冷量", f"{perf['total_cooling_capacity_kw']:.1f} kW")
                with col2:
                    st.metric("系统COP", f"{perf['system_cop']:.3f}")
                with col3:
                    st.metric("总功率", f"{perf['total_power_consumption_kw']:.1f} kW")
                with col4:
                    st.metric("年能耗", f"{perf['annual_energy_consumption_kwh']:,} 度")

                # 成本分析
                st.markdown("### 💰 成本分析")

                auxiliary_cost = 0
                if 'plate_heat_exchanger' in perf and perf['plate_heat_exchanger']['selected']:
                    auxiliary_cost += perf['plate_heat_exchanger']['total_price_yuan']

                if 'evaporative_condenser' in perf and perf['evaporative_condenser']['selected']:
                    auxiliary_cost += perf['evaporative_condenser']['total_price_yuan']

                compressor_cost = perf['total_compressor_cost']
                budget_yuan = project_info['budget_limit'] * 10000
                total_investment = compressor_cost + auxiliary_cost
                budget_utilization = (compressor_cost / budget_yuan) * 100

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("压缩机总投资", f"¥{compressor_cost:,}")
                with col2:
                    st.metric("辅助设备投资", f"¥{auxiliary_cost:,}")
                with col3:
                    st.metric("总投资", f"¥{total_investment:,}")
                with col4:
                    st.metric("预算利用率", f"{budget_utilization:.1f}%")

                if budget_utilization <= 100:
                    st.success(f"✅ 总投资在预算范围内，剩余 ¥{budget_yuan - total_investment:,.0f}")
                else:
                    st.warning(f"⚠️ 总投资超支 ¥{total_investment - budget_yuan:,.0f}")

                # 详细辅助设备信息展开部分
                with st.expander("📋 查看辅助设备详细信息"):
                    col1, col2 = st.columns(2)

                    with col1:
                        if 'plate_heat_exchanger' in perf and perf['plate_heat_exchanger']['selected']:
                            plate = perf['plate_heat_exchanger']
                            st.markdown("#### 板式换热器详情")
                            st.write(f"**型号:** {plate['model']}")
                            st.write(f"**换热量:** {plate['heat_exchange_capacity_kw']} kW")
                            st.write(f"**需求负荷:** {plate['required_capacity_kw']} kW")
                            st.write(f"**板换数量:** {plate['plate_count']}")
                            st.write(f"**制冷泵配置:** {plate['pump_count']}台 × {plate['pump_power_kw']}kW")
                            st.write(f"**管道接口:**")
                            if 'details' in plate and '氟利昂进口管径' in plate['details']:
                                st.write(f"- 氟利昂进口: {plate['details']['氟利昂进口管径']}")
                                st.write(f"- CO2进口: {plate['details']['CO2进口管径']}")
                                st.write(f"- CO2出口: {plate['details']['CO2出口管径']}")
                                st.write(f"- CO2回液口: {plate['details']['CO2回液口管径']}")
                            st.write(
                                f"**尺寸:** {plate['details'].get('长(mm)', '')}×{plate['details'].get('宽(mm)', '')}×{plate['details'].get('高(mm)', '')} mm")
                            st.write(f"**价格:** ¥{plate['total_price_yuan']:,}")

                    with col2:
                        if 'evaporative_condenser' in perf and perf['evaporative_condenser']['selected']:
                            condenser = perf['evaporative_condenser']
                            st.markdown("#### 蒸发式冷凝器详情")
                            st.write(f"**型号:** {condenser['model']}")
                            st.write(f"**排热量:** {condenser['heat_rejection_capacity_kw']} kW")
                            st.write(f"**需求排热量:** {condenser['required_heat_rejection_kw']} kW")
                            st.write(f"**配置数量:** {condenser['required_count']}台")
                            st.write(f"**风机功率:** {condenser['details'].get('轴流风机功率KW', '')}")
                            st.write(f"**循环水泵功率:** {condenser['details'].get('循环水泵功率KW', '')}")
                            st.write(f"**总功率:** {condenser['details'].get('总功率KW', '')} kW")
                            st.write(f"**价格:** ¥{condenser['total_price_yuan']:,}")

                # 导出按钮
                st.markdown("### 💾 导出设计方案")

                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("📄 生成详细报告", use_container_width=True):
                        report = generate_detailed_proposal_report(proposal, project_info, low_temp_rooms)
                        st.download_button(
                            label="下载报告",
                            data=report,
                            file_name=f"复叠系统设计方案_{proposal['proposal_name']}_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                            mime="text/plain"
                        )
                with col2:
                    if st.button("🔄 重新选型", use_container_width=True):
                        if 'selected_proposal_idx' in st.session_state:
                            del st.session_state.selected_proposal_idx
                        if 'selected_proposal' in st.session_state:
                            del st.session_state.selected_proposal
                        if 'proposals' in st.session_state:
                            del st.session_state.proposals
                        st.rerun()
                with col3:
                    if st.button("🏠 返回首页", use_container_width=True):
                        st.switch_page("cold_storage_input_interface.py")

        except Exception as e:
            st.error(f"复叠系统选型失败: {e}")
            import traceback
            st.error(f"详细错误: {traceback.format_exc()}")


if __name__ == "__main__":

    main()
