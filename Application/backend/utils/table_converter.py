import json
from typing import List, Dict, Union

def convert_table_data(raw_data: List[List[Union[str, dict]]]) -> dict:
    """
    将二维表数据转换为标准化JSON格式
    输入格式示例：
    [
        ["用例ID", "数组类型", ...], # 首行为列头
        ["CASE1", "静态", ...],     # 数据行
        ["CASE2", "动态", ...]
    ]
    
    输出格式：
    {
        "columns": ["col1", "col2", ...],
        "rows": [
            {"col1": "value1", "col2": "value2", ...},
            ...
        ]
    }
    """
    if len(raw_data) < 1:
        raise ValueError("表格数据必须包含列头")

    columns = [str(col).strip() for col in raw_data[0]]
    rows = []
    
    for row in raw_data[1:]:
        if len(row) != len(columns):
            raise ValueError(f"行数据列数不匹配，期望 {len(columns)} 列，实际 {len(row)} 列")
        
        row_dict = {}
        for idx, val in enumerate(row):
            # 处理特殊格式数据
            if isinstance(val, dict):
                row_dict[columns[idx]] = json.dumps(val, ensure_ascii=False)
            else:
                row_dict[columns[idx]] = str(val).strip()
        
        rows.append(row_dict)
    
    return {"columns": columns, "rows": rows}