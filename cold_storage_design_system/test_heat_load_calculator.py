# test_heat_load_detailed.py
"""
详细测试热负荷计算器 - 展示每个Q的计算结果
"""

import sys
import os

# 添加当前目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from heat_load_calculator import HeatLoadCalculator


def print_detailed_q_calculations(results):
    """详细打印每个Q的计算结果"""

    print("\n" + "=" * 80)
    print("🔍 详细各项热负荷计算结果")
    print("=" * 80)

    # Q1 - 侵入热
    print(f"\n📐 Q1 - 侵入热 (围护结构传热)")
    print("-" * 40)
    print(f"  计算结果: {results['q1_envelope_load_w']:.2f} W")
    print(f"          : {results['q1_envelope_load_w'] / 1000:.3f} kW")
    print("  说明: 通过冷间围护结构传入的热量，包括屋顶、墙壁、地面")

    # Q2 - 货物热
    print(f"\n📦 Q2 - 货物热 (产品负荷)")
    print("-" * 40)
    print(f"  计算结果: {results['q2_product_load_w']:.2f} W")
    print(f"          : {results['q2_product_load_w'] / 1000:.3f} kW")
    print(f"  P系数: {results['p_factor']:.2f}")
    print("  说明: 货物降温、呼吸热、包装材料等产生的热量")

    # Q3 - 换气热
    print(f"\n🌬️ Q3 - 换气热 (通风负荷)")
    print("-" * 40)
    print(f"  计算结果: {results['q3_ventilation_load_w']:.2f} W")
    print(f"          : {results['q3_ventilation_load_w'] / 1000:.3f} kW")
    print(f"  换气次数: {results['air_change_rate']:.2f} 次/天")
    print(f"  室内空气密度: {results['indoor_air_density_kg_m3']:.4f} kg/m³")
    print("  说明: 开门时室外空气进入带来的热量")

    # Q4 - 电机热
    print(f"\n⚡ Q4 - 电机热 (风机负荷)")
    print("-" * 40)
    print(f"  计算结果: {results['q4_motor_load_w']:.2f} W")
    print(f"          : {results['q4_motor_load_w'] / 1000:.3f} kW")
    print("  说明: 冷风机、水泵等电机设备运行产生的热量")

    # Q5 - 操作热
    print(f"\n👥 Q5 - 操作热 (操作负荷)")
    print("-" * 40)
    print(f"  计算结果: {results['q5_operational_load_w']:.2f} W")
    print(f"          : {results['q5_operational_load_w'] / 1000:.3f} kW")
    print("  说明: 人员活动、照明、开门操作等产生的热量")

    # Q6 - 化霜热
    print(f"\n❄️ Q6 - 化霜热 (除霜负荷)")
    print("-" * 40)
    print(f"  计算结果: {results['q6_defrost_load_w']:.2f} W")
    print(f"          : {results['q6_defrost_load_w'] / 1000:.3f} kW")
    print("  说明: 蒸发器除霜过程产生的热量")

    # 汇总分析
    print(f"\n📊 热负荷汇总分析")
    print("-" * 40)

    q_values = {
        'Q1-侵入热': results['q1_envelope_load_w'],
        'Q2-货物热': results['q2_product_load_w'],
        'Q3-换气热': results['q3_ventilation_load_w'],
        'Q4-电机热': results['q4_motor_load_w'],
        'Q5-操作热': results['q5_operational_load_w'],
        'Q6-化霜热': results['q6_defrost_load_w']
    }

    total_q = sum(q_values.values())

    if total_q > 0:
        print(f"  各项热负荷占比:")
        for name, value in q_values.items():
            percentage = value / total_q * 100
            print(f"    {name}: {percentage:.1f}% ({value / 1000:.3f} kW)")

        print(f"\n  总热负荷: {total_q / 1000:.3f} kW")

    # 最终结果
    print(f"\n🎯 最终计算结果")
    print("-" * 40)
    print(f"  设备负荷 (Equipment Load): {results['equipment_load_kw']:.3f} kW")
    print(f"  机械负荷 (Mechanical Load): {results['mechanical_load_kw']:.3f} kW")
    print(f"  n2系数: {results['n2_factor']:.2f}")


def test_with_image_parameters():
    """使用图片中的参数测试热负荷计算器"""

    print("=" * 80)
    print("冷库热负荷计算测试 - 根据图片参数")
    print("=" * 80)

    # 初始化计算器
    calculator = HeatLoadCalculator(data_dir=".")

    # 根据图片提取参数
    print("\n📊 从图片提取的参数:")
    print("-" * 40)

    # 基本几何参数 (从图片)
    length = 30.00  # 东西长(m)
    width = 39.00  # 南北长(m)
    height = 4.65  # 高度(m)

    print(f"冷间尺寸: {length}m × {width}m × {height}m")
    volume = length * width * height
    print(f"体积: {volume:.2f} m³")

    # 温度参数 (从图片)
    room_temp = -20.00  # 出库温度作为库温(℃)
    top_temp = 10.00  # 顶部温度(℃)
    bottom_temp = 15.00  # 底部温度(℃)

    # 水平方向温度 (从图片)
    east_temp = -15.00  # 东侧温度(℃)
    south_temp = -15.00  # 南侧温度(℃)
    west_temp = -15.00  # 西侧温度(℃)
    north_temp = 15.00  # 北侧温度(℃)

    # 货物参数 (从图片)
    product_type = "猪肉"
    incoming_temp = 8.00  # 入库温度(℃)
    outgoing_temp = -20.00  # 出库温度(℃)
    incoming_coefficient = 5.0  # 入库系数(%)
    cooling_time = 24.0  # 降温时间(小时)

    # 缺少的参数 - 设置为合理默认值
    ambient_temp = 30.0  # 环境温度(℃) - 夏季平均
    ambient_humidity = 70.0  # 环境相对湿度(%)
    insulation_thickness = 150.0  # 保温厚度(mm) - 常见值
    door_count = 2  # 门数量
    people_count = 2  # 工作人员数量
    working_hours = 8  # 每日工作时间(小时)
    lighting_power = 5.0  # 照明功率(W/m²)
    defrost_power = 2.0  # 化霜功率(kW) - 电热除霜
    fan_power = 0.75  # 风机功率(kW)
    fan_count = 4  # 风机数量 - 根据体积估算

    # 其他参数
    storage_type = "冷冻冷藏间"
    storage_method = "通用"
    packaging_material = "瓦楞纸类"
    room_type = "冷冻冷藏间"

    print(f"\n🌡️ 温度参数:")
    print(f"  库温: {room_temp}℃")
    print(f"  入库温度: {incoming_temp}℃ → 出库温度: {outgoing_temp}℃")
    print(f"  入库温差: {incoming_temp - outgoing_temp}℃")

    print(f"\n📦 货物参数:")
    print(f"  产品类型: {product_type}")
    print(f"  入库系数: {incoming_coefficient}%")
    print(f"  降温时间: {cooling_time}小时")

    print(f"\n🏗️ 构造参数:")
    print(f"  保温厚度: {insulation_thickness}mm")
    print(f"  门数量: {door_count}")
    print(f"  工作人员: {people_count}人")

    # 执行计算
    print("\n" + "=" * 80)
    print("🔬 开始计算...")
    print("=" * 80)

    try:
        results = calculator.calculate_heat_load(
            # 几何参数
            length=length,
            width=width,
            height=height,

            # 温度参数
            room_temp=room_temp,
            top_temp=top_temp,
            bottom_temp=bottom_temp,
            east_temp=east_temp,
            south_temp=south_temp,
            west_temp=west_temp,
            north_temp=north_temp,

            # 环境参数
            ambient_temp=ambient_temp,
            ambient_humidity=ambient_humidity,

            # 货物参数
            storage_type=storage_type,
            product_type=product_type,
            incoming_temp=incoming_temp,
            outgoing_temp=outgoing_temp,
            incoming_coefficient=incoming_coefficient,
            cooling_time=cooling_time,

            # 构造参数
            insulation_thickness=insulation_thickness,
            door_count=door_count,
            people_count=people_count,
            working_hours=working_hours,
            lighting_power=lighting_power,
            defrost_power=defrost_power,
            fan_power=fan_power,
            fan_count=fan_count,
            room_type=room_type,
            storage_method=storage_method,
            packaging_material=packaging_material,
        )

        # 显示详细计算结果
        print_detailed_q_calculations(results)

        # 冷风机选型建议
        print(f"\n❄️  冷风机选型建议:")
        print("-" * 40)

        if results['mechanical_load_kw'] > 0:
            cooler_selection = calculator.select_air_cooler(
                cooling_capacity_kw=results['mechanical_load_kw'],
                room_temp=room_temp,
                defrost_method="电热除霜"
            )

            if cooler_selection:
                print(f"  推荐型号: {cooler_selection['型号']}")
                print(f"  制冷量: {cooler_selection['制冷量_R507(kW)']} kW")
                print(f"  风机功率: {cooler_selection['风机功率(kW)']} kW")
                print(f"  化霜功率: {cooler_selection['化霜功率(kW)']} kW")
                print(f"  工况: {cooler_selection['工况说明']}")
            else:
                print("  警告: 未找到合适的冷风机型号")

        return results

    except Exception as e:
        print(f"\n❌ 计算过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_q1_calculation_details(calculator):
    """详细展示Q1计算过程"""

    print("\n" + "=" * 80)
    print("🔍 Q1 - 侵入热详细计算示例")
    print("=" * 80)

    # 示例参数
    length = 30.0
    width = 39.0
    height = 4.65
    insulation_thickness = 150.0
    room_temp = -20.0

    # 温度参数
    top_temp = 10.0
    bottom_temp = 15.0
    east_temp = -15.0
    south_temp = -15.0
    west_temp = -15.0
    north_temp = 15.0

    # 计算各项
    top_area = length * width
    bottom_area = length * width
    east_area = width * height
    west_area = width * height
    south_area = length * height
    north_area = length * height

    print(f"几何参数:")
    print(f"  东西长: {length}m, 南北宽: {width}m, 高度: {height}m")
    print(f"  体积: {length * width * height:.2f} m³")

    print(f"\n面积计算:")
    print(f"  顶部面积: {top_area:.2f} m²")
    print(f"  底部面积: {bottom_area:.2f} m²")
    print(f"  东西墙面积: {east_area:.2f} m²")
    print(f"  南北墙面积: {south_area:.2f} m²")

    print(f"\n温差计算 (相对于库温{room_temp}℃):")
    print(f"  顶部温差: {top_temp - room_temp:.1f}℃")
    print(f"  底部温差: {bottom_temp - room_temp:.1f}℃")
    print(f"  东墙温差: {east_temp - room_temp:.1f}℃")
    print(f"  西墙温差: {west_temp - room_temp:.1f}℃")
    print(f"  南墙温差: {south_temp - room_temp:.1f}℃")
    print(f"  北墙温差: {north_temp - room_temp:.1f}℃")

    # 修正系数
    top_factor = 1.6
    bottom_factor = 0.6
    wall_factor = 1.3

    print(f"\n修正系数:")
    print(f"  顶部修正系数: {top_factor}")
    print(f"  底部修正系数: {bottom_factor}")
    print(f"  墙面修正系数: {wall_factor}")

    # 计算各项热量
    top_heat = top_area * (top_temp - room_temp) * top_factor
    bottom_heat = bottom_area * (bottom_temp - room_temp) * bottom_factor
    east_heat = east_area * (east_temp - room_temp) * wall_factor
    west_heat = west_area * (west_temp - room_temp) * wall_factor
    south_heat = south_area * (south_temp - room_temp) * wall_factor
    north_heat = north_area * (north_temp - room_temp) * wall_factor

    print(f"\n各项热量:")
    print(f"  顶部热量: {top_heat:.2f} W")
    print(f"  底部热量: {bottom_heat:.2f} W")
    print(f"  东墙热量: {east_heat:.2f} W")
    print(f"  西墙热量: {west_heat:.2f} W")
    print(f"  南墙热量: {south_heat:.2f} W")
    print(f"  北墙热量: {north_heat:.2f} W")

    total_heat = top_heat + bottom_heat + east_heat + west_heat + south_heat + north_heat
    print(f"\n总热量和: {total_heat:.2f} W")

    # 计算传热系数
    k_factor = 0.000024 * 1000 / insulation_thickness
    print(f"\n传热系数计算:")
    print(f"  k = 0.000024 × 1000 / {insulation_thickness}")
    print(f"    = {k_factor:.6f}")

    q1 = k_factor * total_heat
    print(f"\n最终Q1侵入热: {q1:.2f} W")
    print(f"              {q1 / 1000:.3f} kW")


def test_q2_calculation_details(calculator):
    """详细展示Q2计算过程"""

    print("\n" + "=" * 80)
    print("🔍 Q2 - 货物热详细计算示例")
    print("=" * 80)

    # 示例参数
    volume = 5425.5  # 30*39*4.65
    product_type = "猪肉"
    incoming_temp = 8.0
    outgoing_temp = -20.0
    incoming_coefficient = 5.0
    cooling_time = 24.0
    storage_type = "冷冻冷藏间"

    print(f"输入参数:")
    print(f"  冷间体积: {volume:.2f} m³")
    print(f"  产品类型: {product_type}")
    print(f"  入库温度: {incoming_temp}℃")
    print(f"  出库温度: {outgoing_temp}℃")
    print(f"  入库系数: {incoming_coefficient}%")
    print(f"  降温时间: {cooling_time}小时")

    # 获取食品密度
    food_category = calculator._get_food_category_by_storage_type(storage_type)
    food_density = calculator.get_food_density(food_category)
    print(f"\n食品密度:")
    print(f"  食品类别: {food_category}")
    print(f"  密度: {food_density} kg/m³")

    # 计算体积系数
    is_vegetable = storage_type in ["蔬菜水果"]
    volume_coefficient = calculator._get_volume_coefficient(volume, is_vegetable)
    print(f"\n体积系数:")
    print(f"  体积: {volume:.2f} m³")
    print(f"  是否蔬菜: {is_vegetable}")
    print(f"  体积系数: {volume_coefficient}")

    # 计算最大库容量
    max_capacity_ton = volume * volume_coefficient * food_density / 1000
    print(f"\n最大库容量:")
    print(f"  G = 体积 × 体积系数 × 密度 / 1000")
    print(f"    = {volume:.2f} × {volume_coefficient} × {food_density} / 1000")
    print(f"    = {max_capacity_ton:.2f} t")

    # 计算每日进货量
    daily_incoming_ton = max_capacity_ton * incoming_coefficient / 100
    print(f"\n每日进货量:")
    print(f"  G' = G × 入库系数 / 100")
    print(f"     = {max_capacity_ton:.2f} × {incoming_coefficient} / 100")
    print(f"     = {daily_incoming_ton:.2f} t")

    # 获取食品焓值
    enthalpy_in = calculator.get_food_enthalpy(product_type, incoming_temp)
    enthalpy_out = calculator.get_food_enthalpy(product_type, outgoing_temp)
    print(f"\n食品焓值:")
    print(f"  入库温度焓值({incoming_temp}℃): {enthalpy_in} kJ/kg")
    print(f"  出库温度焓值({outgoing_temp}℃): {enthalpy_out} kJ/kg")
    print(f"  焓值差: {enthalpy_in - enthalpy_out} kJ/kg")

    # 计算各部分
    # 第一部分: G'*(食品焓值差)/t
    part1 = daily_incoming_ton * 1000 * (enthalpy_in - enthalpy_out) / cooling_time
    print(f"\n第一部分 (食品焓值变化):")
    print(f"  公式: G' × (h1 - h2) / t")
    print(f"  计算: {daily_incoming_ton:.3f} × 1000 × ({enthalpy_in:.1f} - {enthalpy_out:.1f}) / {cooling_time}")
    print(f"  结果: {part1:.2f} W")

    # 获取包装材料参数
    packaging_coefficient = calculator.get_packaging_weight_coefficient(food_category, "通用")
    packaging_specific_heat = calculator.get_packaging_specific_heat("瓦楞纸类")
    print(f"\n包装材料参数:")
    print(f"  重量系数 B: {packaging_coefficient}")
    print(f"  比热容 c: {packaging_specific_heat} kJ/(kg·℃)")

    # 第二部分: G'*B*c(θ1-θ2)/t
    part2 = daily_incoming_ton * 1000 * packaging_coefficient * packaging_specific_heat * (
                incoming_temp - outgoing_temp) / cooling_time
    print(f"\n第二部分 (包装材料):")
    print(f"  公式: G' × B × c × (θ1 - θ2) / t")
    print(
        f"  计算: {daily_incoming_ton:.3f} × 1000 × {packaging_coefficient} × {packaging_specific_heat} × ({incoming_temp} - {outgoing_temp}) / {cooling_time}")
    print(f"  结果: {part2:.2f} W")

    # 第三部分: G'*(q1+q2)/2 (呼吸热)
    respiration_rate_in = calculator.get_respiration_heat(product_type, incoming_temp) / 1000
    respiration_rate_out = calculator.get_respiration_heat(product_type, outgoing_temp) / 1000

    # 对于冷冻猪肉，呼吸热应为0
    if storage_type not in ["蔬菜水果"]:
        respiration_rate_in = 0
        respiration_rate_out = 0

    part3 = daily_incoming_ton * 1000 * (respiration_rate_in + respiration_rate_out) / 2
    print(f"\n第三部分 (呼吸热):")
    print(f"  入库呼吸热: {respiration_rate_in} W/kg")
    print(f"  出库呼吸热: {respiration_rate_out} W/kg")
    print(f"  公式: G' × (q1 + q2) / 2")
    print(f"  结果: {part3:.2f} W")

    # 第四部分: (G-G')*q2
    gn = (max_capacity_ton - daily_incoming_ton) * 1000
    part4 = gn * respiration_rate_out
    print(f"\n第四部分 (库存呼吸热):")
    print(f"  库存质量 G-G': {(max_capacity_ton - daily_incoming_ton):.3f} t = {gn} kg")
    print(f"  公式: (G - G') × q2")
    print(f"  结果: {part4:.2f} W")

    # 总和
    q2_total = (part1 + part2) / 3600 + part3 / 1000 + part4 / 1000
    print(f"\nQ2货物热总计:")
    print(f"  Q2 = (第一部分 + 第二部分)/3600 + 第三部分/1000 + 第四部分/1000")
    print(f"     = ({part1:.2f} + {part2:.2f})/3600 + {part3:.2f}/1000 + {part4:.2f}/1000")
    print(f"     = {q2_total:.3f} kW")
    print(f"     = {q2_total * 1000:.2f} W")


if __name__ == "__main__":
    # 测试主函数
    print("冷库热负荷计算器 - 详细测试程序")
    print("基于提供的计算逻辑和图片参数")
    print()

    # 初始化计算器
    calculator = HeatLoadCalculator(data_dir=".")

    # 运行主要测试
    results = test_with_image_parameters()

    if results:
        print("\n" + "=" * 80)
        print("🧪 详细计算过程演示")
        print("=" * 80)

        # 详细展示Q1计算
        test_q1_calculation_details(calculator)

        # 详细展示Q2计算
        test_q2_calculation_details(calculator)

        # 参数敏感性分析
        print("\n" + "=" * 80)
        print("📈 参数敏感性分析")
        print("=" * 80)

        # 分析不同入库温度的影响
        print(f"\n入库温度影响分析:")
        incoming_temps = [15.0, 8.0, 0.0, -5.0]
        for temp in incoming_temps:
            # 模拟计算
            temp_diff = temp - (-20.0)
            if temp_diff < 15:
                p_factor = 1.0
            else:
                p_factor = 1.3

            # 估算Q2变化（简化）
            q2_original = results['q2_product_load_w']
            if temp_diff > 0:
                q2_new = q2_original * (temp_diff / 28) * p_factor  # 28是原始温差
            else:
                q2_new = q2_original * 0.1  # 温差小时负荷小

            equipment_load_new = results['q1_envelope_load_w'] + p_factor * q2_new + results['q3_ventilation_load_w'] + \
                                 results['q4_motor_load_w'] + results['q5_operational_load_w']

            print(f"  入库温度 {temp}℃ (温差 {temp_diff:.1f}℃):")
            print(f"    P系数: {p_factor:.1f}")
            print(f"    设备负荷估算: {equipment_load_new / 1000:.2f} kW")

    print("\n✅ 测试完成！")