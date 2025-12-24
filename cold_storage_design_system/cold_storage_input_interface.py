# cold_storage_input_interface.py
import base64
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import json
import os
import pickle

class ColdStorageInputInterface:
    """冷库参数输入界面"""

    def __init__(self):
        self.storage_types = {
            "肉类": {"temp_range": (-25, -18), "humidity": 0.90},
            "海鲜": {"temp_range": (-22, -18), "humidity": 0.95},
            "蛋奶制品": {"temp_range": (2, 6), "humidity": 0.85},
            "蔬菜水果": {"temp_range": (4, 8), "humidity": 0.90}
        }

        # 从JSON文件加载产品类型数据
        self.product_types = self.load_product_types()

        # 加载气象数据
        self.weather_data = self.load_weather_data()
        self.provinces = self.get_provinces()

    def load_product_types(self):
        """从JSON文件加载产品类型数据"""
        try:
            # 如果session_state中已有数据，直接使用
            if 'product_types_data' in st.session_state and st.session_state.product_types_data:
                return st.session_state.product_types_data

            # 从JSON文件加载数据
            json_paths = [
                'product_types.json',
                './product_types.json',
                os.path.join(os.path.dirname(__file__), 'product_types.json'),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), 'product_types.json')
            ]

            product_types_data = None
            for json_path in json_paths:
                try:
                    if os.path.exists(json_path):
                        with open(json_path, 'r', encoding='utf-8') as f:
                            product_data = json.load(f)
                        product_types_data = product_data['product_types']
                        st.success(f"✅ 成功从 {json_path} 加载产品类型数据")
                        break
                except Exception as e:
                    st.warning(f"无法从 {json_path} 加载产品类型数据: {e}")
                    continue

            if product_types_data is None:
                st.error("❌ 未找到产品类型数据文件 'product_types.json'，请确保文件存在于程序目录下")
                return {}

            st.session_state.product_types_data = product_types_data
            return product_types_data

        except Exception as e:
            st.error(f"加载产品类型数据失败: {e}")
            return {}

    def load_weather_data(self):
        """从JSON文件加载完整的气象数据"""
        try:
            # 如果session_state中已有数据，直接使用
            if 'weather_df' in st.session_state and not st.session_state.weather_df.empty:
                return st.session_state.weather_df

            # 从JSON文件加载数据
            json_paths = [
                'weather_data.json',
                './weather_data.json',
                os.path.join(os.path.dirname(__file__), 'weather_data.json'),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), 'weather_data.json')
            ]

            weather_df = None
            for json_path in json_paths:
                try:
                    if os.path.exists(json_path):
                        with open(json_path, 'r', encoding='utf-8') as f:
                            weather_data = json.load(f)
                        weather_df = pd.DataFrame(weather_data['weather_data'])
                        st.success(f"✅ 成功从 {json_path} 加载气象数据")
                        break
                except Exception as e:
                    st.warning(f"无法从 {json_path} 加载数据: {e}")
                    continue

            if weather_df is None:
                st.error("❌ 未找到气象数据文件 'weather_data.json'，请确保文件存在于程序目录下")
                return pd.DataFrame()

            st.session_state.weather_df = weather_df
            return weather_df

        except Exception as e:
            st.error(f"加载气象数据失败: {e}")
            return pd.DataFrame()

    def get_products_by_storage_type(self, storage_type):
        """根据存储类型获取产品列表"""
        if storage_type in self.product_types:
            return self.product_types[storage_type]
        else:
            return ["通用产品"]

    def get_provinces(self):
        """获取省份列表"""
        if not self.weather_data.empty:
            provinces = self.weather_data['省份'].dropna().unique().tolist()
            return [p for p in provinces if p and p.strip()]
        return []

    def get_cities_by_province(self, province):
        """根据省份获取城市列表"""
        if not self.weather_data.empty and province:
            cities = self.weather_data[self.weather_data['省份'] == province]['城市名称'].dropna().unique().tolist()
            return [c for c in cities if c and c.strip()]
        return []

    def get_weather_data_by_city(self, province, city):
        """根据省份和城市获取气象数据"""
        if not self.weather_data.empty and province and city:
            mask = (self.weather_data['省份'] == province) & (self.weather_data['城市名称'] == city)
            city_data = self.weather_data[mask]
            if not city_data.empty:
                return city_data.iloc[0]
        return None

    def save_project_data(self, project_info, rooms_data):
        """保存项目数据到本地文件"""
        try:
            # 创建保存目录
            save_dir = "saved_projects"
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)

            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            project_name = project_info.get('project_name', 'untitled').replace(" ", "_")
            filename = f"{save_dir}/{project_name}_{timestamp}.pkl"

            # 准备数据
            save_data = {
                'project_info': project_info,
                'rooms_data': rooms_data,
                'save_time': datetime.now().isoformat(),
                'version': '1.0'
            }

            # 保存为pickle文件
            with open(filename, 'wb') as f:
                pickle.dump(save_data, f)

            return filename
        except Exception as e:
            st.error(f"保存失败: {e}")
            return None

    def load_saved_projects(self):
        """加载所有保存的项目"""
        save_dir = "saved_projects"
        saved_projects = []

        if os.path.exists(save_dir):
            for filename in os.listdir(save_dir):
                if filename.endswith('.pkl'):
                    try:
                        filepath = os.path.join(save_dir, filename)
                        with open(filepath, 'rb') as f:
                            project_data = pickle.load(f)
                            saved_projects.append({
                                'filename': filename,
                                'filepath': filepath,
                                'project_name': project_data.get('project_info', {}).get('project_name', '未知项目'),
                                'save_time': project_data.get('save_time', ''),
                                'data': project_data
                            })
                    except Exception as e:
                        print(f"加载项目文件失败 {filename}: {e}")

        # 按保存时间排序（最新的在前）
        saved_projects.sort(key=lambda x: x.get('save_time', ''), reverse=True)
        return saved_projects


def initialize_input_session():
    """初始化输入会话状态"""
    if 'rooms_data' not in st.session_state:
        st.session_state.rooms_data = []
    if 'project_info' not in st.session_state:
        st.session_state.project_info = {}
    if 'current_room_editing' not in st.session_state:
        st.session_state.current_room_editing = None
    if 'weather_df' not in st.session_state:
        st.session_state.weather_df = pd.DataFrame()
    if 'current_storage_type' not in st.session_state:
        st.session_state.current_storage_type = "冷冻食品"  # 默认值
    if 'current_product_options' not in st.session_state:
        st.session_state.current_product_options = ["猪肉", "牛肉", "禽肉", "鱼虾", "冷冻调理食品", "其他冷冻食品"]
    if 'current_product_type' not in st.session_state:
        st.session_state.current_product_type = "猪肉"
    if 'form_submitted' not in st.session_state:
        st.session_state.form_submitted = False


def create_header_with_icon(title, icon_path="./icons/logo.png", icon_size=100,
                            top_offset=0):
    """创建带自定义图标的标题"""
    with open(icon_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode()
    icon_html = f'<img src="data:image/png;base64,{encoded_string}" width="{icon_size}" height="{icon_size}" style="position: relative; top: {top_offset}px; margin-right: 12px; border-radius: 5px;">'

    return f'<h1 class="main-header">{icon_html}{title}</h1>'


def main():
    st.set_page_config(
        page_title="英诺绿能冷库智能化系统",
        page_icon="./icons/logo.png",
        layout="wide",
        initial_sidebar_state="expanded"
    )

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
    .input-card {
        background-color: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        border: 2px solid #dee2e6;
        margin-bottom: 1rem;
    }
    .room-card {
        background-color: #e7f3ff;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #2e86ab;
        margin-bottom: 0.5rem;
    }
    .summary-card {
        background-color: #d4edda;
        padding: 1.5rem;
        border-radius: 10px;
        border: 2px solid #c3e6cb;
    }
    .warning-card {
        background-color: #fff3cd;
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid #ffeaa7;
    }
    .weather-info {
        background-color: #e8f4fd;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #2196F3;
        margin-top: 1rem;
    }
    .error-card {
        background-color: #f8d7da;
        padding: 1.5rem;
        border-radius: 8px;
        border-left: 4px solid #dc3545;
        margin-bottom: 1rem;
    }
    /* 自定义下拉菜单样式 */
    div[data-baseweb="select"] {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
    }
    
    div[data-baseweb="select"] div[role="option"] {
        padding: 8px 12px !important;
        font-size: 14px !important;
    }
    
    /* 分组标题样式 - 灰色不可选 */
    div[data-baseweb="select"] div[role="option"][aria-disabled="true"] {
        color: #666666 !important;
        background-color: #f5f5f5 !important;
        font-weight: bold !important;
        font-size: 14px !important;
        cursor: not-allowed !important;
        opacity: 1 !important;
        border-top: 1px solid #ddd !important;
        border-bottom: 1px solid #ddd !important;
        margin: 2px 0 !important;
    }
    
    /* 具体产品选项样式 - 黑色可选 */
    div[data-baseweb="select"] div[role="option"]:not([aria-disabled="true"]) {
        color: #333333 !important;
        padding-left: 24px !important;
        font-size: 14px !important;
        cursor: pointer !important;
    }
    
    /* 悬停效果 */
    div[data-baseweb="select"] div[role="option"]:not([aria-disabled="true"]):hover {
        background-color: #e6f7ff !important;
        color: #1890ff !important;
    }
    
    /* 选中状态 */
    div[data-baseweb="select"] div[role="option"][aria-selected="true"] {
        background-color: #e6f7ff !important;
        color: #1890ff !important;
        font-weight: normal !important;
    }
    
    /* 下拉菜单容器（仅针对select） */
    div[data-baseweb="select"] + div[data-baseweb="popover"] {
        border: 1px solid #d9d9d9 !important;
        border-radius: 4px !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15) !important;
        max-height: 400px !important;
        overflow-y: auto !important;
    }
    
    /* 修正输入框帮助提示的样式 */
    div[data-baseweb="input"] + div[data-baseweb="popover"] {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
    }

    div[data-baseweb="input"] + div[data-baseweb="popover"] div {
    line-height: 1.5 !important;
    text-align: left !important;
    padding: 8px 12px !important;
    white-space: pre-wrap !important;
    }

    /* 确保帮助文本正常换行和对齐 */
    div[data-baseweb="popover"] div[role="tooltip"] {
    max-width: 500px !important;
    white-space: pre-wrap !important;
    text-align: left !important;
    line-height: 1.6 !important;
    }
    
    /* 特定针对number_input的提示框 */
    div[data-baseweb="form-control"] + div[data-baseweb="popover"] {
    font-size: 14px !important;
    line-height: 1.6 !important;
    }
    </style>
    """, unsafe_allow_html=True)

    icon_url = "https://raw.githubusercontent.com/Cortez-1/inno/main/cold_storage_design_system/icons/logo.png"
    
    st.markdown(create_header_with_icon("英诺绿能冷库智能化系统", icon_url,
                                        top_offset=-8), unsafe_allow_html=True)

    # 初始化会话状态
    initialize_input_session()
    interface = ColdStorageInputInterface()

    # 添加回调函数
    def on_storage_type_change():
        """当货物类型改变时的回调函数"""
        st.session_state.current_product_options = interface.get_products_by_storage_type(
            st.session_state.storage_type_select
        )
        # 重置产品选择为第一个选项
        if st.session_state.current_product_options:
            st.session_state.current_product_type = st.session_state.current_product_options[0]

    # 检查气象数据是否加载成功
    if interface.weather_data.empty:
        st.markdown('<div class="error-card">', unsafe_allow_html=True)
        st.error("❌ 气象数据加载失败")
        st.write("请确保 `weather_data.json` 文件存在于以下位置之一：")
        st.write("- 当前工作目录")
        st.write("- 与Python文件相同的目录")
        st.write("")
        st.write("文件内容格式应为：")
        st.code("""
    {
      "weather_data": [
        {
          "省份": "北京",
          "城市名称": "北京", 
          "空调干球温度(℃)": 33.5,
          "空调室外计算湿球温度(℃)": 26.4,
          "通风计算相对湿度(%)": 61,
          "夏季大气压力(hPa)": 1000.2
        },
        // ... 更多城市数据
      ]
    }
            """)
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # 项目基本信息
    st.markdown('<h2 class="section-header">🏢 项目基本信息</h2>', unsafe_allow_html=True)

    with st.container():
        col1, col2, col3 = st.columns(3)

        with col1:
            project_name = st.text_input("项目名称", placeholder="例如：XX物流中心冷库项目")
            customer_name = st.text_input("客户名称", placeholder="例如：XX食品有限公司")

        with col2:
            # 省份选择
            selected_province = st.selectbox(
                "项目省份",
                options=interface.provinces,
                index=0 if interface.provinces else None,
                key="province_select"
            )

            # 城市选择（根据省份动态更新）
            cities = interface.get_cities_by_province(selected_province)
            selected_city = st.selectbox(
                "项目城市",
                options=cities,
                index=0 if cities else None,
                key="city_select"
            )

        with col3:
            design_priority = st.selectbox(
                "设计优先级",
                ["成本优化", "能效优先", "可靠性优先", "快速交付", "平衡设计"]
            )
            budget_limit = st.number_input("预算限制(万元)", min_value=10, max_value=5000, value=500, step=50)
            project_deadline = st.date_input("项目期限", value=datetime.now())

    # 显示选择的气象数据
    if selected_province and selected_city:
        weather_info = interface.get_weather_data_by_city(selected_province, selected_city)
        if weather_info is not None:
            st.markdown(f"""
            <div class="weather-info">
                <h4>🌤️ {selected_province} - {selected_city} 气象数据</h4>
                <p><b>夏季干球温度:</b> {weather_info['空调干球温度(℃)']}°C | 
                <b>夏季湿球温度:</b> {weather_info['空调室外计算湿球温度(℃)']}°C</p>
                <p><b>夏季相对湿度:</b> {weather_info['通风计算相对湿度(%)']}% | 
                <p><b>夏季空调日平均温度:</b> {weather_info['夏季空调日平均温度(℃)']}°C</p>
                <b>夏季大气压力:</b> {weather_info['夏季大气压力(hPa)']} hPa</p>
            </div>
            """, unsafe_allow_html=True)

    # 环境参数
    st.markdown('<h2 class="section-header">🌡️ 环境参数</h2>', unsafe_allow_html=True)

    with st.container():
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            # 自动设置夏季最高环境温度为夏季干球温度
            summer_temp_default = 35.0
            if selected_province and selected_city and weather_info is not None:
                summer_temp_default = float(weather_info['空调干球温度(℃)'])

            summer_temp = st.number_input(
                "夏季最高环境温度(°C)",
                min_value=20.0,
                max_value=45.0,
                value=summer_temp_default,
                step=0.1,
                key="summer_temp_input"
            )

        with col2:
            winter_temp_default = -10.0
            winter_temp = st.number_input(
                "冬季最低环境温度(°C)",
                min_value=-30.0,
                max_value=15.0,
                value=winter_temp_default,
                step=1.0,
                key="winter_temp_input"
            )

        with col3:
            # 自动设置相对湿度
            humidity_default = 70
            if selected_province and selected_city and weather_info is not None:
                humidity_default = int(weather_info['通风计算相对湿度(%)'])

            relative_humidity = st.slider(
                "环境相对湿度(%)",
                min_value=30,
                max_value=95,
                value=humidity_default,
                step=1,
                key="humidity_input"
            )

        # 显示其他气象信息（只读）
        if selected_province and selected_city and weather_info is not None:
            col1, col2, col3  = st.columns(3)
            with col1:
                st.text_input(
                    "夏季湿球温度(°C)",
                    value=f"{weather_info['空调室外计算湿球温度(℃)']}",
                    disabled=True
                )
            with col2:
                st.text_input(
                    "夏季空调日平均温度(°C)",
                    value=f"{weather_info['夏季空调日平均温度(℃)']}",
                    disabled=True
                )
            with col3:
                st.text_input(
                    "夏季大气压力(hPa)",
                    value=f"{weather_info['夏季大气压力(hPa)']}",
                    disabled=True
                )

    # 冷间配置
    st.markdown('<h2 class="section-header">❄️ 冷间配置</h2>', unsafe_allow_html=True)

    # 冷间输入表单
    with st.form("room_input_form", clear_on_submit=True):
        st.subheader("➕ 添加冷间")

        col1, col2 = st.columns(2)

        with col1:
            room_name = st.text_input("冷间名称", placeholder="例如：低温冷冻库1")
            col_type_packaging = st.columns([1, 1])  # 两个等宽列

            with col_type_packaging[0]:
                room_type = st.selectbox(
                    "冷间类型",
                    ["冷冻冷藏间", "冷却冷藏间", "操作间"],
                    index=0,  # 默认选择第一个
                )

            with col_type_packaging[1]:
                # 包装材料选择
                packaging_materials = [
                    "木板类",
                    "黄铜",
                    "铁皮",
                    "铝皮",
                    "玻璃容器类",
                    "马粪纸、瓦楞纸类",
                    "黄油纸",
                    "布雷",
                    "竹器类"
                ]

                # 查找"马粪纸、瓦楞纸类"的索引作为默认值
                default_packaging_index = packaging_materials.index(
                    "马粪纸、瓦楞纸类") if "马粪纸、瓦楞纸类" in packaging_materials else 0

                packaging_material = st.selectbox(
                    "包装材料",
                    options=packaging_materials,
                    index=default_packaging_index,
                )

            col1a, col1b, col1c = st.columns(3)
            with col1a:
                room_length = st.number_input("东西长(m)", min_value=5.0, max_value=100.0, value=20.0, step=1.0)
            with col1b:
                room_width = st.number_input("南北长(m)", min_value=5.0, max_value=50.0, value=12.0, step=1.0)
            with col1c:
                room_height = st.number_input("高度(m)", min_value=3.0, max_value=20.0, value=8.0, step=0.5)

            # 创建带分组的产品选择
            product_options_with_groups = []
            for storage_type, products in interface.product_types.items():
                # 添加分隔符（货物类型标签）
                product_options_with_groups.append({
                    'label': f"📦 {storage_type}",
                    'value': f"separator_{storage_type}",
                    'disabled': True
                })
                # 添加具体产品
                for product in products:
                    product_options_with_groups.append({
                        'label': f"    {product}",
                        'value': f"{storage_type}::{product}",
                        'disabled': False
                    })

            # 创建选择框选项
            selectbox_options = []
            option_formats = {}
            default_index = 0

            for i, option in enumerate(product_options_with_groups):
                selectbox_options.append(option['value'])
                # 为选项创建显示标签
                if option['disabled']:
                    # 分组标题 - 灰色不可选
                    option_formats[option['value']] = f"📦 {option['label'][2:]}"
                else:
                    # 具体产品 - 黑色可选
                    option_formats[option['value']] = f"    {option['label'][6:]}"

                # 找到第一个可用的选项作为默认值
                if not option.get('disabled', False) and default_index == 0:
                    default_index = i

            # 使用自定义选择组件
            selected_product = st.selectbox(
                "货物类型 - 具体产品",
                options=[opt['value'] for opt in product_options_with_groups],
                format_func=lambda x: next((opt['label'] for opt in product_options_with_groups if opt['value'] == x),
                                           x),
                index=default_index,
                key="product_type_select"
            )

            # 解析选中的值
            if "::" in selected_product:
                selected_storage_type, selected_product_type = selected_product.split("::")
            else:
                # 如果选择了分隔符，使用第一个可用产品
                for option in product_options_with_groups:
                    if not option.get('disabled', False) and "::" in option['value']:
                        selected_storage_type, selected_product_type = option['value'].split("::")
                        break
                else:
                    selected_storage_type = "肉类"
                    selected_product_type = "猪肉"

        with col2:
            # 根据选择的货物类型显示温度范围建议
            temp_range = interface.storage_types.get(selected_storage_type, {"temp_range": (-25, -18)})['temp_range']

            room_temp = st.number_input(
                "库温(°C)",
                min_value=-40.0,
                max_value=15.0,
                value=float(temp_range[0] if temp_range[0] <= -18 else -18.0),
                step=0.5,
                help=f"建议范围: {temp_range[0]}°C 到 {temp_range[1]}°C"
            )

            incoming_temp = st.number_input(
                "入库温度(°C)",
                min_value=-40.0,
                max_value=30.0,
                value=25.0,
                step=0.5,
                help="""
            入库温度确定原则：

            1. 未经冷却的屠宰鲜肉应取39℃
            2. 已经冷却的鲜肉温度应取4℃
            3. 从外库调入的冻结货物温度应取-10℃～-15℃
            4. 无外库调入的冷库，进入冻结物冷藏间的货物温度，应按该冷库冻结间终止降温时或产品包装后的货物温度确定
            5. 冰鲜鱼虾整理后的温度应取15℃
            6. 鲜鱼虾整理后进入冷加工间的温度，按整理鱼虾用水的水温确定
            7. 鱼虾、水果、蔬菜的进货温度，按冷间生产旺月气温的月平均温度确定
            """
            )

            outgoing_temp = st.number_input(
                "出库温度(°C)",
                min_value=-50.0,
                max_value=50.0,
                value=0.0,
                step=0.5
            )



            col_params1, col_params2 = st.columns(2)

            with col_params1:
                # 降温时间
                cooling_time = st.number_input(
                    "降温时间(小时)",
                    min_value=1,
                    max_value=24,
                    value=24,
                    step=1
                )

            with col_params2:
                # 入库系数
                incoming_coefficient = st.slider(
                    "入库系数(%)",
                    min_value=1,
                    max_value=30,
                    value=5,
                    step=1,
                    help="""
                入库系数说明：

                1. 冷却间或冻结间应按设计冷加工能力计算；
                2. 存放果蔬的冷却物冷藏间，不应大于该间计算吨位的10%计算；
                3. 存放鲜蛋的冷却物冷藏间，不应大于该间计算吨位的5%计算；
                4. 有从外库调入货物的冷库，其冻结物冷藏间每间每日进货质量应按该间计算吨位的5%~15%计算；
                5. 无外库调入货物的冷库，其冻结物冷藏间每间每日进货量可按该间计算吨位的5%~15%计算；
                6. 冻结量大的水产冷库，其冻结物冷藏间的每日进货量可按具体情况确定。

                💡 建议范围：5% - 15%
                        """
                )

        # 新增：冷间各部位温度
        st.markdown("#### 🌡️ 冷间各部位温度")
        col_temp1, col_temp2 = st.columns(2)

        with col_temp1:
            # 垂直方向温度
            st.markdown("**垂直方向**")
            top_temp = st.number_input(
                    "顶部温度(°C)",
                    min_value=-50.0,
                    max_value=50.0,
                    value=room_temp,  # 默认与库温相同
                    step=0.5,
                    key="top_temp_input"
                )
            bottom_temp = st.number_input(
                    "底部温度(°C)",
                    min_value=-50.0,
                    max_value=50.0,
                    value=room_temp,  # 默认与库温相同
                    step=0.5,
                    key="bottom_temp_input"
                )

        with col_temp2:
            # 水平方向温度
            st.markdown("**水平方向**")
            east_temp = st.number_input(
                    "东侧温度(°C)",
                    min_value=-50.0,
                    max_value=50.0,
                    value=room_temp,  # 默认与库温相同
                    step=0.5,
                    key="east_temp_input"
                )
            south_temp = st.number_input(
                    "南侧温度(°C)",
                    min_value=-50.0,
                    max_value=50.0,
                    value=room_temp,  # 默认与库温相同
                    step=0.5,
                    key="south_temp_input"
                )
            west_temp = st.number_input(
                    "西侧温度(°C)",
                    min_value=-50.0,
                    max_value=50.0,
                    value=room_temp,  # 默认与库温相同
                    step=0.5,
                    key="west_temp_input"
                )
            north_temp = st.number_input(
                    "北侧温度(°C)",
                    min_value=-50.0,
                    max_value=50.0,
                    value=room_temp,  # 默认与库温相同
                    step=0.5,
                    key="north_temp_input"
                )

        # 高级参数（可折叠）
        with st.expander("高级参数配置"):
            col_adv1, col_adv2, col_adv3 = st.columns(3)

            with col_adv1:
                door_count = st.number_input("门数量", min_value=1, max_value=10, value=2)
                door_size = st.selectbox("门尺寸", ["小(0.8x1.8m)", "中(1.2x2.0m)", "大(1.5x2.2m)"])
                insulation_thickness = st.slider("保温厚度(mm)", min_value=100, max_value=300, value=150, step=10)

            with col_adv2:
                people_count = st.number_input("工作人员数量", min_value=0, max_value=20, value=2)
                working_hours = st.slider("每日工作时间(小时)", min_value=0, max_value=24, value=8, step=1)
                lighting_power = st.number_input("照明功率(W/m²)", min_value=5, max_value=30, value=10, step=1)

            with col_adv3:
                defrost_method = st.selectbox("除霜方式", ["电热除霜", "热气除霜", "水除霜", "自然除霜"])
                defrost_frequency = st.slider("除霜频率(次/天)", min_value=0, max_value=10, value=2, step=1)
                special_requirements = st.text_area("特殊要求", placeholder="例如：湿度控制、气调要求等")

        # 提交按钮
        submitted = st.form_submit_button("✅ 添加冷间")

        if submitted:
            if room_name.strip() == "":
                st.error("请输入冷间名称")
            else:
                # 检查冷间名称是否重复
                existing_names = [room.get('room_name', '') for room in st.session_state.rooms_data]
                if room_name in existing_names:
                    st.error("冷间名称已存在，请使用不同的名称")
                else:
                    new_room = {
                        'room_name': room_name,
                        'room_type': room_type,
                        'length': room_length,
                        'width': room_width,
                        'height': room_height,
                        'temperature': room_temp,
                        'incoming_temp': incoming_temp,
                        'outgoing_temp': outgoing_temp,
                        'incoming_coefficient': incoming_coefficient,
                        'cooling_time': cooling_time,
                        'top_temp': top_temp,
                        'bottom_temp': bottom_temp,
                        'east_temp': east_temp,
                        'south_temp': south_temp,
                        'west_temp': west_temp,
                        'north_temp': north_temp,
                        'storage_type': selected_storage_type,  # 从产品选择中获取
                        'product_type': selected_product_type,  # 从产品选择中获取
                        'door_count': door_count,
                        'door_size': door_size,
                        'insulation_thickness': insulation_thickness,
                        'people_count': people_count,
                        'working_hours': working_hours,
                        'lighting_power': lighting_power,
                        'defrost_method': defrost_method,
                        'defrost_frequency': defrost_frequency,
                        'special_requirements': special_requirements,
                        'volume': room_length * room_width * room_height,
                        'surface_area': 2 * (
                                    room_length * room_width + room_length * room_height + room_width * room_height)
                    }

                    st.session_state.rooms_data.append(new_room)
                    st.success(f"成功添加冷间: {room_name}")
                    st.rerun()

    # 显示已添加的冷间
    if st.session_state.rooms_data:
        st.markdown(f'<h3 class="section-header">📋 已添加冷间 ({len(st.session_state.rooms_data)}个)</h3>',
                    unsafe_allow_html=True)

        # 冷间概览
        rooms_df = pd.DataFrame(st.session_state.rooms_data)

        # 显示摘要表格
        summary_cols = ['room_name', 'room_type', 'length', 'width', 'height', 'temperature', 'storage_type', 'volume']
        display_df = rooms_df[summary_cols].copy()
        display_df.columns = ['冷间名称', '冷间类型', '长度(m)', '宽度(m)', '高度(m)', '温度(°C)', '货物类型', '体积(m³)']

        st.dataframe(display_df, use_container_width=True)

        # 冷间详细列表
        for i, room in enumerate(st.session_state.rooms_data):
            with st.container():
                col1, col2, col3 = st.columns([3, 2, 1])

                with col1:
                    st.markdown(f"""
                    <div class="room-card">
                    <h4>🏢 {room['room_name']} - {room.get('room_type', '冷冻冷藏间')}</h4>
                    <p><b>尺寸:</b> {room['length']}×{room['width']}×{room['height']} m | 
                    <b>体积:</b> {room['volume']:.1f} m³ | 
                    <b>温度:</b> {room['temperature']}°C</p>
                    <p><b>货物:</b> {room['storage_type']} - {room['product_type']} | 
                    <p><b>入库温度:</b> {room['incoming_temp']}°C | 
                    <b>出货温度:</b> {room['outgoing_temp']}°C | 
                    <b>降温时间:</b> {room['cooling_time']}h</p>
                    </div>
                    """, unsafe_allow_html=True)

                with col2:
                    # 温度合规性检查
                    expected_range = interface.storage_types[room['storage_type']]['temp_range']
                    if expected_range[0] <= room['temperature'] <= expected_range[1]:
                        st.success("✅ 温度合规")
                    else:
                        st.warning(f"⚠️ 温度建议: {expected_range[0]}°C ~ {expected_range[1]}°C")

                    # 体积分类
                    if room['volume'] < 500:
                        size_category = "小型"
                    elif room['volume'] < 2000:
                        size_category = "中型"
                    else:
                        size_category = "大型"
                    st.info(f"📦 {size_category}冷间")

                with col3:
                    col3a, col3b = st.columns(2)
                    with col3a:
                        if st.button("✏️", key=f"edit_{i}", help="编辑"):
                            st.session_state.current_room_editing = i
                            st.rerun()
                    with col3b:
                        if st.button("🗑️", key=f"delete_{i}", help="删除"):
                            st.session_state.rooms_data.pop(i)
                            st.rerun()

        # 项目统计
        st.markdown('<div class="summary-card">', unsafe_allow_html=True)
        st.subheader("📊 项目统计")

        col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)

        total_volume = sum(room['volume'] for room in st.session_state.rooms_data)
        total_area = sum(room['surface_area'] for room in st.session_state.rooms_data)
        temp_ranges = [room['temperature'] for room in st.session_state.rooms_data]

        with col_stat1:
            st.metric("冷间总数", len(st.session_state.rooms_data))
            st.metric("低温冷间(≤-18°C)", len([t for t in temp_ranges if t <= -18]))

        with col_stat2:
            st.metric("总体积", f"{total_volume:.0f} m³")
            st.metric("高温冷间(>0°C)", len([t for t in temp_ranges if t > 0]))

        with col_stat3:
            st.metric("总表面积", f"{total_area:.0f} m²")
            st.metric("温度范围", f"{min(temp_ranges)}°C ~ {max(temp_ranges)}°C")

        with col_stat4:
            st.metric("设计优先级", design_priority)

        st.markdown('</div>', unsafe_allow_html=True)

        # 温度分布图
        if len(st.session_state.rooms_data) > 1:
            st.subheader("🌡️ 温度分布")

            temp_data = []
            for room in st.session_state.rooms_data:
                temp_data.append({
                    '冷间': room['room_name'],
                    '温度(°C)': room['temperature'],
                    '体积(m³)': room['volume'],
                    '类型': room['storage_type']
                })

            temp_df = pd.DataFrame(temp_data)

            import plotly.express as px
            fig = px.scatter(temp_df, x='冷间', y='温度(°C)', size='体积(m³)',
                             color='类型', title='各冷间温度分布')
            st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("👆 请在上面添加冷间配置")

    # 编辑冷间功能
    if st.session_state.current_room_editing is not None:
        edit_index = st.session_state.current_room_editing
        room_to_edit = st.session_state.rooms_data[edit_index]

        st.markdown("---")
        st.subheader(f"✏️ 编辑冷间: {room_to_edit['room_name']}")

        with st.form("edit_room_form"):
            col_edit1, col_edit2 = st.columns(2)

            with col_edit1:
                edited_name = st.text_input("冷间名称", value=room_to_edit['room_name'])
                col_edit_type_packaging = st.columns([1, 1])  # 两个等宽列

                with col_edit_type_packaging[0]:
                    edited_room_type = st.selectbox(
                        "冷间类型",
                        ["冷冻冷藏间", "冷却冷藏间", "操作间"],
                        index=["冷冻冷藏间", "冷却冷藏间", "操作间"].index(room_to_edit.get('room_type', '冷冻冷藏间')),
                        key="edit_room_type"
                    )

                with col_edit_type_packaging[1]:
                    # 包装材料选择（编辑模式）
                    edit_packaging_materials = [
                        "木板类",
                        "黄铜",
                        "铁皮",
                        "铝皮",
                        "玻璃容器类",
                        "马粪纸、瓦楞纸类",
                        "黄油纸",
                        "布雷",
                        "竹器类"
                    ]

                    # 查找当前包装材料的索引
                    current_packaging_index = edit_packaging_materials.index(
                        room_to_edit.get('packaging_material', '马粪纸、瓦楞纸类')
                    ) if room_to_edit.get(
                        'packaging_material') in edit_packaging_materials else edit_packaging_materials.index(
                        "马粪纸、瓦楞纸类")

                    edited_packaging_material = st.selectbox(
                        "包装材料",
                        options=edit_packaging_materials,
                        index=current_packaging_index,
                        key="edit_packaging_material"
                    )

                col_edit1a, col_edit1b, col_edit1c = st.columns(3)
                with col_edit1a:
                    edited_length = st.number_input("东西长(m)", value=room_to_edit['length'], key="edit_length")
                with col_edit1b:
                    edited_width = st.number_input("南北长(m)", value=room_to_edit['width'], key="edit_width")
                with col_edit1c:
                    edited_height = st.number_input("高度(m)", value=room_to_edit['height'], key="edit_height")

                # 创建带分组的产品选择（编辑模式）
                edit_product_options_with_groups = []
                current_value = f"{room_to_edit['storage_type']}::{room_to_edit['product_type']}"
                current_index = 0

                for i, (storage_type, products) in enumerate(interface.product_types.items()):
                    # 添加分隔符（货物类型标签）- 用灰色显示
                    edit_product_options_with_groups.append({
                        'label': f"📦 {storage_type}",
                        'value': f"separator_{storage_type}",
                        'disabled': True
                    })
                    # 添加具体产品
                    for j, product in enumerate(products):
                        option_value = f"{storage_type}::{product}"
                        edit_product_options_with_groups.append({
                            'label': f"   📋 {product}",
                            'value': option_value,
                            'disabled': False
                        })
                        if option_value == current_value:
                            current_index = len(edit_product_options_with_groups) - 1

                # 产品选择
                edited_product = st.selectbox(
                    "货物类型 - 具体产品",
                    options=[opt['value'] for opt in edit_product_options_with_groups],
                    format_func=lambda x: next(
                        (opt['label'] for opt in edit_product_options_with_groups if opt['value'] == x), x),
                    index=current_index,
                    key="edit_product_type_select"
                )

                # 解析选中的值
                if "::" in edited_product:
                    edited_storage_type, edited_product_type = edited_product.split("::")
                else:
                    edited_storage_type = room_to_edit['storage_type']
                    edited_product_type = room_to_edit['product_type']

            with col_edit2:
                temp_range = interface.storage_types.get(edited_storage_type, {"temp_range": (-25, -18)})['temp_range']

                edited_temp = st.number_input("库温(°C)", value=room_to_edit['temperature'], key="edit_temp")
                edited_incoming_temp = st.number_input(
                    "入库温度(°C)",
                    value=room_to_edit['incoming_temp'],
                    key="edit_incoming",
                    help="""
                入库温度确定原则：

                1. 未经冷却的屠宰鲜肉应取39℃
                2. 已经冷却的鲜肉温度应取4℃
                3. 从外库调入的冻结货物温度应取-10℃～-15℃
                4. 无外库调入的冷库，进入冻结物冷藏间的货物温度，应按该冷库冻结间终止降温时或产品包装后的货物温度确定
                5. 冰鲜鱼虾整理后的温度应取15℃
                6. 鲜鱼虾整理后进入冷加工间的温度，按整理鱼虾用水的水温确定
                7. 鱼虾、水果、蔬菜的进货温度，按冷间生产旺月气温的月平均温度确定
                """
                )
                edited_outgoing_temp = st.number_input("出库温度(°C)", value=room_to_edit['outgoing_temp'],
                                                       key="edit_outgoing")


            col_edit_params1, col_edit_params2 = st.columns(2)

            with col_edit_params1:
                edited_cooling_time = st.number_input(
                    "降温时间(小时)",
                    min_value=1,
                    max_value=24,
                    value=room_to_edit['cooling_time'],
                    step=1,
                    key="edit_cooling_time"
                )

            with col_edit_params2:
                edited_incoming_coefficient = st.slider(
                    "入库系数(%)",
                    min_value=1,
                    max_value=30,
                    value=room_to_edit['incoming_coefficient'],
                    step=1,
                    key="edit_incoming_coefficient",
                    help="""
                入库系数说明：

                1. 冷却间或冻结间应按设计冷加工能力计算；
                2. 存放果蔬的冷却物冷藏间，不应大于该间计算吨位的10%计算；
                3. 存放鲜蛋的冷却物冷藏间，不应大于该间计算吨位的5%计算；
                4. 有从外库调入货物的冷库，其冻结物冷藏间每间每日进货质量应按该间计算吨位的5%~15%计算；
                5. 无外库调入货物的冷库，其冻结物冷藏间每间每日进货量可按该间计算吨位的5%~15%计算；
                6. 冻结量大的水产冷库，其冻结物冷藏间的每日进货量可按具体情况确定。

                💡 建议范围：5% - 15%

                """
                )

            # 冷间各部位温度
            st.markdown("#### 🌡️ 冷间各部位温度")
            col_edit_temp1, col_edit_temp2 = st.columns(2)

            with col_edit_temp1:
                st.markdown("**垂直方向**")
                edited_top_temp = st.number_input(
                    "顶部温度(°C)",
                    min_value=-50.0,
                    max_value=50.0,
                    value=room_to_edit['top_temp'],
                    step=0.5,
                    key="edit_top_temp"
                )
                edited_bottom_temp = st.number_input(
                    "底部温度(°C)",
                    min_value=-50.0,
                    max_value=50.0,
                    value=room_to_edit['bottom_temp'],
                    step=0.5,
                    key="edit_bottom_temp"
                )

            with col_edit_temp2:
                st.markdown("**水平方向**")
                edited_east_temp = st.number_input(
                    "东侧温度(°C)",
                    min_value=-50.0,
                    max_value=50.0,
                    value=room_to_edit['east_temp'],
                    step=0.5,
                    key="edit_east_temp"
                )
                edited_south_temp = st.number_input(
                    "南侧温度(°C)",
                    min_value=-50.0,
                    max_value=50.0,
                    value=room_to_edit['south_temp'],
                    step=0.5,
                    key="edit_south_temp"
                )
                edited_west_temp = st.number_input(
                    "西侧温度(°C)",
                    min_value=-50.0,
                    max_value=50.0,
                    value=room_to_edit['west_temp'],
                    step=0.5,
                    key="edit_west_temp"
                )
                edited_north_temp = st.number_input(
                    "北侧温度(°C)",
                    min_value=-50.0,
                    max_value=50.0,
                    value=room_to_edit['north_temp'],
                    step=0.5,
                    key="edit_north_temp"
                )

            col_save, col_cancel = st.columns(2)
            with col_save:
                save_clicked = st.form_submit_button("💾 保存修改")
            with col_cancel:
                cancel_clicked = st.form_submit_button("❌ 取消")

            if save_clicked:
                st.session_state.rooms_data[edit_index].update({
                    'room_name': edited_name,
                    'room_type': edited_room_type,
                    'length': edited_length,
                    'width': edited_width,
                    'height': edited_height,
                    'temperature': edited_temp,
                    'incoming_temp': edited_incoming_temp,
                    'outgoing_temp': edited_outgoing_temp,
                    'incoming_coefficient': edited_incoming_coefficient,
                    'cooling_time': edited_cooling_time,
                    'top_temp': edited_top_temp,
                    'bottom_temp': edited_bottom_temp,
                    'east_temp': edited_east_temp,
                    'south_temp': edited_south_temp,
                    'west_temp': edited_west_temp,
                    'north_temp': edited_north_temp,
                    'storage_type': edited_storage_type,
                    'product_type': edited_product_type,
                    'volume': edited_length * edited_width * edited_height,
                    'surface_area': 2 * (
                                edited_length * edited_width + edited_length * edited_height + edited_width * edited_height)
                })
                st.session_state.current_room_editing = None
                st.success("修改已保存")
                st.rerun()

            if cancel_clicked:
                st.session_state.current_room_editing = None
                st.rerun()

    # 导出配置
    if st.session_state.rooms_data:
        st.markdown("---")
        st.markdown('<h2 class="section-header">💾 导出配置</h2>', unsafe_allow_html=True)

        col_export1, col_export2, col_export3, col_export4 = st.columns(4)

        with col_export1:
            if st.button("💾 保存项目", use_container_width=True, type="primary"):
                # 检查是否有数据
                if not st.session_state.rooms_data:
                    st.error("请先添加冷间配置")
                elif not project_name:
                    st.error("请输入项目名称")
                elif not customer_name:
                    st.error("请输入客户名称")
                else:

                    # 保存项目信息
                    project_location = f"{selected_province} - {selected_city}"
                    project_info = {
                        'project_name': project_name,
                        'project_location': project_location,
                        'customer_name': customer_name,
                        'design_priority': design_priority,
                        'budget_limit': budget_limit,
                        'project_deadline': project_deadline.isoformat(),
                        'summer_temp': summer_temp,
                        'winter_temp': winter_temp,
                        'relative_humidity': relative_humidity,
                        'total_rooms': len(st.session_state.rooms_data),
                        'total_volume': sum(room['volume'] for room in st.session_state.rooms_data),
                        'total_area': sum(room['surface_area'] for room in st.session_state.rooms_data),
                        'save_time': datetime.now().isoformat()
                    }

                    st.session_state.project_info = project_info

                    # 调用保存方法
                    saved_file = interface.save_project_data(project_info, st.session_state.rooms_data)
                    if saved_file:
                        st.success(f"✅ 项目已保存到: {saved_file}")
                        st.balloons()
                    else:
                        st.error("保存失败")

        with col_export2:
            if st.button("📄 导出配置JSON", use_container_width=True):
                config_data = {
                    'project_info': st.session_state.project_info,
                    'rooms_data': st.session_state.rooms_data
                }

                st.download_button(
                    label="下载JSON配置",
                    data=json.dumps(config_data, ensure_ascii=False, indent=2),
                    file_name=f"cold_storage_config_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                    mime="application/json"
                )

        with col_export3:
            if st.button("📊 导出Excel表格", use_container_width=True):
                # 创建Excel文件
                output = create_excel_export(st.session_state.project_info, st.session_state.rooms_data)
                st.download_button(
                    label="下载Excel表格",
                    data=output,
                    file_name=f"cold_storage_data_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

        with col_export4:
            if st.button("🚀 开始系统设计", type="primary", use_container_width=True):
                if 'project_info' in st.session_state and st.session_state.project_info:
                    # 使用之前保存的项目信息
                    project_info = st.session_state.project_info
                    st.info("✅ 使用已保存的项目信息")
                else:
                    if not project_name or not customer_name:
                        st.error("❌ 请输入项目名称和客户名称")
                        return

                    if not st.session_state.rooms_data:
                        st.error("❌ 请至少添加一个冷间")
                        return

                    project_location = f"{selected_province} - {selected_city}"
                    project_info = {
                            'project_name': project_name,
                            'project_location': project_location,
                            'customer_name': customer_name,
                            'design_priority': design_priority,
                            'budget_limit': budget_limit,
                            'project_deadline': project_deadline.isoformat(),
                            'summer_temp': summer_temp,
                            'winter_temp': winter_temp,
                            'relative_humidity': relative_humidity,
                            'total_rooms': len(st.session_state.rooms_data),
                            'total_volume': total_volume if 'total_volume' in locals() else sum(
                                room['volume'] for room in st.session_state.rooms_data),
                            'total_area': total_area if 'total_area' in locals() else sum(
                                room['surface_area'] for room in st.session_state.rooms_data),
                            'save_time': datetime.now().isoformat()
                    }

                    # 自动保存
                    interface.save_project_data(project_info, st.session_state.rooms_data)

                # 传递数据到设计系统
                st.session_state.design_data = {
                    'project_info': st.session_state.project_info,
                    'rooms_data': st.session_state.rooms_data
                }

                # 保存到文件缓存
                try:
                    from data_sharing import DataSharing
                    data_sharing = DataSharing()
                    data_sharing.save_design_data(project_info, st.session_state.rooms_data)
                except ImportError:
                    st.warning("数据共享模块不可用，仅保存到会话状态")

                st.success("配置已保存，正在跳转到系统设计...")

                # 使用新的导航方式
                st.switch_page("pages/2_🏭_系统设计.py")


def create_excel_export(project_info, rooms_data):
    """创建Excel导出文件"""
    from io import BytesIO
    import pandas as pd

    output = BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # 项目概况
        project_df = pd.DataFrame([project_info])
        project_df.to_excel(writer, sheet_name='项目概况', index=False)

        # 冷间数据
        rooms_export = []
        for room in rooms_data:
            room_export = room.copy()
            # 移除计算字段
            room_export.pop('volume', None)
            room_export.pop('surface_area', None)
            rooms_export.append(room_export)

        rooms_df = pd.DataFrame(rooms_export)
        rooms_df.to_excel(writer, sheet_name='冷间配置', index=False)

        # 统计汇总
        summary_data = {
            '统计项': ['冷间总数', '总体积(m³)', '总表面积(m²)', '温度范围(°C)', '平均周转率(%)'],
            '数值': [
                len(rooms_data),
                sum(room['volume'] for room in rooms_data),
                sum(room['surface_area'] for room in rooms_data),
                f"{min(room['temperature'] for room in rooms_data)} ~ {max(room['temperature'] for room in rooms_data)}",
                f"{np.mean([room['daily_turnover'] for room in rooms_data]):.1f}"
            ]
        }
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='统计汇总', index=False)

    return output.getvalue()


if __name__ == "__main__":

    main()


