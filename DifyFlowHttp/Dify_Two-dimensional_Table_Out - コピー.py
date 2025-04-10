from flask import Flask, request, jsonify
import os
import uuid
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# 配置数据库连接
app.config['SQLALCHEMY_DATABASE_URI'] = \
    'mssql+pyodbc://sa:Aa123456@192.168.2.61/ASIS_INFO_DIFY?driver=ODBC+Driver+17+for+SQL+Server'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# 定义CommandLog模型
class CommandLog(db.Model):
    __tablename__ = 'CommandLog'
    __table_args__ = {'schema': 'dbo'}
    
    ID = db.Column(db.Integer, primary_key=True)
    CommandValue = db.Column(db.String(500), nullable=False)
    CommandType = db.Column(db.String(50), nullable=False)
    FileName = db.Column(db.String, nullable=False, default='')
    CreatedAt = db.Column(db.DateTime, server_default=db.func.now())
    UpdatedAt = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())
    OutFolderPath = db.Column(db.String(500), nullable=False, default='')

# 从环境变量或命令行参数读取端口（默认5000）
PORT = int(os.getenv('PORT', 5000))  # 默认端口
BASE_DIR = r"\\192.168.9.177\shared\ASIS_OUT_DIFY"      # 文件保存路径

# 确保保存目录存在
if not os.path.exists(BASE_DIR):
    os.makedirs(BASE_DIR)

@app.route('/api/save_content', methods=['POST'])
def save_content():
    try:
        data = request.get_json()
        content = data.get('content')
        command_name = data.get('command_name')
        workflow_run_id = data.get('workflow_run_id')  # 新增获取工作流运行ID

        if not content or not workflow_run_id:  # 增加对workflow_run_id的校验
            return jsonify({"error": "Missing required parameters: 'content' or 'workflow_run_id'"}), 400

        # 获取命令值
        command_value = command_name.split('_')[0]
        
        # 创建命令值对应的文件夹
        command_dir = os.path.join(BASE_DIR, command_value)
        if not os.path.exists(command_dir):
            os.makedirs(command_dir)

        # 创建workflow_run_id子文件夹
        sub_dir = os.path.join(command_dir, workflow_run_id)
        if not os.path.exists(sub_dir):
            os.makedirs(sub_dir)

        # 生成唯一文件名（时间戳+UUID）
        filename = f"{command_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex}.md"
        file_path = os.path.join(sub_dir, filename)  # 修改为使用子文件夹路径

        # 写入文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        # 插入数据库记录
        command_type = data.get('command_type', 'UNKNOWN')
        db.session.add(CommandLog(
            CommandValue=command_value,
            CommandType=command_type,
            FileName=filename,
            OutFolderPath=sub_dir  # 更新为子文件夹路径
        ))
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Content saved and logged successfully",
            "file_path": file_path
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=True)
