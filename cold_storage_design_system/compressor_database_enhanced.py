# compressor_database_enhanced.py
import pandas as pd
import numpy as np
import json
from scipy.interpolate import griddata

try:
    from duleng_compressor_calculator import DulengCompressorCalculator
except ImportError:
    print("⚠️  DulengCompressorCalculator未找到，将使用备用方案")


class BitzerCompressorCalculator:
    """比泽尔压缩机性能计算器"""

    def __init__(self, bitzer_data):
        # 从传入的比泽尔数据初始化
        self.bitzer_coefficients = {}

        for comp in bitzer_data:
            model = comp["型号"]
            # 存储Q系数和P系数
            self.bitzer_coefficients[model] = {
                'Q': [comp["Q_系数"][f"C{i}"] for i in range(1, 11)],
                'P': [comp["P_系数"][f"C{i}"] for i in range(1, 11)]
            }

        # 适用温度范围
        self.temp_ranges = {
            'evap_min': -50,  # 蒸发温度最小值 (°C)
            'evap_max': 20,  # 蒸发温度最大值 (°C)
            'cond_min': 20,  # 冷凝温度最小值 (°C)
            'cond_max': 60  # 冷凝温度最大值 (°C)
        }

        print("✅ 比泽尔压缩机计算器初始化完成")
        print(f"📊 支持 {len(self.bitzer_coefficients)} 个动态计算型号")

    def calculate_performance(self, model, evap_temp, cond_temp):
        """
        计算比泽尔压缩机性能

        Args:
            model: 压缩机型号
            evap_temp: 蒸发温度 (°C)
            cond_temp: 冷凝温度 (°C)

        Returns:
            dict: 包含制冷量、功率、COP等性能数据
        """
        # 检查型号是否支持
        if model not in self.bitzer_coefficients:
            return {
                'calculation_valid': False,
                'error_message': f'不支持的比泽尔压缩机型号: {model}'
            }

        # 检查温度范围
        if not (self.temp_ranges['evap_min'] <= evap_temp <= self.temp_ranges['evap_max']):
            return {
                'calculation_valid': False,
                'error_message': f'蒸发温度 {evap_temp}°C 超出范围 [{self.temp_ranges["evap_min"]}, {self.temp_ranges["evap_max"]}]'
            }

        if not (self.temp_ranges['cond_min'] <= cond_temp <= self.temp_ranges['cond_max']):
            return {
                'calculation_valid': False,
                'error_message': f'冷凝温度 {cond_temp}°C 超出范围 [{self.temp_ranges["cond_min"]}, {self.temp_ranges["cond_max"]}]'
            }

        try:
            coefficients = self.bitzer_coefficients[model]

            # 计算制冷量 Q (W)
            Q_watts = self._calculate_polynomial(coefficients['Q'], evap_temp, cond_temp)
            Q_kw = Q_watts / 1000  # 转换为kW

            # 计算功率 P (W)
            P_watts = self._calculate_polynomial(coefficients['P'], evap_temp, cond_temp)
            P_kw = P_watts / 1000  # 转换为kW

            # 计算COP
            if P_kw > 0:
                cop = Q_kw / P_kw
            else:
                cop = 0

            return {
                'calculation_valid': True,
                'cooling_capacity_kw': Q_kw,
                'power_consumption_w': P_watts,
                'power_consumption_kw': P_kw,
                'cop': cop,
                'evap_temp': evap_temp,
                'cond_temp': cond_temp,
                'model': model,
                'refrigerant': 'R507A'
            }

        except Exception as e:
            return {
                'calculation_valid': False,
                'error_message': f'计算失败: {str(e)}'
            }

    def _calculate_polynomial(self, coefficients, to, tc):
        """
        计算多项式值
        y = c1 + c2*to + c3*tc + c4*to^2 + c5*to*tc + c6*tc^2 + c7*to^3 + c8*tc*to^2 + c9*to*tc^2 + c10*tc^3
        """
        c1, c2, c3, c4, c5, c6, c7, c8, c9, c10 = coefficients

        to2 = to * to
        tc2 = tc * tc
        to3 = to2 * to
        tc3 = tc2 * tc

        y = (c1 +
             c2 * to +
             c3 * tc +
             c4 * to2 +
             c5 * to * tc +
             c6 * tc2 +
             c7 * to3 +
             c8 * tc * to2 +
             c9 * to * tc2 +
             c10 * tc3)

        return y

    def get_supported_models(self):
        """获取支持的压缩机型号列表"""
        return list(self.bitzer_coefficients.keys())



class CDS3001BCalculator:
    """都凌CDS3001B CO2压缩机性能计算器（基于真实数据）"""

    def __init__(self, compressor_data=None):
        """初始化，可选参数compressor_data用于保持接口兼容"""
        # 基于PDF中的真实数据构建性能数据库
        self.performance_data = self._initialize_performance_data()
        self.interpolation_points = self._create_interpolation_grid()

        # 如果需要，可以保存传入的数据
        self.compressor_data = compressor_data

        print("✅ CDS3001B CO2压缩机计算器初始化完成（基于真实数据）")

    def _initialize_performance_data(self):
        """基于PDF数据初始化性能数据库"""
        # 蒸发温度范围 (Te)
        evap_temps = [-35, -30, -25, -20, -15, -10, -5]
        # 冷凝温度范围 (Tc)
        cond_temps = [-20, -15, -10, -5, 0, 5, 10]

        # 制冷量数据 (W) - 从PDF表格提取
        cooling_capacity_data = {
            (-20, -35): 103489,
            (-15, -30): 120126, (-15, -35): 97563,
            (-10, -25): 137279, (-10, -30): 112578, (-10, -35): 91216,
            (-5, -20): 154567, (-5, -25): 127944, (-5, -30): 104670, (-5, -35): 84574,
            (0, -15): 143277, (0, -20): 118308, (0, -25): 96527, (0, -35): 77761,
            (5, -10): 131748, (5, -15): 108498, (5, -20): 88274, (5, -25): 70903,
            (10, -5): 120105, (10, -10): 98638, (10, -15): 80036, (10, -20): 64126
        }

        # 输入功率数据 (kW) - 从PDF表格提取
        power_consumption_data = {
            (-20, -35): 12.42,
            (-15, -30): 13.70, (-15, -35): 15.12,
            (-10, -25): 15.17, (-10, -30): 16.92, (-10, -35): 17.77,
            (-5, -20): 16.84, (-5, -25): 18.94, (-5, -30): 20.07, (-5, -35): 20.40,
            (0, -15): 21.19, (0, -20): 22.61, (0, -25): 23.15, (0, -35): 23.01,
            (5, -10): 25.40, (5, -15): 26.18, (5, -20): 26.19, (5, -25): 25.63,
            (10, -5): 29.49, (10, -10): 29.67, (10, -15): 29.21, (10, -20): 28.29
        }

        # 质量流量数据 (kg/h) - 从PDF表格提取
        mass_flow_data = {
            (-20, -35): 1273.9,
            (-15, -30): 1530.2, (-15, -35): 1247.9,
            (-10, -25): 1815.9, (-10, -30): 1493.1, (-10, -35): 1214.7,
            (-5, -20): 2131.6, (-5, -25): 1767.1, (-5, -30): 1449.6, (-5, -35): 1176.0,
            (0, -15): 2070.8, (0, -20): 1712.8, (0, -25): 1401.3, (0, -35): 1133.5,
            (5, -10): 2005.2, (5, -15): 1654.6, (5, -20): 1350.2, (5, -25): 1089.1,
            (10, -5): 1936.6, (10, -10): 1594.2, (10, -15): 1297.9, (10, -20): 1044.6
        }

        return {
            'cooling_capacity': cooling_capacity_data,
            'power_consumption': power_consumption_data,
            'mass_flow': mass_flow_data,
            'evap_temps': evap_temps,
            'cond_temps': cond_temps
        }

    def _create_interpolation_grid(self):
        """创建插值网格用于计算任意工况点"""
        points = []
        cooling_values = []
        power_values = []
        mass_flow_values = []

        for (tc, te), cooling in self.performance_data['cooling_capacity'].items():
            points.append([tc, te])
            cooling_values.append(cooling)
            power_values.append(self.performance_data['power_consumption'][(tc, te)])
            mass_flow_values.append(self.performance_data['mass_flow'][(tc, te)])

        return {
            'points': np.array(points),
            'cooling_values': np.array(cooling_values),
            'power_values': np.array(power_values),
            'mass_flow_values': np.array(mass_flow_values)
        }

    def _check_temperature_constraints(self, evap_temp, cond_temp):
        """
        检查温度约束条件

        约束条件:
        -50 ≤ Tₑ ≤ -20
        -20 ≤ T_c ≤ 15
        T_c ≥ Tₑ + 15
        T_c ≤ -0.4Tₑ + 5
        T_c ≤ 1.3333Tₑ + 61.6667
        """
        constraints = [
            # 基础约束
            (evap_temp >= -50, f"蒸发温度 {evap_temp}°C 低于最小值 -50°C"),
            (evap_temp <= -20, f"蒸发温度 {evap_temp}°C 高于最大值 -20°C"),
            (cond_temp >= -20, f"冷凝温度 {cond_temp}°C 低于最小值 -20°C"),
            (cond_temp <= 15, f"冷凝温度 {cond_temp}°C 高于最大值 15°C"),

            # 线性约束
            (cond_temp >= evap_temp + 15,
             f"冷凝温度 {cond_temp}°C 低于下限 Tₑ + 15 = {evap_temp + 15:.1f}°C"),

            (cond_temp <= -0.4 * evap_temp + 5,
             f"冷凝温度 {cond_temp}°C 超出上限 -0.4Tₑ + 5 = {-0.4 * evap_temp + 5:.1f}°C"),

            (cond_temp <= 1.3333 * evap_temp + 61.6667,
             f"冷凝温度 {cond_temp}°C 超出上限 1.3333Tₑ + 61.6667 = {1.3333 * evap_temp + 61.6667:.1f}°C")
        ]

        violations = []
        for condition, message in constraints:
            if not condition:
                violations.append(message)

        return len(violations) == 0, violations

    def _is_in_data_range(self, evap_temp, cond_temp):
        """检查是否在数据范围内"""
        data_evap_min = min(self.performance_data['evap_temps'])
        data_evap_max = max(self.performance_data['evap_temps'])
        data_cond_min = min(self.performance_data['cond_temps'])
        data_cond_max = max(self.performance_data['cond_temps'])

        in_range = (data_evap_min <= evap_temp <= data_evap_max and
                    data_cond_min <= cond_temp <= data_cond_max)

        return in_range, {
            'evap_range': (data_evap_min, data_evap_max),
            'cond_range': (data_cond_min, data_cond_max)
        }

    def calculate_performance(self, evap_temp, cond_temp):
        """
        计算CDS3001B在指定工况下的性能

        Args:
            evap_temp: 蒸发温度 (°C)
            cond_temp: 冷凝温度 (°C)

        Returns:
            dict: 性能数据
        """
        # 检查温度约束条件
        constraints_valid, constraint_errors = self._check_temperature_constraints(evap_temp, cond_temp)
        if not constraints_valid:
            return {
                'calculation_valid': False,
                'error_message': f'温度约束条件不满足: {"; ".join(constraint_errors)}'
            }

        # 检查是否在数据范围内
        in_data_range, data_ranges = self._is_in_data_range(evap_temp, cond_temp)
        if not in_data_range:
            return {
                'calculation_valid': False,
                'error_message': f'超出数据范围: 蒸发温度应在{data_ranges["evap_range"][0]}至{data_ranges["evap_range"][1]}°C, '
                                 f'冷凝温度应在{data_ranges["cond_range"][0]}至{data_ranges["cond_range"][1]}°C'
            }

        try:
            # 使用插值计算性能
            cooling_watts = griddata(
                self.interpolation_points['points'],
                self.interpolation_points['cooling_values'],
                [[cond_temp, evap_temp]],
                method='linear'
            )[0]

            power_kw = griddata(
                self.interpolation_points['points'],
                self.interpolation_points['power_values'],
                [[cond_temp, evap_temp]],
                method='linear'
            )[0]

            mass_flow_kg_h = griddata(
                self.interpolation_points['points'],
                self.interpolation_points['mass_flow_values'],
                [[cond_temp, evap_temp]],
                method='linear'
            )[0]

            # 计算COP
            cooling_kw = cooling_watts / 1000
            cop = cooling_kw / power_kw if power_kw > 0 else 0

            return {
                'calculation_valid': True,
                'cooling_capacity_w': cooling_watts,
                'cooling_capacity_kw': cooling_kw,
                'power_consumption_kw': power_kw,
                'mass_flow_kg_h': mass_flow_kg_h,
                'mass_flow_kg_s': mass_flow_kg_h / 3600,
                'cop': cop,
                'evap_temp': evap_temp,
                'cond_temp': cond_temp,
                'model': 'CDS3001B',
                'refrigerant': 'R744_CO2'
            }

        except Exception as e:
            return {
                'calculation_valid': False,
                'error_message': f'性能计算失败: {str(e)}'
            }

    def get_temperature_constraints_info(self):
        """获取温度约束条件的详细信息"""
        return {
            'constraints': [
                '-50 ≤ Tₑ ≤ -20',
                '-20 ≤ T_c ≤ 15',
                'T_c ≥ Tₑ + 15',
                'T_c ≤ -0.4Tₑ + 5',
                'T_c ≤ 1.3333Tₑ + 61.6667'
            ],
            'data_ranges': {
                'evap_min': min(self.performance_data['evap_temps']),
                'evap_max': max(self.performance_data['evap_temps']),
                'cond_min': min(self.performance_data['cond_temps']),
                'cond_max': max(self.performance_data['cond_temps'])
            }
        }

    def get_available_temperature_ranges(self):
        """获取可用的温度范围"""
        return {
            'evap_min': -50,  # 约束条件最小值
            'evap_max': max(self.performance_data['evap_temps']),  # 数据最大值
            'cond_min': -20,   # 约束条件最小值
            'cond_max': max(self.performance_data['cond_temps']),  # 数据最大值
            'data_evap_min': min(self.performance_data['evap_temps']),
            'data_evap_max': max(self.performance_data['evap_temps']),
            'data_cond_min': min(self.performance_data['cond_temps']),
            'data_cond_max': max(self.performance_data['cond_temps'])
        }



if __name__ == "__main__":
    test_enhanced_compressor_database()