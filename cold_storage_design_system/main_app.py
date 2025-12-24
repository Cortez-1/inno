# main_app.py
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import json
import sys
import os
from typing import Dict, List, Any

# 添加自定义模块路径
sys.path.append(os.path.dirname(__file__))

from data_manager import DataManager
from custom_components import DynamicSelectComponent

# 页面配置
st.set_page_config(
    page_title="英诺绿能冷库智能化系统",
    page_icon="❄️",
    layout="wide",
    initial_sidebar_state="expanded"
)

class ColdStorageApp:
    """冷库应用主类"""
    
    def __init__(self):
        self.data_manager = DataManager()
        self.component = DynamicSelectComponent()
        self.initialize_session_state()
    
    def initialize_session_state(self):
        """初始化会话状态"""
        # 应用状态
        if 'app_initialized' not in st.session_state:
            st.session_state.app_initialized = True
            st.session_state.rooms_data = []
            st.session_state.project_info = {}
            st.session_state.current_room_editing = None
        
        # 自定义组件状态
        if 'component_state' not in st.session_state:
            component_data = self.data_manager.get_component_data()
            st.session_state.component_state = {
                'storage_type': '冷冻食品',  # 直接设置默认值，不使用get()
                'product_type': '猪肉',     # 直接设置默认值
                'last_update': '从未',
                'component_ready': False
            }
        
        # 组件数据
        if 'component_data' not in st.session_state:
            st.session_state.component_data = self.data_manager.get_component_data()
    
    def render_header(self):
        """渲染页面头部"""
        st.markdown("""
        <style>
        .main-header {
            font-size: 2.5rem;
            color: #1f77b4;
            text-align: center;
            margin-bottom: 2rem;
            padding: 1rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: bold;
        }
        .section-header {
            font-size: 1.5rem;
            color: #2e86ab;
            border-bottom: 2px solid #2e86ab;
            padding-bottom: 0.5rem;
            margin-top: 2rem;
        }
        .success-box {
            background: #d1fae5;
            padding: 1rem;
            border-radius: 8px;
            border-left: 4px solid #10b981;
            margin: 1rem 0;
        }
        </style>
        """, unsafe_allow_html=True)
        
        st.markdown('<h1 class="main-header">🏭 英诺绿能冷库智能化系统</h1>', unsafe_allow_html=True)
    
    def handle_component_updates(self, component_value):
        """处理自定义组件的更新"""
        if component_value and component_value.get('action') == 'selection_updated':
            new_storage_type = component_value.get('storage_type', '')
            new_product_type = component_value.get('product_type', '')
            timestamp = component_value.get('timestamp', '未知时间')
            
            # 更新会话状态
            st.session_state.component_state.update({
                'storage_type': new_storage_type,
                'product_type': new_product_type,
                'last_update': timestamp,
                'component_ready': True
            })
            
            # 显示成功消息
            st.success(f"✅ 货物配置已更新: **{new_storage_type}** - **{new_product_type}**")
            
            # 重新运行以更新界面
            st.rerun()
    
    def render_product_selection(self):
        """渲染产品选择区域"""
        st.markdown('<h3 class="section-header">📦 货物配置</h3>', unsafe_allow_html=True)

        # 显示当前选择状态 - 确保使用正确的session_state键
        current_selection = st.session_state.component_state
        storage_type = current_selection.get('storage_type', '冷冻食品')
        product_type = current_selection.get('product_type', '猪肉')
        last_update = current_selection.get('last_update', '从未')

        st.info(f"""
            **当前货物配置:**
            - 🏷️ 货物类型: **{storage_type}**
            - 📋 具体产品: **{product_type}**
            - ⏰ 最后更新: {last_update}
            """)
        
        # 渲染自定义组件
        st.markdown("#### 动态选择器")
        component_value = self.component.create(
            st.session_state.component_data,
            st.session_state.component_state
        )
        
        # 处理组件更新
        self.handle_component_updates(component_value)
    
    def render_room_form(self):
        """渲染冷间配置表单"""
        st.markdown('<h3 class="section-header">➕ 添加冷间</h3>', unsafe_allow_html=True)
        
        with st.form("room_input_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                room_name = st.text_input(
                    "冷间名称", 
                    placeholder="例如：低温冷冻库1",
                    help="请输入唯一的冷间名称"
                )
                
                # 显示当前货物配置（只读）
                current_selection = st.session_state.component_state
                storage_type = current_selection.get('storage_type', '冷冻食品')
                product_type = current_selection.get('product_type', '猪肉')

                st.text_input(
                    "货物类型", 
                    value=f"{storage_type} - {product_type}",
                    disabled=True,
                    help="当前选择的货物配置"
                )
                
                col1a, col1b, col1c = st.columns(3)
                with col1a:
                    room_length = st.number_input("东西长(m)", min_value=5.0, max_value=100.0, value=20.0, step=1.0)
                with col1b:
                    room_width = st.number_input("南北长(m)", min_value=5.0, max_value=50.0, value=12.0, step=1.0)
                with col1c:
                    room_height = st.number_input("高度(m)", min_value=3.0, max_value=20.0, value=8.0, step=0.5)

            with col2:
                # 获取当前存储类型的温度范围
                storage_type = current_selection['storage_type']
                temp_range = self.data_manager.storage_types[storage_type]['temp_range']
                
                room_temp = st.number_input(
                    "库温(°C)",
                    min_value=-40.0,
                    max_value=15.0,
                    value=float(temp_range[0]),
                    step=1.0,
                    help=f"建议范围: {temp_range[0]}°C 到 {temp_range[1]}°C"
                )
                
                incoming_temp = st.number_input(
                    "入库温度(°C)",
                    min_value=-40.0,
                    max_value=30.0,
                    value=25.0,
                    step=1.0,
                    help="货物入库时的温度"
                )

                daily_turnover = st.slider(
                    "日周转率(%)", 
                    min_value=1, 
                    max_value=50, 
                    value=10, 
                    step=1,
                    help="每日货物周转的百分比"
                )
            
            # 高级参数
            with st.expander("⚙️ 高级参数配置", expanded=False):
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
            col_submit, col_clear = st.columns(2)
            with col_submit:
                submitted = st.form_submit_button(
                    "✅ 添加冷间", 
                    use_container_width=True,
                    type="primary"
                )
            with col_clear:
                clear_clicked = st.form_submit_button(
                    "🗑️ 清空表单", 
                    use_container_width=True
                )
            
            if submitted:
                self.handle_add_room(
                    room_name, room_length, room_width, room_height,
                    room_temp, incoming_temp, daily_turnover,
                    door_count, door_size, insulation_thickness,
                    people_count, working_hours, lighting_power,
                    defrost_method, defrost_frequency, special_requirements
                )
            
            if clear_clicked:
                st.info("表单已清空，可以重新填写")
                st.rerun()
    
    def handle_add_room(self, room_name, length, width, height, temperature, 
                       incoming_temp, daily_turnover, door_count, door_size, 
                       insulation_thickness, people_count, working_hours, 
                       lighting_power, defrost_method, defrost_frequency, 
                       special_requirements):
        """处理添加冷间逻辑"""
        
        if room_name.strip() == "":
            st.error("❌ 请输入冷间名称")
            return
        
        # 检查冷间名称是否重复
        existing_names = [room.get('room_name', '') for room in st.session_state.rooms_data]
        if room_name in existing_names:
            st.error("❌ 冷间名称已存在，请使用不同的名称")
            return
        
        # 获取当前货物配置
        current_selection = st.session_state.component_state
        
        # 创建新冷间
        new_room = {
            'room_name': room_name,
            'length': length,
            'width': width,
            'height': height,
            'temperature': temperature,
            'incoming_temp': incoming_temp,
            'storage_type': current_selection['storage_type'],
            'product_type': current_selection['product_type'],
            'daily_turnover': daily_turnover,
            'door_count': door_count,
            'door_size': door_size,
            'insulation_thickness': insulation_thickness,
            'people_count': people_count,
            'working_hours': working_hours,
            'lighting_power': lighting_power,
            'defrost_method': defrost_method,
            'defrost_frequency': defrost_frequency,
            'special_requirements': special_requirements,
            'volume': length * width * height,
            'surface_area': 2 * (length * width + length * height + width * height),
            'created_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # 添加到数据列表
        st.session_state.rooms_data.append(new_room)
        
        st.success(f"✅ 成功添加冷间: **{room_name}**")
        st.balloons()
        
        # 重新运行以更新界面
        st.rerun()
    
    def render_rooms_list(self):
        """渲染已添加的冷间列表"""
        if not st.session_state.rooms_data:
            return
        
        st.markdown('<h3 class="section-header">📋 已添加冷间</h3>', unsafe_allow_html=True)
        
        # 创建数据框显示
        rooms_df = pd.DataFrame(st.session_state.rooms_data)
        display_columns = ['room_name', 'length', 'width', 'height', 'temperature', 
                          'storage_type', 'product_type', 'volume']
        
        display_df = rooms_df[display_columns].copy()
        display_df.columns = ['冷间名称', '长度(m)', '宽度(m)', '高度(m)', '温度(°C)', 
                             '货物类型', '具体产品', '体积(m³)']
        
        st.dataframe(display_df, use_container_width=True)
        
        # 显示统计信息
        total_volume = sum(room['volume'] for room in st.session_state.rooms_data)
        total_rooms = len(st.session_state.rooms_data)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("冷间总数", total_rooms)
        with col2:
            st.metric("总体积", f"{total_volume:.0f} m³")
        with col3:
            avg_temp = np.mean([room['temperature'] for room in st.session_state.rooms_data])
            st.metric("平均温度", f"{avg_temp:.1f}°C")
    
    def run(self):
        """运行主应用"""
        self.render_header()
        
        # 主内容区域
        tab1, tab2, tab3 = st.tabs(["🚀 冷间配置", "📊 数据查看", "⚙️ 系统设置"])
        
        with tab1:
            self.render_product_selection()
            self.render_room_form()
            self.render_rooms_list()
        
        with tab2:
            self.render_data_view()
        
        with tab3:
            self.render_system_settings()
    
    def render_data_view(self):
        """渲染数据查看标签页"""
        st.markdown('<h3 class="section-header">📊 数据统计与分析</h3>', unsafe_allow_html=True)
        
        if not st.session_state.rooms_data:
            st.info("暂无冷间数据，请先在冷间配置标签页添加冷间")
            return
        
        # 数据统计
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_volume = sum(room['volume'] for room in st.session_state.rooms_data)
            st.metric("总体积", f"{total_volume:.0f} m³")
        
        with col2:
            total_rooms = len(st.session_state.rooms_data)
            st.metric("冷间数量", total_rooms)
        
        with col3:
            low_temp_rooms = len([r for r in st.session_state.rooms_data if r['temperature'] <= -18])
            st.metric("低温冷间", low_temp_rooms)
        
        with col4:
            high_temp_rooms = len([r for r in st.session_state.rooms_data if r['temperature'] > 0])
            st.metric("高温冷间", high_temp_rooms)
        
        # 温度分布图
        st.subheader("🌡️ 温度分布")
        if len(st.session_state.rooms_data) > 1:
            try:
                import plotly.express as px
                
                plot_data = []
                for room in st.session_state.rooms_data:
                    plot_data.append({
                        '冷间': room['room_name'],
                        '温度(°C)': room['temperature'],
                        '体积(m³)': room['volume'],
                        '货物类型': room['storage_type']
                    })
                
                plot_df = pd.DataFrame(plot_data)
                fig = px.scatter(plot_df, x='冷间', y='温度(°C)', size='体积(m³)',
                               color='货物类型', title='各冷间温度分布',
                               hover_data=['体积(m³)'])
                
                st.plotly_chart(fig, use_container_width=True)
            except ImportError:
                st.warning("请安装plotly来显示图表: pip install plotly")
    
    def render_system_settings(self):
        """渲染系统设置标签页"""
        st.markdown('<h3 class="section-header">⚙️ 系统设置</h3>', unsafe_allow_html=True)
        
        st.subheader("🔧 自定义组件状态")
        
        # 显示组件状态信息
        component_state = st.session_state.component_state
        st.json(component_state)
        
        # 调试信息
        with st.expander("🔍 调试信息"):
            st.write("会话状态键:", list(st.session_state.keys()))
            st.write("冷间数据数量:", len(st.session_state.rooms_data))
            
            if st.button("🔄 重置组件状态"):
                st.session_state.component_state['component_ready'] = False
                st.rerun()
            
            if st.button("🗑️ 清空所有数据"):
                st.session_state.rooms_data = []
                st.session_state.component_state.update({
                    'storage_type': "冷冻食品",
                    'product_type': "猪肉",
                    'last_update': '重置时间',
                    'component_ready': False
                })
                st.rerun()

def main():
    """主函数"""
    try:
        app = ColdStorageApp()
        app.run()
    except Exception as e:
        st.error(f"应用运行出错: {e}")
        st.info("请检查所有依赖是否已正确安装")

if __name__ == "__main__":
    main()