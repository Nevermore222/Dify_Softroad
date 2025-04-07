import os
from flask import Flask, jsonify, request, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from datetime import datetime
import markdown

app = Flask(__name__)

# 配置
app.config['SQLALCHEMY_DATABASE_URI'] = \
    'mssql+pyodbc://sa:Aa123456@192.168.2.61/ASIS_INFO_DIFY?driver=ODBC+Driver+17+for+SQL+Server'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
app.config['ALLOWED_EXTENSIONS'] = {'md'}
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

# 确保上传目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

class CommandLog(db.Model):
    """命令日志表实体类"""
    __tablename__ = 'CommandLog'
    
    ID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    CommandValue = db.Column(db.NVARCHAR(500), nullable=False, comment='命令内容')
    CommandType = db.Column(db.NVARCHAR(50), nullable=False, comment='命令类型')
    TableDataPath = db.Column(db.NVARCHAR(500), nullable=True, comment='表格数据存储路径')
    CreatedAt = db.Column(db.DateTime, server_default=db.func.now(), comment='创建时间')
    UpdatedAt = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), comment='更新时间')

    def to_dict(self):
        return {
            "id": self.ID,
            "command_value": self.CommandValue,
            "command_type": self.CommandType,
            "table_data_path": self.TableDataPath,
            "created_at": self.CreatedAt.isoformat() if self.CreatedAt else None,
            "updated_at": self.UpdatedAt.isoformat() if self.UpdatedAt else None
        }

@app.route('/api/files/content', methods=['GET'])
def get_file_content():
    """获取物理文件内容"""
    file_path = request.args.get('path')
    if not file_path:
        return jsonify({"error": "Path parameter is required"}), 400
    
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return jsonify({"error": "File not found"}), 404
        
        # 读取文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 获取文件最后修改时间
        timestamp = datetime.fromtimestamp(os.path.getmtime(file_path))
        
        return jsonify({
            "content": content,
            "file_path": file_path,
            "timestamp": timestamp.isoformat(),
            "file_name": os.path.basename(file_path)
        })
    except Exception as e:
        app.logger.error(f"Failed to read file {file_path}: {str(e)}")
        return jsonify({"error": "Failed to read file"}), 500

@app.route('/api/files/save', methods=['PUT'])
def save_file_content():
    """保存文件内容"""
    data = request.get_json()
    # 处理前端可能发送的不同格式
    if isinstance(data, dict):
        file_path = data.get('path')
        content = data.get('content')
    else:
        return jsonify({"error": "Invalid request format"}), 400
    
    if not all([file_path, content]):
        return jsonify({"error": "Missing required parameters"}), 400
    
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # 写入文件内容
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # 更新关联的命令更新时间
        command = CommandLog.query.filter(CommandLog.TableDataPath == file_path).first()
        if command:
            command.UpdatedAt = datetime.now()
            db.session.commit()
        
        return jsonify({
            "status": "success",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Failed to save file {file_path}: {str(e)}")
        return jsonify({"error": "Failed to save file"}), 500

@app.route('/api/commands', methods=['GET'])
def get_command_logs():
    """获取命令日志"""
    try:
        page = request.args.get('page', 1, type=int)
        page_size = min(request.args.get('page_size', 10, type=int), 100)
        command_type = request.args.get('type')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        search_keyword = request.args.get('search')

        # 先获取唯一的命令值列表
        distinct_query = db.session.query(
            CommandLog.CommandValue,
            CommandLog.CommandType,
            db.func.max(CommandLog.CreatedAt).label('latest_created')
        )

        if command_type:
            distinct_query = distinct_query.filter(CommandLog.CommandType == command_type)
        if start_date:
            distinct_query = distinct_query.filter(CommandLog.CreatedAt >= start_date)
        if end_date:
            distinct_query = distinct_query.filter(CommandLog.CreatedAt <= end_date)
        if search_keyword:
            distinct_query = distinct_query.filter(
                CommandLog.CommandValue.ilike(f'%{search_keyword}%')
            )

        distinct_query = distinct_query.group_by(
            CommandLog.CommandValue,
            CommandLog.CommandType
        ).order_by(db.desc('latest_created'))

        # 分页处理
        pagination = distinct_query.paginate(
            page=page,
            per_page=page_size,
            error_out=False
        )

        # 获取每个命令的最新文件路径
        result = []
        for item in pagination.items:
            latest_log = CommandLog.query.filter(
                CommandLog.CommandValue == item.CommandValue
            ).order_by(CommandLog.CreatedAt.desc()).first()
            
            if latest_log:
                result.append(latest_log.to_dict())

        return jsonify({
            "data": result,
            "pagination": {
                "current_page": pagination.page,
                "total_pages": pagination.pages,
                "total_items": pagination.total,
                "page_size": page_size
            }
        })
    except Exception as e:
        app.logger.error(f"Query failed: {str(e)}")
        return jsonify({"error": "Server error"}), 500

@app.route('/api/commands', methods=['POST'])
def create_command_log():
    """创建命令日志"""
    try:
        data = request.get_json()
        required_fields = ['command_value', 'command_type']
        if not all(field in data for field in required_fields):
            return jsonify({"error": "Missing required fields"}), 400

        new_log = CommandLog(
            CommandValue=data['command_value'],
            CommandType=data['command_type'],
            TableDataPath=data.get('table_data_path')
        )
        
        db.session.add(new_log)
        db.session.commit()
        
        return jsonify(new_log.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Create failed: {str(e)}")
        return jsonify({"error": "Server error"}), 500

@app.route('/api/commands/<int:command_id>', methods=['GET'])
def get_command_detail(command_id):
    """获取命令详情"""
    try:
        command = CommandLog.query.get_or_404(command_id)
        return jsonify(command.to_dict())
    except Exception as e:
        app.logger.error(f"Get detail failed: {str(e)}")
        return jsonify({"error": "Server error"}), 500

@app.route('/api/commands/<int:command_id>', methods=['PUT'])
def update_command(command_id):
    """更新命令基本信息"""
    try:
        command = CommandLog.query.get_or_404(command_id)
        data = request.get_json()
        
        if 'command_value' in data:
            command.CommandValue = data['command_value']
        if 'command_type' in data:
            command.CommandType = data['command_type']
        if 'table_data_path' in data:
            command.TableDataPath = data['table_data_path']
        
        db.session.commit()
        return jsonify(command.to_dict())
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Update command failed: {str(e)}")
        return jsonify({"error": "Server error"}), 500

@app.route('/api/commands/<string:command_value>/files', methods=['GET'])
def get_command_files_by_value(command_value):
    """获取相同CommandValue的所有文件路径"""
    try:
        files = CommandLog.query.filter_by(CommandValue=command_value).order_by(CommandLog.CreatedAt.desc()).all()
        return jsonify({
            "files": [{
                "id": file.ID,
                "table_data_path": file.TableDataPath,
                "created_at": file.CreatedAt.isoformat() if file.CreatedAt else None
            } for file in files]
        })
    except Exception as e:
        app.logger.error(f"Get command files failed: {str(e)}")
        return jsonify({"error": "Server error"}), 500

@app.route('/api/commands/<int:command_id>', methods=['DELETE'])
def delete_command(command_id):
    """删除命令记录"""
    try:
        command = CommandLog.query.get_or_404(command_id)
        
        # 删除关联的文件
        if command.TableDataPath and os.path.exists(command.TableDataPath):
            try:
                os.remove(command.TableDataPath)
            except Exception as e:
                app.logger.error(f"Failed to delete file {command.TableDataPath}: {str(e)}")
        
        db.session.delete(command)
        db.session.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Delete failed: {str(e)}")
        return jsonify({"error": "Server error"}), 500

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """提供上传的文件"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        try:
            db.session.execute(
                text("CREATE SEQUENCE CommandSequence START WITH 1 INCREMENT BY 1")
            )
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.warning(f"Sequence already exists: {str(e)}")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
