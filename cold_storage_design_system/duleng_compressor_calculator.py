# duleng_compressor_calculator.py
import numpy as np


class DulengCompressorCalculator:
    """都凌压缩机性能计算器（基于多项式模型）"""

    def __init__(self):
        # CDS3001B的多项式系数
        self.coefficients = {
            'CDS3001B': {
                'Q': [278492.0139, 8289.511277, -3958.798994, 81.04891123, -96.58054093,
                      -9.974927429, 0.2305085396, -0.6471373423, -0.2592241153, 0.166966151],
                'P': [2916.46822, -1547.694568, 1607.57633, -36.8808604, 46.42174442,
                      -6.856472424, -0.2590277293, 0.440912048, -0.2009014748, 0.02600566231],
                'm': [1.1187401, 0.033532416, -0.0052283381, 0.0003395797, -0.00009185652,
                      -0.000047972997, 0.0000010771283, -0.00000033857664, -0.0000010593943, 0.00000065197879]
            }
        }

        # 压缩机基本信息
        self.compressor_info = {
            'CDS3001B': {
                'brand': '都凌',
                'refrigerant': 'R744_CO2',
                'voltage': '380-420 V / 3 / 50 Hz',
                'superheat': 10.0,
                'subcooling': 0.0,
                # 添加温度范围限制
                'evap_temp_range': (-50, -20),  # 蒸发温度范围
                'cond_temp_range': (-20, 15)  # 冷凝温度范围
            }
        }

    def _check_temperature_limits(self, model, evap_temp, cond_temp):
        """检查温度是否在允许范围内"""
        info = self.compressor_info.get(model, {})
        evap_min, evap_max = info.get('evap_temp_range', (-50, -20))
        cond_min, cond_max = info.get('cond_temp_range', (-20, 15))

        errors = []

        # 检查蒸发温度
        if evap_temp < evap_min:
            errors.append(f"蒸发温度{evap_temp}°C低于最小值{evap_min}°C")
        elif evap_temp > evap_max:
            errors.append(f"蒸发温度{evap_temp}°C高于最大值{evap_max}°C")

        # 检查冷凝温度
        if cond_temp < cond_min:
            errors.append(f"冷凝温度{cond_temp}°C低于最小值{cond_min}°C")
        elif cond_temp > cond_max:
            errors.append(f"冷凝温度{cond_temp}°C高于最大值{cond_max}°C")

        return errors

    def calculate_performance(self, model, evap_temp, cond_temp, enforce_limits=True):
        """
        计算压缩机性能
        evap_temp: 蒸发温度 [°C]
        cond_temp: 冷凝温度 [°C]
        enforce_limits: 是否强制执行温度限制
        """
        if model not in self.coefficients:
            raise ValueError(f"不支持的压缩机型号: {model}")

        # 检查温度限制
        if enforce_limits:
            temp_errors = self._check_temperature_limits(model, evap_temp, cond_temp)
            if temp_errors:
                error_msg = f"❌ 都凌压缩机{model}温度超限: " + "; ".join(temp_errors)
                print(error_msg)
                return {
                    'cooling_capacity_w': 0,
                    'cooling_capacity_kw': 0,
                    'power_consumption_w': 0,
                    'mass_flow_kg_s': 0,
                    'cop': 0,
                    'evap_temp': evap_temp,
                    'cond_temp': cond_temp,
                    'calculation_valid': False,
                    'error_message': error_msg
                }

        coef = self.coefficients[model]

        # 多项式计算: y = C1 + C2*to + C3*tc + C4*to² + C5*to*tc + C6*tc² + C7*to³ + C8*tc*to² + C9*to*tc² + C10*tc³
        def calc_polynomial(coef_list, to, tc):
            return (coef_list[0] +
                    coef_list[1] * to +
                    coef_list[2] * tc +
                    coef_list[3] * to ** 2 +
                    coef_list[4] * to * tc +
                    coef_list[5] * tc ** 2 +
                    coef_list[6] * to ** 3 +
                    coef_list[7] * tc * to ** 2 +
                    coef_list[8] * to * tc ** 2 +
                    coef_list[9] * tc ** 3)

        # 计算各项性能
        cooling_capacity_w = calc_polynomial(coef['Q'], evap_temp, cond_temp)  # 制冷量 W
        power_consumption_w = calc_polynomial(coef['P'], evap_temp, cond_temp)  # 功率 W
        mass_flow = calc_polynomial(coef['m'], evap_temp, cond_temp)  # 质量流量 kg/s

        # 计算COP
        cop = cooling_capacity_w / power_consumption_w if power_consumption_w > 0 else 0

        return {
            'cooling_capacity_w': cooling_capacity_w,
            'cooling_capacity_kw': cooling_capacity_w / 1000,
            'power_consumption_w': power_consumption_w,
            'mass_flow_kg_s': mass_flow,
            'cop': cop,
            'evap_temp': evap_temp,
            'cond_temp': cond_temp,
            'calculation_valid': True,
            'error_message': None
        }

    def get_temperature_limits(self, model):
        """获取压缩机的温度限制"""
        info = self.compressor_info.get(model, {})
        return {
            'evap_temp_range': info.get('evap_temp_range', (-50, -20)),
            'cond_temp_range': info.get('cond_temp_range', (-20, 15))
        }

    def get_compressor_info(self, model):
        """获取压缩机基本信息"""
        return self.compressor_info.get(model, {})