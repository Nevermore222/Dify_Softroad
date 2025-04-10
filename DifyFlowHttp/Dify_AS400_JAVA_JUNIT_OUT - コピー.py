from flask import Flask, request, jsonify
import os
import uuid
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
import threading
from collections import defaultdict

app = Flask(__name__)

# 数据库配置
app.config['SQLALCHEMY_DATABASE_URI'] = \
    'mssql+pyodbc://sa:Aa123456@192.168.2.61/ASIS_INFO_DIFY?driver=ODBC+Driver+17+for+SQL+Server'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# 数据模型
class CommandLog(db.Model):
    __tablename__ = 'CommandLog'
    __table_args__ = {'schema': 'dbo'}
    
    ID = db.Column(db.Integer, primary_key=True)
    CommandValue = db.Column(db.String(500), nullable=False)
    CommandType = db.Column(db.String(50), nullable=False)
    FileName = db.Column(db.Text, nullable=False)
    OutFolderPath = db.Column(db.Text, nullable=False)
    CreatedAt = db.Column(db.DateTime, server_default=db.func.now())
    UpdatedAt = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

# 全局配置
PORT = int(os.getenv('PORT', 5555))
BASE_DIR = r"\\192.168.9.177\shared\ASIS_OUT_DIFY"
folder_lock = threading.Lock()
workflow_locks = defaultdict(threading.Lock)
processed_workflows = set()

# 初始化目录
os.makedirs(BASE_DIR, exist_ok=True)

def handle_folder_creation(command_value, workflow_id):
    """处理文件夹创建和版本管理"""
    target_dir = os.path.join(BASE_DIR, command_value)
    
    if os.path.exists(target_dir):
        # 获取原始目录信息
        create_time = datetime.fromtimestamp(os.path.getctime(target_dir))
        timestamp = create_time.strftime("%Y%m%d_%H%M%S")
        archived_dir = f"{target_dir}_{timestamp}"
        
        # 执行重命名操作
        os.rename(target_dir, archived_dir)
        
        # 更新数据库记录
        try:
            CommandLog.query.filter(
                CommandLog.OutFolderPath == target_dir
            ).update(
                {"OutFolderPath": archived_dir},
                synchronize_session=False
            )
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise RuntimeError(f"数据库更新失败: {str(e)}")
    
    # 创建新目录
    os.makedirs(target_dir, exist_ok=True)
    processed_workflows.add(workflow_id)

@app.route('/api/save_content', methods=['POST'])
def save_content():
    try:
        data = request.get_json()
        two_dim_flow_id = data.get('Two-dimensional_flow_id')
        content = data.get('content')
        command_name = data.get('command_name')
        workflow_run_id = data.get('workflow_run_id')
        command_type = data.get('command_type', 'UNKNOWN')

        # 修改参数校验部分
        if not all([content, command_name, workflow_run_id, two_dim_flow_id]):
            return jsonify({"error": "Missing required parameters"}), 400

        # 修改后的目录搜索逻辑
        command_value = command_name.split('_')[0]
        base_command_dir = os.path.join(BASE_DIR, command_value)
        
        # 搜索包含 two_dim_flow_id 的目录
        matching_dirs = []
        if os.path.exists(base_command_dir):
            with os.scandir(base_command_dir) as entries:
                matching_dirs = [entry.name for entry in entries 
                               if entry.is_dir() and two_dim_flow_id in entry.name]

        # 在锁内处理目录创建
        if workflow_run_id not in processed_workflows:
            with workflow_locks[f"{two_dim_flow_id}_{command_value}"]:
                if workflow_run_id not in processed_workflows:
                    os.makedirs(base_command_dir, exist_ok=True)
                    
                    # 选择现有目录或创建新目录
                    selected_dir = matching_dirs[0] if matching_dirs else \
                        f"{two_dim_flow_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    base_flow_dir = os.path.join(base_command_dir, selected_dir)
                    
                    os.makedirs(base_flow_dir, exist_ok=True)
                    target_dir = os.path.join(base_flow_dir, command_value)
                    handle_folder_creation(target_dir, workflow_run_id)
                    processed_workflows.add(workflow_run_id)

        # 生成文件名和路径
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{command_name}_{timestamp}.md"
        file_path = os.path.join(target_dir, filename)

        # 写入文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        # 数据库记录
        log_entry = CommandLog(
            CommandValue=command_value,
            CommandType=command_type,
            FileName=filename,
            OutFolderPath=target_dir  # 更新为新的路径结构
        )
        db.session.add(log_entry)
        db.session.commit()

        return jsonify({
            "status": "success",
            "folder": command_value,
            "file_name": filename,
            "out_folder": target_dir
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"文件处理失败: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=True)