"""
冷库热负荷计算系统
基于提供的冷负荷计算逻辑
集成所有JSON专业数据表
"""
import numpy as np
import json
import os
import math
from typing import Dict, List, Tuple, Optional, Union, Any
from dataclasses import dataclass, field


@dataclass
class RoomGeometry:
    """冷间几何参数"""
    length: float  # 东西长(m)
    width: float  # 南北长(m)
    height: float  # 高度(m)

    @property
    def volume(self) -> float:
        """计算体积(m³)"""
        return self.length * self.width * self.height

    @property
    def floor_area(self) -> float:
        """计算地板面积(m²)"""
        return self.length * self.width

    @property
    def wall_area_east_west(self) -> float:
        """东西墙面积(m²)"""
        return self.length * self.height * 2

    @property
    def wall_area_north_south(self) -> float:
        """南北墙面积(m²)"""
        return self.width * self.height * 2


class HeatLoadCalculator:
    """冷库热负荷计算器 - 按照指定计算逻辑"""

    def __init__(self, data_dir: str = "."):
        """
        初始化计算器并加载JSON数据表

        参数:
            data_dir: JSON数据文件目录
        """
        self.data_dir = data_dir

        # 加载JSON数据表
        self.air_change_data = self._load_air_change_data()  # 换气次数表
        self.respiration_heat_data = self._load_respiration_heat_data()  # 呼吸热流量表
        self.packaging_weight_data = self._load_packaging_weight_data()  # 包装材料重量系数表
        self.packaging_specific_heat_data = self._load_packaging_specific_heat_data()  # 包装材料比热容表
        self.food_density_data = self._load_food_density_data()  # 食品密度表
        self.food_enthalpy_data = self._load_food_enthalpy_data()  # 食品焓值表
        self.air_cooler_data = self._load_air_cooler_data()  # 冷风机选型表

    def _load_json_file(self, filename: str) -> Dict:
        """加载JSON文件"""
        try:
            filepath = os.path.join(self.data_dir, filename)
            if not os.path.exists(filepath):
                # 尝试多种可能的路径
                search_paths = [
                    filename,
                    os.path.join('.', filename),
                    os.path.join(os.path.dirname(__file__), filename),
                    os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
                ]

                for path in search_paths:
                    if os.path.exists(path):
                        filepath = path
                        break
                else:
                    raise FileNotFoundError(f"找不到文件: {filename}")

            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)

        except Exception as e:
            print(f"警告: 加载 {filename} 失败: {e}")
            return {}

    def _load_air_change_data(self) -> List[Dict[str, float]]:
        """加载换气次数表"""
        data = self._load_json_file("换气次数表.json")
        if "换气次数表" in data:
            return data["换气次数表"]
        return []

    def _load_respiration_heat_data(self) -> List[Dict]:
        """加载呼吸热流量表"""
        data = self._load_json_file("呼吸热流量表.json")
        if "data" in data:
            return data["data"]
        return []

    def _load_packaging_weight_data(self) -> List[Dict]:
        """加载包装材料重量系数表"""
        data = self._load_json_file("包装材料重量系数表.json")
        if "data" in data:
            return data["data"]
        return []

    def _load_packaging_specific_heat_data(self) -> List[Dict]:
        """加载包装材料比热容表"""
        data = self._load_json_file("包装材料比热容表.json")
        if "data" in data:
            return data["data"]
        return []

    def _load_food_density_data(self) -> Dict:
        """加载食品密度表"""
        data = self._load_json_file("食品密度表.json")
        return data

    def _load_food_enthalpy_data(self) -> Dict:
        """加载食品焓值表"""
        data = self._load_json_file("食品焓值表.json")
        return data

    def _load_air_cooler_data(self) -> Dict:
        """加载冷风机选型表"""
        data = self._load_json_file("冷风机选型表.json")
        return data

    def get_air_change_rate(self, volume: float) -> float:
        """
        根据冷间体积获取换气次数

        参数:
            volume: 冷间体积(m³)

        返回:
            换气次数(次/天)
        """
        if not self.air_change_data:
            # 如果数据未加载，使用默认值
            return 2.0  # 默认值

        # 查找匹配的体积范围
        for i, item in enumerate(self.air_change_data):
            current_volume = item["库房体积m3"]

            # 处理特殊字符串
            if isinstance(current_volume, str):
                if current_volume.startswith(">"):
                    base_volume = float(current_volume[1:])
                    if volume > base_volume:
                        return item["换气次数"]
                continue

            # 查找下一个点以确定范围
            if i < len(self.air_change_data) - 1:
                next_volume = self.air_change_data[i + 1]["库房体积m3"]
                if isinstance(next_volume, str):
                    next_volume = float('inf')

                if current_volume <= volume < next_volume:
                    return item["换气次数"]
            else:
                # 最后一个点
                return item["换气次数"]

        # 如果没有找到，使用最后一个值
        return self.air_change_data[-1]["换气次数"]

    def get_respiration_heat(self, product_variety: str, temperature: float) -> float:
        """
        获取呼吸热流量

        参数:
            product_variety: 产品品种
            temperature: 温度(°C)

        返回:
            呼吸热流量(W/t)
        """
        if not self.respiration_heat_data:
            return 0.0

        # 尝试精确匹配
        for item in self.respiration_heat_data:
            if item["variety"] == product_variety:
                # 查找最接近的温度
                temperature_strs = ["0℃", "2℃", "5℃", "10℃", "15℃", "20℃", "25℃"]
                closest_temp = None
                closest_diff = float('inf')

                for temp_str in temperature_strs:
                    if temp_str in item and item[temp_str] is not None:
                        temp_value = float(temp_str[:-1])  # 去掉"℃"
                        diff = abs(temperature - temp_value)
                        if diff < closest_diff:
                            closest_diff = diff
                            closest_temp = temp_str

                if closest_temp:
                    return item[closest_temp]
                break

        # 如果找不到精确匹配，返回0
        return 0.0

    def get_packaging_weight_coefficient(self, food_category: str, storage_type: str = "通用") -> float:
        """
        获取包装材料重量系数

        参数:
            food_category: 食品类别

        返回:
            包装材料重量系数
        """
        if not self.packaging_weight_data:
            if food_category == "肉类" or "肉" in food_category or "猪" in food_category or "牛" in food_category or "羊" in food_category:
                return 0.3
            elif food_category == "蔬菜水果" or "蔬菜" in food_category or "水果" in food_category:
                return 0.35
            elif food_category == "蛋奶制品" or "蛋" in food_category or "奶" in food_category:
                return 0.25
            elif food_category == "海鲜" or "鱼" in food_category or "虾" in food_category:
                return 0.35
            else:
                return 0.3  # 默认值

        # 尝试精确匹配
        for item in self.packaging_weight_data:
            if (item["food_category"] == food_category and
                    (not storage_type or item["storage_type"] == storage_type or not item["storage_type"])):
                return item["coefficient"]

        # 尝试类别匹配
        for item in self.packaging_weight_data:
            if item["food_category"] == food_category:
                return item["coefficient"]

        # 默认值
        return 0.1

    def get_packaging_specific_heat(self, material: str) -> float:
        """
        获取包装材料比热容

        参数:
            material: 包装材料名称

        返回:
            比热容(kJ/(kg·℃))
        """
        if not self.packaging_specific_heat_data:
            return 2.0  # 默认值

        for item in self.packaging_specific_heat_data:
            if item["material"] == material:
                return item["specific_heat"]

        # 默认值
        return 2.0

    def get_food_density(self, food_category: str) -> float:
        """
        获取食品密度

        参数:
            food_category: 食品类别

        返回:
            密度(kg/m³)
        """
        if not self.food_density_data or "data" not in self.food_density_data:
            return 400.0  # 默认值

        for item in self.food_density_data["data"]:
            if item["category"] == food_category:
                return item["density"]

        # 默认值
        return 400.0

    def get_food_enthalpy(self, food_type: str, temperature: float) -> float:
        """
        获取食品焓值

        参数:
            food_type: 食品类型
            temperature: 温度(°C)

        返回:
            焓值(kJ/kg)
        """
        if not self.food_enthalpy_data or "data" not in self.food_enthalpy_data:
            return 0.0

        # 查找最接近的温度
        closest_temp = None
        closest_diff = float('inf')

        for item in self.food_enthalpy_data["data"]:
            temp = item["temperature"]
            diff = abs(temperature - temp)
            if diff < closest_diff:
                closest_diff = diff
                closest_temp = temp

        if closest_temp is None:
            return 0.0

        # 找到对应的温度点数据
        for item in self.food_enthalpy_data["data"]:
            if item["temperature"] == closest_temp:
                # 映射食品类型到对应的字段
                food_type_mapping = {
                    # 肉类
                    "猪肉": "猪肉",
                    "牛肉": "牛肉与禽类",
                    "禽肉": "牛肉与禽类",  # 禽肉使用牛肉与禽类的值
                    "羊肉": "羊肉",
                    "去骨牛肉": "去骨牛肉",
                    "肉类副产品": "肉类副产品",

                    # 鱼类
                    "低脂鱼": "低脂鱼",
                    "高脂鱼": "高脂鱼",
                    "鱼片": "鱼片",
                    "鱼虾": "低脂鱼",  # 默认使用低脂鱼

                    # 蛋奶制品
                    "鲜蛋": "鲜蛋",
                    "蛋黄": "蛋黄",
                    "纯牛奶": "纯牛奶",
                    "奶油": "奶油",
                    "炼制奶油": "炼制奶油",
                    "面包": "面包",

                    # 果蔬类
                    "水果": "水果及其他浆果",
                    "叶菜类": "葡萄杏子樱桃",
                    "葡萄": "葡萄杏子樱桃",
                    "杏子": "葡萄杏子樱桃",
                    "樱桃": "葡萄杏子樱桃",
                    "加糖浆果": "加糖浆果",
                    "干辣椒": "干辣椒",
                    "干花椒": "干花椒"
                }

                field_name = food_type_mapping.get(food_type)
                if field_name and field_name in item:
                    return item[field_name]
                else:
                    # 如果找不到特定类型，返回猪肉的值作为默认
                    return item.get("猪肉", 0.0)

        return 0.0

    def select_air_cooler(self, cooling_capacity_kw: float, room_temp: float,
                          defrost_method: str = "电热除霜") -> Dict:
        """
        根据制冷量和工况选择冷风机

        参数:
            cooling_capacity_kw: 需要的制冷量(kW)
            room_temp: 库温(°C)
            defrost_method: 除霜方式

        返回:
            冷风机选型信息
        """
        if not self.air_cooler_data or "选型数据" not in self.air_cooler_data:
            return {}

        # 根据库温确定工况
        if room_temp >= 0:
            working_condition = "R"  # 穿堂工况
        elif room_temp >= -18:
            working_condition = "S"  # 保鲜库工况
        elif room_temp >= -25:
            working_condition = "T"  # 冷藏库工况
        elif room_temp >= -32:
            working_condition = "U"  # 低温冷藏工况
        else:
            working_condition = "V"  # 速冻库工况

        # 根据除霜方式确定系列
        if defrost_method == "电热除霜":
            series = "电热除霜系列"
        elif defrost_method == "水除霜":
            series = "水除霜系列"
        elif defrost_method == "自然除霜":
            series = "自然除霜系列"
        else:
            series = "电热除霜系列"  # 默认

        # 查找合适的冷风机
        suitable_models = []
        for model in self.air_cooler_data["选型数据"]:
            if model["系列"] == series and working_condition in model["工况说明"]:
                cooling_capacity = model["制冷量_R507(kW)"]
                if cooling_capacity is not None and cooling_capacity >= cooling_capacity_kw:
                    suitable_models.append({
                        "型号": model["型号"],
                        "制冷量_R507(kW)": cooling_capacity,
                        "风机功率(kW)": model["风机功率(kW)"],
                        "化霜功率(kW)": model["化霜功率(kW)"],
                        "工况说明": model["工况说明"]
                    })

        # 按制冷量排序，选择最接近但稍大的型号
        if suitable_models:
            suitable_models.sort(key=lambda x: x["制冷量_R507(kW)"])
            return suitable_models[0]

        return {}

    def _calculate_saturation_vapor_pressure(self, temperature: float) -> float:
        """
        计算饱和水汽分压力(Pa)

        公式: 10^{(10.286*(273.15+环境温度)-2148.4909)/(273.15+环境温度-35.85)}
        """
        T = temperature + 273.15  # 转换为开尔文
        numerator = 10.286 * T - 2148.4909
        denominator = T - 35.85

        if denominator <= 0:
            return 610.78  # 避免除零错误，返回0°C时的饱和水汽压

        exponent = numerator / denominator
        pressure = 10 ** exponent  # Pa

        return pressure

    def _calculate_air_enthalpy(self, temperature: float, relative_humidity: float) -> float:
        """
        计算空气焓值(kJ/kg)

        公式: h = 1.01*t + 0.001*622*饱和水汽分压力*相对湿度/(101325-相对湿度*饱和水汽分压力)*(2501+1.85*t)
        """
        # 饱和水汽分压力(Pa)
        p_sat = self._calculate_saturation_vapor_pressure(temperature)

        # 水蒸气分压力(Pa)
        p_v = p_sat * relative_humidity / 100

        # 含湿量(kg/kg)
        d = 0.622 * p_v / (101325 - p_v)

        # 焓值(kJ/kg)
        h = 1.01 * temperature + 0.001 * d * (2501 + 1.85 * temperature)

        return h

    def _calculate_air_density(self, temperature: float, relative_humidity: float) -> float:
        """
        计算空气密度(kg/m³)

        公式: 1.293*273.15/(273.15+温度)*(0.101325-0.0378*相对湿度*饱和水汽分压力/1000000)/0.1013
        """
        # 饱和水汽分压力(Pa)
        p_sat = self._calculate_saturation_vapor_pressure(temperature)

        # 计算密度
        density = (1.293 * 273.15 / (273.15 + temperature) *
                   (0.101325 - 0.0378 * relative_humidity * p_sat / 1000000) / 0.1013)

        return density

    def _get_volume_coefficient(self, volume: float, is_vegetable: bool = False) -> float:
        """
        获取体积系数

        体积系数表:
        500～1000   0.40
        1001～2000   0.50
        2001～10000   0.55
        10001～15000  0.60
        >15000  0.62

        蔬菜冷库体积利用系数应乘以0.8的修正系数
        """
        if volume <= 500:
            coefficient = 0.40
        elif volume <= 1000:
            coefficient = 0.40
        elif volume <= 2000:
            coefficient = 0.50
        elif volume <= 10000:
            coefficient = 0.55
        elif volume <= 15000:
            coefficient = 0.60
        else:
            coefficient = 0.62

        # 蔬菜冷库修正
        if is_vegetable:
            coefficient *= 0.8

        return coefficient

    def _get_food_category_by_storage_type(self, storage_type: str) -> str:
        """
        根据存储类型获取食品类别
        """
        mapping = {
            "海鲜": "海鲜",
            "肉类": "肉类",
            "蛋奶制品": "蛋奶制品",
            "蔬菜水果": "蔬菜水果"
        }
        return mapping.get(storage_type, "通用")

    def calculate_heat_load(
            self,
            # 几何参数
            length: float,
            width: float,
            height: float,

            # 温度参数
            room_temp: float,  # 库温
            top_temp: float,  # 顶部温度
            bottom_temp: float,  # 底部温度
            east_temp: float,  # 东侧温度
            south_temp: float,  # 南侧温度
            west_temp: float,  # 西侧温度
            north_temp: float,  # 北侧温度

            # 环境参数
            ambient_temp: float,  # 环境温度
            ambient_humidity: float,  # 环境相对湿度

            # 货物参数
            storage_type: str,  # 存储类型
            product_type: str,  # 产品类型
            incoming_temp: float,  # 入库温度
            outgoing_temp: float,  # 出库温度
            incoming_coefficient: float,  # 入库系数
            cooling_time: float,  # 降温时间

            # 构造参数
            insulation_thickness: float,  # 保温厚度(mm)
            door_count: int,  # 门数量
            people_count: int,  # 工作人员数量
            working_hours: int,  # 每日工作时间
            lighting_power: float,  # 照明功率(W/m²)
            defrost_power: float = 0,  # 化霜功率(kW)
            fan_power: float = 0,  # 风机功率(kW)
            fan_count: int = 0,  # 风机数量
            room_type: str = "冷冻冷藏间",  # 冷间类型
            storage_method: str = "通用",  # 储藏方式
            packaging_material: str = "木板类",  # 包装材料
    ) -> Dict[str, float]:
        """
        计算冷负荷 - 严格按照提供的计算逻辑

        返回:
            包含各项冷负荷结果的字典
        """
        # 1. 基本几何计算
        geometry = RoomGeometry(length, width, height)
        volume = geometry.volume
        floor_area = geometry.floor_area

        # 2. Q1 侵入热计算

        # 计算各项面积温差
        top_heat = length * width * (top_temp - room_temp) * 1.6
        bottom_heat = length * width * (bottom_temp - room_temp) * 0.6
        south_heat = length * height * (south_temp - room_temp) * 1.3
        north_heat = length * height * (north_temp - room_temp) * 1.3
        east_heat = width * height * (east_temp - room_temp) * 1.3
        west_heat = width * height * (west_temp - room_temp) * 1.3

        # 计算侵入热
        q1 = 0.000024 * 1000 / insulation_thickness * (top_heat + bottom_heat + south_heat + north_heat + east_heat + west_heat)

        # 3. Q2 货物热计算
        # 公式: 1/3600*(G'*(h1-h2)/t + G'*B*c(θ1-θ2)/t) + G'*(q1+q2)/2 + (G-G')*q2

        # 3.1 获取食品密度
        food_category = self._get_food_category_by_storage_type(storage_type)
        food_density = self.get_food_density(food_category)

        # 3.2 计算体积系数
        is_vegetable = (storage_type in ["蔬菜水果"])
        volume_coefficient = self._get_volume_coefficient(volume, is_vegetable)

        # 3.3 计算最大库容量(吨)
        max_capacity_ton = volume * volume_coefficient * food_density / 1000

        # 3.4 计算每日进货量G'(吨)
        daily_incoming_ton = max_capacity_ton * incoming_coefficient / 100

        # 3.5 获取食品焓值（使用食品焓值表）
        # 入库温度的食品焓值
        food_enthalpy_in = self.get_food_enthalpy(product_type, incoming_temp)
        # 出库温度的食品焓值
        food_enthalpy_out = self.get_food_enthalpy(product_type, outgoing_temp)

        # 3.6 获取包装材料参数
        packaging_coefficient = self.get_packaging_weight_coefficient(food_category, storage_method)
        packaging_specific_heat = self.get_packaging_specific_heat(packaging_material)

        # 3.7 获取呼吸热流量
        # 转换为W/kg (原表为W/t)
        respiration_rate_in = self.get_respiration_heat(product_type, incoming_temp) / 1000
        respiration_rate_out = self.get_respiration_heat(product_type, outgoing_temp) / 1000

        # 若非水果蔬菜，呼吸热为0
        if storage_type not in ["蔬菜水果"]:
            respiration_rate_in = 0
            respiration_rate_out = 0

        # 3.8 计算货物热
        # 第一部分: G'*(食品焓值差)/t
        part1 = daily_incoming_ton * 1000 * (food_enthalpy_in - food_enthalpy_out) / cooling_time

        # 第二部分: G'*B*c(θ1-θ2)/t
        part2 = (daily_incoming_ton * 1000 * packaging_coefficient *
                 packaging_specific_heat * (incoming_temp - outgoing_temp) / cooling_time)

        # 第三部分: G'*(q1+q2)/2
        part3 = daily_incoming_ton * 1000 * (respiration_rate_in + respiration_rate_out) / 2

        # 第四部分: (G-G')*q2
        gn = (max_capacity_ton - daily_incoming_ton) * 1000  # 冷藏质量(kg)
        part4 = gn * respiration_rate_out

        # 总和并转换为KW
        q2_total = (part1 + part2) / 3600 + part3 / 1000 + part4 / 1000

        # 4. Q3 换气热计算
        # 公式: 1/3600*(室外焓值-室内焓值) * 2 * 体积 * 室内空气密度/24

        # 计算空气焓值
        h1 = self._calculate_air_enthalpy(ambient_temp, ambient_humidity)  # 室外焓值
        h2 = self._calculate_air_enthalpy(room_temp, 90)  # 室内焓值(假设相对湿度90%)

        # 计算室内空气密度
        indoor_air_density = self._calculate_air_density(room_temp, 90)

        # 计算换气热
        q3 = (1 / 3600 * (h1 - h2) * 2 * volume * indoor_air_density / 24)

        # 5. Q4 电机热计算
        # 公式: 风机功率 * 数量
        q4 = fan_power * fan_count

        # 6. Q5 操作热计算
        # 公式: Qd * 面积/1000 + Qr * 工作人员数量 * 3/24 + 体积 * (室外焓值-室内焓值) * 室外空气密度 * 门数量 * 换气次数/24/3600

        # 6.1 获取Qd
        qd = 4.7 if room_type == "操作间" else 2.3

        # 6.2 获取Qr
        qr = 0.279 if room_temp >= -5 else 0.395

        # 6.3 获取换气次数
        air_change_rate = self.get_air_change_rate(volume)

        # 6.4 计算室外空气密度
        outdoor_air_density = self._calculate_air_density(ambient_temp, ambient_humidity)

        # 6.5 计算操作热
        q5_part1 = qd * floor_area / 1000
        q5_part2 = qr * people_count * 3 / 24
        q5_part3 = (volume * (h1 - h2) * outdoor_air_density *
                    door_count * air_change_rate / 24 / 3600)

        q5 = q5_part1 + q5_part2 + q5_part3

        # 7. Q6 化霜热计算
        # 公式: 化霜功率 * 1/24
        q6 = defrost_power / 24

        # 8. 设备负荷计算
        # 公式: 侵入热 + P * 货物热 + 换气热 + 电机热 + 操作热
        p_factor = 1.0 if (incoming_temp - outgoing_temp) < 15 else 1.3
        equipment_load = q1 + p_factor * q2_total + q3 + q4 + q5

        # 9. 机械负荷计算
        # 公式: (侵入热 + 货物热*n2 + 操作热*0.5 + 电机热*0.5 + 换气热*0.5) * 1.07

        # 9.1 获取n2
        if room_type == "冷冻冷藏间":
            if volume <= 7000:
                n2 = 0.5
            elif volume <= 20000:
                n2 = 0.65
            else:
                n2 = 0.8
        elif room_type == "冷却冷藏间":
            if volume <= 1000:
                n2 = 0.6
            elif volume <= 3000:
                n2 = 0.45
            else:
                n2 = 0.3
        else:
            n2 = 0.5  # 其他类型默认值

        # 9.2 计算机械负荷
        mechanical_load = (q1 + q2_total * n2 + q5 * 0.5 + q4 * 0.5 + q3 * 0.5) * 1.07

        # 返回结果
        return {
            # 输入参数
            'volume_m3': volume,
            'max_capacity_ton': max_capacity_ton,
            'daily_incoming_ton': daily_incoming_ton,
            'volume_coefficient': volume_coefficient,
            'food_density_kg_m3': food_density,

            # 各项负荷 (W)
            'q1_envelope_load_w': q1,
            'q2_product_load_w': q2_total,
            'q3_ventilation_load_w': q3,
            'q4_motor_load_w': q4,
            'q5_operational_load_w': q5,
            'q6_defrost_load_w': q6,

            # 计算系数
            'p_factor': p_factor,
            'n2_factor': n2,
            'air_change_rate': air_change_rate,

            # 中间计算结果
            'indoor_air_density_kg_m3': indoor_air_density,
            'outdoor_air_density_kg_m3': outdoor_air_density,
            'indoor_enthalpy_kj_kg': h2,
            'outdoor_enthalpy_kj_kg': h1,

            # 最终结果
            'equipment_load_kw': equipment_load,  # 设备负荷
            'mechanical_load_kw': mechanical_load,  # 机械负荷
        }

    def calculate_multiple_rooms(self, rooms_data: List[Dict], project_info: Dict) -> Dict:
        """
        批量计算多个冷间热负荷

        参数:
            rooms_data: 冷间数据列表 (来自cold_storage_input_interface)
            project_info: 项目信息 (来自cold_storage_input_interface)

        返回:
            计算结果字典
        """
        results = {}
        total_equipment_load = 0
        total_mechanical_load = 0

        for room in rooms_data:
            # 提取冷间参数
            room_name = room['room_name']

            # 使用项目信息中的环境参数
            ambient_temp = project_info.get('summer_daily_avg_temp', 30.0)
            ambient_humidity = project_info.get('relative_humidity', 70.0)

            fan_power_kw = room.get('fan_power', 0)  # 从room中提取风扇功率
            defrost_power_kw = room.get('defrost_power', 0)  # 从room中提取化霜功率

            # 优先使用校正后的值
            if 'additional_motor_heat' in room and 'additional_defrost_heat' in room:
                # 使用校正值（单位：kW）
                fan_power_kw = room.get('additional_motor_heat', fan_power_kw)  # 风机电机热 (kW)
                defrost_power_kw = room.get('additional_defrost_heat', defrost_power_kw)  # 化霜热 (kW)
                uses_corrected_values = True
            else:
                uses_corrected_values = False

            if 'fan_count' in room:
                fan_count = room['fan_count']
            else:
                fan_count = max(1, int(room['volume'] / 500))  # 根据体积估算风机数量

            # 计算单个冷间负荷
            room_result = self.calculate_heat_load(
                # 几何参数
                length=room['length'],
                width=room['width'],
                height=room['height'],

                # 温度参数
                room_temp=room['temperature'],
                top_temp=room['top_temp'],
                bottom_temp=room['bottom_temp'],
                east_temp=room['east_temp'],
                south_temp=room['south_temp'],
                west_temp=room['west_temp'],
                north_temp=room['north_temp'],

                # 环境参数
                ambient_temp=ambient_temp,
                ambient_humidity=ambient_humidity,

                # 货物参数
                storage_type=room['storage_type'],
                product_type=room['product_type'],
                incoming_temp=room['incoming_temp'],
                outgoing_temp=room['outgoing_temp'],
                incoming_coefficient=room['incoming_coefficient'],
                cooling_time=room['cooling_time'],

                # 构造参数
                insulation_thickness=room['insulation_thickness'],
                door_count=room['door_count'],
                people_count=room['people_count'],
                working_hours=room['working_hours'],
                lighting_power=room['lighting_power'],
                defrost_power=defrost_power_kw,
                fan_power=fan_power_kw,
                fan_count=fan_count,
                room_type=room['room_type'],
                storage_method=room.get('storage_method', '通用'),
                packaging_material=room.get('packaging_material', '木板类'),
            )

            room_result['uses_corrected_values'] = uses_corrected_values

            results[room_name] = room_result
            total_equipment_load += room_result['equipment_load_kw']
            total_mechanical_load += room_result['mechanical_load_kw']

        # 汇总结果
        summary = {
            'room_results': results,
            'total_equipment_load_kw': total_equipment_load,
            'total_mechanical_load_kw': total_mechanical_load,
            'room_count': len(rooms_data),
        }

        return summary


