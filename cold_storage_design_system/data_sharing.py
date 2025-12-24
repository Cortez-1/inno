# data_sharing.py
import json
import os
import streamlit as st
from datetime import datetime, timedelta

class DataSharing:
    """数据共享类，用于页面间数据传递"""
    
    def __init__(self, cache_dir=".streamlit_cache"):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def save_design_data(self, project_info, rooms_data):
        """保存设计数据到文件和session_state"""
        data = {
            'project_info': project_info,
            'rooms_data': rooms_data,
            'timestamp': datetime.now().isoformat(),
            'project_name': project_info.get('project_name', 'unknown')
        }
        
        # 保存到 session_state
        st.session_state.design_data = data
        
        # 保存到文件（备份）
        filename = f"{self.cache_dir}/design_data_{project_info.get('project_name', 'default')}.json"
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return filename
        except Exception as e:
            print(f"保存文件失败: {e}")
            return "session_only"
    
    def load_design_data(self, project_name=None):
        """从文件或session_state加载设计数据"""
        # 首先检查 session_state
        if 'design_data' in st.session_state and st.session_state.design_data:
            return st.session_state.design_data
        
        # 然后尝试从文件加载
        try:
            if project_name:
                filename = f"{self.cache_dir}/design_data_{project_name}.json"
            else:
                # 加载最新的文件
                files = [f for f in os.listdir(self.cache_dir) if f.startswith('design_data_') and f.endswith('.json')]
                if not files:
                    return None
                # 按修改时间排序，取最新的
                files_with_time = []
                for f in files:
                    filepath = os.path.join(self.cache_dir, f)
                    mtime = os.path.getmtime(filepath)
                    files_with_time.append((mtime, f))
                
                files_with_time.sort(reverse=True)
                filename = os.path.join(self.cache_dir, files_with_time[0][1])
            
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 同时保存到 session_state
                st.session_state.design_data = data
                return data
                
        except FileNotFoundError:
            return None
        except Exception as e:
            print(f"加载文件失败: {e}")
            return None
    
    def get_available_projects(self):
        """获取可用的项目列表"""
        try:
            files = [f for f in os.listdir(self.cache_dir) if f.startswith('design_data_') and f.endswith('.json')]
            projects = []
            for f in files:
                try:
                    filepath = os.path.join(self.cache_dir, f)
                    with open(filepath, 'r', encoding='utf-8') as file:
                        data = json.load(file)
                        projects.append({
                            'name': data.get('project_info', {}).get('project_name', '未知项目'),
                            'filename': f,
                            'timestamp': data.get('timestamp', ''),
                            'room_count': len(data.get('rooms_data', []))
                        })
                except:
                    continue
            return sorted(projects, key=lambda x: x['timestamp'], reverse=True)
        except:
            return []
    
    def clear_old_data(self, max_age_hours=24):
        """清理过期数据"""
        current_time = datetime.now()
        for filename in os.listdir(self.cache_dir):
            if filename.startswith('design_data_'):
                filepath = os.path.join(self.cache_dir, filename)
                try:
                    file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                    if (current_time - file_time).total_seconds() > max_age_hours * 3600:
                        os.remove(filepath)
                except:
                    continue

# 创建全局实例
data_sharing = DataSharing()