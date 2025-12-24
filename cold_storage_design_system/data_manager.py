# data_manager.py
import json
import pandas as pd
import streamlit as st
from typing import Dict, List, Any

class DataManager:
    """数据管理器 - 统一管理所有数据操作"""
    
    def __init__(self):
        self.storage_types = {
            "冷冻食品": {"temp_range": (-25, -18), "humidity": 0.95},
            "深冷食品": {"temp_range": (-40, -25), "humidity": 0.95},
            "海鲜": {"temp_range": (-22, -18), "humidity": 0.95},
            "冰淇淋": {"temp_range": (-28, -24), "humidity": 0.90},
            "药品": {"temp_range": (-25, -15), "humidity": 0.60},
            "肉类": {"temp_range": (-2, 2), "humidity": 0.90},
            "乳制品": {"temp_range": (2, 6), "humidity": 0.85},
            "蔬菜水果": {"temp_range": (4, 8), "humidity": 0.90},
            "物流仓储": {"temp_range": (-18, 15), "humidity": 0.70}
        }
    
    def load_product_types(self) -> Dict[str, List[str]]:
        """加载产品类型数据"""
        try:
            # 模拟数据 - 您可以用实际的JSON文件替换
            product_data = {
                "冷冻食品": ["猪肉", "牛肉", "禽肉", "鱼虾", "冷冻调理食品", "其他冷冻食品"],
                "深冷食品": ["金枪鱼", "高档海鲜", "特殊冷冻食品", "生物制品"],
                "海鲜": ["鱼类", "虾类", "贝类", "蟹类", "海参"],
                "冰淇淋": ["杯装冰淇淋", "盒装冰淇淋", "冰淇淋蛋糕", "雪糕"],
                "药品": ["疫苗", "生物制剂", "注射剂", "特殊药品"],
                "肉类": ["冷却猪肉", "冷却牛肉", "冷却羊肉", "禽肉"],
                "乳制品": ["牛奶", "酸奶", "奶酪", "黄油", "奶油"],
                "蔬菜水果": ["叶菜类", "根茎类", "水果类", "菌菇类"],
                "物流仓储": ["综合食品", "电商商品", "物流中转货物"]
            }
            return product_data
        except Exception as e:
            st.error(f"加载产品数据失败: {e}")
            return {}
    
    def get_component_data(self) -> Dict[str, Any]:
        """为自定义组件准备数据"""
        product_mapping = self.load_product_types()
        
        return {
            'storage_types': list(self.storage_types.keys()),
            'product_mapping': product_mapping,
            'default_storage_type': "冷冻食品",
            'default_product_type': product_mapping.get("冷冻食品", [""])[0] if product_mapping.get("冷冻食品") else ""
        }