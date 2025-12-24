import streamlit.components.v1 as components
import json
from typing import Dict, List, Any


class DynamicSelectComponent:
    """动态选择自定义组件"""

    def __init__(self):
        pass

    def create(self, component_data: Dict, current_selection: Dict) -> Any:
        """创建动态选择组件"""

        storage_types = component_data['storage_types']
        product_mapping = component_data['product_mapping']

        component_html = self._generate_html(storage_types, product_mapping, current_selection)

        return components.html(
            component_html,
            height=320
        )

    def _generate_html(self, storage_types: List[str], product_mapping: Dict, current_selection: Dict) -> str:
        """生成组件的HTML代码"""

        # 在Python中预先处理好所有值 - 确保所有get()调用都在这里
        storage_type_value = current_selection.get('storage_type', '冷冻食品')
        product_type_value = current_selection.get('product_type', '猪肉')
        last_update_value = current_selection.get('last_update', '从未')

        # 创建简单的组件ID
        component_id = f"comp_{abs(hash(str(current_selection))) % 10000}"

        # 生成存储类型的选项HTML
        storage_options = []
        for stype in storage_types:
            selected = 'selected' if stype == storage_type_value else ''
            storage_options.append(f'<option value="{stype}" {selected}>{stype}</option>')

        storage_options_html = ''.join(storage_options)

        # 将product_mapping转换为JSON字符串
        product_mapping_json = json.dumps(product_mapping)

        # 现在HTML字符串中只包含简单的变量替换，没有Python方法调用
        html_content = f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>动态选择组件</title>
    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        .dynamic-select-container {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            padding: 20px;
            border: 2px solid #e1e5e9;
            border-radius: 12px;
            background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            max-width: 500px;
            margin: 0 auto;
        }}

        .select-group {{
            margin-bottom: 20px;
        }}

        .select-label {{
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #1e293b;
            font-size: 14px;
            display: flex;
            align-items: center;
        }}

        .select-label i {{
            margin-right: 8px;
            font-size: 16px;
        }}

        .select-field {{
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #cbd5e1;
            border-radius: 8px;
            font-size: 14px;
            background: white;
            transition: all 0.3s ease;
            cursor: pointer;
        }}

        .select-field:hover {{
            border-color: #94a3b8;
        }}

        .select-field:focus {{
            outline: none;
            border-color: #3b82f6;
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
        }}

        .status-container {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-top: 16px;
            padding: 12px;
            background: white;
            border-radius: 8px;
            border: 1px solid #e2e8f0;
        }}

        .status-indicator {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .status-dot {{
            width: 10px;
            height: 10px;
            border-radius: 50%;
            transition: background-color 0.3s ease;
        }}

        .status-synced {{ background: #10b981; }}
        .status-pending {{ background: #f59e0b; animation: pulse 1.5s infinite; }}

        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}

        .status-text {{
            font-size: 12px;
            font-weight: 500;
        }}

        .selection-display {{
            background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
            color: white;
            padding: 16px;
            border-radius: 8px;
            margin-top: 16px;
            text-align: center;
        }}

        .selection-title {{
            font-size: 12px;
            opacity: 0.9;
            margin-bottom: 4px;
        }}

        .selection-content {{
            font-size: 16px;
            font-weight: 600;
        }}

        .last-update {{
            font-size: 10px;
            opacity: 0.7;
            margin-top: 4px;
        }}

        .instructions {{
            background: #fffbeb;
            border: 1px solid #fcd34d;
            border-radius: 6px;
            padding: 12px;
            margin-top: 16px;
            font-size: 12px;
            color: #92400e;
        }}
    </style>
</head>
<body>
    <div class="dynamic-select-container">
        <div class="select-group">
            <label class="select-label">
                <i>📦</i> 储存货物类型
            </label>
            <select class="select-field" id="storageSelect" onchange="handleStorageTypeChange()">
                {storage_options_html}
            </select>
        </div>

        <div class="select-group">
            <label class="select-label">
                <i>🏷️</i> 具体产品
            </label>
            <select class="select-field" id="productSelect" onchange="handleProductTypeChange()">
                <!-- 产品选项将通过JavaScript动态生成 -->
            </select>
        </div>

        <div class="status-container">
            <div class="status-indicator">
                <div id="statusDot" class="status-dot status-synced"></div>
                <span id="statusText" class="status-text">已同步</span>
            </div>
            <button onclick="forceSync()" style="background: #3b82f6; color: white; border: none; padding: 6px 12px; border-radius: 4px; font-size: 12px; cursor: pointer;">
                手动同步
            </button>
        </div>

        <div class="selection-display">
            <div class="selection-title">当前选择</div>
            <div class="selection-content">
                <span id="currentStorage">{storage_type_value}</span> - 
                <span id="currentProduct">{product_type_value}</span>
            </div>
            <div id="lastUpdate" class="last-update">
                最后更新: {last_update_value}
            </div>
        </div>

        <div class="instructions">
            💡 提示: 选择货物类型后，产品列表会自动更新。点击"手动同步"可立即同步到系统。
        </div>
    </div>

    <script>
        // 配置数据 - 这里只使用预定义的变量
        const CONFIG = {{
            productMapping: {product_mapping_json},
            currentStorage: "{storage_type_value}",
            currentProduct: "{product_type_value}",
            componentId: "{component_id}"
        }};

        let syncInProgress = false;

        // 初始化函数
        function initializeComponent() {{
            console.log('🚀 初始化动态选择组件');
            updateProductOptions();
            updateDisplay();
            setStatus('synced');
        }}

        // 更新产品选项
        function updateProductOptions() {{
            const storageSelect = document.getElementById('storageSelect');
            const productSelect = document.getElementById('productSelect');
            const storageType = storageSelect.value;
            const products = CONFIG.productMapping[storageType] || ['暂无产品'];

            // 保存当前产品选择
            const currentProduct = productSelect.value;

            // 清空并重新填充产品选项
            productSelect.innerHTML = '';
            products.forEach(product => {{
                const option = document.createElement('option');
                option.value = product;
                option.textContent = product;
                option.selected = (product === currentProduct) || 
                                 (product === CONFIG.currentProduct && currentProduct === '');
                productSelect.appendChild(option);
            }});

            console.log('🔄 更新产品列表: ' + storageType + ' -> ' + products.length + '个产品');
        }}

        // 处理存储类型变化
        function handleStorageTypeChange() {{
            console.log('📦 存储类型发生变化');
            updateProductOptions();
            updateDisplay();
            sendSelectionToStreamlit();
        }}

        // 处理产品类型变化
        function handleProductTypeChange() {{
            console.log('🏷️ 产品类型发生变化');
            updateDisplay();
            sendSelectionToStreamlit();
        }}

        // 强制同步
        function forceSync() {{
            console.log('🔄 手动同步触发');
            sendSelectionToStreamlit();
        }}

        // 发送选择到Streamlit
        function sendSelectionToStreamlit() {{
            if (syncInProgress) {{
                console.log('⏳ 同步进行中，跳过');
                return;
            }}

            syncInProgress = true;
            setStatus('pending');

            const storageType = document.getElementById('storageSelect').value;
            const productType = document.getElementById('productSelect').value;

            const selectionData = {{
                action: 'selection_updated',
                storage_type: storageType,
                product_type: productType,
                timestamp: new Date().toLocaleString('zh-CN'),
                component_id: CONFIG.componentId
            }};

            console.log('📤 发送数据到Streamlit:', selectionData);

            // 方法1: 使用Streamlit Bridge (推荐)
            if (window.parent.streamlitBridge) {{
                window.parent.streamlitBridge.setComponentValue(selectionData);
                setTimeout(() => setStatus('synced'), 1000);
            }} 
            // 方法2: 使用postMessage
            else if (window.parent && window.parent !== window) {{
                window.parent.postMessage({{
                    type: 'STREAMLIT_COMPONENT_UPDATE',
                    data: selectionData
                }}, '*');
                setTimeout(() => setStatus('synced'), 1000);
            }}
            // 方法3: 控制台输出（调试用）
            else {{
                console.warn('❌ 无法连接到Streamlit，数据:', selectionData);
                setStatus('synced');
            }}

            syncInProgress = false;
        }}

        // 更新状态显示
        function setStatus(status) {{
            const statusDot = document.getElementById('statusDot');
            const statusText = document.getElementById('statusText');

            statusDot.className = 'status-dot ' + (
                status === 'pending' ? 'status-pending' : 'status-synced'
            );
            statusText.textContent = status === 'pending' ? '同步中...' : '已同步';
        }}

        // 更新显示内容
        function updateDisplay() {{
            const storageType = document.getElementById('storageSelect').value;
            const productType = document.getElementById('productSelect').value;

            document.getElementById('currentStorage').textContent = storageType;
            document.getElementById('currentProduct').textContent = productType;
            document.getElementById('lastUpdate').textContent = 
                '最后更新: ' + new Date().toLocaleString('zh-CN');
        }}

        // 监听来自Streamlit的消息
        window.addEventListener('message', function(event) {{
            if (event.data.type === 'UPDATE_FROM_STREAMLIT') {{
                console.log('📥 收到Streamlit消息:', event.data);

                if (event.data.storage_type) {{
                    document.getElementById('storageSelect').value = event.data.storage_type;
                    updateProductOptions();
                }}
                if (event.data.product_type) {{
                    document.getElementById('productSelect').value = event.data.product_type;
                }}

                updateDisplay();
                setStatus('synced');
            }}
        }});

        // 页面加载完成后初始化
        if (document.readyState === 'loading') {{
            document.addEventListener('DOMContentLoaded', initializeComponent);
        }} else {{
            initializeComponent();
        }}

        console.log('✅ 动态选择组件脚本加载完成');
    </script>
</body>
</html>
'''
        return html_content