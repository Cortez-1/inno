# pages/3_📚_项目历史.py
import streamlit as st
import pandas as pd
from datetime import datetime
import os
import json
import pickle

st.set_page_config(
    page_title="项目历史记录",
    layout="wide"
)

st.title("📚 项目历史记录")

# 加载所有保存的项目
def load_all_projects():
    projects = []
    
    # 检查保存目录
    save_dirs = ["saved_projects", "autosave_data"]
    
    for save_dir in save_dirs:
        if os.path.exists(save_dir):
            for filename in os.listdir(save_dir):
                filepath = os.path.join(save_dir, filename)
                try:
                    if filename.endswith('.pkl'):
                        with open(filepath, 'rb') as f:
                            data = pickle.load(f)
                    elif filename.endswith('.json'):
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                    else:
                        continue
                    
                    projects.append({
                        'filename': filename,
                        'filepath': filepath,
                        'project_name': data.get('project_info', {}).get('project_name', '未命名'),
                        'customer': data.get('project_info', {}).get('customer_name', '未知'),
                        'save_time': data.get('last_saved') or data.get('save_time', ''),
                        'rooms_count': len(data.get('rooms_data', [])),
                        'data': data
                    })
                except Exception as e:
                    st.warning(f"加载文件失败 {filename}: {e}")
    
    # 按时间排序
    projects.sort(key=lambda x: x.get('save_time', ''), reverse=True)
    return projects

# 显示项目列表
projects = load_all_projects()

if projects:
    st.success(f"找到 {len(projects)} 个保存的项目")
    
    # 创建数据表格
    project_data = []
    for i, proj in enumerate(projects):
        save_time = proj['save_time']
        if isinstance(save_time, str) and len(save_time) > 10:
            save_time = save_time[:19].replace('T', ' ')
        
        project_data.append({
            '序号': i + 1,
            '项目名称': proj['project_name'],
            '客户': proj['customer'],
            '冷间数量': proj['rooms_count'],
            '保存时间': save_time,
            '文件': proj['filename']
        })
    
    df = pd.DataFrame(project_data)
    st.dataframe(df, use_container_width=True)
    
    # 选择项目操作
    selected_idx = st.selectbox(
        "选择要操作的项目",
        range(len(projects)),
        format_func=lambda x: f"{projects[x]['project_name']} ({projects[x]['save_time'][:10]})"
    )
    
    if selected_idx is not None:
        selected_project = projects[selected_idx]
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📂 加载此项目", use_container_width=True):
                st.session_state.project_info = selected_project['data']['project_info']
                st.session_state.rooms_data = selected_project['data']['rooms_data']
                st.success(f"已加载项目: {selected_project['project_name']}")
                st.switch_page("cold_storage_input_interface.py")
        
        with col2:
            if st.button("🔍 查看详情", use_container_width=True):
                st.subheader(f"项目详情: {selected_project['project_name']}")
                
                # 显示项目信息
                st.json(selected_project['data']['project_info'])
                
                # 显示冷间信息
                st.subheader("冷间列表")
                rooms_df = pd.DataFrame(selected_project['data']['rooms_data'])
                st.dataframe(rooms_df[['room_name', 'temperature', 'length', 'width', 'height']])
        
        with col3:
            if st.button("🗑️ 删除此项目", type="secondary", use_container_width=True):
                try:
                    os.remove(selected_project['filepath'])
                    st.success(f"已删除项目: {selected_project['project_name']}")
                    st.rerun()
                except Exception as e:
                    st.error(f"删除失败: {e}")
    
    # 批量操作
    st.markdown("### 🛠️ 批量操作")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📥 导出所有项目", use_container_width=True):
            # 创建zip文件
            import zipfile
            from io import BytesIO
            
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
                for proj in projects:
                    zip_file.write(proj['filepath'], proj['filename'])
            
            st.download_button(
                label="下载ZIP文件",
                data=zip_buffer.getvalue(),
                file_name=f"冷库项目备份_{datetime.now().strftime('%Y%m%d_%H%M')}.zip",
                mime="application/zip"
            )
    
    with col2:
        if st.button("🔄 从备份恢复", use_container_width=True):
            uploaded_file = st.file_uploader("上传项目备份文件", type=['zip', 'pkl', 'json'])
            if uploaded_file:
                # 处理上传的文件
                st.info("文件上传成功，恢复功能开发中...")
else:
    st.info("📭 暂无保存的项目")
    
    if st.button("🏠 返回主页面"):
        st.switch_page("cold_storage_input_interface.py")