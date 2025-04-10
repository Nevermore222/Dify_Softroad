from flask import Flask, request, jsonify
import os
import uuid
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
import threading
from collections import defaultdict
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging
from logging.handlers import RotatingFileHandler

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

# 新增全局字典存储工作流与目录映射
workflow_dir_map = {}

# 在全局配置部分增加重试机制配置
RETRY_STRATEGY = Retry(
    total=3,  # 最大重试次数
    backoff_factor=1,  # 重试间隔时间
    status_forcelist=[500, 502, 503, 504]  # 需要重试的状态码
)
ADAPTER = HTTPAdapter(max_retries=RETRY_STRATEGY)

# 在全局配置部分后添加日志配置
# 配置日志格式
log_formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
)

# 创建日志处理器（自动轮转，最大10MB，保留5个备份）
file_handler = RotatingFileHandler(
    'app.log', 
    maxBytes=10*1024*1024,
    backupCount=5,
    encoding='utf-8'
)
file_handler.setFormatter(log_formatter)

# 控制台日志
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)

# 获取根日志记录器
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# 初始化目录
os.makedirs(BASE_DIR, exist_ok=True)

def handle_folder_creation(target_dir, workflow_run_id):
    logger.debug("开始处理目录创建: %s", target_dir)
    try:
        if folder_lock:
            """带版本管理的目录创建"""
            if os.path.exists(target_dir):
                logger.info("检测到已存在目录: %s", target_dir)
                if workflow_run_id not in processed_workflows:
                    create_time = datetime.fromtimestamp(os.path.getctime(target_dir))
                    logger.info("准备重命名目录，创建时间: %s", create_time)
                    timestamp = create_time.strftime("%Y%m%d_%H%M%S")
                    archived_dir = f"{target_dir}_{timestamp}"
                    
                    os.rename(target_dir, archived_dir)
                    logger.info("目录已重命名: %s -> %s", target_dir, archived_dir)
                    
                    # 更新数据库记录
                    try:
                        result = CommandLog.query.filter(
                            CommandLog.OutFolderPath == target_dir
                        ).update(
                            {"OutFolderPath": archived_dir},
                            synchronize_session=False
                        )
                        db.session.commit()
                        logger.info("更新了 %d 条数据库记录", result.rowcount)
                    except Exception as e:
                        logger.error("数据库更新失败: %s", str(e), exc_info=True)
                        raise
            
            os.makedirs(target_dir, exist_ok=True)
            logger.debug("目录创建/确认完成: %s", target_dir)
            processed_workflows.add(workflow_run_id)
            logger.info("已标记工作流: %s", workflow_run_id)
    except Exception as e:
        logger.error("目录创建失败: %s", str(e), exc_info=True)
        raise

@app.route('/api/save_content', methods=['POST'])
def save_content():
    logger.info(f"开始处理请求，参数: {request.json}")
    try:
        data = request.get_json()
        two_dim_flow_id = data.get('Two-dimensional_flow_id')
        content = data.get('content')
        command_name = data.get('command_name')
        workflow_run_id = data.get('workflow_run_id')
        command_type = data.get('command_type', 'UNKNOWN')

        # 参数校验
        if not all([content, command_name, workflow_run_id, two_dim_flow_id]):
            logger.error("缺少必要参数: %s", request.json)
            return jsonify({"error": "Missing required parameters"}), 400

        logger.debug("参数校验通过，开始处理目录")

        command_value = command_name.split('_')[0]
        base_command_dir = os.path.join(BASE_DIR, command_value)
        
        # 搜索包含 two_dim_flow_id 的目录
        logger.info("正在搜索目录: %s 下的匹配项", base_command_dir)
        matching_dirs = []
        if os.path.exists(base_command_dir):
            with os.scandir(base_command_dir) as entries:
                matching_dirs = [entry.name for entry in entries 
                               if entry.is_dir() and two_dim_flow_id in entry.name]
        logger.debug("找到 %d 个匹配目录", len(matching_dirs))

        # 初始化target_dir为None
        target_dir = None
        
        with workflow_locks[workflow_run_id]:
            if workflow_run_id not in processed_workflows:
                logger.info("开始创建目录结构 workflow_run_id=%s", workflow_run_id)
                
                # 添加目录创建日志
                os.makedirs(base_command_dir, exist_ok=True)
                logger.debug("已创建基础目录: %s", base_command_dir)

                selected_dir = matching_dirs[0] if matching_dirs else \
                    f"{two_dim_flow_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                logger.info("选择目录: %s", selected_dir)

                base_flow_dir = os.path.join(base_command_dir, selected_dir)
                os.makedirs(base_flow_dir, exist_ok=True)
                logger.debug("已创建流程目录: %s", base_flow_dir)

                target_dir = os.path.join(base_flow_dir, command_value)
                logger.info("目标目录: %s", target_dir)
                
                try:
                    handle_folder_creation(target_dir, workflow_run_id)
                    logger.info("目录处理完成: %s", target_dir)
                except Exception as e:
                    logger.error("目录创建失败: %s", str(e), exc_info=True)
                    raise
                
                # 记录生成的目录
                workflow_dir_map[workflow_run_id] = selected_dir
                processed_workflows.add(workflow_run_id)
            else:
                # 复用已生成的目录
                selected_dir = workflow_dir_map.get(workflow_run_id)
                if not selected_dir:
                    raise ValueError("无法找到已记录的工作流目录")

        # 统一构造目录路径
        base_flow_dir = os.path.join(base_command_dir, selected_dir)
        target_dir = os.path.join(base_flow_dir, command_value)
        
        # 确保目录存在（即使已处理过）
        os.makedirs(target_dir, exist_ok=True)

        # 生成文件名和路径
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{command_name}_{timestamp}.md"
        file_path = os.path.join(target_dir, filename)

        # 添加文件操作日志
        logger.debug("生成文件名，原始时间戳: %s", timestamp)
        if os.path.exists(file_path):
            logger.warning("检测到文件冲突: %s", file_path)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S%f")
            logger.info("使用新时间戳: %s", timestamp)
        
        logger.info("正在写入文件: %s", file_path)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.debug("文件写入完成，大小: %d bytes", len(content))

        # 数据库记录
        log_entry = CommandLog(
            CommandValue=command_value,
            CommandType=command_type,
            FileName=filename,
            OutFolderPath=target_dir
        )

        # 添加数据库日志
        try:
            db.session.add(log_entry)
            db.session.commit()
            logger.info("数据库记录成功，ID: %d", log_entry.ID)
        except Exception as e:
            logger.error("数据库操作失败: %s", str(e), exc_info=True)
            db.session.rollback()

        logger.info("请求处理完成")
        return jsonify({
            "status": "success",
            "folder": command_value,
            "file_name": filename,
            "out_folder": target_dir
        }), 200

    except Exception as e:
        logger.exception("处理请求时发生未捕获的异常")
        db.session.rollback()
        return jsonify({"error": f"文件处理失败: {str(e)}"}), 500

# 在调用接口时使用重试机制
def call_save_content_api(data):
    session = requests.Session()
    session.mount("http://", ADAPTER)
    session.mount("https://", ADAPTER)
    
    try:
        response = session.post(
            "http://192.168.2.61:5555/api/save_content",
            json=data,
            timeout=10  # 设置超时时间为10秒
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"API调用失败: {str(e)}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=True)