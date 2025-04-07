from flask import Flask, request, jsonify
import os
import uuid
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
import json

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
    TableDataPath = db.Column(db.Text, nullable=False)
    CreatedAt = db.Column(db.DateTime, server_default=db.func.now())
    UpdatedAt = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())


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

        if not content:
            return jsonify({"error": "Missing 'content' in request"}), 400

        # 生成唯一文件名（时间戳+UUID）
        filename = f"{command_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex}.md"
        file_path = os.path.join(BASE_DIR, filename)

        # 写入文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        # 插入数据库记录
        command_type = data.get('command_type', 'UNKNOWN')  # 默认为UNKNOWN如果未提供
        command_value = command_name.split('_')[0]  # 取第一个下划线前的部分
        db.session.add(CommandLog(
            CommandValue=command_value,
            CommandType=command_type,
            TableDataPath=file_path  # 直接存储文件路径字符串
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
