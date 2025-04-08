import os
from flask import Flask, jsonify, request, send_from_directory, Response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from datetime import datetime
import markdown
import requests
import logging
from urllib.parse import unquote
import chardet

app = Flask(__name__)

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

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
    __table_args__ = {'schema': 'dbo'}
    
    ID = db.Column(db.Integer, primary_key=True)
    CommandValue = db.Column(db.NVARCHAR(500), nullable=False)
    CommandType = db.Column(db.NVARCHAR(50), nullable=False)
    FileName = db.Column(db.NVARCHAR(255), nullable=False)
    OutFolderPath = db.Column(db.NVARCHAR(500), nullable=False)
    CreatedAt = db.Column(db.DateTime, server_default=db.func.now())
    UpdatedAt = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    def to_dict(self):
        return {
            "id": self.ID,
            "command_value": self.CommandValue,
            "command_type": self.CommandType,
            "file_name": self.FileName,
            "out_folder_path": self.OutFolderPath,
            "full_path": f"{self.OutFolderPath}/{self.FileName}".replace('\\', '/'),
            "created_at": self.CreatedAt.isoformat(),
            "updated_at": self.UpdatedAt.isoformat()
        }

@app.route('/api/files/content', methods=['GET'])
def get_file_content():
    """增强路径校验逻辑"""
    file_path = request.args.get('path')
    if not file_path:
        return jsonify({"error": "需要提供path参数"}), 400

    try:
        # 详细解码过程
        decoded_path = unquote(file_path)
        normalized_path = os.path.normpath(decoded_path)
        
        app.logger.debug(f"请求路径解码结果: {normalized_path}")

        # 增强路径存在性检查
        if not os.path.exists(normalized_path):
            app.logger.error(f"路径不存在: {normalized_path}")
            return jsonify({
                "error": "文件不存在",
                "request_path": file_path,
                "decoded_path": decoded_path,
                "normalized_path": normalized_path
            }), 404

        # 检查文件类型
        if not os.path.isfile(normalized_path):
            return jsonify({"error": "请求路径不是文件"}), 400

        # 检查文件大小（限制10MB）
        file_size = os.path.getsize(normalized_path)
        if file_size > 10 * 1024 * 1024:
            return jsonify({"error": "文件超过10MB限制"}), 400

        # 多种编码尝试
        encodings = ['utf-8', 'gbk', 'shift-jis']
        content = None
        for encoding in encodings:
            try:
                with open(normalized_path, 'r', encoding=encoding) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue

        if content is None:
            return jsonify({"error": "无法解码文件内容"}), 400

        return jsonify({
            "content": content,
            "file_path": normalized_path,
            "timestamp": datetime.fromtimestamp(os.path.getmtime(normalized_path)).isoformat(),
            "file_name": os.path.basename(normalized_path),
            "size": file_size
        })

    except Exception as e:
        app.logger.error(f"文件读取失败: {str(e)}", exc_info=True)
        return jsonify({"error": f"服务器错误: {str(e)}"}), 500

@app.route('/api/files/save', methods=['PUT'])
def save_file_content():
    """保存文件内容"""
    try:
        data = request.get_json()
        if not data or not isinstance(data, dict):
            return jsonify({"error": "无效的请求格式"}), 400

        file_path = data.get('path')
        content = data.get('content')
        
        if not all([file_path, content]):
            return jsonify({"error": "缺少必要参数: path 或 content"}), 400
            
        # 标准化路径格式
        file_path = os.path.normpath(file_path)
        
        # 确保目录存在
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # 写入文件内容
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # 更新关联的命令更新时间
        command = CommandLog.query.filter(
            db.func.replace(CommandLog.OutFolderPath, '/', '\\') == os.path.dirname(file_path).replace('/', '\\')
        ).first()
        
        if command:
            command.UpdatedAt = datetime.now()
            db.session.commit()
        
        return jsonify({
            "status": "success",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Failed to save file: {str(e)}")
        return jsonify({"error": f"Failed to save file: {str(e)}"}), 500

@app.route('/api/commands', methods=['GET'])
def get_command_logs():
    """获取命令日志"""
    try:
        page = request.args.get('page', 1, type=int)
        page_size = min(request.args.get('page_size', 10, type=int), 100)

        # 优化后的查询语句
        subquery = db.session.query(
            CommandLog.OutFolderPath,
            db.func.max(CommandLog.CreatedAt).label('max_created')
        ).filter(
            CommandLog.OutFolderPath.isnot(None),  # 排除NULL路径
            CommandLog.OutFolderPath != ''  # 排除空路径
        ).group_by(CommandLog.OutFolderPath).subquery()

        query = db.session.query(CommandLog).join(
            subquery,
            db.and_(
                CommandLog.OutFolderPath == subquery.c.OutFolderPath,
                CommandLog.CreatedAt == subquery.c.max_created
            )
        )

        # 过滤条件处理
        filters = []
        if command_type := request.args.get('type'):
            filters.append(CommandLog.CommandType == command_type)
        if search_key := request.args.get('search'):
            filters.append(CommandLog.CommandValue.ilike(f'%{search_key}%'))
        if (date_range := request.args.getlist('date_range[]')) and len(date_range) == 2:
            filters.append(CommandLog.CreatedAt.between(date_range[0], date_range[1]))

        if filters:
            query = query.filter(*filters)

        # 添加默认排序
        query = query.order_by(CommandLog.CreatedAt.desc())

        # 分页处理
        pagination = query.paginate(
            page=page, 
            per_page=page_size,
            error_out=False
        )

        return jsonify({
            "data": [item.to_dict() for item in pagination.items],
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
        # 添加路径标准化处理
        out_folder = os.path.dirname(data.get('table_data_path', ''))
        file_name = os.path.basename(data.get('table_data_path', ''))
        
        new_log = CommandLog(
            CommandValue=data['command_value'],
            CommandType=data['command_type'],
            OutFolderPath=out_folder.replace('\\', '/'),  # 统一存储为斜杠
            FileName=file_name
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
        
        db.session.commit()
        return jsonify(command.to_dict())
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Update command failed: {str(e)}")
        return jsonify({"error": "Server error"}), 500

@app.route('/api/commands/<string:command_value>/files', methods=['GET'])
def get_command_files_by_value(command_value):
    try:
        files = CommandLog.query.filter_by(CommandValue=command_value).all()
        return jsonify({
            "files": [{
                "full_path": os.path.normpath(
                    os.path.join(file.OutFolderPath, file.FileName)
                ).replace("\\", "/"),
                "file_name": file.FileName,
                "created_at": file.CreatedAt.isoformat()
            } for file in files]
        })
    except Exception as e:
        app.logger.error(f"获取文件列表失败: {str(e)}")
        return jsonify({"error": "服务器错误"}), 500

@app.route('/api/commands/<int:command_id>', methods=['DELETE'])
def delete_command(command_id):
    """删除命令记录"""
    try:
        command = CommandLog.query.get_or_404(command_id)
        
        # 删除关联的文件
        if command.OutFolderPath and os.path.exists(command.OutFolderPath):
            try:
                os.remove(command.OutFolderPath)
            except Exception as e:
                app.logger.error(f"Failed to delete file {command.OutFolderPath}: {str(e)}")
        
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

@app.route('/api/commands/call-dify-agent', methods=['POST'])
def call_dify_agent():
    try:
        # 获取请求数据
        data = request.get_json()
        app.logger.debug(f"Received raw request data: {data}")
        command_id = data.get('command_id')
        two_dimensional_file = data.get('two_dimensional_file')  # 直接获取文件内容

        app.logger.debug(f"Received request with Command_id: {command_id}, Two_Dimensional_File: {two_dimensional_file}")

        # 检查必要参数是否存在
        if not all([command_id, two_dimensional_file]):
            return jsonify({"error": "Missing required parameters"}), 400

        # 调用 Dify 智能体 API
        dify_url = 'http://192.168.9.177/v1/chat-messages'
        headers = {
            'Authorization': 'Bearer app-KFQmXKuhLqE9xMFPhzWmiXu5',
            'Content-Type': 'application/json'
        }
        payload = {
            "inputs": {
                "command_id": command_id,
                "two_dimensional_file": two_dimensional_file  # 直接传递文件内容
            },
            "query": f"请根据AS400命令{command_id}基于二维表{two_dimensional_file}生成AS400的检证用例,并封装成JAVA,最后基于封装后的JAVA代码生成Junit测试用例",
            "response_mode": "streaming",
            "conversation_id": "",
            "user": "abc-123",
            "files": [],
            "parent_message_id": None
        }

        try:
            app.logger.debug(f"Calling Dify API with payload: {payload}")
            response = requests.post(dify_url, json=payload, headers=headers)
            response.raise_for_status()
            app.logger.debug(f"Dify API response: {response.text}")
            return jsonify(response.json()), 200
        except requests.exceptions.RequestException as e:
            app.logger.error(f"Dify API request failed: {str(e)}")
            return jsonify({"error": f"Dify API request failed: {str(e)}"}), 500

    except Exception as e:
        app.logger.error(f"Failed to call Dify agent: {str(e)}")
        return jsonify({"error": f"Failed to call Dify agent: {str(e)}"}), 500

@app.route('/api/commands/folder/<path:folder_path>/files', methods=['GET'])
def get_command_files_by_folder(folder_path):
    """获取指定文件夹下的所有文件"""
    try:
        decoded_path = unquote(folder_path)
        normalized_path = os.path.normpath(decoded_path)
        
        files = CommandLog.query.filter(
            CommandLog.OutFolderPath == normalized_path
        ).with_entities(
            CommandLog.ID,
            CommandLog.FileName,
            CommandLog.OutFolderPath,
            CommandLog.CreatedAt
        ).order_by(CommandLog.CreatedAt.desc()).all()
        
        return jsonify({
            "files": [{
                "id": file.ID,
                "file_name": file.FileName,
                "out_folder_path": file.OutFolderPath,
                "full_path": f"{file.OutFolderPath}/{file.FileName}".replace('\\', '/'),
                "created_at": file.CreatedAt.isoformat()
            } for file in files]
        })
    except Exception as e:
        app.logger.error(f"Get folder files failed: {str(e)}")
        return jsonify({"error": "Server error"}), 500

@app.route('/api/files/preview', methods=['GET'])
def preview_folder():
    """预览文件夹"""
    folder_path = request.args.get('path')
    if not folder_path:
        return jsonify({"error": "Path parameter is required"}), 400
    
    try:
        # 解码并标准化路径
        decoded_path = unquote(folder_path)
        normalized_path = os.path.normpath(decoded_path)
        
        # 返回物理路径供前端使用
        return jsonify({
            "real_path": normalized_path,
            "is_directory": os.path.isdir(normalized_path)
        })
    except Exception as e:
        app.logger.error(f"Preview failed: {str(e)}")
        return jsonify({"error": "Server error"}), 500

@app.route('/api/files/check', methods=['GET'])
def check_file_exists():
    """检查文件是否存在"""
    file_path = request.args.get('path')
    if not file_path:
        return jsonify({"error": "Path parameter is required"}), 400
    
    try:
        decoded_path = unquote(file_path)
        normalized_path = os.path.normpath(decoded_path)
        
        exists = os.path.exists(normalized_path)
        return jsonify({
            "exists": exists,
            "path": normalized_path,
            "is_file": os.path.isfile(normalized_path) if exists else False
        })
    except Exception as e:
        app.logger.error(f"Path check failed: {str(e)}")
        return jsonify({"error": "Server error"}), 500

@app.route('/preview')
def preview_markdown():
    file_path = request.args.get('path')
    if not file_path:
        return jsonify({"error": "需要提供path参数"}), 400
    
    try:
        # 路径解码与标准化
        decoded_path = unquote(file_path)
        normalized_path = os.path.normpath(decoded_path)
        absolute_path = os.path.abspath(normalized_path)
        
        # 路径安全检查
        if not os.path.exists(absolute_path):
            return jsonify({"error": "文件不存在"}), 404
        if not os.path.isfile(absolute_path):
            return jsonify({"error": "路径不是文件"}), 400
        if not absolute_path.lower().endswith('.md'):
            return jsonify({"error": "仅支持Markdown文件"}), 400
        
        # 读取文件内容
        with open(absolute_path, 'rb') as f:
            raw_data = f.read()
            detected_encoding = chardet.detect(raw_data)['encoding']
            content = raw_data.decode(detected_encoding or 'utf-8')
        
        # 生成带样式的HTML
        html_content = markdown.markdown(content, extensions=['extra', 'tables'])
        full_html = f"""
        <!DOCTYPE html>
        <html>
            <head>
                <meta charset="utf-8">
                <link rel="stylesheet" href="/static/github-markdown.css">
            </head>
            <body class="markdown-body">
                {html_content}
            </body>
        </html>
        """
        return Response(full_html, mimetype='text/html')
    except Exception as e:
        app.logger.error(f"预览失败: {str(e)}")
        return jsonify({"error": "文件预览失败"}), 500

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(os.path.join(app.root_path, 'static'), filename)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    
    app.run(host='0.0.0.0', port=5500, debug=True)
