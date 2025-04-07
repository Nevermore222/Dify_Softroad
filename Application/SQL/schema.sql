-- 动态表结构存储
CREATE TABLE dynamic_table (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name VARCHAR(100) UNIQUE NOT NULL,
    fields JSON NOT NULL,  -- 存储字段定义 [{"name":"字段1","type":"string"},...]
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 动态表数据存储
CREATE TABLE dynamic_table_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_id INTEGER NOT NULL,
    row_data JSON NOT NULL,  -- 存储实际数据 {"字段1":"值1",...}
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(table_id) REFERENCES dynamic_table(id)
);

-- 工作流调用记录
CREATE TABLE workflow_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_id INTEGER NOT NULL,
    request_data JSON,
    response_data JSON,
    status VARCHAR(20),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);