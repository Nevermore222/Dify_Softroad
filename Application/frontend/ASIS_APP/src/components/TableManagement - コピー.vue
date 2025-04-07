<!-- 保留模板部分不变 -->
<template>
  <div class="command-management-container">
    <!-- 查询表单区域 -->
    <div class="query-section">
      <el-form :model="queryParams" inline>
        <el-form-item label="命令类型">
          <el-select 
            v-model="queryParams.command_type" 
            clearable
            placeholder="请选择命令类型"
          >
            <el-option
              v-for="type in commandTypes"
              :key="type.value"
              :label="type.label"
              :value="type.value"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="日期范围">
          <el-date-picker
            v-model="queryParams.date_range"
            type="daterange"
            value-format="YYYY-MM-DD"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
          />
        </el-form-item>

        <el-form-item label="关键词">
          <el-input
            v-model="queryParams.search_key"
            placeholder="命令内容/表格数据"
            clearable
            @keyup.enter="handleSearch"
          >
            <template #append>
              <el-button @click="handleSearch">
                <el-icon><Search /></el-icon>
              </el-button>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon>
            <span>查询</span>
          </el-button>
          <el-button type="success" @click="handleCreateCommand">
            <el-icon><Plus /></el-icon>
            <span>新建命令</span>
          </el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 命令列表区域 -->
    <div class="command-list-section">
      <el-table
        :data="commandList"
        v-loading="loading"
        row-key="id"
        stripe
        highlight-current-row
        @row-click="handleRowClick"
        style="width: 100%"
      >
        <el-table-column prop="command_type" label="类型" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="getCommandTypeStyle(row.command_type)" effect="light">
              {{ row.command_type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="command_value" label="命令内容" min-width="200" show-overflow-tooltip />
        <el-table-column prop="table_data_path" label="表格文件" width="250" show-overflow-tooltip>
          <template #default="{ row }">
            <el-link type="primary" @click.stop="previewFile(row.table_data_path)">
              {{ getFileName(row.table_data_path) }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" sortable>
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right" align="center">
          <template #default="{ row }">
            <el-button size="small" @click.stop="handleEditCommand(row)">
              编辑
            </el-button>
            <el-button 
              type="danger" 
              size="small" 
              @click.stop="handleDeleteCommand(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>

        <!-- 展开行显示文件内容 -->
        <el-table-column type="expand" width="60">
          <template #default="{ row }">
            <div class="file-content-section">
              <div class="path-list-header">
                <el-icon><Document /></el-icon>
                <span>关联文件列表 (按时间倒序)</span>
              </div>
              
              <div class="path-list-container">
                <div 
                  v-for="(file, index) in row.file_paths" 
                  :key="index"
                  class="path-item"
                >
                  <div class="path-header" @click="toggleFileEditor(row, file.path)">
                    <el-icon :class="{'rotate-icon': showFileEditor && currentFile?.path === file.path}">
                      <ArrowRight />
                    </el-icon>
                    <span class="path-text">{{ file.path }}</span>
                    <span class="file-time">{{ formatDateTime(file.created_at) }}</span>
                    <el-tag v-if="fileStatus[file.path]" :type="fileStatus[file.path].type" size="small">
                      {{ fileStatus[file.path].text }}
                    </el-tag>
                  </div>

                  <div class="file-editor-container" v-if="showFileEditor && currentFile?.path === file.path">
                    <div class="editor-area">
                      <el-input
                        v-model="fileContent"
                        type="textarea"
                        :rows="20"
                        resize="none"
                        placeholder="Markdown内容..."
                        @input="handleContentChange"
                      />
                    </div>
                    <div class="preview-area">
                      <div class="preview-header">
                        <span>实时预览</span>
                        <div>
                          <el-tag v-if="unsavedChanges" type="warning">未保存</el-tag>
                          <span class="last-saved" v-if="lastSavedTime">
                            最后修改: {{ formatDateTime(lastSavedTime) }}
                          </span>
                        </div>
                      </div>
                      <div class="markdown-preview" v-html="compiledMarkdown" />
                    </div>
                    
                    <div class="editor-actions">
                      <el-button 
                        type="primary" 
                        @click="saveFileContent(row, file.path)"
                        :loading="savingFile"
                        :disabled="!unsavedChanges"
                      >
                        <el-icon><Upload /></el-icon>
                        <span>保存更改</span>
                      </el-button>
                      <el-button @click="reloadFileContent(row, file.path)">
                        <el-icon><Refresh /></el-icon>
                        <span>重新加载</span>
                      </el-button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 分页区域 -->
    <div class="pagination-section">
      <el-pagination
        v-model="pagination.current_page"
        :page-size="pagination.page_size"
        @size-change="handleSizeChange"
        :total="pagination.total"
        @current-change="handlePageChange"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        background
      />
    </div>

    <!-- 命令编辑对话框 -->
    <el-dialog
      v-model="commandDialogVisible"
      :title="dialogTitle"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form 
        :model="editingCommand" 
        label-width="100px"
        ref="commandFormRef"
        :rules="commandRules"
      >
        <el-form-item label="命令类型" prop="command_type">
          <el-select 
            v-model="editingCommand.command_type" 
            placeholder="请选择命令类型"
          >
            <el-option
              v-for="type in commandTypes"
              :key="type.value"
              :label="type.label"
              :value="type.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="命令内容" prop="command_value">
          <el-input 
            v-model="editingCommand.command_value" 
            type="textarea" 
            rows="4"
            placeholder="请输入命令内容"
            show-word-limit
            maxlength="500"
          />
        </el-form-item>
        
        <el-form-item 
          label="表格文件路径" 
          prop="table_data_path"
          v-if="isCreating"
        >
          <el-input
            v-model="editingCommand.table_data_path"
            placeholder="输入Markdown文件路径，如：F:\path\to\file.md"
          />
          <div class="path-hint">
            <el-icon><InfoFilled /></el-icon>
            请确保路径可访问且有写入权限
          </div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="commandDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSaveCommand">
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  Search, Plus, Document, Delete, View, 
  Upload, InfoFilled, ArrowRight, Refresh 
} from '@element-plus/icons-vue'
import { marked } from 'marked'
import hljs from 'highlight.js'

// 配置marked
marked.setOptions({
  breaks: true,
  gfm: true,
  highlight: (code, lang) => {
    const language = hljs.getLanguage(lang) ? lang : 'plaintext'
    return hljs.highlight(code, { language }).value
  }
})

// 状态管理
const loading = ref(false)
const savingFile = ref(false)
const commandDialogVisible = ref(false)
const isCreating = ref(false)
const commandFormRef = ref(null)
const showFileEditor = ref(false)
const fileContent = ref('')
const lastSavedTime = ref(null)
const unsavedChanges = ref(false)
const fileStatus = ref({})
const currentFile = ref(null)

// 数据相关
const commandList = ref([])
const currentCommand = ref(null)

// 查询参数
const queryParams = reactive({
  command_type: '',
  date_range: [],
  search_key: ''
})

// 分页参数
const pagination = reactive({
  current_page: 1,
  page_size: 10,
  total: 0
})

// 编辑中的命令
const editingCommand = reactive({
  id: null,
  command_value: '',
  command_type: 'CLP',
  table_data_path: ''
})

// 命令类型选项
const commandTypes = [
  { value: 'CLP', label: 'CLP命令' },
  { value: 'RPGLE', label: 'RPG程序' },
  { value: 'JAVA', label: 'Java调用' },
  { value: 'WORKFLOW', label: '工作流' }
]

// 表单验证规则
const commandRules = {
  command_type: [
    { required: true, message: '请选择命令类型', trigger: 'blur' }
  ],
  command_value: [
    { required: true, message: '请输入命令内容', trigger: 'blur' }
  ],
  table_data_path: [
    { required: true, message: '请输入表格文件路径', trigger: 'blur' }
  ]
}

// 计算属性
const dialogTitle = computed(() => {
  return isCreating.value ? '新建命令' : '编辑命令'
})

const compiledMarkdown = computed(() => {
  return marked(fileContent.value || '')
})

// 方法定义
const fetchCommandList = async () => {
  try {
    loading.value = true
    const params = {
      page: pagination.current_page,
      page_size: pagination.page_size,
      type: queryParams.command_type,
      search: queryParams.search_key
    }

    if (queryParams.date_range?.length === 2) {
      params.start_date = queryParams.date_range[0]
      params.end_date = queryParams.date_range[1]
    }

    const res = await axios.get('/api/commands', { params })
    
    // 获取每个命令的所有文件路径
    const commandsWithFiles = await Promise.all(
      res.data.data.map(async command => {
        const filesRes = await axios.get(`/api/commands/${encodeURIComponent(command.command_value)}/files`)
        return {
          ...command,
          file_paths: filesRes.data.files.map(file => ({
            path: file.table_data_path,
            created_at: file.created_at
          }))
        }
      })
    )

    commandList.value = commandsWithFiles
    pagination.total = res.data.pagination.total_items
  } catch (error) {
    ElMessage.error('加载命令列表失败: ' + error.message)
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.current_page = 1
  fetchCommandList()
}

const handleRowClick = (row) => {
  currentCommand.value = row
}

const toggleFileEditor = async (row, filePath) => {
  if (!filePath) {
    ElMessage.warning('文件路径不存在')
    return
  }

  if (showFileEditor.value && currentFile.value?.path === filePath) {
    showFileEditor.value = false
    currentFile.value = null
    return
  }

  try {
    currentCommand.value = row
    currentFile.value = { path: filePath }
    showFileEditor.value = true
    await loadFileContent(filePath)
  } catch (error) {
    console.error('打开文件失败:', error)
    showFileEditor.value = false
    currentFile.value = null
  }
}

const loadFileContent = async (filePath) => {
  try {
    const res = await axios.get('/api/files/content', {
      params: { path: filePath }
    })
    
    fileContent.value = res.data.content
    lastSavedTime.value = res.data.timestamp
    unsavedChanges.value = false
    
    fileStatus.value = {
      ...fileStatus.value,
      [filePath]: {
        type: 'success',
        text: '加载成功'
      }
    }
  } catch (error) {
    fileStatus.value = {
      ...fileStatus.value,
      [filePath]: {
        type: 'danger',
        text: '加载失败'
      }
    }
    ElMessage.error(`文件加载失败(${getFileName(filePath)}): ${error.message}`)
  }
}

const saveFileContent = async (filePath) => {
  try {
    savingFile.value = true
    const res = await axios.put('/api/files/save', {
      path: filePath,
      content: fileContent.value
    })
    
    lastSavedTime.value = res.data.timestamp
    unsavedChanges.value = false
    
    // 更新关联命令的更新时间
    const command = commandList.value.find(cmd => 
      cmd.file_paths.some(f => f.path === filePath)
    )
    if (command) {
      command.updated_at = res.data.timestamp
    }
    
    fileStatus.value = {
      ...fileStatus.value,
      [filePath]: {
        type: 'success',
        text: '保存成功'
      }
    }
    ElMessage.success(`文件保存成功(${getFileName(filePath)})`)
  } catch (error) {
    fileStatus.value = {
      ...fileStatus.value,
      [filePath]: {
        type: 'danger',
        text: '保存失败'
      }
    }
    ElMessage.error(`保存失败(${getFileName(filePath)}): ${error.message}`)
  } finally {
    savingFile.value = false
  }
}

const reloadFileContent = async (filePath) => {
  if (unsavedChanges.value) {
    try {
      await ElMessageBox.confirm('有未保存的更改，确认重新加载吗？', '提示', {
        confirmButtonText: '确认',
        cancelButtonText: '取消',
        type: 'warning'
      })
    } catch {
      return
    }
  }
  await loadFileContent(filePath)
}

const handleContentChange = () => {
  unsavedChanges.value = true
}

const previewFile = (filePath) => {
  if (!filePath) return
  window.open(filePath, '_blank')
}

const getFileName = (path) => {
  if (!path) return ''
  return path.split('\\').pop() || path.split('/').pop()
}

const handleCreateCommand = () => {
  isCreating.value = true
  Object.assign(editingCommand, {
    id: null,
    command_value: '',
    command_type: 'CLP',
    table_data_path: ''
  })
  
  commandDialogVisible.value = true
}

const handleEditCommand = (command) => {
  isCreating.value = false
  Object.assign(editingCommand, {
    id: command.id,
    command_value: command.command_value,
    command_type: command.command_type,
    table_data_path: command.table_data_path
  })
  
  commandDialogVisible.value = true
}

const handleSaveCommand = async () => {
  try {
    await commandFormRef.value.validate()
    
    if (isCreating.value) {
      await axios.post('/api/commands', editingCommand)
      ElMessage.success('命令创建成功')
    } else {
      await axios.put(`/api/commands/${editingCommand.id}`, editingCommand)
      ElMessage.success('命令更新成功')
    }
    
    commandDialogVisible.value = false
    fetchCommandList()
  } catch (error) {
    if (error.response?.data?.error) {
      ElMessage.error('操作失败: ' + error.response.data.error)
    }
  }
}

const handleDeleteCommand = async (command) => {
  try {
    await ElMessageBox.confirm(
      '确认删除该命令及其关联文件吗？此操作不可恢复！',
      '警告',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger'
      }
    )
    
    await axios.delete(`/api/commands/${command.id}`)
    ElMessage.success('命令删除成功')
    
    if (currentCommand.value?.id === command.id) {
      currentCommand.value = null
      showFileEditor.value = false
    }
    
    fetchCommandList()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败: ' + error.message)
    }
  }
}

const handlePageChange = (page) => {
  pagination.current_page = page
  fetchCommandList()
}

const handleSizeChange = (size) => {
  pagination.page_size = size
  fetchCommandList()
}

const getCommandTypeStyle = (type) => {
  const typeMap = {
    CLP: 'success',
    RPGLE: 'warning',
    JAVA: 'info',
    WORKFLOW: 'danger'
  }
  return typeMap[type] || ''
}

const formatDateTime = (isoString) => {
  if (!isoString) return ''
  const date = new Date(isoString)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  })
}

// 初始化加载
fetchCommandList()
</script>

<!-- 保留之前修复的CSS部分 -->
<style scoped>
.command-management-container {
  padding: 20px;
}

.query-section {
  margin-bottom: 20px;
  padding: 15px;
  background: #fff;
  border-radius: 4px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
}

.command-list-section {
  margin-bottom: 20px;
  background: #fff;
  border-radius: 4px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
}

.pagination-section {
  display: flex;
  justify-content: flex-end;
  padding: 15px;
  background: #fff;
  border-radius: 4px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
}

.file-content-section {
  padding: 15px;
  background-color: #fafafa;
  border-radius: 4px;
}

.path-header {
  padding: 10px 15px;
  background-color: #f5f7fa;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  margin-bottom: 10px;
}

.path-header:hover {
  background-color: #ebedf0;
}

.path-text {
  margin-left: 8px;
  flex: 1;
  font-family: monospace;
  color: #409eff;
}

.rotate-icon {
  transform: rotate(90deg);
  transition: transform 0.3s;
}

.file-editor-container {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-top: 10px;
}

.editor-area {
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  overflow: hidden;
}

.preview-area {
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  padding: 15px;
  background: white;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  padding-bottom: 10px;
  border-bottom: 1px solid #eee;
}

.markdown-preview {
  overflow-y: auto;
  max-height: 600px;
}

.editor-actions {
  grid-column: span 2;
  display: flex;
  align-items: center;
  gap: 15px;
  padding-top: 10px;
}

.last-saved {
  margin-left: 15px;
  color: #909399;
  font-size: 12px;
}

.path-hint {
  margin-top: 8px;
  padding: 8px;
  background-color: #f5f7fa;
  border-radius: 4px;
  color: #606266;
  font-size: 12px;
  line-height: 1.5;
}
</style>
