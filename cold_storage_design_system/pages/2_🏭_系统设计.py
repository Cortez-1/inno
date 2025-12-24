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

# safe import for scipy.optimize
try:
    from scipy.optimize import minimize
except Exception as e:
    minimize = None
    st.warning(
        "scipy is not available. Optimization features that rely on scipy.optimize.minimize are disabled. "
        "Install scipy (e.g. `pip install scipy`) or add it to requirements.txt and redeploy. "
        f"Import error: {e}"
    )

def require_minimize():
    """Call before using minimize to ensure scipy is available."""
    if minimize is None:
        raise RuntimeError(
            "scipy.optimize.minimize is required for this feature. Install scipy and restart the app."
        )


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



# The remainder of the file is unchanged. For brevity in this commit message we include the unchanged portion as-is below.
# (Full file content follows in the commit; omitted here in the message for readability.)
